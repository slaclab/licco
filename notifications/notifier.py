import inspect
import logging
from typing import List, Literal, Optional
from notifications.email_sender import EmailSettings, EmailSender, EmailSenderInterface

logger = logging.getLogger(__name__)

_NOTIFICATION_TEMPLATES = {
    "add_approver": {
        "html": inspect.cleandoc("""
        <p>Automated Message - Please Do Not Reply</p>
        <p>You have been added to project <a href="{project_url}">{project_name}</a> in the Machine Configuration Database as Project Approver. Please take action at <a href="{project_url}">{project_url}</a></p>
        <p>If you have any questions, please contact the database administrator at {admin_email}.</p>"""),
        # if more templates are necessary, simply add them to this map, e.g:
        # "markdown": You have been added to the project [project_name](project_url)...
    },
    "remove_approver": {
        "html": inspect.cleandoc("""
        <p>Automated Message - Please Do Not Reply</p>
        <p>You have been removed from project "{project_name}" in the Machine Configuration Database as Project Approver.</p>
        <p>If you have any questions, please contact the database administrator at {admin_email}.</p>""")
    },
    "project_approval_submitted": {
        "html": inspect.cleandoc("""
        <p>Automated Message - Please Do Not Reply</p>
        <p>Your project <a href="{project_url}">{project_name}</a> in the Machine Configuration Database have been submitted to approval.</p>
        <p>If you have any questions, please contact the database administrator at {admin_email}.</p>""")
    },
    "project_approval_rejected": {
        "html": inspect.cleandoc("""
        <p>Automated Message - Please Do Not Reply</p>
        <p>Your project <a href="{project_url}">{project_name}</a> in the Machine Configuration Database have been rejected by {user_who_rejected}.</p>
        <p>If you have any questions, please contact the database administrator at {admin_email}.</p>""")
    },
    "project_approval_approved": {
        "html": inspect.cleandoc("""
        <p>Automated Message - Please Do Not Reply</p>
        <p>Your project <a href="{project_url}">{project_name}</a> in the Machine Configuration Database have been approved.</p>
        <p>If you have any questions, please contact the database administrator at {admin_email}.</p>""")
    },
    "add_editors": {
        "html": inspect.cleandoc("""
        <p>Automated Message - Please Do Not Reply</p>
        <p>You have been added to project <a href="{project_url}">{project_name}</a> in the Machine Configuration Database as Project Editor.</p>
        <p>If you have any questions, please contact the database administrator at {admin_email}</p>""")
    },
    "remove_editors": {
        "html": inspect.cleandoc("""
        <p>Automated Message - Please Do Not Reply</p>
        <p>You have been removed from project "{project_name}" in the Machine Configuration Database as Project Editor.</p>
        <p>If you have any questions, please contact the database administrator at {admin_email}.</p>"""),
    }
}


def create_notification_msg(template_key: str, format_type: Literal["html"], **kwargs):
    try:
        template = _NOTIFICATION_TEMPLATES[template_key][format_type]
        msg = template.format(**kwargs)
        return msg
    except KeyError as e:
        raise ValueError(f"Template for {template_key} in format '{format_type}' does not exist") from e


class Notifier:
    """Helper class for sending user notifications"""
    # TODO: decide on the default 'from' username, should probably come from email configuration as well
    DEFAULT_FROM_USER = "slac noreply"

    def __init__(self, licco_service_url: str, email_sender: EmailSenderInterface):
        # service url is necessary so we can construct a valid url that points to the project
        # during development this url will in the form of "localhost:port", in production it
        # should have the url that gets assigned to the licco project.
        self.licco_service_url = licco_service_url
        self.email_sender = email_sender
        self.admin_email = "XX@slac.stanford.edu"  # TODO: this should come from the configuration

    def add_project_approvers(self, notified_user_ids: List[str], project_name: str, project_id: str):
        subject = f"You were selected as an approver for the project {project_name}"
        content = create_notification_msg("add_approver", "html",
                                          project_name=project_name,
                                          project_url=self._create_project_url(project_id),
                                          admin_email=self.admin_email)
        self.send_email_notification(notified_user_ids, subject, content)

    def remove_project_approvers(self, notified_user_ids: List[str], project_name: str, project_id: str):
        subject = f"You were removed from the approvers for the project {project_name}"
        content = create_notification_msg("remove_approver", "html",
                                          project_name=project_name,
                                          project_url=self._create_project_url(project_id),
                                          admin_email=self.admin_email)
        self.send_email_notification(notified_user_ids, subject, content)

    def project_approval_approved(self, notified_user_ids: List[str], project_name: str, project_id: str):
        subject = f"Project {project_name} was approved"
        content = create_notification_msg("project_approval_approved", "html",
                                          project_name=project_name,
                                          project_url=self._create_project_url(project_id),
                                          admin_email=self.admin_email)
        self.send_email_notification(notified_user_ids, subject, content)

    def project_approval_rejected(self, notified_user_ids: List[str], project_name: str, project_id: str,
                                  user_who_rejected: str):
        subject = f"Project {project_name} was rejected"
        content = create_notification_msg("project_approval_rejected", "html",
                                          project_name=project_name,
                                          project_url=self._create_project_url(project_id),
                                          user_who_rejected=user_who_rejected,
                                          admin_email=self.admin_email)
        self.send_email_notification(notified_user_ids, subject, content)

    def send_email_notification(self, receivers: List[str], subject: str, html_msg: str,
                                plain_text_msg: str = ""):
        """
        Send an email notification, if the email credentials were loaded.

        - receivers: usernames or emails of users. If the provided name is an username, an additional
          network call will be made to the central service to get the user's right email address
        """
        if not self.email_sender:
            return
        if len(receivers) == 0:
            raise ValueError("No receiver emails were specified: at least one is expected")

        # we are sending notifications in a separate thread, to avoid blocking the main thread
        # that is supposed to send a response back to the user.
        from_user = Notifier.DEFAULT_FROM_USER
        self.email_sender.send_email(from_user, receivers, subject, html_msg, plain_text_content=plain_text_msg)

    def _create_project_url(self, project_id: str):
        return f"{self.licco_service_url}/projects/{project_id}"
