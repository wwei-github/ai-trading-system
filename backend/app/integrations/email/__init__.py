"""邮件服务集成。

支持两种模式：
- EMAIL_TEST_MODE=true：仅控制台打印，不实际发送
- 否则：通过 fastapi-mail + SMTP 发送

提供 5 类模板：
1. 邮箱验证（register_verify）
2. 登录异常告警（login_alert）
3. 密码找回（password_reset）
4. 同步失败（sync_failed）
5. 报告推送（report_push）
"""

from typing import Optional

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema
from loguru import logger

from app.core.config import settings


# ---------- 模板内容（简化版，避免 Jinja2 文件依赖） ----------


def render_register_verify(code: str, app_url: str) -> tuple[str, str]:
    """邮箱验证码：返回 (subject, html_body)。"""
    subject = f"【{settings.APP_NAME}】邮箱验证码"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto;">
      <h2 style="color: #1677ff;">欢迎注册 {settings.APP_NAME}</h2>
      <p>您的邮箱验证码为：</p>
      <p style="font-size: 28px; font-weight: bold; color: #1677ff; letter-spacing: 4px;">{code}</p>
      <p>验证码 15 分钟内有效，请勿告知他人。</p>
      <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;">
      <p style="color: #999; font-size: 12px;">此邮件由系统自动发送，请勿回复。</p>
    </div>
    """
    return subject, html


def render_login_alert(ip: str, device: str, time_str: str) -> tuple[str, str]:
    """登录异常告警。"""
    subject = f"【{settings.APP_NAME}】登录异常提醒"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto;">
      <h2 style="color: #fa8c16;">登录异常提醒</h2>
      <p>您的账号检测到异常登录行为：</p>
      <ul>
        <li>IP：{ip}</li>
        <li>设备：{device}</li>
        <li>时间：{time_str}</li>
      </ul>
      <p>若非本人操作，请立即修改密码并启用 2FA。</p>
      <p>访问 <a href="{settings.APP_URL}">{settings.APP_URL}</a> 修改安全设置。</p>
    </div>
    """
    return subject, html


def render_password_reset(code: str) -> tuple[str, str]:
    """密码找回验证码。"""
    subject = f"【{settings.APP_NAME}】密码找回验证码"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto;">
      <h2 style="color: #1677ff;">密码找回</h2>
      <p>您正在重置密码，验证码为：</p>
      <p style="font-size: 28px; font-weight: bold; color: #1677ff; letter-spacing: 4px;">{code}</p>
      <p>验证码 15 分钟内有效。若非本人操作请忽略此邮件。</p>
    </div>
    """
    return subject, html


def render_sync_failed(account_alias: str, reason: str) -> tuple[str, str]:
    """交易所同步失败通知。"""
    subject = f"【{settings.APP_NAME}】交易所同步失败"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto;">
      <h2 style="color: #f5222d;">同步失败</h2>
      <p>账号 <b>{account_alias}</b> 同步失败：</p>
      <blockquote style="border-left: 4px solid #f5222d; padding-left: 12px; color: #666;">{reason}</blockquote>
      <p>系统将自动重试。若多次失败，请检查 API Key 是否过期或权限变更。</p>
    </div>
    """
    return subject, html


def render_report_push(report_title: str, summary: str, report_url: str) -> tuple[str, str]:
    """报告推送。"""
    subject = f"【{settings.APP_NAME}】{report_title}"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto;">
      <h2 style="color: #1677ff;">{report_title}</h2>
      <p>{summary}</p>
      <p><a href="{report_url}" style="display: inline-block; padding: 8px 16px; background: #1677ff; color: white; text-decoration: none; border-radius: 4px;">查看完整报告</a></p>
    </div>
    """
    return subject, html


# ---------- 发送 ----------


def _build_mailer() -> Optional[FastMail]:
    """构建 FastMail 实例，未配置 SMTP 时返回 None。"""
    if not settings.EMAIL_SMTP_HOST:
        return None
    conf = ConnectionConfig(
        MAIL_USERNAME=settings.EMAIL_SMTP_USER or settings.EMAIL_FROM,
        MAIL_PASSWORD=settings.EMAIL_SMTP_PASSWORD,
        MAIL_FROM=settings.EMAIL_FROM,
        MAIL_PORT=settings.EMAIL_SMTP_PORT,
        MAIL_SERVER=settings.EMAIL_SMTP_HOST,
        MAIL_STARTTLS=not settings.EMAIL_USE_TLS and settings.EMAIL_SMTP_PORT == 587,
        MAIL_SSL_TLS=settings.EMAIL_USE_TLS,
        USE_CREDENTIALS=bool(settings.EMAIL_SMTP_USER),
    )
    return FastMail(conf)


async def send_email(to: str, subject: str, html: str) -> bool:
    """发送邮件。返回是否成功。

    - EMAIL_TEST_MODE=true：仅打印日志，返回 True
    - 未配置 SMTP：打印警告，返回 False
    - 否则实际发送
    """
    if settings.EMAIL_TEST_MODE:
        logger.info(
            "[EMAIL-TEST] 收件人={} | 主题={} | 正文长度={}",
            to, subject, len(html),
        )
        logger.debug("[EMAIL-TEST] 正文:\n{}", html)
        return True

    mailer = _build_mailer()
    if mailer is None:
        logger.warning("未配置 SMTP，跳过邮件发送 | to={} subject={}", to, subject)
        return False

    try:
        message = MessageSchema(
            subject=subject,
            recipients=[to],
            html_body=html,
            subtype="html",
        )
        await mailer.send_message(message)
        logger.info("邮件已发送 | to={} subject={}", to, subject)
        return True
    except Exception as exc:
        logger.exception("邮件发送失败 | to={} subject={} err={}", to, subject, exc)
        return False


async def send_register_verify(to: str, code: str) -> bool:
    subject, html = render_register_verify(code, settings.APP_URL)
    return await send_email(to, subject, html)


async def send_login_alert(to: str, ip: str, device: str, time_str: str) -> bool:
    subject, html = render_login_alert(ip, device, time_str)
    return await send_email(to, subject, html)


async def send_password_reset(to: str, code: str) -> bool:
    subject, html = render_password_reset(code)
    return await send_email(to, subject, html)


async def send_sync_failed(to: str, account_alias: str, reason: str) -> bool:
    subject, html = render_sync_failed(account_alias, reason)
    return await send_email(to, subject, html)


async def send_report_push(to: str, report_title: str, summary: str, report_url: str) -> bool:
    subject, html = render_report_push(report_title, summary, report_url)
    return await send_email(to, subject, html)
