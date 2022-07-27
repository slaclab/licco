'''
The model level business logic goes here.
Most of the code here gets a connection to the database, executes a query and formats the results.
'''

import json
import logging
import datetime
import collections
from enum import Enum

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import PyMongoError

from context import licco_db

from .projdetails import get_project_attributes, get_all_project_changes

__author__ = 'mshankar@slac.stanford.edu'

line_config_db_name = "lineconfigdb"
logger = logging.getLogger(__name__)

class FCState(Enum):
    Conceptual = "Conceptual"
    Planned = "Planned"
    ReadyForInstallation = "ReadyForInstallation"
    Installed = "Installed"
    Operational = "Operational"
    NonOperational = "NonOperational"
    Removed = "Removed"
    def describe(self):
        return descriptions[self]
    @classmethod
    def descriptions(cls):
        return {
            FCState.Conceptual: { "sortorder": 0, "label": "Conceptual", "description": "There are no firm plans to proceed with applying this configuration, it is still under heavy development. Configuration changes are frequent." },
            FCState.Planned: { "sortorder": 1, "label": "Planned", "description": "A planned configuration, installation planning is underway. Configuration changes are less frequent." },
            FCState.ReadyForInstallation: { "sortorder": 2, "label": "Ready for installation", "description": "Configuration is designated as ready for installation. Installation is imminent. Installation effort is planned and components may be fully assembled and bench-tested." },
            FCState.Installed: { "sortorder": 3, "label": "Installed", "description": "Component is physically installed but not fully operational" },
            FCState.Operational: { "sortorder": 4, "label": "Operational", "description": "Component is operational, commissioning and TTO is complete" },
            FCState.NonOperational: { "sortorder": 5, "label": "Non-operational", "description": "Component remains installed but is slated for removal" },
            FCState.Removed: { "sortorder": 6, "label": "Removed", "description": "Component is no longer a part of the configuration, record is maintained" },
        }

def initialize_collections():
    if 'name_1' not in licco_db[line_config_db_name]["projects"].index_information().keys():
        licco_db[line_config_db_name]["projects"].create_index([("name", ASCENDING)], unique=True, name="name_1")
    if 'owner_1' not in licco_db[line_config_db_name]["projects"].index_information().keys():
        licco_db[line_config_db_name]["projects"].create_index([("owner", ASCENDING)], name="owner_1")
    if 'editors_1' not in licco_db[line_config_db_name]["projects"].index_information().keys():
        licco_db[line_config_db_name]["projects"].create_index([("editors", ASCENDING)], name="editors_1")
    if 'name_1' not in licco_db[line_config_db_name]["fcs"].index_information().keys():
        licco_db[line_config_db_name]["fcs"].create_index([("name", ASCENDING)], unique=True, name="name_1")
    if 'prj_time_1' not in licco_db[line_config_db_name]["projects_history"].index_information().keys():
        licco_db[line_config_db_name]["projects_history"].create_index([("prj", ASCENDING), ("time", DESCENDING)], name="prj_time_1")
    if 'prj_fc_time_1' not in licco_db[line_config_db_name]["projects_history"].index_information().keys():
        licco_db[line_config_db_name]["projects_history"].create_index([("prj", ASCENDING), ("fc", ASCENDING), ("time", DESCENDING)], name="prj_fc_time_1")
    if 'sw_time_1' not in licco_db[line_config_db_name]["switch"].index_information().keys():
        licco_db[line_config_db_name]["switch"].create_index([("switch_time", DESCENDING)], unique=True, name="sw_time_1")
    if 'name_prj_1' not in licco_db[line_config_db_name]["tags"].index_information().keys():
        licco_db[line_config_db_name]["tags"].create_index([("name", ASCENDING), ("prj", ASCENDING)], unique=True, name="name_prj_1")

def get_projects_for_user(username):
    """
    Return all the projects for which the user is an owner or an editor.
    :param username - the userid of the user from authn
    :return: List of projects
    """
    owned_projects = list(licco_db[line_config_db_name]["projects"].find({ "owner": username }))
    editable_projects = list(licco_db[line_config_db_name]["projects"].find({ "editors": username }))
    return owned_projects + editable_projects

def get_project(id):
    """
    Get the details for the project given its id.
    """
    oid = ObjectId(id)
    prj = licco_db[line_config_db_name]["projects"].find_one({"_id": oid})
    return prj

def get_project_fcs(id, showallentries=True, asoftimestamp=None):
    """
    Get the functional components for a project given its id.
    """
    oid = ObjectId(id)
    logger.info("Looking for project details for %s", oid)
    return get_project_attributes(licco_db[line_config_db_name], id, skipClonedEntries=False if showallentries else True, asoftimestamp=asoftimestamp)

def get_project_changes(id):
    """
    Get a history of changes to the project.
    """
    oid = ObjectId(id)
    logger.info("Looking for project details for %s", id)
    return get_all_project_changes(licco_db[line_config_db_name], oid)

def get_fcs():
    """
    Get the functional component objects - typically just the name and description.
    """
    fcs = list(licco_db[line_config_db_name]["fcs"].find({}))
    return fcs

