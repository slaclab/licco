import smtplib
import ssl
from email.message import Message
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List


class EmailSettings:
    def __init__(self, url: str, port: int, username: str, password: str, email_send_as_ssl: bool = False):
        if not url:
            raise ValueError("Email url should not be empty")
        if not port:
            raise ValueError("Email port should not be empty")
        if not username:
            raise ValueError("Username should not be empty")
        if not password:
            raise ValueError("Password should not be empty")

        self.url = url
        self.port = port
        self.username = username
        self.password = password
        # send as SMTP_SSL or SMTP_StartTLS
        self.email_send_as_ssl = email_send_as_ssl


class EmailSender:
    """Helper class for easy sending of email notifications"""

    def __init__(self, settings: EmailSettings):
        self.settings = settings
        self.context = ssl.create_default_context()

    def send_email(self, from_user: str, to_users: List[str], subject: str, content: str,
                   plain_text_content: str = ""):
        """
        - from_user: user that sent an email in the form of "<first name> <last name> <email@example.com>"
        - to_users: emails of all users to which an email will be sent
        - subject: email subject (plain text)
        - content: email html content
        - plain_text_content: (optional) if plain text content alongside html version is expected

        raises an Exception in case of any error
        """
        if not from_user:
            raise ValueError("From user is not specified")
        if len(to_users) < 1:
            raise ValueError("Expected at least 1 email recipient")
        if not subject:
            raise ValueError("Email subject should not be empty")
        if not content:
            raise ValueError("Email message should not be empty")

        email = MIMEMultipart("alternative")
        email["Subject"] = subject
        email["From"] = from_user
        email["To"] = ",".join(to_users)

        # if plain text is required, it should be attached first
        # (email clients apparently display the last attached text [html] if possible)
        if plain_text_content:
            plain_text = MIMEText(plain_text_content, "plain")
            email.attach(plain_text)

        # html should be attached last, since last message is displayed first
        html_text = MIMEText(content, "html")
        email.attach(html_text)
        self._send_email(email)

    def _send_email(self, msg: Message):
        if self.settings.email_send_as_ssl:
            with smtplib.SMTP_SSL(self.settings.url, self.settings.port, context=self.context) as server:
                server.login(self.settings.username, self.settings.password)
                server.send_message(msg)
                return

        with smtplib.SMTP(self.settings.url, self.settings.port) as server:
            server.ehlo()
            server.starttls(context=self.context)
            server.ehlo()
            server.login(self.settings.username, self.settings.password)
            server.send_message(msg)
