"""邮件发送：未配置 SMTP 时写入日志文件，保证本地可演示。"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from pathlib import Path

from intern_platform.config import PROJECT_ROOT, get_settings

logger = logging.getLogger(__name__)

REJECT_SUBJECT = "【开源实习】申请未通过通知 / Application Not Accepted"

REJECT_BODY_TMPL = """尊敬的 {name}：

很抱歉地通知您：您申请的项目「{project_title}」未通过导师审核。

您可以登录实习平台查看详情，或继续浏览并申请其他项目。
如有疑问，请通过平台「个人中心 · 通知」查看说明。

—— 华科开放原子开源俱乐部 · 开源实习管理系统

--------------------

Dear {name},

We regret to inform you that your application for the project "{project_title}" was not accepted by the mentor.

You may log in to the internship platform for details, or browse and apply for other projects.

— HUST OpenAtom Open-Source Internship Platform
"""


def notify_email_for(user) -> str:  # noqa: ANN001
    contact = (getattr(user, "contact_email", None) or "").strip()
    if contact:
        return contact.lower()
    return (user.email or "").strip().lower()


def notify_emails_for(user) -> list[str]:  # noqa: ANN001
    """登录邮箱 + 联系邮箱都尝试通知（去重）。"""
    seen: set[str] = set()
    out: list[str] = []
    for raw in (
        (getattr(user, "contact_email", None) or "").strip().lower(),
        (getattr(user, "email", None) or "").strip().lower(),
    ):
        if raw and raw not in seen:
            seen.add(raw)
            out.append(raw)
    return out


def send_mail(*, to_addr: str, subject: str, body: str) -> bool:
    """返回是否真正通过 SMTP 发出；失败/未配置时落盘并返回 False。"""
    settings = get_settings()
    host = getattr(settings, "smtp_host", "") or ""
    port = int(getattr(settings, "smtp_port", 587) or 587)
    user = getattr(settings, "smtp_user", "") or ""
    password = getattr(settings, "smtp_password", "") or ""
    from_addr = getattr(settings, "smtp_from", "") or user or "noreply@intern-platform.local"

    log_dir = PROJECT_ROOT / "data" / "mail"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_to = to_addr.replace("@", "_at_").replace("/", "_")
    (log_dir / f"{stamp}_{safe_to}.txt").write_text(
        f"TO: {to_addr}\nSUBJECT: {subject}\nSMTP_HOST: {host or '(未配置)'}\n\n{body}\n",
        encoding="utf-8",
    )

    if not host or not to_addr:
        logger.warning(
            "SMTP not configured; reject mail saved to data/mail for %s (configure SMTP_* in .env)",
            to_addr,
        )
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            smtp.ehlo()
            try:
                smtp.starttls()
                smtp.ehlo()
            except smtplib.SMTPException:
                pass
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Failed to send mail to %s", to_addr)
        return False


def send_reject_mail(*, user, project_title: str) -> bool:  # noqa: ANN001
    body = REJECT_BODY_TMPL.format(
        name=getattr(user, "display_name", None) or "同学",
        project_title=project_title or "实习项目",
    )
    ok_any = False
    for to_addr in notify_emails_for(user):
        if send_mail(to_addr=to_addr, subject=REJECT_SUBJECT, body=body):
            ok_any = True
    return ok_any
