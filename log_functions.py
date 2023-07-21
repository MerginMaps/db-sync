import logging
import pathlib
import sys
import typing
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dynaconf import Dynaconf

from config import config


def filter_below_error(record):
    """Only lets through log messages with log level below ERROR ."""
    return record.levelno < logging.ERROR


def setup_logger(
    log_path: pathlib.Path = None, log_verbosity: str = "DEBUG", with_time=True, with_level=True
) -> logging.Logger:
    log = logging.getLogger()
    log.setLevel(logging.DEBUG)

    print_error_handler = logging.StreamHandler(stream=sys.stderr)
    print_error_handler.setLevel(logging.DEBUG)
    log.addHandler(print_error_handler)

    if log_path:
        log_handler = logging.FileHandler(log_path, mode="a")

        log_handler.setLevel(log_verbosity_to_logging(log_verbosity))

        format = "%(asctime)s -" if with_time else ""
        format += "%(levelname)s - %(message)s" if with_level else "%(message)s"
        log_handler.setFormatter(logging.Formatter(format))

        log.addHandler(log_handler)


def log_verbosity_to_logging(verbosity: str):
    data = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "FATAL": logging.FATAL,
        "CRITICAL": logging.CRITICAL,
    }

    return data[verbosity]


def handle_error_and_exit(error: typing.Union[str, Exception]):
    logging.error(str(error))
    sys.exit(1)


def send_email(error: str, date_time: str = None) -> None:
    smtp_conn = smtplib.SMTP(config.notification.smtp_server)
    smtp_conn.login(config.notification.smtp_username, config.notification.smtp_password)

    msg = MIMEMultipart()
    msg["Subject"] = config.notification.email_subject
    msg["From"] = config.notification.email_sender
    msg["To"] = ", ".join(config.notification.email_recipients)
    msg.preamble = error

    if date_time:
        error = f"{date_time}: {error}"

    msg.attach(MIMEText(error, "plain"))

    smtp_conn.sendmail(config.notification.smtp_username, config.notification.email_recipients, msg.as_string())
    smtp_conn.quit()


def can_send_email(config: Dynaconf) -> bool:
    if "notification" in config:
        return True
    return False
