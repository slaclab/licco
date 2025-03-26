import inspect
import json
import logging
import smtplib
import ssl
import threading
from email.message import Message
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List
from urllib import request

logger = logging.getLogger(__name__)


class EmailSenderInterface:
    def send_email(self, from_user: str, to_users: List[str], subject: str, content: str,
                   plain_text_content: str = "", send_as_separate_emails: bool = True):
        pass

    def validate_email(self, username_or_email: str):
        return False


class EmailSenderMock(EmailSenderInterface):
    """Mock email sender implementation that only prints the content into console.
    It's only used during development to avoid sending hundreds of test emails to
    unsuspecting users from the database.
    """
    def send_email(self, from_user: str, to_users: List[str], subject: str, content: str,
                   plain_text_content: str = "", send_as_separate_emails: bool = True):
        content = self._create_email(from_user, to_users, subject, content, plain_text_content, send_as_separate_emails)
        logger.info(f"\n{content}")

    def _create_email(self, from_user: str, to_users: List[str], subject: str, content: str,
                   plain_text_content: str = "", send_as_separate_emails: bool = True):
        to_field = ",".join(to_users)
        if send_as_separate_emails:
            to_field += " (sent as separate_emails)"

        plain_text = ""
        if plain_text_content:
            plain_text += "\n\n" + inspect.cleandoc(f"""
            ---- plain text ----
            {plain_text_content}
        """)

        msg = (f"-----------------------------------------------------------------\n"
               f"From:    {from_user}\n"
               f"To:      {to_field}\n"
               f"Subject: {subject}\n"
               f"\n"
               f"{content}{plain_text}\n"
               f"-----------------------------------------------------------------")
        return msg

    def validate_email(self, username_or_email: str):
        # every mock email is valid (except for a special case)
        if username_or_email == "invalid_email@example.com":
            return False
        return True

class EmailSettings:
    def __init__(self, url: str, port: int, email_auth: bool, 
                 username: str, password: str,
                 username_to_email_service_url: str = "",
                 email_send_as_ssl: bool = False):
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
        # bool for if we need email authentication
        self.email_auth = email_auth
        self.username = username
        self.password = password
        # url of a service that turns licco username into an email
        # (only used in production)
        self.username_to_email_service = username_to_email_service_url
        # send as SMTP_SSL or SMTP_StartTLS
        self.email_send_as_ssl = email_send_as_ssl


class EmailSender(EmailSenderInterface):
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

        # send email in a background thread to avoid blocking the main thread,
        # since email sending could take a long time
        thread = threading.Thread(target=self._prepare_and_send_emails,
                                  args=(from_user, to_users, subject, content,
                                        plain_text_content, send_as_separate_emails))
        thread.start()

    def _prepare_and_send_emails(self, from_user: str, to_users: List[str], subject: str, content: str,
                                 plain_text_content: str = "", send_as_separate_emails: bool = True):
        to_users = EmailSender.convert_usernames_to_emails(self.settings.username_to_email_service, to_users)
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
        errors = self._send_emails(emails_to_send)
        if errors:
            logger.error("Failed to send emails: %s", errors)

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

    def _send_emails(self, emails: List[Message]) -> List[Exception]:
        if self.settings.email_send_as_ssl:
            with smtplib.SMTP_SSL(self.settings.url, self.settings.port, context=self.context) as server:
                if self.settings.email_auth:
                    server.login(self.settings.username, self.settings.password)
                # If sending an email to a certain account has failed for some reason (account doesn't exist)
                # that should not stop sending the rest of the emails.
                exceptions = []
                for e in emails:
                    try:
                        server.send_message(e)
                    except Exception as ex:
                        exceptions.append(ex)
                return exceptions

        with smtplib.SMTP(self.settings.url, self.settings.port) as server:
            server.ehlo()
            if self.settings.email_auth:
                server.starttls(context=self.context)
                server.ehlo()
                server.login(self.settings.username, self.settings.password)
            exceptions = []
            for e in emails:
                try:
                    server.send_message(e)
                except Exception as ex:
                    exceptions.append(ex)
            return exceptions

    def validate_email(self, username_or_email: str):
        # we don't know if the provided email is valid, hence we have to check it
        # against the account service
        username = username_or_email.split("@")[0]
        user_email = EmailSender.convert_usernames_to_emails(self.settings.username_to_email_service, [username])
        if len(user_email) == 0:  # invalid email, this user does not exist
            return False
        return True

    @staticmethod
    def convert_usernames_to_emails(service_url, usernames: List[str]) -> List[str]:
        # turn given usernames into emails by querying the right service
        # since we have to make a separate request for every name, this method
        # could be quite slow (and should therefore run in a background thread)
        if not service_url:
            return usernames

        emails = []
        for name in usernames:
            if "@" in name:
                # this name is already an email
                emails.append(name)
                continue

            # get the email from the service
            try:
                with request.urlopen(f"{service_url}?unixAcct={name}") as response:
                    if response.status != 200:
                        logger.error(f"Failed to get an email for '{name}': unexpected status code: {response.status}")
                        continue

                    # successful response, parse the email
                    data = json.loads(response.read())
                    email = data["email"]
                    if email and "@" in email:
                        emails.append(email)
                    else:
                        logger.error(f"User '{name}' does not have a valid email account: '{email}'")
                    return emails
            except Exception as e:
                # Since this is running in a background notification thread, we can't inform the
                # user that something went wrong with notifications. Therefore we can only log
                # an error and hope that a system administrator notices an issue
                logger.error(f"Failed to get an email for user {name}: {str(e)}")


class NoOpEmailSender(EmailSenderInterface):
    def __init__(self):
        pass

