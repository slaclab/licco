import datetime
import io
import logging
from typing import List, Dict, Mapping, Any

import mongomock.mongo_client
import pytest
import pytz
from bson import ObjectId
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError

from dal import mcd_model, db_utils, mcd_import, mcd_datatypes
from dal.mcd_model import initialize_collections
from notifications.email_sender import EmailSenderInterface
from notifications.notifier import Notifier, NoOpNotifier

_TEST_DB_NAME = "_licco_test_db_"

client: MongoClient[Mapping[str, Any]]


def create_test_db_client():
    try:
        # NOTE: short timeout so that switch to mongomock is fast
        db_client = db_utils.create_mongo_client(timeout=500)
        # this ping is necessary for checking the connection,
        # as the client is only connected on the first db call
        db_client.admin.command('ping')
        print("\n==== MongoDb is connected ====\n")
        return db_client
    except ServerSelectionTimeoutError:
        # mongo db is not connected (maybe it doesn't even exist on this system)
        # therefore we switch to mongo mock in order to mock db calls
        print("\n==== MongoDb is not connected, switching to MongoMock ====\n")
        db_client = mongomock.mongo_client.MongoClient()
        return db_client
    except Exception as e:
        print("\nFailed to create a mongodb client for tests:\n")
        raise e

@pytest.fixture(scope="session")
def db():
    """Create db at the start of the session"""
    global client
    client = create_test_db_client()
    db = client[_TEST_DB_NAME]
    initialize_collections(db)

    # we expect a fresh test database to only have 1 project (master project)
    projects = list(db['projects'].find())
    assert len(projects) == 1, "only one project should be present (master project)"
    assert projects[0]['name'] == "LCLS Machine Configuration Database", "expected a master project"

    # roles used in tests
    admin_users = {"app": "Licco", "name": "admin", "players": ["uid:admin_user"], "privileges": ["read", "write", "edit", "approve", "admin"]}
    approvers = {"app": "Licco", "name": "approver", "players": ["uid:approve_user"], "privileges": ["read", "write", "edit", "approve"]}
    super_approvers = {"app": "Licco", "name": "superapprover", "players": ["uid:super_approver"], "privileges": ["read", "write", "edit", "approve", "super_approve"]}
    editors = {"app": "Licco", "name": "editor", "players": ["uid:editor_user", "uid:editor_user_2"], "privileges": ["read", "write", "edit"]}
    res = db['roles'].insert_many([admin_users, approvers, super_approvers, editors])
    assert len(res.inserted_ids) == 4, "roles should be inserted"

    # ffts used in tests
    ffts = [{"fc": "TESTFC", "fg": "TESTFG"}, {"fc": "TESTFC_2", "fg": "TESTFG_2"}]
    for f in ffts:
        ok, err, fft = mcd_model.create_new_fft(db, f['fc'], f['fg'])
        assert ok, f"fft '{f['fc']}' could not be inserted due to: {err}"

    return db

@pytest.fixture(scope="session", autouse=True)
def destroy_db():
    """Destroy db and its data at the end of the testing session"""
    yield
    global client
    if client:
        client.drop_database(_TEST_DB_NAME)
        client.close()


class _TestEmailSender(EmailSenderInterface):  # NOTE: _ is in front of class name for the coverage to work correctly
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


# -------- helper functions --------

def create_test_project(db, owner, project_name, description, editors: List[str] = None) -> Dict[str, any]:
    if not editors:
        editors = []

    err, project = mcd_model.create_new_project(db, owner, project_name, description, editors, NoOpNotifier())
    assert err == ""
    assert project, f"project {project_name} should be created but it was not"
    return project


# -------- tests ---------

def test_create_delete_project(db):
    """test project creation and deletion.
    A regular user can't delete a project, but only hide it via a status flag (status == hidden)
    """
    project = create_test_project(db, "test_user", "test_create_delete_project", "my description", editors=['my_editor@example.com', 'another_username'])
    assert project, "project should be created"
    assert len(str(project["_id"])) > 0, "Project id should exist"
    assert project["description"] == "my description", "wrong description inserted"
    assert len(project["editors"]) == 2, "there should be an editor there"
    assert sorted(project["editors"]) == ["another_username", "my_editor"]
    assert len(project["approvers"]) == 0, "there should be no approvers"

    projects = list(db["projects"].find({"name": "test_create_delete_project"}))
    assert len(projects) == 1, "Only one such project should be found"

    prj = projects[0]
    assert prj["owner"] == "test_user", "wrong project owner set"
    assert prj["status"] == "development", "newly created project should be in development"
    ok, err = mcd_model.delete_project(db, "test_user", prj["_id"])
    assert err == "", "there should be no error"
    assert ok

    # regular user can't delete a project, only hide it
    found_after_delete = list(db['projects'].find({'_id': prj['_id']}))
    assert len(found_after_delete) == 1, "project should not be deleted"
    assert found_after_delete[0]['status'] == 'hidden', "project should be hidden"
    # verify name of project is changed to reflect hidden status
    hidden_name = 'hidden' + '_' + prj['name'] + '_' + datetime.date.today().strftime('%m/%d/%Y')
    assert hidden_name == found_after_delete[0]['name']


