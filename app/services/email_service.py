import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def _send_email(to_email: str, subject: str, body_html: str) -> bool:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.MAIL_FROM or settings.MAIL_USERNAME
        msg["To"] = to_email
        msg.attach(MIMEText(body_html, "html"))

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(settings.MAIL_HOST, settings.MAIL_PORT, context=context) as server:
            server.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
            server.sendmail(settings.MAIL_USERNAME, to_email, msg.as_string())
        return True
    except Exception as e:
        logger.error(f"Email send failed to {to_email}: {e}")
        return False


def send_otp_email(to_email: str, otp: str, full_name: str = "User") -> bool:
    subject = f"Your {settings.APP_NAME} Verification Code"
    body_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #7C3AED;">Welcome to {settings.APP_NAME}!</h2>
        <p>Hi {full_name},</p>
        <p>Your verification code is:</p>
        <div style="background: #F3F4F6; padding: 20px; text-align: center; border-radius: 8px; margin: 20px 0;">
            <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #7C3AED;">{otp}</span>
        </div>
        <p>This code expires in <strong>10 minutes</strong>.</p>
        <p>If you did not request this, please ignore this email.</p>
        <hr>
        <p style="color: #9CA3AF; font-size: 12px;">© {settings.APP_NAME}. All rights reserved.</p>
    </body>
    </html>
    """
    return _send_email(to_email, subject, body_html)


def send_approval_email(to_email: str, full_name: str, prompt_title: str, points: int) -> bool:
    subject = f"Submission Approved — +{points} Points!"
    body_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #059669;">Submission Approved!</h2>
        <p>Hi {full_name},</p>
        <p>Your submission for <strong>"{prompt_title}"</strong> has been approved.</p>
        <div style="background: #ECFDF5; padding: 20px; text-align: center; border-radius: 8px; margin: 20px 0;">
            <span style="font-size: 24px; font-weight: bold; color: #059669;">+{points} Points Earned!</span>
        </div>
        <p>Keep up the great work. Check your wallet for your updated balance.</p>
        <a href="{settings.BASE_URL}/wallet" style="background: #7C3AED; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; display: inline-block; margin-top: 10px;">View Wallet</a>
    </body>
    </html>
    """
    return _send_email(to_email, subject, body_html)


def send_rejection_email(to_email: str, full_name: str, prompt_title: str, reason: str) -> bool:
    subject = f"Submission Needs Revision — {prompt_title}"
    body_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #DC2626;">Submission Not Approved</h2>
        <p>Hi {full_name},</p>
        <p>Unfortunately, your submission for <strong>"{prompt_title}"</strong> was not approved.</p>
        <div style="background: #FEF2F2; padding: 16px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #DC2626;">
            <strong>Reason:</strong> {reason}
        </div>
        <p>Please review the prompt instructions and try again.</p>
        <a href="{settings.BASE_URL}/dashboard" style="background: #7C3AED; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; display: inline-block; margin-top: 10px;">Back to Dashboard</a>
    </body>
    </html>
    """
    return _send_email(to_email, subject, body_html)
