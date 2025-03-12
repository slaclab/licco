import inspect
import logging
from typing import List, Literal
from notifications.email_sender import EmailSenderInterface, NoOpEmailSender

logger = logging.getLogger(__name__)

_NOTIFICATION_TEMPLATES = {
    "add_approver": {
        "html": inspect.cleandoc("""
        <p>Automated Message - Please Do Not Reply</p>
        <p>You have been added to project <a href="{project_url}">{project_name}</a> in the Machine Configuration Database as Project Approver. Please take action at <a href="{project_url}">{project_url}.</a></p>
        <p>If you have any questions, please contact the database administrator at {admin_email}.</p>"""),
        # if more templates are necessary, simply add them to this map, e.g:
        # "markdown": You have been added to the project [project_name](project_url)...
    },
    "add_superapprover": {
        "html": inspect.cleandoc("""
        <p>Automated Message - Please Do Not Reply</p>
        <p>As a Super Approver, your review has been requested for project <a href="{project_url}">{project_name}</a> in the Machine Configuration Database. Your action is required at <a href="{project_url}">{project_url}.</a></p>
        <p>If you have any questions, please contact the database administrator at {admin_email}.</p>"""),
    },
    "remove_approver": {
        "html": inspect.cleandoc("""
        <p>Automated Message - Please Do Not Reply</p>
        <p>You have been removed from project "{project_name}" in the Machine Configuration Database as Project Approver.</p>
        <p>If you have any questions, please contact the database administrator at {admin_email}.</p>""")
    },
    "inform_editors_of_approver_update": {
        "html": inspect.cleandoc("""
        <p>Automated Message - Please Do Not Reply</p>
        <p>The approvers for <a href="{project_url}">{project_name}</a> have changed.<br/>Current approvers: {approvers}</p>
        <p>If you have any questions, please contact the database administrator at {admin_email}.</p>""")
    },
    "project_approval_submitted": {
        "html": inspect.cleandoc("""
        <p>Automated Message - Please Do Not Reply</p>
        <p>The project <a href="{project_url}">{project_name}</a> in the Machine Configuration Database has been submitted for approval.</p>
        <p>If you have any questions, please contact the database administrator at {admin_email}.</p>""")
    },
    "project_approval_rejected": {
        "html": inspect.cleandoc("""
        <p>Automated Message - Please Do Not Reply</p>
        <p>The project <a href="{project_url}">{project_name}</a> in the Machine Configuration Database has been rejected by {user_who_rejected}.<br/>Reason:</p>
        <p>{reason}</p>
        <p>If you have any questions, please contact the database administrator at {admin_email}.</p>""")
    },
    "project_approval_approved": {
        "html": inspect.cleandoc("""
        <p>Automated Message - Please Do Not Reply</p>
        <p>The project <a href="{project_url}">{project_name}</a> in the Machine Configuration Database has been approved.</p>
        <p>If you have any questions, please contact the database administrator at {admin_email}.</p>""")
    },
    "add_editor": {
        "html": inspect.cleandoc("""
        <p>Automated Message - Please Do Not Reply</p>
        <p>You have been added to project <a href="{project_url}">{project_name}</a> in the Machine Configuration Database as Project Editor.</p>
        <p>If you have any questions, please contact the database administrator at {admin_email}</p>""")
    },
    "remove_editor": {
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

    def __init__(self, licco_service_url: str, email_sender: EmailSenderInterface, admin_email: str):
        # service url is necessary so we can construct a valid url that points to the project
        # during development this url will in the form of "localhost:port", in production it
        # should have the url that gets assigned to the licco project.
        self.licco_service_url = licco_service_url
        self.email_sender = email_sender
        self.admin_email = admin_email

    def validate_email(self, username_or_email: str):
        """Validates email with the chosen email sender. If a production verifier is used, this method
           call could be quite slow"""
        return self.email_sender.validate_email(username_or_email)

    def add_project_editors(self, new_editor_ids: List[str], project_name: str, project_id: str):
        subject = f"(MCD) You were selected as an editor for the project {project_name}"
        content = create_notification_msg("add_editor", "html",
                                          project_name=project_name,
                                          project_url=self._create_project_url(project_id),
                                          admin_email=self.admin_email)
        self.send_email_notification(new_editor_ids, subject, content)

    def remove_project_editors(self, removed_editor_ids: List[str], project_name: str, project_id: str):
        subject = f"(MCD) You were removed as an editor for the project {project_name}"
        content = create_notification_msg("remove_editor", "html",
                                          project_name=project_name,
                                          project_url=self._create_project_url(project_id),
                                          admin_email=self.admin_email)
        self.send_email_notification(removed_editor_ids, subject, content)

    def add_project_approvers(self, notified_user_ids: List[str], project_name: str, project_id: str):
        subject = f"(MCD) You were selected as an approver for the project {project_name}"
        content = create_notification_msg("add_approver", "html",
                                          project_name=project_name,
                                          project_url=self._create_approval_url(project_id),
                                          admin_email=self.admin_email)
        self.send_email_notification(notified_user_ids, subject, content)

    def add_project_superapprovers(self, notified_user_ids: List[str], project_name: str, project_id: str):
        subject = f"(MCD) You were added as a Super Approver for the project {project_name}"
        content = create_notification_msg("add_superapprover", "html",
                                          project_name=project_name,
                                          project_url=self._create_approval_url(project_id),
                                          admin_email=self.admin_email)
        self.send_email_notification(notified_user_ids, subject, content)

    def remove_project_approvers(self, notified_user_ids: List[str], project_name: str, project_id: str):
        subject = f"(MCD) You were removed from the approvers for the project {project_name}"
        content = create_notification_msg("remove_approver", "html",
                                          project_name=project_name,
                                          project_url=self._create_project_url(project_id),
                                          admin_email=self.admin_email)
        self.send_email_notification(notified_user_ids, subject, content)

    def inform_editors_of_approver_change(self, notified_user_ids: List[str], project_name: str, project_id: str, current_approvers: List[str]):
        subject = f"(MCD) Approvers have been updated for the project {project_name}"
        content = create_notification_msg("inform_editors_of_approver_update", "html",
                                          project_url=self._create_project_url(project_id),
                                          project_name=project_name,
                                          approvers=current_approvers,
                                          admin_email=self.admin_email)
        self.send_email_notification(notified_user_ids, subject, content)

    def project_submitted_for_approval(self, notified_user_ids: List[str], project_name: str, project_id: str):
        subject = f"(MCD) Project {project_name} was submitted for approval"
        content = create_notification_msg("project_approval_submitted", "html",
                                          project_name=project_name,
                                          project_url=self._create_project_url(project_id),
                                          admin_email=self.admin_email)
        self.send_email_notification(notified_user_ids, subject, content)

    def project_approval_approved(self, notified_user_ids: List[str], project_name: str, project_id: str):
        subject = f"(MCD) Project {project_name} was approved"
        content = create_notification_msg("project_approval_approved", "html",
                                          project_name=project_name,
                                          project_url=self._create_project_url(project_id),
                                          admin_email=self.admin_email)
        self.send_email_notification(notified_user_ids, subject, content)

    def project_approval_rejected(self, notified_user_ids: List[str], project_name: str, project_id: str,
                                  user_who_rejected: str, reason: str):
        subject = f"(MCD) Project {project_name} was rejected"
        content = create_notification_msg("project_approval_rejected", "html",
                                          project_name=project_name,
                                          project_url=self._create_project_url(project_id),
                                          user_who_rejected=user_who_rejected,
                                          reason=reason,
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
    
    def _create_approval_url(self, project_id: str):
        return self._create_project_url(project_id) + '/approval/'


class NoOpNotifier(Notifier):
    def __init__(self):
        super().__init__('', NoOpEmailSender(), "admin@example.com")
        pass

    def validate_email(self, username_or_email: str):
        return True

    def send_email_notification(self, receivers: List[str], subject: str, html_msg: str,
                                plain_text_msg: str = ""):
        # do nothing
        pass