def test_create_delete_project_admin(db):
    """test project creation and deletion for an admin user
    As opposed to the regular user, the admin user can delete a project and all its device values
    """
    # create project
    project = create_test_project(db, "test_user", "test_create_delete_project_admin", "", [])
    prjid = project["_id"]

    # add fft to the project
    fft_id = str(mcd_model.get_fft_id_by_names(db, "TESTFC", "TESTFG"))
    assert fft_id, "fft_id should exist"
    fft_update = {'_id': fft_id, 'comments': 'some comment', 'nom_ang_x': 1.23}
    ok, err, update_status = mcd_model.update_fft_in_project(db, "test_user", prjid, fft_update)
    assert err == ""

    # add discussion comment to the project
    new_comment = {'_id': fft_id, 'author': 'test_author', 'discussion': 'my comment'}
    ok, err, update_status = mcd_model.update_fft_in_project(db, "test_user", prjid, new_comment)
    assert err == ""

    # verify inserted ffts
    project_ffts = mcd_model.get_project_ffts(db, prjid)
    assert len(project_ffts) == 1, "we should have at least 1 fft inserted"
    assert len(project_ffts[fft_id]['discussion']) == 1, "there should be only 1 comment there"
    comment = project_ffts[fft_id]['discussion'][0]
    assert comment['author'] == 'test_user'
    assert comment['comment'] == 'my comment'

    # delete a project and verify that it doesn't exist
    ok, err = mcd_model.delete_project(db, "admin_user", prjid)
    assert err == "", "there should be no error when deleting a project"
    project_after_delete = db["projects"].find_one({"_id": prjid})
    assert project_after_delete is None, "project should not be found after an admin has deleted it"

    # there should be no ffts for a deleted project
    out = mcd_model.get_project_ffts(db, prjid)
    assert len(out) == 0, "there should be no ffts for the deleted project"


def test_delete_project_if_not_owner(db):
    """Project should only be deleted by the owner or admin, other users should get an error"""
    prj = create_test_project(db, "test_user", "test_delete_project_if_not_owner", "", [])
    _, err = mcd_model.update_project_details(db, "test_user", prj["_id"], {"editors": ["editor_user"]}, notifier=NoOpNotifier())
    assert err == ""

    expected_msg = "You don't have permissions to delete the project test_delete_project_if_not_owner"
    _, err = mcd_model.delete_project(db, "random_user", prj["_id"])
    assert expected_msg in err
    verify_prj = mcd_model.get_project(db, prj["_id"])
    assert verify_prj is not None, "project should exist"
    assert verify_prj['status'] == 'development'

    _, err = mcd_model.delete_project(db, "editor_user", prj["_id"])
    assert expected_msg in err
    assert mcd_model.get_project(db, prj["_id"]) is not None, "project should exist"
    verify_prj = mcd_model.get_project(db, prj["_id"])
    assert verify_prj is not None, "project should exist"
    assert verify_prj['status'] == 'development'


def test_clone_project(db):
    project = create_test_project(db, "test_user", 'test_clone_project', "original_description")
    prjid = project["_id"]

    # add ffts to the project
    fft_id = str(mcd_model.get_fft_id_by_names(db, "TESTFC", "TESTFG"))
    assert fft_id, "fft_id should exist"
    fft_update = {'_id': fft_id, 'comments': 'some comment', 'nom_ang_x': 1.23}
    ok, err, update_status = mcd_model.update_fft_in_project(db, "test_user", prjid, fft_update)
    assert err == ""
    # add discussion comment to the project
    new_comment = {'_id': fft_id, 'author': 'test_author', 'discussion': 'my comment'}
    ok, err, update_status = mcd_model.update_fft_in_project(db, "test_user", prjid, new_comment)
    assert err == ""

    # clone the project and verify that all ffts (including discussion comments) are cloned
    ok, err, cloned_project = mcd_model.clone_project(db, "test_user", prjid, "test_clone_project_cloned", "cloned_description", ['editor_user'], notifier=NoOpNotifier())
    assert err == ""
    assert len(str(cloned_project["_id"])) > 0
    assert str(project['_id']) != str(cloned_project['_id']), "id should be different"
    assert project['creation_time'] < cloned_project['creation_time']
    assert project['description'] != cloned_project['description']

    # in cloned project, there should be 1 fft with the same fields and same discussion comments
    ffts = mcd_model.get_project_ffts(db, cloned_project["_id"])
    assert len(ffts) == 1
    fft = list(ffts.values())[0]
    assert fft.get('nom_ang_y', None) is None, "nom_ang_y was not set and should be None"
    assert fft['nom_ang_x'] == 1.23
    assert fft['comments'] == 'some comment'
    assert len(fft['discussion']) == 1
    assert fft['discussion'][0]['comment'] == 'my comment'


