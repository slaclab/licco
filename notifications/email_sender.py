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
                   plain_text_content: str = "", send_as_separate_emails: bool = True):
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

        emails_to_send = []
        if send_as_separate_emails:
            # each user will receive its own email (without the other users in the 'To' field)
            for recipient in to_users:
                email = self._create_email(from_user, [recipient], subject, content, plain_text_content)
                emails_to_send.append(email)
        else:
            # users will be able to see who received an email (they are all listed in 'To' field)
            email = self._create_email(from_user, to_users, subject, content, plain_text_content)
            emails_to_send.append(email)

        self._send_emails(emails_to_send)

    def _create_email(self, from_user: str, to_users: List[str],
                      subject: str, html_content: str, plain_text_content: str = ""):
        email = MIMEMultipart("alternative")
        email["Subject"] = subject
        email["From"] = from_user
        email["To"] = ",".join(to_users)

        # if plain text is required, it should be attached first
        # (email clients apparently display the last attached text [html] if possible)
        if plain_text_content:
            plain_text = MIMEText(plain_text_content, "plain")
            email.attach(plain_text)

        # html should be attached last, since last message is displayed first in email clients
        html_text = MIMEText(html_content, "html")
        email.attach(html_text)
        return email

    def _send_emails(self, emails: List[Message]):
        if self.settings.email_send_as_ssl:
            with smtplib.SMTP_SSL(self.settings.url, self.settings.port, context=self.context) as server:
                server.login(self.settings.username, self.settings.password)
                # TODO: this should run in the background, to avoid blocking the email sender
                # use a sending thread and a concurrent queue.
                #
                # TODO: how to handle failures in this case? If one email could not be send
                # that should not terminate the sending of the rest of the emails
                for e in emails:
                    server.send_message(e)
                return

        with smtplib.SMTP(self.settings.url, self.settings.port) as server:
            server.ehlo()
            server.starttls(context=self.context)
            server.ehlo()
            server.login(self.settings.username, self.settings.password)
            for e in emails:
                server.send_message(e)
