"""Small local ASGI guard: request budget, same-origin writes, headers, rate limit.
In-memory rate limits are per process, not a replacement for an edge gateway.
"""
from collections import OrderedDict,deque
from time import monotonic
from urllib.parse import urlsplit
import json

class SecurityGuard:
    def __init__(self,app,max_body=65536,limit=120,window=60):
        self.app=app;self.max_body=max_body;self.limit=limit;self.window=window;self.clients=OrderedDict()
    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        headers={key.decode().lower():value.decode() for key,value in scope['headers']}
        async def guarded_send(message):
            if message['type']=='http.response.start':
                extra=[(b'x-content-type-options',b'nosniff'),(b'referrer-policy',b'no-referrer'),
                    (b'content-security-policy',b"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'"),
                    (b'permissions-policy',b'camera=(), microphone=(), geolocation=()')]
                if scope['path'].startswith('/api/'):extra.append((b'cache-control',b'no-store'))
                message={**message,'headers':message.get('headers',[])+extra}
            await send(message)
        async def reject(code,text):
            await guarded_send({'type':'http.response.start','status':code,'headers':[(b'content-type',b'application/json')]})
            await guarded_send({'type':'http.response.body','body':json.dumps({'detail':text}).encode()})
        if scope['path'].startswith('/api/'):
            client=(scope.get('client') or ('unknown',0))[0];now=monotonic()
            if client not in self.clients and len(self.clients)>=4096:self.clients.popitem(last=False)
            bucket=self.clients.setdefault(client,deque());self.clients.move_to_end(client)
            while bucket and bucket[0]<=now-self.window:bucket.popleft()
            if len(bucket)>=self.limit:return await reject(429,'Too many API requests; try again later')
            bucket.append(now)
            if scope['method'] in ('POST','PUT','PATCH','DELETE'):
                origin=headers.get('origin')
                if 'bep_session=' in headers.get('cookie','') and not origin:return await reject(403,'Origin required for session writes')
                if origin:
                    parsed=urlsplit(origin)
                    if parsed.scheme!=scope.get('scheme') or parsed.netloc!=headers.get('host'):
                        return await reject(403,'Cross-origin writes are not allowed')
                if scope['method'] in ('POST','PUT','PATCH'):
                    if headers.get('content-type','').lower().split(';',1)[0].strip()!='application/json':return await reject(415,'JSON request body required')
                    if headers.get('content-encoding','identity')!='identity':return await reject(415,'Compressed request bodies not supported')
                    try:
                        if int(headers.get('content-length','0'))>self.max_body:return await reject(413,'Request body too large')
                    except ValueError:return await reject(400,'Invalid content length')
                    chunks=[];length=0
                    while True:
                        event=await receive()
                        if event['type']=='http.disconnect':return
                        part=event.get('body',b'');length+=len(part)
                        if length>self.max_body:return await reject(413,'Request body too large')
                        chunks.append(part)
                        if not event.get('more_body',False):break
                    body=b''.join(chunks);sent=False
                    def unique(pairs):
                        result={}
                        for name,value in pairs:
                            if name in result:raise ValueError('Duplicate JSON field')
                            result[name]=value
                        return result
                    def invalid_constant(value):raise ValueError('Non-finite JSON number')
                    try:json.loads(body,object_pairs_hook=unique,parse_constant=invalid_constant)
                    except (ValueError,UnicodeDecodeError,RecursionError):return await reject(400,'Invalid, duplicate-field or non-finite JSON body')
                    async def replay():
                        nonlocal sent
                        if not sent:sent=True;return {'type':'http.request','body':body,'more_body':False}
                        return await receive()
                    return await self.app(scope,replay,guarded_send)
        return await self.app(scope,receive,guarded_send)