def test_copy_fft_values(db):
    """Copy ffts values from one project to another: only chosen fields should be copied over"""
    a = create_test_project(db, "test_user", "test_copy_fft_values_1", "")
    b = create_test_project(db, "test_user", "test_copy_fft_values_2", "")
    assert a
    assert b

    # 'a' insert fft
    fft_id = str(mcd_model.get_fft_id_by_names(db, "TESTFC", "TESTFG"))
    assert fft_id, "fft_id should exist"
    fft_update_a = {'_id': fft_id, 'comments': 'project_a comment', 'nom_ang_x': 2.45, 'nom_ang_y': 1.20}
    _, err, _ = mcd_model.update_fft_in_project(db, "test_user", a["_id"], fft_update_a)
    assert err == ""

    # 'b' should have no fft
    b_ffts = mcd_model.get_project_ffts(db, b["_id"])
    assert len(b_ffts) == 0, "there should be no ffts in project 'b'"

    ok, err, updated_ffts = mcd_model.copy_ffts_from_project(db, a["_id"], b["_id"], fft_id, ['nom_ang_x', 'comments'], "test_user")
    assert err == ""
    assert ok

    # after copy there should be fft with the chosen fields within the 'b' project
    b_ffts = mcd_model.get_project_ffts(db, b["_id"])
    assert len(b_ffts) == 1, "there should be 1 fft present in 'b' after copy"
    fft = list(b_ffts.values())[0]
    assert fft['comments'] == 'project_a comment'
    assert fft['nom_ang_x'] == 2.45
    assert fft.get('nom_ang_y', None) is None, "nom_ang_y should not exist in copied fft, because it wasn't selected for copying"


def test_change_of_fft_in_a_project(db):
    """Change fft device in a project: device should be correctly changed"""
    prj = create_test_project(db, "test_user", "test_change_of_fft_in_a_project", "")
    _, err = mcd_model.update_project_details(db, "test_user", prj["_id"], {"editors": ["editor_user"]}, notifier=NoOpNotifier())
    assert err == ""

    # create fft device with some data
    fft_id = str(mcd_model.get_fft_id_by_names(db, "TESTFC", "TESTFG"))
    assert fft_id, "fft_id should exist"
    fft_update = {'_id': fft_id, 'comments': 'initial comment', 'nom_ang_x': 2.45, 'nom_ang_y': 1.20}
    _, err, _ = mcd_model.update_fft_in_project(db, "test_user", prj["_id"], fft_update)

    # create a discussion comment for previous fft
    mcd_model.add_fft_comment(db, "test_user", prj["_id"], fft_id, "Initial discussion comment")

    # change the device fc
    new_fc = "TESTFC_2"
    fc = db["fcs"].find_one({"name": new_fc})
    update = {"_id": fft_id, "fc": str(fc["_id"]), "nom_ang_y": 1.40, "discussion": [{"author": "editor_user", "comment": "Editor comment"}]}
    _, err, new_fftid = mcd_model.change_of_fft_in_project(db, "editor_user", prj["_id"], update)
    assert err == ""
    assert new_fftid != ""

    # verify that changes were applied and 'fc' has changed
    ffts = mcd_model.get_project_ffts(db, prj["_id"])
    assert len(ffts) == 1, "there should be only 1 fft stored"
    fft = list(ffts.values())[0]
    assert fft["comments"] == "initial comment"
    assert fft["nom_ang_x"] == 2.45
    assert fft["nom_ang_y"] == 1.40, "nom_ang_y did not change but it should"

    discussion = fft["discussion"]
    assert len(discussion) == 2, "invalid number of discussion comments"

    # comments are sorted in descending order
    assert discussion[0]["author"] == "editor_user"
    assert discussion[0]["comment"] == "Editor comment"

    assert discussion[1]["author"] == "test_user"
    assert discussion[1]["comment"] == "Initial discussion comment"


def test_diff_project(db):
    """Diff two projects and check if changes are detected"""
    a = create_test_project(db, "test_user", "test_diff_project", "")
    b = create_test_project(db, "test_user", "test_diff_project_2", "")

    # update a with some values
    fft_id = str(mcd_model.get_fft_id_by_names(db, "TESTFC", "TESTFG"))
    assert fft_id, "fft_id should exist"
    fft_update_a = {'_id': fft_id, 'comments': 'some comment', 'nom_ang_x': 1.23}
    _, err, _ = mcd_model.update_fft_in_project(db, "test_user", a["_id"], fft_update_a)
    assert err == ""

    # update b with different values
    fft_update_b = {'_id': fft_id, 'comments': 'some comment', 'nom_ang_y': 2.56, 'nom_ang_x': 0.51}
    _, err, _ = mcd_model.update_fft_in_project(db, "test_user", b["_id"], fft_update_b)
    assert err == ""

    # check the diff algorithm
    ok, err, diff = mcd_model.diff_project(db, a["_id"], b["_id"], "test_user")
    assert err == ""
    diff_elements = [d for d in diff if d['diff'] is True]
    assert len(diff_elements) == 2, "there should only be 2 diff elements"

    for el in diff_elements:
        # key = <fftid>.<field_name>
        if 'nom_ang_x' in el['key']:
            a_val = el['my']
            b_val = el['ot']
            assert a_val == 1.23
            assert b_val == 0.51
        elif 'nom_ang_y' in el['key']:
            a_val = el['my']
            b_val = el['ot']
            assert a_val is None
            assert b_val == 2.56
        else:
            assert False, "unhandled diff element:\n{el}"