def create_new_project(name, description, userid):
    """
    Create a new project belonging to the specified user.
    """
    newprjid = licco_db[line_config_db_name]["projects"].insert_one({"name": name, "description": description, "owner": userid, "editors": [], "status": "development", "creation_time": datetime.datetime.utcnow()}).inserted_id
    prj = licco_db[line_config_db_name]["projects"].find_one({"_id": newprjid})
    return prj

def create_new_functional_component(name, description):
    """
    Create a new functional component
    """
    if not name:
        return False, "The name is a required field", None
    if not description:
        return False, "The description is a required field", None
    if licco_db[line_config_db_name]["fcs"].find_one({"name": name}):
        return False, f"Functional component {name} already exists", None
    try:
        fcid = licco_db[line_config_db_name]["fcs"].insert_one({ "name": name, "description": description }).inserted_id
        return True, "", licco_db[line_config_db_name]["fcs"].find_one({"_id": fcid})
    except Exception as e:
        return False, str(e), None

# We could perhaps use dataclasses here but we're not really storing the document as it is.
# So, let's try explicit metadata for the fc attrs
fcattrs = {
    "x": {
        "type": "float",
        "fromstr": float,
        "label": "X",
        "desc": "The X component of the FC's location in the beamline",
        "required": True
    },
    "y": {
        "type": "float",
        "fromstr": float,
        "label": "Y",
        "desc": "The Y component of the FC's location in the beamline",
        "required": True
    },
    "z": {
        "type": "float",
        "fromstr": float,
        "label": "Z",
        "desc": "The Z component of the FC's location in the beamline",
        "required": True
    },
    "state": {
        "type": "enum",
        "fromstr": lambda x: FCState[x].value,
        "label": "FC state",
        "desc": "The current state of the functional component",
        "required": True,
        "default": "Conceptual"
    }
}

def update_functional_component_in_project(prjid, fcid, fcupdate, userid, modification_time=None):
    """
    Update the value(s) of a functional component in a project
    """
    prj = licco_db[line_config_db_name]["projects"].find_one({"_id": ObjectId(prjid)})
    if not prj:
        return False, f"Cannot find project for {prjid}", None
    fc = licco_db[line_config_db_name]["fcs"].find_one({"_id": ObjectId(fcid)})
    if not fc:
        return False, f"Cannot find functional component for {fcid}", None
    current_attrs = get_project_attributes(licco_db[line_config_db_name], ObjectId(prjid))

    logger.info(fcupdate)
    if not modification_time:
        modification_time = datetime.datetime.utcnow()

    for attrname, attrmeta in fcattrs.items():
        if "default" in attrmeta and attrname not in fcupdate and attrname not in current_attrs:
            fcupdate[attrname] = attrmeta["default"]
        if attrmeta["required"] and (attrname not in fcupdate and attrname not in current_attrs):
            return False, f"Parameter {attrname} is a required attribute", None
        if attrmeta["required"] and (attrname in fcupdate and not fcupdate[attrname]):
            return False, f"Parameter {attrname} is a required attribute and cannot be blank", None
        if attrname in fcupdate:
            cnvattrval = attrmeta["fromstr"](fcupdate[attrname])
            if attrname not in current_attrs or current_attrs[attrname] != cnvattrval:
                licco_db[line_config_db_name]["projects_history"].insert_one({
                  "prj": ObjectId(prjid),
                  "fc": ObjectId(fcid),
                  "key" : attrname,
                  "val" : cnvattrval,
                  "user" : userid,
                  "time" : modification_time
                })

    return True, "", get_project_attributes(licco_db[line_config_db_name], ObjectId(prjid))


def submit_project_for_approval(prjid, userid):
    """
    Submit a project for approval.
    Set the status to submitted
    """
    prj = licco_db[line_config_db_name]["projects"].find_one({"_id": ObjectId(prjid)})
    if not prj:
        return False, f"Cannot find project for {prjid}", None
    if prj["status"] != "development":
        return False, f"Project {prjid} is not in development status", None
    licco_db[line_config_db_name]["projects"].update_one({"_id": prj["_id"]}, {"$set": {"status": "submitted", "submitter": userid }})
    return True, "", prj

def approve_project(prjid, userid):
    """
    Approve a submitted project.
    Set the status to approved
    """
    prj = licco_db[line_config_db_name]["projects"].find_one({"_id": ObjectId(prjid)})
    if not prj:
        return False, f"Cannot find project for {prjid}", None
    if prj["status"] != "submitted":
        return False, f"Project {prjid} is not in submitted status", None
    licco_db[line_config_db_name]["switch"].insert_one({
        "prj": prj["_id"],
        "switch_time" : datetime.datetime.utcnow(),
        "requestor_uid" : userid
        })
    licco_db[line_config_db_name]["projects"].update_many({"status": "approved"}, {"$set": {"status": "development" }})
    licco_db[line_config_db_name]["projects"].update_one({"_id": prj["_id"]}, {"$set": {"status": "approved", "approver": userid }})
    return True, "", prj

