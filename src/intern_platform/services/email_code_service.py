"""注册邮箱验证码：发信 + 校验。"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from intern_platform.config import get_settings
from intern_platform.models.email_code import EmailVerificationCode
from intern_platform.models.user import User
from intern_platform.services.mail_service import send_mail

PURPOSE_REGISTER = "register"
CODE_TTL_MINUTES = 10
RESEND_SECONDS = 60


def _now() -> datetime:
    return datetime.now(timezone.utc)


class EmailCodeService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def send_register_code(self, email: str) -> dict:
        email_n = email.strip().lower()
        if not email_n or "@" not in email_n:
            raise ValueError("邮箱格式不正确")
        existing = self.session.scalar(select(User).where(User.email == email_n))
        if existing:
            raise ValueError("邮箱已注册，请直接登录")

        latest = self.session.scalar(
            select(EmailVerificationCode)
            .where(
                EmailVerificationCode.email == email_n,
                EmailVerificationCode.purpose == PURPOSE_REGISTER,
                EmailVerificationCode.consumed_at.is_(None),
            )
            .order_by(EmailVerificationCode.id.desc())
            .limit(1)
        )
        if latest is not None:
            created = latest.created_at
            if created is not None and created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created is not None and (_now() - created).total_seconds() < RESEND_SECONDS:
                wait = RESEND_SECONDS - int((_now() - created).total_seconds())
                raise ValueError(f"发送太频繁，请 {max(wait, 1)} 秒后再试")

        code = f"{secrets.randbelow(1_000_000):06d}"
        row = EmailVerificationCode(
            email=email_n,
            purpose=PURPOSE_REGISTER,
            code=code,
            expires_at=_now() + timedelta(minutes=CODE_TTL_MINUTES),
            send_count=1,
        )
        self.session.add(row)
        self.session.commit()

        subject = "【华科开源实习】注册验证码"
        body = (
            f"您好：\n\n"
            f"您正在注册华科开放原子开源实习管理系统，验证码为：\n\n"
            f"    {code}\n\n"
            f"验证码 {CODE_TTL_MINUTES} 分钟内有效。如非本人操作，请忽略本邮件。\n\n"
            f"—— 华科开放原子开源俱乐部\n"
            f"（此邮件由系统自动发送，请勿直接回复）\n"
        )
        sent = send_mail(to_addr=email_n, subject=subject, body=body)
        settings = get_settings()
        out: dict = {
            "ok": True,
            "sent": sent,
            "message": (
                "验证码已发送到邮箱，请查收（含垃圾箱）"
                if sent
                else "本地未配置发信，已生成演示验证码（不会发到邮箱）"
            ),
            "cooldown_seconds": RESEND_SECONDS,
        }
        # 开发环境未真正发信时回传演示码，便于本地联调
        if not sent and settings.app_env.lower() in {"development", "dev", "local"}:
            out["dev_code"] = code
        return out

    def consume_register_code(self, email: str, code: str) -> None:
        email_n = email.strip().lower()
        code_n = (code or "").strip()
        if not code_n:
            raise ValueError("请填写邮箱验证码")
        row = self.session.scalar(
            select(EmailVerificationCode)
            .where(
                EmailVerificationCode.email == email_n,
                EmailVerificationCode.purpose == PURPOSE_REGISTER,
                EmailVerificationCode.consumed_at.is_(None),
                EmailVerificationCode.code == code_n,
            )
            .order_by(EmailVerificationCode.id.desc())
            .limit(1)
        )
        if row is None:
            raise ValueError("验证码错误或已失效")
        exp = row.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < _now():
            raise ValueError("验证码已过期，请重新获取")
        row.consumed_at = _now()
        self.session.add(row)
        self.session.flush()
