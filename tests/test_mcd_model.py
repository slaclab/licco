from typing import List, Dict

import pytest

import context
from dal import mcd_model
from dal.mcd_model import initialize_collections
from notifications.email_sender import EmailSenderInterface
from notifications.notifier import Notifier

_TEST_DB_NAME = "_licco_test_db_"

@pytest.fixture(scope="session")
def db():
    """Create db at the start of the session"""
    client = context.mongo_client
    db = client[_TEST_DB_NAME]
    context.licco_db = db
    initialize_collections(db)

    # we expect a fresh test database to only have 1 project (master project)
    projects = db['projects'].find().to_list()
    assert len(projects) == 1, "only one project should be present (master project)"
    assert projects[0]['name'] == "LCLS Machine Configuration Database", "expected a master project"

    # roles used in tests
    admin_users = {"app": "Licco", "name": "Admin", "players": ["uid:admin_user"], "privileges": ["read", "write", "edit", "approve", "admin"]}
    approvers = {"app": "Licco", "name": "Approver", "players": ["uid:approve_user"], "privileges": ["read", "write", "edit", "approve"]}
    super_approvers = {"app": "Licco", "name": "Super Approver", "players": ["uid:super_approver"], "privileges": ["read", "write", "edit", "approve", "super_approve"]}
    editors = {"app": "Licco", "name": "Editor", "players": ["uid:editor_user", "uid:editor_user_2"], "privileges": ["read", "write", "edit"]}
    res = db['roles'].insert_many([admin_users, approvers, super_approvers, editors])
    assert len(res.inserted_ids) == 4, "roles should be inserted"

    # ffts used in tests
    ffts = [{"fc": "TESTFC", "fc_desc": "fcDesc", "fg": "TESTFG", "fg_desc": "fgDesc"}]
    for f in ffts:
        ok, err, fft = mcd_model.create_new_fft(db, f['fc'], f['fg'], f.get('fc_desc', ''), f.get('fg_desc', ''))
        assert ok, f"fft '{f['fc']}' could not be inserted due to: {err}"

    return db

@pytest.fixture(scope="session", autouse=True)
def destroy_db():
    """Destroy db and its data at the end of the testing session"""
    yield
    client = context.mongo_client
    client.drop_database(_TEST_DB_NAME)
    client.close()


class TestEmailSender(EmailSenderInterface):
    """Testing email sender, so we can verify whether the emails were correctly assigned"""
    def __init__(self):
        self.emails_sent = []

    def send_email(self, from_user: str, to_users: List[str], subject: str, content: str,
                   plain_text_content: str = "", send_as_separate_emails: bool = True):
            self.emails_sent.append({'from': from_user, 'to': sorted(to_users), 'subject': subject, 'content': content})

    def validate_email(self, username_or_email: str):
        if username_or_email == 'invalid_user@example.com':
            # an invalid account used for testing
            return False
        return True

    def clear(self):
        self.emails_sent = []


class NoOpEmailSender(EmailSenderInterface):
    def __init__(self):
        pass

class NoOpNotifier(Notifier):
    def __init__(self):
        super().__init__('', NoOpEmailSender())
        pass

    def send_email_notification(self, receivers: List[str], subject: str, html_msg: str,
                                plain_text_msg: str = ""):
        # do nothing
        pass

# -------- helper functions --------

def create_project(db, project_name, owner, editors: List[str] = None, approvers: List[str] = None) -> Dict[str, any]:
    if not editors:
        editors = []
    if not approvers:
        approvers = []

    # TODO: create project should probably accept editors and approvers as well, we would have to verify them though
    project = mcd_model.create_new_project(db, project_name, "", owner)
    if editors or approvers:
        mcd_model.update_project_details(db, owner, project['_id'], {'editors': editors, 'approvers': approvers}, NoOpNotifier())
    assert project, "project should be created but it was not"
    return project


# -------- tests ---------

def test_create_delete_project(db):
    """test project creation and deletion.
    A regular user can't delete a project, but only hide it via a status flag (status == hidden)
    """
    project = mcd_model.create_new_project(db, "test_create_delete_project", "my description", "test_user")
    assert project, "project should be created"
    assert len(str(project["_id"])) > 0, "Project id should exist"
    assert project["description"] == "my description", "wrong description inserted"
    assert len(project["editors"]) == 0, "no editors should be there"
    assert len(project["approvers"]) == 0, "no approvers should be there"

    projects = db["projects"].find({"name": "test_create_delete_project"}).to_list()
    assert len(projects) == 1, "Only one such project should be found"

    prj = projects[0]
    assert prj["owner"] == "test_user", "wrong project owner set"
    assert prj["status"] == "development", "newly created project should be in development"
    ok, err = mcd_model.delete_project(db, "test_user", prj["_id"])
    assert ok
    assert err == "", "there should be no error"

    # regular user can't delete a project, only hide it
    found_after_delete = db["projects"].find({"name": "test_create_delete_project"}).to_list()
    assert len(found_after_delete) == 1, "project should not be deleted"
    assert found_after_delete[0]['status'] == 'hidden', "project should be hidden"


