"""Run once on the trusted backend host to provision the first owner."""
import argparse,getpass
from backend.accounts.service import Accounts

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--email',required=True);parser.add_argument('--name',required=True);parser.add_argument('--branches',nargs='+',required=True);args=parser.parse_args()
 password=getpass.getpass('Owner password (12–128 characters): ')
 if password!=getpass.getpass('Confirm password: '):raise SystemExit('Passwords did not match')
 Accounts().create({'role':'owner','branches':args.branches},{'email':args.email,'password':password,'name':args.name,'role':'owner','branches':args.branches})
 print('Owner account created. Sign in using the Owner workspace.')
if __name__=='__main__':main()
