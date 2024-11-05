from typing import List, Literal

from notifications.email_sender import EmailSettings, EmailSender

_NOTIFICATION_TEMPLATES = {
    "approve": {
        "html": "<p>You were selected as an approver for the project <a href='{service_url}/projects/{project_id}'>{project_name}</a>. Please approve or decline project changes.</p>",
        "plain": "You were selected as an approver for the project {project_name} - {service_url}/projects/{project_id}. Please approve or decline project changes.",
        "markdown": "You were selected as an approver for the project [{project_name}]({service_url}/projects/{project_id}). Please approve or decline project changes.",
    }
}


def create_notification_msg(template_key: str, format_type: Literal["html", "plain", "markdown"], **kwargs):
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

    def __init__(self, service_url, email_config: EmailSettings = None):
        self.service_url = service_url
        self.email_sender = None
        if email_config:
            if not self.service_url:
                raise ValueError("Notifier service url should not be empty")
            self.email_sender = EmailSender(email_config)

    def notify_project_approver(self, approver_emails: List[str], project_name: str, project_id: str):
        subject = f"You were selected as an approver for the project {project_name}"
        content = create_notification_msg("approve", "html", service_url=self.service_url, project_id=project_id,
                                          project_name=project_name)
        self.send_email_notification(approver_emails, subject, content)

    def send_email_notification(self, approver_emails: List[str], subject: str, html_msg: str,
                                plain_text_msg: str = ""):
        if not self.email_sender:
            return
        if len(approver_emails) == 0:
            raise ValueError("No approver emails were found")

        from_user = Notifier.DEFAULT_FROM_USER
        self.email_sender.send_email(from_user, approver_emails, subject, html_msg, plain_text_content=plain_text_msg)