@pytest.mark.skip(reason="TODO: implement this test case")
def test_create_delete_project_admin(db):
    """test project creation and deletion for an admin user
    As opposed to the regular user, the admin user can delete a project and all its device values
    """
    # TODO: check that project and all its fft fields (such as comments) are properly deleted when admin
    # deletes the project
    pass


def test_add_fft_to_project(db):
    # TODO: check what happens if non editor is trying to update fft: we should return an error
    project = mcd_model.create_new_project(db, "test_add_fft_to_project", "", "test_user")

    # get ffts for project, there should be none
    project_ffts = mcd_model.get_project_ffts(db, project["_id"])
    assert len(project_ffts) == 0, "there should be no ffts in a new project"

    # add fft change
    fft_id = str(mcd_model.get_fft_id_by_names(db, "TESTFC", "TESTFG"))
    assert fft_id, "fft_id should exist"
    fft_update = {'_id': fft_id, 'comments': 'some comment', 'nom_ang_x': 1.23}
    ok, err, update_status = mcd_model.update_fft_in_project(db, "test_user", project["_id"], fft_update)
    assert ok, "fft should be inserted"
    assert err == "", "there should be no error"

    project_ffts = mcd_model.get_project_ffts(db, project["_id"])
    assert len(project_ffts) == 1, "we should have at least 1 fft inserted"

    inserted_fft = project_ffts[fft_id]
    assert str(inserted_fft["fft"]["_id"]) == fft_update["_id"]
    assert inserted_fft["comments"] == fft_update["comments"]
    assert inserted_fft["nom_ang_x"] == pytest.approx(fft_update["nom_ang_x"], "0.001")
    assert len(inserted_fft["discussion"]) == 0, "there should be no discussion comments"
    # discussion and fft are extra fields
    default_fields = 2
    inserted_fields = 2
    total_fields = default_fields + inserted_fields
    assert len(inserted_fft.keys()) == total_fields, "there should not be more fields than the one we have inserted"


def test_remove_fft_from_project(db):
    project = mcd_model.create_new_project(db, "test_remove_fft_from_project", "", "test_user")
    prjid = str(project["_id"])

    # insert new fft
    fft_id = str(mcd_model.get_fft_id_by_names(db, "TESTFC", "TESTFG"))
    fft_update = {'_id': fft_id, 'nom_ang_y': 1.23}
    ok, err, update_status = mcd_model.update_fft_in_project(db, "test_user", prjid, fft_update)
    assert ok
    assert err == ""

    inserted_ffts = mcd_model.get_project_ffts(db, prjid)
    assert len(inserted_ffts) == 1
    inserted_fft = inserted_ffts[fft_id]
    assert str(inserted_fft["fft"]["_id"]) == fft_update["_id"]

    # remove inserted fft
    ok, err = mcd_model.remove_ffts_from_project(db, "test_user", prjid, [fft_id])
    assert ok
    assert err == ""

    project_ffts = mcd_model.get_project_ffts(db, prjid)
    assert len(project_ffts) == 0, "there should be no ffts after deletion"


