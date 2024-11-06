from typing import List, Literal

from notifications.email_sender import EmailSettings, EmailSender

_NOTIFICATION_TEMPLATES = {
    "add_approver": {
        "html": """
        <p>Automated Message - Please Do Not Reply</p>
        <p>You have been added to project <a href="{project_url}">{project_name}</a> in the Machine Configuration Database as Project Approver. Please take action at <a href="{project_url}">{project_url}</a></p>
        <p>If you have any questions, please contact the database administrator at {admin_email}.</p>" 
        """,
        # if more templates are necessary, simply add them to this map, e.g:
        # "markdown": You have been added to the project [project_name](project_url)...
    },
    "remove_approver": {
        "html": """
        <p>Automated Message - Please Do Not Reply</p>
        <p>You have been removed from project "{project_name}" in the Machine Configuration Database as Project Approver.</p>
        <p>If you have any questions, please contact the database administrator at {admin_email}.</p>
        """
    },
    "project_approval_submitted": {
        "html": """
        <p>Automated Message - Please Do Not Reply</p>
        <p>Your project <a href="{project_url}">{project_name}</a> in the Machine Configuration Database have been submitted to approval.</p>
        <p>If you have any questions, please contact the database administrator at {admin_email}.</p>
        """
    },
    "project_approval_rejected": {
        "html": """
        <p>Automated Message - Please Do Not Reply</p>
        <p>Your project <a href="{project_url}">{project_name}</a> in the Machine Configuration Database have been rejected by {user_who_rejected}.</p>
        <p>If you have any questions, please contact the database administrator at {admin_email}.</p>
        """
    },
    "project_approval_approved": {
        "html": """
        <p>Automated Message - Please Do Not Reply</p>
        <p>Your project <a href="{project_url}">{project_name}</a> in the Machine Configuration Database have been approved.</p>
        <p>If you have any questions, please contact the database administrator at {admin_email}.</p>
        """
    },
    "add_editors": {
        "html": """
        <p>Automated Message - Please Do Not Reply</p>
        <p>You have been added to project <a href="{project_url}">{project_name}</a> in the Machine Configuration Database as Project Editor.</p>
        <p>If you have any questions, please contact the database administrator at {admin_email}</p>
        """
    },
    "remove_editors": {
        "html": """
        <p>Automated Message - Please Do Not Reply</p>
        <p>You have been removed from project "{project_name}" in the Machine Configuration Database as Project Editor.</p>
        <p>If you have any questions, please contact the database administrator at {admin_email}.</p>
        """
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
    # TODO: decide on the default 'from' username
    DEFAULT_FROM_USER = "slac noreply"

    def __init__(self, service_url: str, email_config: EmailSettings = None):
        # service url is necessary so we can construct a valid url that points to the project
        # during development this url will in the form of "localhost:port", in production it
        # should have the url that gets assigned to the licco project.
        self.service_url = service_url
        self.email_sender = None
        self.admin_email = "XX@slac.stanford.edu"  # TODO: this should come from the configuration
        if email_config:
            if not self.service_url:
                raise ValueError("Notifier service url should not be empty")
            self.email_sender = EmailSender(email_config)

    def add_project_approvers(self, approver_emails: List[str], project_name: str, project_id: str):
        subject = f"You were selected as an approver for the project {project_name}"
        content = create_notification_msg("add_approver", "html",
                                          project_name=project_name,
                                          project_url=self._create_project_url(project_id),
                                          admin_email=self.admin_email)
        self.send_email_notification(approver_emails, subject, content)

    def remove_project_approvers(self, removed_emails: List[str], project_name: str, project_id: str):
        subject = f"You were removed from the approvers for the project {project_name}"
        content = create_notification_msg("remove_approver", "html",
                                          project_name=project_name,
                                          project_url=self._create_project_url(project_id),
                                          admin_email=self.admin_email)

    def project_approval_approved(self, notified_user_emails: List[str], project_name: str, project_id: str):
        subject = f"Project {project_name} was approved"
        content = create_notification_msg("project_approval_approved", "html",
                                          project_name=project_name,
                                          project_url=self._create_project_url(project_id),
                                          admin_email=self.admin_email)
        self.send_email_notification(notified_user_emails, subject, content)

    def project_approval_rejected(self, notified_user_emails: List[str], project_name: str, project_id: str,
                                  user_who_rejected: str):
        subject = f"Project {project_name} was rejected"
        content = create_notification_msg("project_approval_rejected", "html",
                                          project_name=project_name,
                                          project_url=self._create_project_url(project_id),
                                          user_who_rejected=user_who_rejected,
                                          admin_email=self.admin_email)
        self.send_email_notification(notified_user_emails, subject, content)

    def send_email_notification(self, receiver_emails: List[str], subject: str, html_msg: str,
                                plain_text_msg: str = ""):
        if not self.email_sender:
            return
        if len(receiver_emails) == 0:
            raise ValueError("No receiver emails were specified: at least one is expected")

        # TODO: we may want to send this in the background to avoid blocking
        # the REST API response while we are sending our emails.
        from_user = Notifier.DEFAULT_FROM_USER
        self.email_sender.send_email(from_user, receiver_emails, subject, html_msg, plain_text_content=plain_text_msg)

    def _create_project_url(self, project_id: str):
        return f"{self.service_url}/projects/{project_id}"