def test_project_filter_for_owner(db):
    """Checking if the project filtering is correct for a specific non-admin project owner"""
    # create project that should appear in the result
    project = create_test_project(db, "test_project_filter_owner", "test_project_filter_for_owner", "")
    assert project

    projects = mcd_model.get_all_projects(db, 'test_project_filter_owner')
    assert len(projects) == 2
    assert projects[0]['name'] == "test_project_filter_for_owner"
    assert projects[1]['name'] == mcd_datatypes.MASTER_PROJECT_NAME


def test_project_filter_for_editor(db):
    """Check if project editor gets back this project"""
    # create irrelevant project that should not appear after applying a filter
    project = create_test_project(db, "test_project_filter_owner_2",
                                           "test_project_filter_for_editor_irrelevant_project", "")
    assert project

    # create project that should appear in the result
    project = create_test_project(db, "test_project_filter_owner_2", "test_project_filter_for_editor", "")
    assert project
    ok, err = mcd_model.update_project_details(db, "test_project_filter_owner_2", project["_id"],
                                               {'editors': [
                                                   # NOTE: we use multiple editors in this field to check if mongo
                                                   # array filtering works as expected
                                                   "test_project_filter_editor",
                                                   "test_project_filter_editor_2"
                                               ]}, NoOpNotifier())
    assert err == ""
    assert ok
    # get projects for the user that was chosen as editor
    projects = mcd_model.get_all_projects(db, 'test_project_filter_editor')
    assert len(projects) == 2
    assert projects[0]['name'] == 'test_project_filter_for_editor'
    assert projects[1]['name'] == mcd_datatypes.MASTER_PROJECT_NAME


def test_project_filter_for_approver(db):
    # create irrelevant project that should not appear after applying a filter
    project = create_test_project(db, "test_project_filter_owner_3",
                                           "test_project_filter_for_approver_irrelevant_project", "")
    assert project
    # create project that should appear in result
    project = create_test_project(db, "test_project_filter_owner_3", "test_project_filter_for_approver", "")
    assert project
    result = db['projects'].update_one({'_id': ObjectId(project["_id"])}, {"$set": {
        'editors': [],
        # NOTE: we use multiple approvers in this field to check if mongo array filtering works as expected
        'approvers': [
            'test_project_filter_approver_2',
            'test_project_filter_approver',
        ]
    }})
    assert result.modified_count == 1

    projects = mcd_model.get_all_projects(db, 'test_project_filter_approver')
    assert len(projects) == 2
    assert projects[0]['name'] == 'test_project_filter_for_approver'
    assert projects[1]['name'] == mcd_datatypes.MASTER_PROJECT_NAME


def test_project_filter_for_user_with_no_projects(db):
    project = create_test_project(db, "test_project_filter_owner_4",
                                           "test_project_filter_for_user_with_no_projects", "")
    assert project
    # user with no projects should find only a master project
    projects = mcd_model.get_all_projects(db, 'test_project_filter_user_with_no_projects')
    assert len(projects) == 1
    assert projects[0]['name'] == mcd_datatypes.MASTER_PROJECT_NAME


def test_project_filter_for_admins(db):
    # admins should see every project
    project = create_test_project(db, "test_project_filter_owner", "test_project_filter_for_admins", "")

    projects = mcd_model.get_all_projects(db, 'admin_user')
    assert len(projects) >= 2, "there should be at least master project and 'test_project_filter_for_admins' in the db"
    assert projects[len(projects)-1]['name'] == mcd_datatypes.MASTER_PROJECT_NAME

    project_names = [project['name'] for project in projects]
    assert "test_project_filter_for_admins" in project_names, "created file was not found"


def test_add_fft_to_project(db):
    # TODO: check what happens if non editor is trying to update fft: we should return an error
    project = create_test_project(db, "test_user", "test_add_fft_to_project", "")

    # get ffts for project, there should be none
    project_ffts = mcd_model.get_project_ffts(db, project["_id"])
    assert len(project_ffts) == 0, "there should be no ffts in a new project"

    # add fft change
    fft_id = str(mcd_model.get_fft_id_by_names(db, "TESTFC", "TESTFG"))
    assert fft_id, "fft_id should exist"
    fft_update = {'_id': fft_id, 'comments': 'some comment', 'nom_ang_x': 1.23}
    ok, err, update_status = mcd_model.update_fft_in_project(db, "test_user", project["_id"], fft_update)
    assert err == "", "there should be no error"
    assert ok, "fft should be inserted"

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