def test_project_approval_workflow(db):
    # testing happy path
    project = mcd_model.create_new_project(db, "test_approval_workflow", "", "test_user")
    prjid = project["_id"]

    email_sender = TestEmailSender()
    notifier = Notifier('', email_sender)
    ok, err = mcd_model.update_project_details(db, "test_user", prjid, {'editors': ['editor_user', 'editor_user_2']}, notifier)
    assert err == ""
    assert ok

    # check if notifications were sent (editor should receive an email when assigned)
    assert len(email_sender.emails_sent) == 1, "Editor should receive a notification that they were appointed"
    editor_mail = email_sender.emails_sent[0]
    assert editor_mail['to'] == ['editor_user', 'editor_user_2']
    assert editor_mail['subject'] == 'You were selected as an editor for the project test_approval_workflow'
    email_sender.clear()

    # an editor user should be able to save an fft
    fftid = str(mcd_model.get_fft_id_by_names(db, "TESTFC", "TESTFG"))
    ok, err, update_status = mcd_model.update_fft_in_project(db, "editor_user", prjid, {"_id": fftid, "tc_part_no": "PART 123"})
    assert err == ""
    assert ok
    assert update_status['success'] == 1

    # verify status and submitter (should not exist right now)
    project = mcd_model.get_project(db, prjid)
    assert project["status"] == "development"
    assert project.get("submitter", None) is None

    # the editor should be able to submit a project
    ok, err, project = mcd_model.submit_project_for_approval(db, prjid, "editor_user", project['editors'], ['approve_user'], notifier)
    assert err == ""
    assert ok
    assert project["_id"] == prjid
    assert project["status"] == "submitted"
    assert project["submitter"] == "editor_user"

    # verify notifications
    assert len(email_sender.emails_sent) == 2, "wrong number of notification emails sent"
    approver_email = email_sender.emails_sent[0]
    # TODO: add a super approver once that branch is merged in
    assert approver_email['to'] == ['approve_user']
    assert approver_email['subject'] == "You were selected as an approver for the project test_approval_workflow"

    # this project was submitted for the first time, therefore an initial message should be sent to editors
    editor_email = email_sender.emails_sent[1]
    assert editor_email['to'] == ["editor_user", "editor_user_2", "test_user"]
    assert editor_email['subject'] == "Project test_approval_workflow was submitted for approval"
    email_sender.clear()

    project = mcd_model.get_project(db, prjid)
    # TODO: add "super_approver" to the list once the super approvers branch is merged in
    assert project['approvers'] == ["approve_user"]
    assert project.get('approved_by', []) == []

    # TODO: once super_approver branch is merged in approve by super approver
    # ok, all_approved, err, prj = mcd_model.approve_project(db, prjid, "super_approver", notifier)
    # assert err == ""
    # assert ok
    # assert all_approved == False
    # assert prj['approved_by'] == ['super_approver']
    # assert len(email_sender.emails_sent) == 0, "there should be no notifications"
    # assert prj['status'] == 'submitted'

    # approve by the final approver, we should receive notifications about approved project
    ok, all_approved, err, prj = mcd_model.approve_project(db, prjid, 'approve_user', notifier)
    assert err == ""
    assert ok
    assert all_approved, "the project should be approved"
    # approved this project goes back into a development branch
    assert prj['editors'] == []
    assert prj['approvers'] == []
    assert prj['approved_by'] == []
    assert prj['status'] == 'development'

    # the changed fft data should reflect in the master project
    master_project = mcd_model.get_master_project(db)
    ffts = mcd_model.get_fft_values_by_project(db, fftid, master_project['_id'])
    assert ffts['tc_part_no'] == "PART 123"

    assert len(email_sender.emails_sent) == 1, "only one set of messages should be sent"
    email = email_sender.emails_sent[0]
    # TODO: once super approve branch is merged in, we have to add super_approver to the list
    assert email['to'] == ['approve_user', 'editor_user', 'editor_user_2', 'test_user']  # , 'super_approver']
    assert email['subject'] == 'Project test_approval_workflow was approved'
    email_sender.clear()


def test_project_rejection(db):
    project = mcd_model.create_new_project(db, "test_project_rejection_workflow", "", "test_user")
    prjid = project["_id"]

    email_sender = TestEmailSender()
    notifier = Notifier('', email_sender)
    ok, err = mcd_model.update_project_details(db, "test_user", prjid, {'editors': ['editor_user', 'editor_user_2']},
                                               notifier)
    assert err == ""
    assert ok

    ok, err, prj = mcd_model.submit_project_for_approval(db, prjid, "test_user", ['editor_user', 'editor_user_2'], ['approve_user', 'approve_user_2'], notifier)
    assert err == ""
    assert ok
    assert prj['status'] == "submitted"

    # clear sender so we can verify the rejection notifications
    email_sender.clear()

    # approve 1/2 approvers
    ok, all_approved, err, prj = mcd_model.approve_project(db, prjid, "approve_user", notifier)
    assert err == ""
    assert ok
    assert all_approved == False
    assert len(email_sender.emails_sent) == 0, "no emails should be sent"
    assert prj['approved_by'] == ['approve_user']

    # reject
    ok, err, prj = mcd_model.reject_project(db, prjid, "test_user", "This is my rejection message", notifier)
    assert err == ""
    assert ok
    assert prj['status'] == "development", "status should go back into a development state"
    assert prj['editors'] == ['editor_user', 'editor_user_2']
    assert prj['approvers'] == ['approve_user', 'approve_user_2']

    # validate that notifications were send
    assert len(email_sender.emails_sent) == 1
    email = email_sender.emails_sent[0]
    assert email['to'] == ['approve_user', 'approve_user_2', 'editor_user', 'editor_user_2', 'test_user']
    assert email['subject'] == 'Project test_project_rejection_workflow was rejected'
    assert 'This is my rejection message' in email['content']
