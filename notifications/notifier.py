from notifications.email_sender import EmailSettings, EmailSender


class Notifier:
    """Helper class for sending user notifications"""

    def __init__(self, service_url: str = "", email_config: EmailSettings = None):
        self.email_sender = None
        if email_config:
            self.email_sender = EmailSender(email_config)
        self.service_url = service_url

    def notify_project_approver(self, approver_emails: [], project_name: str, project_id: str):
        if self.email_sender:
            if len(approver_emails) == 0 or approver_emails[0] == "":
                raise ValueError("No approver emails found")

            # TODO: decide on the default 'from' username
            from_user = "slac noreply"
            self.email_sender.send_email(from_user, approver_emails, f"You were selected as an approver for the project {project_name}",
                                         f"<p>You were selected as an approver for the project <a href='{self.service_url}/projects/{project_id}'>{project_name}</a>. "
                                         f"Please approve or decline project changes.</p>")

