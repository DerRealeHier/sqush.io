import random
from datetime import datetime, timezone, timedelta
from flask import url_for, current_app
from flask_mail import Message
from werkzeug.security import generate_password_hash
from extensions import db, mail, email_serializer
from models.user import LoginOTP
import config


def send_email(to, subject, html_body):
    #Wrapped so we only have ONE place that can blow up
    mail_user = current_app.config.get("MAIL_USERNAME") or config.MAIL_USERNAME
    if not mail_user:
        print(f"DEBUG: MAIL_USERNAME not set, skipping mail to {to}: {subject}")
        return
    try:
        msg = Message(subject=subject, recipients=[to], html=html_body)
        mail.send(msg)
    except Exception as e:
        print(f"DEBUG: Mail error: {e}")


def _comic_email_shell(headline, body_html):
    #tiny bit of inline CSS comic styling.
    return f"""
    <div style="background:#161616;padding:40px 20px;font-family:Arial,sans-serif;">
      <div style="max-width:420px;margin:0 auto;background:#161616;border:4px solid #000;
                  box-shadow:10px 10px 0px #000;padding:32px;">
        <h1 style="color:#ff3b30;font-size:28px;letter-spacing:1px;margin:0 0 8px 0;">SQUSH</h1>
        <h2 style="color:#ffe14d;font-size:18px;margin:0 0 20px 0;">{headline}</h2>
        <div style="color:#eee;font-size:15px;line-height:1.5;">{body_html}</div>
      </div>
    </div>
    """


def send_verification_email(user):
    token = email_serializer.dumps(user.email, salt="email-verify")
    verify_url = url_for("verify_email", token=token, _external=True)
    body = f"""
      <p>Hey {user.username}, nearly finished!</p>
      <p>Click on the button to confirm your email address:</p>
      <p style="text-align:center;margin:28px 0;">
        <a href="{verify_url}"
           style="background:#33d17a;color:#000;font-weight:bold;text-decoration:none;
                  padding:12px 24px;border:3px solid #000;display:inline-block;">
          CONFIRM EMAIL ADDRESS
        </a>
      </p>
      <p style="color:#999;font-size:12px;">The link is valid for 24 hours. Wasn't it you? Just ignore it.</p>
    """
    send_email(user.email, "Confirm your Email address", _comic_email_shell("Nearly finished!", body))


def send_email_change_verification(user, new_email):
    # separate salt so this token can never be replayed against verify_email
    token = email_serializer.dumps({"user_id": user.id, "new_email": new_email}, salt="email-change")
    verify_url = url_for("verify_email_change", token=token, _external=True)
    body = f"""
      <p>Hey {user.username}, you asked to change your Email address to this one.</p>
      <p>Click on the button to confirm the new address:</p>
      <p style="text-align:center;margin:28px 0;">
        <a href="{verify_url}"
           style="background:#3aa0ff;color:#000;font-weight:bold;text-decoration:none;
                  padding:12px 24px;border:3px solid #000;display:inline-block;">
          CONFIRM NEW EMAIL ADDRESS
        </a>
      </p>
      <p style="color:#999;font-size:12px;">The link is valid for 24 hours. Wasn't it you? Just ignore it and your old address stays active.</p>
    """
    send_email(new_email, "Confirm your new Email address", _comic_email_shell("New address, who dis?", body))


def send_login_otp(user):
    code = f"{random.randint(0, 999999):06d}"
    #kill old codes first
    LoginOTP.query.filter_by(user_id=user.id).delete()
    otp = LoginOTP(
        user_id=user.id,
        code_hash=generate_password_hash(code),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10)
    )
    db.session.add(otp)
    db.session.commit()

    body = f"""
      <p>Hey {user.username}, here is your login code:</p>
      <p style="text-align:center;margin:28px 0;">
        <span style="background:#3aa0ff;color:#000;font-weight:bold;font-size:32px;
                     letter-spacing:6px;padding:12px 24px;border:3px solid #000;display:inline-block;">
          {code}
        </span>
      </p>
      <p style="color:#999;font-size:12px;">Valid for 10 minutes. Wasn't it you? To be on the safe side, change your password.</p>
    """
    send_email(user.email, "Your Sqush login:", _comic_email_shell("Your login code:", body))