def test_add_unchanged_fft_to_project(db):
    """Update the fft values with the existing values - there should be no change"""
    project = create_test_project(db, "test_user", "test_add_unchanged_fft_to_project", "")

    fft_id = str(mcd_model.get_fft_id_by_names(db, "TESTFC", "TESTFG"))
    fft_update = {'_id': fft_id, 'nom_ang_x': 1.23, 'nom_ang_y': 2.54}
    ok, err, update_status = mcd_model.update_fft_in_project(db, "test_user", project["_id"], fft_update)
    assert err == ""
    assert ok
    assert update_status.success == 1

    ok, err, update_status = mcd_model.update_fft_in_project(db, "test_user", project["_id"], fft_update)
    assert update_status.ignored == 1
    assert ok
    assert err == ""


def test_invalid_fft_due_to_missing_attributes(db):
    """If state is not development, certain attributes are expected. An error should be returned if we don't provide them"""
    project = create_test_project(db, "test_user", "test_invalid_fft_due_to_missing_attributes", "")

    fft_id = str(mcd_model.get_fft_id_by_names(db, "TESTFC", "TESTFG"))
    fft_update = {'_id': fft_id, 'state': 'Installed', 'nom_ang_x': 123}
    ok, err, update_status = mcd_model.update_fft_in_project(db, "test_user", project["_id"], fft_update)
    assert err == "FFTs should remain in the Conceptual state while the dimensions are still being determined."


def test_invalid_fft_due_to_invalid_value(db):
    """If an fft value is outside its required range, an error should be returned"""
    project = create_test_project(db, "test_user", "test_invalid_fft_due_to_invalid_value", "")

    fft_id = str(mcd_model.get_fft_id_by_names(db, "TESTFC", "TESTFG"))
    fft_update = {'_id': fft_id, 'nom_ang_x': 123}
    ok, err, update_status = mcd_model.update_fft_in_project(db, "test_user", project["_id"], fft_update)
    assert err == "invalid range for nom_ang_x: expected range [-3.14, 3.14], but got 123.0"
    assert update_status.fail == 1


def test_invalid_fft_due_to_invalid_type(db):
    project = create_test_project(db, "test_user", "test_invalid_fft_due_to_invalid_type", "")

    fft_id = str(mcd_model.get_fft_id_by_names(db, "TESTFC", "TESTFG"))
    fft_update = {'_id': fft_id, 'nom_ang_x': 'this is a string'}
    ok, err, update_status = mcd_model.update_fft_in_project(db, "test_user", project["_id"], fft_update)
    assert err == "Wrong type - nom_ang_x, ('this is a string')"
    assert update_status.fail == 1


def test_remove_fft_from_project(db):
    project = create_test_project(db, "test_user", "test_remove_fft_from_project", "")
    prjid = str(project["_id"])

    # insert new fft
    fft_id = str(mcd_model.get_fft_id_by_names(db, "TESTFC", "TESTFG"))
    fft_update = {'_id': fft_id, 'nom_ang_y': 1.23}
    ok, err, update_status = mcd_model.update_fft_in_project(db, "test_user", prjid, fft_update)
    assert err == ""
    assert ok

    inserted_ffts = mcd_model.get_project_ffts(db, prjid)
    assert len(inserted_ffts) == 1
    inserted_fft = inserted_ffts[fft_id]
    assert str(inserted_fft["fft"]["_id"]) == fft_update["_id"]

    # remove inserted fft
    ok, err = mcd_model.remove_ffts_from_project(db, "test_user", prjid, [fft_id])
    assert err == ""
    assert ok

    project_ffts = mcd_model.get_project_ffts(db, prjid)
    assert len(project_ffts) == 0, "there should be no ffts after deletion"


def test_get_project_ffts(db):
    project = create_test_project(db, "test_user", "test_get_project_ffts", "")
    prjid = str(project["_id"])

    # insert new fft
    fft_id = str(mcd_model.get_fft_id_by_names(db, "TESTFC", "TESTFG"))
    fft_update = {'_id': fft_id, 'nom_ang_y': 1.23, 'nom_ang_x': 2.31}
    ok, err, update_status = mcd_model.update_fft_in_project(db, "test_user", prjid, fft_update)
    assert err == ""
    assert ok

    inserted_ffts = mcd_model.get_project_ffts(db, prjid)
    assert len(inserted_ffts) == 1

    fft = inserted_ffts[fft_id]
    assert fft['nom_ang_y'] == 1.23
    assert fft['nom_ang_x'] == 2.31
    assert fft.get('nom_ang_z', None) is None

    # check what is stored in the database, we should find only the values that we have stored
    changes = list(db['projects_history'].find({'fft': ObjectId(fft_id), 'prj': ObjectId(prjid)}))
    for change in changes:
        assert change['user'] == "test_user", f"expected something else for change: {change}"
        assert str(change['prj']) == prjid, f"wrong project id; change: {change}"
    assert len(changes) == 2, "we made only 2 value changes, so only 2 value changes should be present in db"


