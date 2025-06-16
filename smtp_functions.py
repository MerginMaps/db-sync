import datetime
import logging
import smtplib
import typing
from email.message import EmailMessage

from dynaconf import Dynaconf


def create_connection_and_log_user(config: Dynaconf) -> typing.Union[smtplib.SMTP_SSL, smtplib.SMTP]:
    """Create connection and log user to the SMTP server using the configuration in config."""
    if "smtp_port" in config.notification:
        port = config.notification.smtp_port
    else:
        port = 0

    if "use_ssl" in config.notification and config.notification.use_ssl:
        host = smtplib.SMTP_SSL(config.notification.smtp_server, port)
    else:
        host = smtplib.SMTP(config.notification.smtp_server, port)

    if "use_tls" in config.notification and config.notification.use_tls:
        host.starttls()
    if config.notification.smtp_username and config.notification.smtp_password:
        host.login(config.notification.smtp_username, config.notification.smtp_password)

    return host


def send_email(error: str, config: Dynaconf) -> None:
    """Sends email with provided error using the settings in config."""

    msg = EmailMessage()
    msg["Subject"] = config.notification.email_subject
    msg["From"] = config.notification.email_sender
    msg["To"] = ", ".join(config.notification.email_recipients)

    date_time = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    error = f"{date_time}: {error}"

    msg.set_content(error)

    sender_email = config.notification.email_sender

    try:
        smtp_conn = create_connection_and_log_user(config)
        smtp_conn.sendmail(sender_email, config.notification.email_recipients, msg.as_string())
        smtp_conn.quit()
        logging.debug("Notification email sent.")
    except:
        logging.debug("Failed to send notification email!")
