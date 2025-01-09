import pytest

import context
import start
from dal.mcd_model import initialize_collections
from dal.utils import diff_arrays

_TEST_DB_NAME = "_licco_test_db_"

@pytest.fixture()
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
    return db

@pytest.fixture(scope="session", autouse=True)
def destroy_db():
    """Destroy db and its data at the end of the testing session"""
    yield
    client = context.mongo_client
    client.drop_database(_TEST_DB_NAME)
    client.close()

def test_something(db):
    print("APP:", start.app)
    print("notifier", start.context.notifier)
    out = db['roles'].find()
    print("OUT 1:", out.to_list())
    db['roles'].insert_one({'App': "Test", 'name': 'Test role', 'players': ['test_user'], 'privileges': ['create']})

    out = db['roles'].find()
    print("OUT 2:", out.to_list())
    print("PROJECTS:", db['projects'].find().to_list())


def test_arr_diff():
    old = ['a', 'b']
    new = ['b', 'c']
    diff = diff_arrays(old, new)

    assert diff.removed == ['a']
    assert diff.new == ['c']
    assert diff.in_both == ['b']