def test_get_project_ffts_after_timestamp(db):
    """Only fetch the ffts inserted after a certain timestamp"""
    project = create_test_project(db, "test_user", "test_get_project_ffts_after_timestamp", "")
    prjid = str(project["_id"])

    # insert new fft
    timestamp = datetime.datetime.now(tz=pytz.UTC) - datetime.timedelta(seconds=1)
    fft_id = str(mcd_model.get_fft_id_by_names(db, "TESTFC", "TESTFG"))
    fft_update = {'_id': fft_id, 'nom_ang_y': 1.23}
    ok, err, update_status = mcd_model.update_fft_in_project(db, "test_user", prjid, fft_update)
    assert err == ""
    assert ok

    ffts = mcd_model.get_project_ffts(db, prjid, asoftimestamp=timestamp)
    assert len(ffts) == 0, "there should be no fft before insertion"

    timestamp = datetime.datetime.now(tz=pytz.UTC)
    ffts = mcd_model.get_project_ffts(db, prjid, asoftimestamp=timestamp)
    assert len(ffts) == 1, "there should be 1 fft insert"

    fft = ffts[fft_id]
    assert fft['nom_ang_y'] == 1.23
    assert fft.get('nom_ang_x', None) is None


def test_create_delete_comment(db):
    """Create and delete a fft comment as the project owner"""
    project = create_test_project(db, "test_user", "test_create_delete_comment", "")

    # NOTE: a comment will never be returned, if there is not at least 1 fft field present therefore we
    # have to insert 1 field first before verifying a comment insert
    #
    # insert and verify a comment insertion
    fft_id = str(mcd_model.get_fft_id_by_names(db, "TESTFC", "TESTFG"))
    fft_update = {'_id': fft_id, 'nom_ang_y': 1.23}
    _, err, counter = mcd_model.update_fft_in_project(db, "test_user", project["_id"], fft_update)
    assert err == ""
    assert counter.success == 1

    ok, err, counter = mcd_model.add_fft_comment(db, "test_user", project["_id"], fft_id, "my comment")
    assert err == ""
    assert counter.success == 1

    ffts = mcd_model.get_project_ffts(db, project["_id"])
    assert len(ffts) == 1
    fft = ffts[fft_id]
    assert len(fft["discussion"]) == 1
    comment = fft["discussion"][0]
    assert comment["comment"] == "my comment"
    assert comment["author"] == "test_user"

    # delete a comment
    ok, err = mcd_model.delete_fft_comment(db, "test_user", comment["id"])
    assert err == ""
    assert ok

    # verify that comment was deleted
    ffts = mcd_model.get_project_ffts(db, project["_id"])
    assert len(ffts) == 1
    fft = ffts[fft_id]
    assert len(fft['discussion']) == 0, "fft comment should be deleted"


def test_project_approval_workflow(db):
    # testing happy path
    project = create_test_project(db, "test_user", "test_approval_workflow", "")
    prjid = project["_id"]

    email_sender = _TestEmailSender()
    notifier = Notifier('', email_sender, 'admin@example.com')
    ok, err = mcd_model.update_project_details(db, "test_user", prjid, {'editors': ['editor_user', 'editor_user_2']}, notifier)
    assert err == ""
    assert ok

    # check if notifications were sent (editor should receive an email when assigned)
    assert len(email_sender.emails_sent) == 1, "Editor should receive a notification that they were appointed"
    editor_mail = email_sender.emails_sent[0]
    assert editor_mail['to'] == ['editor_user', 'editor_user_2']
    assert editor_mail['subject'] == '(MCD) You were selected as an editor for the project test_approval_workflow'
    email_sender.clear()

    # an editor user should be able to save an fft
    fftid = str(mcd_model.get_fft_id_by_names(db, "TESTFC", "TESTFG"))
    ok, err, update_status = mcd_model.update_fft_in_project(db, "editor_user", prjid,
                                                             {"_id": fftid, "tc_part_no": "PART 123"})
    assert err == ""
    assert ok
    assert update_status.success == 1

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
    assert len(email_sender.emails_sent) == 3, "wrong number of notification emails sent"
    # this project was submitted for the first time, therefore an initial message should be sent to editors
    editor_email = email_sender.emails_sent[0]
    assert editor_email['to'] == ["editor_user", "editor_user_2", "test_user"]
    assert editor_email['subject'] == "(MCD) Project test_approval_workflow was submitted for approval"

    # verify the super approver and regular notifications sent properly
    super_approver_email = email_sender.emails_sent[1]
    assert super_approver_email['to'] == ['super_approver']
    assert super_approver_email['subject'] == "(MCD) You were added as a Super Approver for the project test_approval_workflow"

    approver_email = email_sender.emails_sent[2]
    assert approver_email['to'] == ['approve_user']
    assert approver_email['subject'] == "(MCD) You were selected as an approver for the project test_approval_workflow"

    email_sender.clear()

    project = mcd_model.get_project(db, prjid)
    assert project['approvers'] == ["approve_user", "super_approver"]
    assert project.get('approved_by', []) == []

    ok, all_approved, err, prj = mcd_model.approve_project(db, prjid, "super_approver", notifier)
    assert err == ""
    assert ok
    assert all_approved == False
    assert prj['approved_by'] == ['super_approver']
    assert len(email_sender.emails_sent) == 0, "there should be no notifications"
    assert prj['status'] == 'submitted'

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
    assert email['to'] == ['approve_user', 'editor_user', 'editor_user_2', 'super_approver', 'test_user']
    assert email['subject'] == '(MCD) Project test_approval_workflow was approved'
    email_sender.clear()


