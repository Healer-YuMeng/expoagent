"""通知服务，用于发送短信和邮件。"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_sms(phone: str, content: str) -> None:
    """发送短信（当前实现为日志记录）。"""
    logger.info("[SMS] 向 %s 发送短信：%s", phone, content)


async def send_email(email: str, subject: str, content: str) -> None:
    """发送邮件。"""
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("SMTP 未配置，邮件功能已禁用。邮件将仅记录在日志中。")
        logger.info("[EMAIL] 向 %s 发送邮件: 主题='%s', 内容='%s'", email, subject, content)
        return

    message = MIMEMultipart()
    message['From'] = f'"{Header(settings.SMTP_SENDER_NAME, "utf-8").encode()}" <{settings.SMTP_USER}>'
    message['To'] = email
    message['Subject'] = Header(subject, 'utf-8')
    message.attach(MIMEText(content, 'plain', 'utf-8'))

    try:
        logger.info(f"准备通过 SMTP ({settings.SMTP_HOST}:{settings.SMTP_PORT}) 发送邮件至 {email}")
        with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_USER, [email], message.as_string())
        logger.info(f"邮件成功发送至 {email}")
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP 认证失败: {e}。请检查 SMTP_USER 和 SMTP_PASSWORD 是否正确。")
    except Exception as e:
        logger.error(f"发送邮件至 {email} 时发生错误: {e}")
