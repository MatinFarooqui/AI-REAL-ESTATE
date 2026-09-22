from __future__ import annotations
import os, smtplib
from email.message import EmailMessage
from urllib.parse import quote
from dotenv import load_dotenv
BASE_DIR=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR,'.env'))

def _required(name):
    value=str(os.getenv(name,'')).strip()
    if not value: raise RuntimeError(f'Email service is not configured: missing {name} in .env')
    return value

def send_verification_email(recipient, name, token):
    host=_required('SMTP_HOST'); username=_required('SMTP_USERNAME'); password=_required('SMTP_PASSWORD')
    sender=str(os.getenv('EMAIL_FROM') or username).strip(); base_url=_required('APP_BASE_URL').rstrip('/')
    port=int(os.getenv('SMTP_PORT','587')); use_ssl=str(os.getenv('SMTP_USE_SSL','0')).strip()=='1'
    url=f"{base_url}/auth/verify-email?token={quote(token)}"
    msg=EmailMessage(); msg['Subject']='Verify your RealtyKey AI account'; msg['From']=sender; msg['To']=recipient
    msg.set_content(f"Hello {name or 'there'},\\n\\nWelcome to RealtyKey AI. Please verify your email address to activate your account.\\n\\nVerify your email: {url}\\n\\nThis link expires in 24 hours and can be used only once.\\n\\nIf you did not create this account, you can ignore this email.\\n\\nRealtyKey AI\\nSmarter Property Decisions")
    if use_ssl:
        with smtplib.SMTP_SSL(host,port,timeout=15) as smtp:
            smtp.login(username,password); smtp.send_message(msg)
    else:
        with smtplib.SMTP(host,port,timeout=15) as smtp:
            smtp.ehlo(); smtp.starttls(); smtp.ehlo(); smtp.login(username,password); smtp.send_message(msg)
