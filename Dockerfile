FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --system --uid 10001 --create-home bep \
    && install -d -o bep -g bep /data
COPY backend ./backend
COPY dist ./dist
USER bep
ENV BEP_ERP_DATABASE=/data/erp.sqlite3 \
    BEP_AUTH_DATABASE=/data/accounts.sqlite3 \
    BEP_DATABASE=/data/finance.sqlite3
VOLUME ["/data"]
EXPOSE 8000
CMD ["python", "-m", "backend.server"]