def test_project_rejection(db):
    project = create_test_project(db, "test_user", "test_project_rejection_workflow", "")
    prjid = project["_id"]

    email_sender = _TestEmailSender()
    notifier = Notifier('', email_sender, 'admin@example.com')
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
    assert prj['approvers'] == ['approve_user', 'approve_user_2', 'super_approver']

    # validate that notifications were send
    assert len(email_sender.emails_sent) == 1
    email = email_sender.emails_sent[0]
    assert email['to'] == ['approve_user', 'approve_user_2', 'editor_user', 'editor_user_2', 'super_approver', 'test_user']
    assert email['subject'] == '(MCD) Project test_project_rejection_workflow was rejected'
    assert 'This is my rejection message' in email['content']


def test_update_ffts_invalid(db):
    project = create_test_project(db, "test_user", "test_update_ffts_invalid", "")

    ok, err, fft = mcd_model.find_or_create_fft(db, "TESTFC", "TESTFG")
    assert err == ""
    assert fft["_id"]

    ffts = [{"_id": fft["_id"], 'state': mcd_datatypes.FCState.Installed.value, "nom_loc_z": 2001, 'nom_ang_x': 1.23}]
    ok, err, updates = mcd_model.update_ffts_in_project(db, "test_user", project["_id"], ffts)
    assert updates.fail == 1
    assert err == 'Missing required header nom_loc_x'
    assert ok is True  # update_ffts method always return a True, even if some fields are missing


def test_update_ffts_invalid_empty_value(db):
    project = create_test_project(db, "test_user", "test_update_ffts_invalid_empty_value", "")

    ok, err, fft = mcd_model.find_or_create_fft(db, "TESTFC", "TESTFG")
    assert err == ""
    ffts = [{"_id": fft["_id"], 'state': mcd_datatypes.FCState.Installed.value, "nom_loc_z": ""}]
    ok, err, updates = mcd_model.update_ffts_in_project(db, "test_user", project["_id"], ffts)
    assert updates.fail == 1
    assert err == "'nom_loc_z' value is required for a Non-Conceptual device"

def test_update_ffts_wrong_type(db):
    project = create_test_project(db, "test_user", "test_update_wrong_type", "")

    ok, err, fft = mcd_model.find_or_create_fft(db, "TESTFC", "TESTFG")
    assert err == ""
    ffts = [{"_id": fft["_id"], 'state': mcd_datatypes.FCState.Installed.value, "nom_loc_z": "aaa"}]
    ok, err, updates = mcd_model.update_ffts_in_project(db, "test_user", project["_id"], ffts)
    assert updates.fail == 1
    assert err == "Invalid data type for 'nom_loc_z': 'aaa'"


def create_string_logger(stream: io.StringIO) -> logging.Logger:
    logger = logging.getLogger('str_logger')
    logger.setLevel(logging.DEBUG)
    for handler in logger.handlers[:]:
        # remove previous handlers, to avoid getting writing to a closed stream error during tests
        logger.removeHandler(handler)
    stream_handler = logging.StreamHandler(stream)
    stream_handler.setLevel(logging.DEBUG)
    logger.addHandler(stream_handler)
    return logger


