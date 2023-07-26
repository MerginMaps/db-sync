import datetime
import smtplib
import typing
from email.message import EmailMessage

from dynaconf import Dynaconf


def create_connection(config: Dynaconf) -> typing.Union[smtplib.SMTP_SSL, smtplib.SMTP]:
    if "smtp_port" in config.notification:
        port = config.notification.smtp_port
    else:
        port = smtplib.SMTP_PORT

    if "use_ssl" in config.notification and config.notification.use_ssl:
        host = smtplib.SMTP_SSL(config.notification.smtp_server, port)
    else:
        host = smtplib.SMTP(config.notification.smtp_server, port)

    return host


def log_smtp_user(host: typing.Union[smtplib.SMTP_SSL, smtplib.SMTP], config: Dynaconf) -> None:
    if "use_tls" in config.notification and config.notification.use_tls:
        host.starttls()
    if config.notification.smtp_username and config.notification.smtp_password:
        host.login(config.notification.smtp_username, config.notification.smtp_password)


def should_send_another_email(
    current_time: datetime.datetime, last_email_send: typing.Optional[datetime.datetime], config: Dynaconf
) -> bool:
    if last_email_send is None:
        return True
    min_time_diff = config.notification.minimal_email_interval if "minimal_email_interval" in config.notification else 4
    time_diff = current_time - last_email_send
    return time_diff.seconds > (min_time_diff * 3600)


def send_email(error: str, last_email_send: typing.Optional[datetime.datetime], config: Dynaconf) -> None:
    current_time = datetime.datetime.now()

    if should_send_another_email(current_time, last_email_send, config):
        smtp_conn = create_connection(config)

        log_smtp_user(smtp_conn, config)

        msg = EmailMessage()
        msg["Subject"] = config.notification.email_subject
        msg["From"] = config.notification.email_sender
        msg["To"] = ", ".join(config.notification.email_recipients)

        date_time = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        error = f"{date_time}: {error}"

        msg.set_content(error)

        sender_email = config.notification.email_sender
        if "smtp_username" in config.notification:
            sender_email = config.notification.smtp_username

        smtp_conn.sendmail(sender_email, config.notification.email_recipients, msg.as_string())
        smtp_conn.quit()


def can_send_email(config: Dynaconf) -> bool:
    if "notification" in config:
        return True
    return False