def get_currently_approved_project():
    """
    Get the current approved project.
    This is really the most recently approved project
    """
    prjs = list(licco_db[line_config_db_name]["switch"].find({}).sort([("switch_time", -1)]).limit(1))
    if prjs:
        current_id = prjs[0]["prj"]
        return licco_db[line_config_db_name]["projects"].find_one({"_id": current_id})
    return None

def __flatten__(obj, prefix=""):
    """
    Flatten a dict into a list of key value pairs using dot notation.
    """
    print(obj)
    print(prefix)
    ret = []
    if isinstance(obj, collections.abc.Mapping):
        for k,v in obj.items():
            ret.extend(__flatten__(v, prefix + "." + k if prefix else k))
    elif type(obj) == list:
        for c,e in enumerate(obj):
            ret.extend(__flatten__(e, prefix + ".[" + str(c) + "]" if prefix else "[" + str(c) + "]"))
    else:
        ret.append((prefix, obj))
    return ret

def __replace_fc__(fcs):
    """
    Replace the object id for the FC with the FC's name for readibility
    """
    ret = {}
    for k,v in fcs.items():
        if isinstance(v, collections.abc.Mapping):
            ret[v["name"]] = v
        else:
            ret[k] = v
    return ret


def diff_project(prjid, other_prjid, userid):
    """
    Diff two projects
    """
    prj = licco_db[line_config_db_name]["projects"].find_one({"_id": ObjectId(prjid)})
    if not prj:
        return False, f"Cannot find project for {prjid}", None

    otr = licco_db[line_config_db_name]["projects"].find_one({"_id": ObjectId(other_prjid)})
    if not otr:
        return False, f"Cannot find project for {other_prjid}", None

    myfcs = __replace_fc__(get_project_attributes(licco_db[line_config_db_name], prjid))
    thfcs = __replace_fc__(get_project_attributes(licco_db[line_config_db_name], other_prjid))

    myflat = __flatten__(myfcs)
    thflat = __flatten__(thfcs)

    mydict = { x[0]: x[1] for x in myflat }
    thdict = { x[0]: x[1] for x in thflat }
    mykeys = set(mydict.keys())
    thkeys = set(thdict.keys())
    keys_u = mykeys.union(thkeys)
    keys_i = mykeys.intersection(thkeys)
    keys_l = mykeys - thkeys
    keys_r = thkeys - mykeys

    diff = []
    for k in keys_u:
        if k in keys_i and mydict[k] == thdict[k]:
            diff.append({"diff": False, "key": k, "my": mydict[k], "ot": thdict[k]})
        else:
            diff.append({"diff": True, "key": k, "my": mydict.get(k, None), "ot": thdict.get(k, None)})

    return True, "", sorted(diff, key=lambda x: x["key"])


def clone_project(prjid, name, description, userid):
    """
    Clone the existing project specified by prjid as a new project with the name and description.
    """
    prj = licco_db[line_config_db_name]["projects"].find_one({"_id": ObjectId(prjid)})
    if not prj:
        return False, f"Cannot find project for {prjid}", None

    otr = licco_db[line_config_db_name]["projects"].find_one({"name": name})
    if otr:
        return False, f"Project with {name} already exists", None

    newprj = create_new_project(name, description, userid)
    if not newprj:
        return False, f"Created a project but could not get the object from the database", None
    myfcs = get_project_attributes(licco_db[line_config_db_name], prjid)
    for fcid, attrs in myfcs.items():
        del attrs["name"]
        status, errormsg, _ = update_functional_component_in_project(newprj["_id"], fcid, attrs, userid, modification_time=newprj["creation_time"])
        if not status:
            return status, "Partially cloned project: " + errormsg, None

    return True, "", newprj

def get_tags_for_project(prjid):
    """
    Get the tags for the specified project
    """
    prj = licco_db[line_config_db_name]["projects"].find_one({"_id": ObjectId(prjid)})
    if not prj:
        return False, f"Cannot find project for {prjid}", None
    tags = list(licco_db[line_config_db_name]["tags"].find({"prj": ObjectId(prjid)}))
    return True, "", tags

def add_project_tag(prjid, tagname, changeid):
    """
    Add a tag at the specified time for the project.
    The time is determined from the change ( as specified by the change_id)
    """
    prj = licco_db[line_config_db_name]["projects"].find_one({"_id": ObjectId(prjid)})
    if not prj:
        return False, f"Cannot find project for {prjid}", None

    extsting_tag = licco_db[line_config_db_name]["tags"].find_one({"name": tagname})
    if extsting_tag:
        return False, f"Tag {tagname} already exists for project {prjid}", None

    change = licco_db[line_config_db_name]["projects_history"].find_one({"prj": ObjectId(prjid), "_id": ObjectId(changeid)})
    if not change:
        return False, f"Cannot find change {changeid} for project {prjid} ", None

    licco_db[line_config_db_name]["tags"].insert_one({"prj": ObjectId(prjid), "name": tagname, "time": change["time"]})
    tags = list(licco_db[line_config_db_name]["tags"].find({"prj": ObjectId(prjid)}))
    return True, "", tags