def test_import_csv_into_a_project(db):
    project = create_test_project(db, "test_user", "test_import_csv_into_a_project", "")
    prjid = project["_id"]

    ffts = mcd_model.get_project_ffts(db, prjid)
    assert len(ffts) == 0, "There should be no project ffts for a freshly created project"

    # import via csv endpoint
    import_csv = """
Machine Config Database,,,

FC,Fungible,TC_part_no,Stand,State,Comments,LCLS_Z_loc,LCLS_X_loc,LCLS_Y_loc,LCLS_Z_roll,LCLS_X_pitch,LCLS_Y_yaw,Must_Ray_Trace
AT1L0,COMBO,12324,SOME_TEST_STAND,Conceptual,TEST,1.21,0.21,2.213,1.231,,,
AT2L0,GAS,3213221,,Conceptual,GAS ATTENUATOR,,,,1.23,-1.25,-0.895304,1
"""

    with io.StringIO() as stream:
        log_reporter = create_string_logger(stream)
        ok, err, counter = mcd_import.import_project(db, "test_user", prjid, import_csv, log_reporter)
        assert err == ""
        assert ok

        assert counter.success == 2
        assert counter.fail == 0
        assert counter.ignored == 0
        headers = "FC,Fungible,TC_part_no,Stand,State,Comments,LCLS_Z_loc,LCLS_X_loc,LCLS_Y_loc,LCLS_Z_roll,LCLS_X_pitch,LCLS_Y_yaw,Must_Ray_Trace"
        assert counter.headers == len(headers.split(",")), "wrong number of csv fields"

        log = stream.getvalue()
        # validate export log?

        # check if fields were actually inserted in the db
        ffts = mcd_model.get_project_ffts(db, prjid)
        assert len(ffts) == 2, "There should be 2 ffts inserted into a project"

        expected_ffts = {
            'COMBO': {'fc': 'AT1L0', 'fg':'', 'fg_desc': 'COMBO', 'tc_part_no': '12324', 'stand': 'SOME_TEST_STAND',
                      'state': 'Conceptual', 'comments': 'TEST',
                      'nom_loc_z': 1.21, 'nom_loc_x': 0.21, 'nom_loc_y': 2.213, 'nom_ang_z': 1.231},
            'GAS': {'fc': 'AT2L0', 'fg': '', 'fg_desc': 'GAS', 'tc_part_no': '3213221',
                    'state': 'Conceptual', 'comments': 'GAS ATTENUATOR',
                    'nom_ang_z': 1.23, 'nom_ang_x': -1.25, 'nom_ang_y': -0.895304, 'ray_trace': 1},
        }

        # convert received ffts into a format that we can compare
        got_ffts = {}
        for _, f in ffts.items():
            fc = f['fft']['fc']
            fg = f['fft']['fg']
            f['fc'] = fc
            f['fg'] = fg
            got_ffts[fc] = f

        # assert fft values
        for expected in expected_ffts.values():
            fc = expected['fc']
            assert fc in got_ffts, f"{expected['fc']} fc was not found in ffts: fft was not inserted correctly"
            got = got_ffts[fc]

            for field in mcd_datatypes.KEYMAP.values():
                # empty fields are by default set to '' (not None) even if they are numeric fields. Is this okay?
                assert got.get(field, '') == expected.get(field, ''), f"{fc}: invalid field value '{field}'"

        assert len(got_ffts) == len(expected_ffts), "wrong number of fft fetched from db"


def test_export_csv_from_a_project(db):
    project = create_test_project(db, "test_user", "test_export_from_a_project", "")
    prjid = project["_id"]

    ffts = mcd_model.get_project_ffts(db, prjid)
    assert len(ffts) == 0, "There should be no project ffts for a freshly created project"

    # import via csv endpoint (import should be possible in any order of columns)
    import_csv = """
FC,Fungible,TC_part_no,Stand,Area,Beamline,State,Comments,LCLS_Z_loc,LCLS_X_loc,LCLS_Y_loc,LCLS_Z_roll,LCLS_X_pitch,LCLS_Y_yaw,Must_Ray_Trace
AT1L0,COMBO,12324,SOME_TEST_STAND,,"RIX, TMO",Conceptual,TEST,1.21,0.21,2.213,1.231,,,
AT2L0,GAS,3213221,,,,Conceptual,GAS ATTENUATOR,,,,1.23,-1.25,-0.895304,1
"""

    with io.StringIO() as stream:
        log_reporter = create_string_logger(stream)
        ok, err, counter = mcd_import.import_project(db, "test_user", prjid, import_csv, log_reporter)
        assert err == ""
        assert ok
        assert counter.success == 2

    ok, err, csv = mcd_import.export_project(db, prjid)
    assert ok
    assert err == ""
    # by default the csv writer ends the lines with \r\n, so this assert would fail without our replace
    expected_export = """
FC,Fungible,TC_part_no,Stand,Area,Beamline,State,LCLS_Z_loc,LCLS_X_loc,LCLS_Y_loc,LCLS_Z_roll,LCLS_X_pitch,LCLS_Y_yaw,Must_Ray_Trace,Comments
AT1L0,COMBO,12324,SOME_TEST_STAND,,"RIX, TMO",Conceptual,1.21,0.21,2.213,1.231,,,,TEST
AT2L0,GAS,3213221,,,,Conceptual,,,,1.23,-1.25,-0.895304,1,GAS ATTENUATOR
"""

    csv = csv.replace("\r\n", "\n")
    assert expected_export.strip() == csv.strip(), "wrong csv output"
