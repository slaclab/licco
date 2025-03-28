"""
The model level business logic goes here.
Most of the code here gets a connection to the database, executes a query and formats the results.
"""
import logging
import datetime
import types
from collections.abc import Mapping
from enum import Enum
import copy
import json
import math
from typing import Dict, Tuple, List, Optional, TypeAlias
import pytz
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING
from pymongo.synchronous.database import Database

from notifications.notifier import Notifier, NoOpNotifier
from .projdetails import get_project_attributes, get_all_project_changes
from .utils import ImportCounter, empty_string_or_none, diff_arrays

logger = logging.getLogger(__name__)

MASTER_PROJECT_NAME = 'LCLS Machine Configuration Database'

MongoDb: TypeAlias = Database[Dict[str, any]]
McdProject: TypeAlias = Dict[str, any]

KEYMAP = {
    # Column names defined in confluence
    "FC": "fc",
    "FG": "fg",
    "Fungible": "fg_desc",
    "TC_part_no": "tc_part_no",
    "Stand": "stand",
    "State": "state",
    "LCLS_Z_loc": "nom_loc_z",
    "LCLS_X_loc": "nom_loc_x",
    "LCLS_Y_loc": "nom_loc_y",
    "LCLS_Z_roll": "nom_ang_z",
    "LCLS_X_pitch": "nom_ang_x",
    "LCLS_Y_yaw": "nom_ang_y",
    "Must_Ray_Trace": "ray_trace",
    "Comments": "comments"
}
KEYMAP_REVERSE = {value: key for key, value in KEYMAP.items()}


class FCState(Enum):
    Conceptual = "Conceptual"
    Planned = "Planned"
    Commissioned = "Commissioned"
    ReadyForInstallation = "ReadyForInstallation"
    Installed = "Installed"
    Operational = "Operational"
    NonOperational = "NonOperational"
    Decommissioned = "Decommissioned"
    Removed = "Removed"

    def describe(self):
        d = self.descriptions()
        return d[self]

    @classmethod
    def descriptions(cls):
        return {
            FCState.Conceptual: {"sortorder": 0, "label": "Conceptual", "description": "There are no firm plans to proceed with applying this configuration, it is still under heavy development. Configuration changes are frequent."},
            FCState.Planned: {"sortorder": 1, "label": "Planned", "description": "A planned configuration, installation planning is underway. Configuration changes are less frequent."},
            FCState.ReadyForInstallation: {"sortorder": 2, "label": "Ready for installation", "description": "Configuration is designated as ready for installation. Installation is imminent. Installation effort is planned and components may be fully assembled and bench-tested."},
            FCState.Installed: {"sortorder": 3, "label": "Installed", "description": "Component is physically installed but not fully operational"},
            FCState.Commissioned: {"sortorder": 4, "label": "Commissioned", "description": "Component is commissioned."},
            FCState.Operational: {"sortorder": 5, "label": "Operational", "description": "Component is operational, commissioning and TTO is complete"},
            FCState.NonOperational: {"sortorder": 6, "label": "Non-operational", "description": "Component remains installed but is slated for removal"},
            FCState.Decommissioned: {"sortorder": 7, "label": "De-commissioned", "description": "Component is de-commissioned."},
            FCState.Removed: {"sortorder": 8, "label": "Removed", "description": "Component is no longer a part of the configuration, record is maintained"},
        }



def initialize_collections(licco_db: MongoDb):
    if 'name_1' not in licco_db["projects"].index_information().keys():
        licco_db["projects"].create_index([("name", ASCENDING)], unique=True, name="name_1")
    # when listing all projects, we need to list projects for which the user is owner or editor (hence the index for both)
    if 'owner_1' not in licco_db["projects"].index_information().keys():
        licco_db["projects"].create_index([("owner", ASCENDING)], name="owner_1")
    if 'editors_1' not in licco_db["projects"].index_information().keys():
        licco_db["projects"].create_index([("editors", ASCENDING)], name="editors_1")

    if 'project_history_id_1' not in licco_db["project_history"].index_information().keys():
        licco_db["project_history"].create_index([("project_id", ASCENDING), ("snapshot_timestamp", DESCENDING)], name="project_history_id_1")

    if 'sw_time_1' not in licco_db["switch"].index_information().keys():
        licco_db["switch"].create_index([("switch_time", DESCENDING)], unique=True, name="sw_time_1")

    if 'name_prj_1' not in licco_db["tags"].index_information().keys():
        licco_db["tags"].create_index([("name", ASCENDING), ("prj", ASCENDING)], unique=True, name="name_prj_1")

    if 'app_1_name_1' not in licco_db["roles"].index_information().keys():
        licco_db["roles"].create_index([("app", ASCENDING), ("name", ASCENDING)], unique=True, name="app_1_name_1")

    # add a master project if it doesn't exist already
    master_project = licco_db["projects"].find_one({"name": MASTER_PROJECT_NAME})
    if not master_project:
        err, prj = create_new_project(licco_db, '', MASTER_PROJECT_NAME, "Master Project", [], NoOpNotifier())
        if err:
            logger.error(f"Failed to create a new master project: {err}")
        else:
            # initial status is set to approved
            licco_db["projects"].update_one({"_id": prj["_id"]}, {"$set": {"status": "approved"}})


def is_user_allowed_to_edit_project(db: MongoDb, userid: str, project: Dict[str, any]) -> bool:
    if userid == '' or None:
        return False

    allowed_to_edit = False
    allowed_to_edit |= userid == project.get('owner', None)
    allowed_to_edit |= userid in project.get('editors', [])
    if not allowed_to_edit:
        allowed_to_edit |= userid in get_users_with_privilege(db, "admin")
    return allowed_to_edit


def get_all_users(licco_db: MongoDb):
    """
    For now, simply return all the owners and editors of projects.
    """
    prjs = list(licco_db["projects"].find({}, {"owner": 1, "editors": 1}))
    ret = set()
    for prj in prjs:
        ret.add(prj["owner"])
        for ed in prj.get("editors", []):
            ret.add(ed)
    return list(ret)


def get_fft_id_by_names(licco_db: MongoDb, fc, fg):
    """
    Return ID of FFT
    based off of a provided string FC and FG names. 
    :param: fft - dict of {fc, fg} with string names of fc, fg
    :return: Tuple of ids FC, FG
    """
    fc_obj = licco_db["fcs"].find_one({"name": fc})
    fg_obj = licco_db["fgs"].find_one({"name": fg})
    fft = licco_db["ffts"].find_one({"fc": ObjectId(fc_obj["_id"]), "fg": ObjectId(fg_obj["_id"])})
    return fft["_id"]

def get_users_with_privilege(licco_db: MongoDb, privilege):
    """
    From the roles database, get all the users with the necessary privilege. 
    For now we do not take into account group memberships. 
    We return a unique list of userid's, for example, [ "awallace", "klafortu", "mlng" ]
    """
    ret = set()
    # Super approvers and admins are a separate entry
    if privilege == "superapprover" or privilege == "admin":
        lookup = {"name": privilege} 
    else:
        lookup = {"privileges": privilege} 
    # looking for editors, owners, approvers, etc
    for role in licco_db["roles"].find(lookup):
        for player in role.get("players", []):
            if player.startswith("uid:"):
                ret.add(player.replace("uid:", ""))
    return sorted(list(ret))


def get_fft_values_by_project(licco_db: MongoDb, fftid, prjid):
    """
    Return newest data connected with the provided Project and FFT
    :param fftid - the id of the FFT
    :param prjid - the id of the project
    :return: Dict of FFT Values
    """
    fft_pairings = {}
    results = list(licco_db["projects_history"].find({"prj": ObjectId(prjid), "fft": ObjectId(fftid)}).sort("time", 1))
    for res in results:
        fft_pairings[res["key"]] = res["val"]
    return fft_pairings


def get_all_projects(licco_db: MongoDb, logged_in_user, sort_criteria = None):
    """
    Return all the projects in the system.
    :return: List of projects
    """
    filter = {}
    admins = get_users_with_privilege(licco_db, "admin")
    is_admin_user = logged_in_user in admins
    if is_admin_user:
        # admin users should see all projects, hence we don't specify the filter
        pass
    else:
        # regular user should only see the projects that are applicable (they are owner, editor or approver)
        # and which are visible (not hidden/deleted)
        filter = {"status": {"$ne": "hidden"},
                  "$and": [{
                      "$or": [
                          # master project should be always returned
                          {'name': MASTER_PROJECT_NAME},
                          {'owner': logged_in_user},
                          {'editors': logged_in_user},
                          {'approvers': logged_in_user},
                      ]
                  }]
                  }

    if not sort_criteria:
        # order in descending order
        sort_criteria = [["creation_time", -1]]

    all_projects = list(licco_db["projects"].find(filter).sort(sort_criteria))
    return all_projects


def get_projects_for_user(licco_db: MongoDb, username):
    """
    Return all the projects for which the user is an owner or an editor.
    :param username - the userid of the user from authn
    :return: List of projects
    """
    owned_projects = list(licco_db["projects"].find({"owner": username}))
    editable_projects = list(licco_db["projects"].find({"editors": username}))
    return owned_projects + editable_projects


def get_project(licco_db: MongoDb, id) -> Optional[McdProject]:
    """
    Get the details for the project given its id.
    """
    oid = ObjectId(id)
    prj = licco_db["projects"].find_one({"_id": oid})
    if prj:
        latest_edit = get_project_last_edit_time(licco_db, prj["_id"])
        if latest_edit:
            prj["edit_time"] = latest_edit
    return prj


def get_project_ffts(licco_db: MongoDb, prjid, showallentries=True, asoftimestamp=None, fftid=None):
    """
    Get the FFTs for a project given its id.
    """
    oid = ObjectId(prjid)
    logger.info("Looking for project details for %s", oid)
    return get_project_attributes(licco_db, prjid, skipClonedEntries=False if showallentries else True, asoftimestamp=asoftimestamp, fftid=fftid)


def get_project_changes(licco_db: MongoDb, prjid):
    """
    Get a history of changes to the project.
    """
    return get_all_project_changes(licco_db, prjid)


def get_fcs(licco_db: MongoDb):
    """
    Get the functional component objects - typically just the name and description.
    """
    fcs = list(licco_db["fcs"].find({}))
    fcs_used = set(licco_db["ffts"].distinct("fc"))
    for fc in fcs:
        fc["is_being_used"] = fc["_id"] in fcs_used
    return fcs


def get_fgs(licco_db: MongoDb):
    """
    Get the fungible token objects - typically just the name and description.
    """
    fgs = list(licco_db["fgs"].find({}))
    fgs_used = set(licco_db["ffts"].distinct("fg"))
    for fg in fgs:
        fg["is_being_used"] = fg["_id"] in fgs_used
    return fgs


def get_ffts(licco_db: MongoDb):
    """
    Get the functional fungible token objects.
    In addition to id's we also return the fc and fg name and description
    """
    ffts = list(licco_db["ffts"].aggregate([
        {"$lookup": {"from": "fcs", "localField": "fc",
                     "foreignField": "_id", "as": "fc"}},
        {"$unwind": "$fc"},
        {"$lookup": {"from": "fgs", "localField": "fg",
                     "foreignField": "_id", "as": "fg"}},
        {"$unwind": "$fg"}
    ]))
    ffts_used = set(licco_db["projects_history"].distinct("fft"))
    for fft in ffts:
        fft["is_being_used"] = fft["_id"] in ffts_used
    return ffts


def delete_fft(licco_db: MongoDb, fftid):
    """
    Delete an FFT if it is not currently being used by any project.
    """
    fftid = ObjectId(fftid)
    ffts_used = set(licco_db["projects_history"].distinct("fft"))
    if fftid in ffts_used:
        return False, "This FFT is being used in a project", None
    logger.info("Deleting FFT with id " + str(fftid))
    licco_db["ffts"].delete_one({"_id": fftid})
    return True, "", None


def add_fft_comment(licco_db: MongoDb, user_id: str, project_id: str, fftid: str, comment: str):
    if not comment:
        return False, f"Comment should not be empty", None

    project = get_project(licco_db, project_id)
    project_name = project["name"]
    status = project["status"]

    allowed_to_comment = False
    allowed_to_comment |= user_id == project["owner"]
    allowed_to_comment |= user_id in project["editors"]

    if status == "submitted":
        allowed_to_comment |= user_id in project["approvers"]

    if not allowed_to_comment:
        allowed_to_comment |= user_id in get_users_with_privilege(licco_db, "admin")

    if not allowed_to_comment:
        return False, f"You are not allowed to comment on a device within a project '{project_name}'", None

    new_comment = {
        "_id": fftid,
        'discussion': [{
        'author': user_id,
        'comment': comment,
        'time': datetime.datetime.now(datetime.UTC),
    }]}
    status, errormsg, results = update_fft_in_project(licco_db, user_id, project_id, new_comment)
    return status, errormsg, results


def delete_fft_comment(licco_db: MongoDb, user_id, comment_id):
    comment = licco_db["projects_history"].find_one({"_id": ObjectId(comment_id)})
    if not comment:
        return False, f"Comment with id {comment_id} does not exist"

    # check permissions for deletion
    project = get_project(licco_db, comment["prj"])
    status = project["status"]
    project_is_in_correct_state = status == "development" or status == "submitted"
    if not project_is_in_correct_state:
        name = project["name"]
        return False, f"Comment {comment_id} could not be deleted: project '{name}' is not in a development or submitted state (current state = {status})"

    # project is in a correct state
    # check if the user has permissions for deleting a comment
    allowed_to_delete = False
    allowed_to_delete |= comment["user"] == user_id    # comment owner (editor and approver) is always allowed to delete their own comments
    allowed_to_delete |= project["owner"] == user_id   # project owner is always allowed to delete project comments
    if not allowed_to_delete:
        # if user is admin, they should be allowed to delete
        allowed_to_delete |= user_id in get_users_with_privilege(licco_db, "admin")

    if not allowed_to_delete:
        return False, f"You are not allowed to delete comment {comment_id}"

    licco_db["projects_history"].delete_one({"_id": ObjectId(comment_id)})
    return True, ""


def create_new_project(licco_db: MongoDb, userid: str, name: str, description: str, editors: List[str], notifier: Notifier) -> Tuple[str, Dict[str, any]]:
    """
    Create a new project belonging to the specified user.
    """
    if name == "":
        return "Project name could not be empty", {}

    if editors:
        # before creating a project we have to validate editors, so that we don't create a project
        # but fail in the update step
        err = validate_editors(licco_db, editors, notifier)
        if err:
            return f"Invalid project editors: {err}", {}

    newprjid = licco_db["projects"].insert_one({
        "name": name, "description": description, "owner": userid, "editors": [], "approvers": [],
        "status": "development", "creation_time": datetime.datetime.now(datetime.UTC)
    }).inserted_id

    if editors:
        ok, err = update_project_details(licco_db, userid, newprjid, {'editors': editors}, notifier)
        if err:
            return err, {}

    prj = get_project(licco_db, newprjid)
    return "", prj


def validate_editors(licco_db: MongoDb, editors: List[str], notifier: Notifier) -> str:
    if not isinstance(editors, list):
        return f"Editors field should be an array"

    # anyone with a SLAC account could be an editor
    invalid_editor_emails = []
    super_approvers = get_users_with_privilege(licco_db, "superapprover")
    for user in editors:
        if user in super_approvers:
            return f"User '{user}' is a super approver and can't be an editor"

        if not notifier.validate_email(user):
            invalid_editor_emails.append(user)

    if invalid_editor_emails:
        invalid_users = ", ".join(invalid_editor_emails)
        return f"Invalid editor emails/accounts: [{invalid_users}]"
    return ""


def create_new_functional_component(licco_db: MongoDb, name, description):
    """
    Create a new functional component
    """
    if not name:
        return False, "The name is a required field", None
    # Add in default data as temporary fix
    if not description:
        description = ""
    if licco_db["fcs"].find_one({"name": name}):
        return False, f"Functional component {name} already exists", None
    try:
        fcid = licco_db["fcs"].insert_one({"name": name, "description": description}).inserted_id
        return True, "", licco_db["fcs"].find_one({"_id": fcid})
    except Exception as e:
        return False, str(e), None


def create_new_fungible_token(licco_db: MongoDb, name, description):
    """
    Create a new fungible token
    """
    if not name:
        name = ""
    # Add in default data as temporary fix
    if not description:
        description = ""
    if licco_db["fgs"].find_one({"name": name}):
        return False, f"Fungible token {name} already exists", None
    try:
        fgid = licco_db["fgs"].insert_one({"name": name, "description": description}).inserted_id
        return True, "", licco_db["fgs"].find_one({"_id": fgid})
    except Exception as e:
        return False, str(e), None


def find_or_create_fft(licco_db: MongoDb, fc_name: str, fg_name: str) -> Tuple[bool, str, Optional[Dict[str, any]]]:
    fcobj = licco_db["fcs"].find_one({"name": fc_name})
    fgobj = licco_db["fgs"].find_one({"name": fg_name})
    if fcobj and fgobj:
        fft = licco_db["ffts"].find_one({"fc": ObjectId(fcobj["_id"]), "fg": ObjectId(fgobj["_id"])})
        if fft:
            return True, "", fft
        # fft was not found, fallthrough and create it

    # fc and fg do not exist, create a new fft
    ok, err, fft = create_new_fft(licco_db, fc_name, fg_name, "Auto generated", "Auto generated")
    if not ok:
        return False, err, None
    return ok, err, fft


def create_new_fft(licco_db: MongoDb, fc, fg, fcdesc="Default", fgdesc="Default") -> Tuple[bool, str, Optional[Dict[str, any]]]:
    """
    Create a new functional component + fungible token based on their names
    If the FC or FG don't exist; these are created if the associated descriptions are also passed in.
    """
    if empty_string_or_none(fc):
        err = "can't create a new fft: FC can't be empty"
        return False, err, None

    logger.info("Creating new fft with %s and %s", fc, fg)
    fcobj = licco_db["fcs"].find_one({"name": fc})
    if not fcobj:
        if not fcdesc:
            return False, f"Could not find functional component {fc}", None
        else:
            logger.debug(f"Creating a new FC as part of creating an FFT {fc}")
            _, _, fcobj = create_new_functional_component(licco_db, fc, fcdesc)
    if not fg:
        fg = ""
        fgdesc = "The default null fg to accommodate outer joins"
    fgobj = licco_db["fgs"].find_one({"name": fg})
    if not fgobj:
        if not fgdesc:
            return False, f"Could not find fungible token with id {fg}", None
        else:
            logger.debug(f"Creating a new FG as part of creating an FFT {fg}")
            _, _, fgobj = create_new_fungible_token(licco_db, fg, fgdesc)
    if licco_db["ffts"].find_one({"fc": ObjectId(fcobj["_id"]), "fg": fgobj["_id"]}):
        return False, f"FFT with {fc}-{fg} has already been registered", None

    try:
        fftid = licco_db["ffts"].insert_one({"fc": fcobj["_id"], "fg": fgobj["_id"]}).inserted_id
        fft = licco_db["ffts"].find_one({"_id": fftid})
        fft["fc"] = licco_db["fcs"].find_one({"_id": fft["fc"]})
        fft["fg"] = licco_db["fgs"].find_one({"_id": fft["fg"]})
        return True, "", fft
    except Exception as e:
        return False, str(e), None


def default_wrapper(func, default):
    def wrapped_func(val):
        if val == '':
            return default
        else:
            return func(val)
    return wrapped_func


def str2bool(val):
    return json.loads(str(val).lower())


def str2float(val):
    return float(val)


def str2int(val):
    return int(val)


# read only attributes and their metadata
fcattrs = types.MappingProxyType({
    "fg_desc": {
        "name": "fg_desc",
        "type": "text",
        "fromstr": str,
        "label": "Fungible",
        "desc": "Fungible_user",
        "required": False
    },
    "tc_part_no": {
        "name": "tc_part_no",
        "type": "text",
        "fromstr": str,
        "label": "TC Part No.",
        "desc": "TC_part_no",
        "required": False
    },
    "state": {
        "name": "state",
        "type": "enum",
        "fromstr": lambda x: FCState[x].value,
        "enumvals": [name for (name, _) in FCState.__members__.items()],
        "label": "State",
        "desc": "The current state of the functional component",
        "required": True,
        "default": "Conceptual"
    },
    "stand": {
        "name": "stand",
        "type": "text",
        "fromstr": str,
        "label": "Stand/Nearest Stand",
        "desc": "Stand/Nearest Stand",
        "required": False,
    },
    "comments": {
        "name": "comments",
        "type": "text",
        "fromstr": str,
        "label": "Comments",
        "desc": "Comments",
        "required": False
    },
    "nom_loc_z": {
        "name": "nom_loc_z",
        "type": "text",
        "fromstr": default_wrapper(str2float, ""),
        "rendermacro": "prec7float",
        "label": "Z",
        "category": {"label": "Nominal Location (meters in LCLS coordinates)", "span": 3},
        "desc": "Nominal Location Z",
        "required": False,
        "is_required_dimension": True
    },
    "nom_loc_x": {
        "name": "nom_loc_x",
        "type": "text",
        "fromstr": default_wrapper(str2float, ""),
        "rendermacro": "prec7float",
        "label": "X",
        "category": {"label": "Nominal Location (meters in LCLS coordinates)"},
        "desc": "Nominal Location X",
        "required": False,
        "is_required_dimension": True
    },
    "nom_loc_y": {
        "name": "nom_loc_y",
        "type": "text",
        "fromstr": default_wrapper(str2float, ""),
        "rendermacro": "prec7float",
        "label": "Y",
        "category": {"label": "Nominal Location (meters in LCLS coordinates)"},
        "desc": "Nominal Location Y",
        "required": False,
        "is_required_dimension": True
    },
    "nom_ang_z": {
        "name": "nom_ang_z",
        "type": "text",
        "fromstr": default_wrapper(str2float, ""),
        "rendermacro": "prec7float",
        "label": "Z",
        "category": {"label": "Nominal Angle (radians)", "span": 3},
        "desc": "Nominal Angle Z",
        "required": False,
        "is_required_dimension": True
    },
    "nom_ang_x": {
        "name": "nom_ang_x",
        "type": "text",
        "fromstr": default_wrapper(str2float, ""),
        "rendermacro": "prec7float",
        "label": "X",
        "category": {"label": "Nominal Angle (radians)"},
        "desc": "Nominal Angle X",
        "required": False,
        "is_required_dimension": True
    },
    "nom_ang_y": {
        "name": "nom_ang_y",
        "type": "text",
        "fromstr": default_wrapper(str2float, ""),
        "rendermacro": "prec7float",
        "label": "Y",
        "category": {"label": "Nominal Angle (radians)"},
        "desc": "Nominal Angle Y",
        "required": False,
        "is_required_dimension": True
    },
    "ray_trace": {
        "name": "ray_trace",
        "type": "text",
        "fromstr": default_wrapper(str2int, None),
        "label": "Must Ray Trace",
        "desc": "Must Ray Trace",
        "required": False
    },
    "discussion": {
        # NOTE: everytime the user changes a device value, a discussion comment is added to the database
        # as a separate document. On load, however, we have to parse all the comments into a structured
        # array of all comments for that specific device.
        "name": "discussion",
        "type": "text",
        "fromstr": str,
        "label": "Discussion",
        "desc": "User discussion about the device value change",
        "required": False,
    }
})


def change_of_fft_in_project(licco_db: MongoDb, userid: str, prjid: str, fcupdate: Dict[str, any]) -> Tuple[bool, str, str]:
    fftid = fcupdate["_id"]
    if empty_string_or_none(fftid):
        return False, f"Can't change device of a project: fftid should not be empty", ""

    project = get_project(licco_db, prjid)
    if not project:
        return False, f"Project {prjid} does not exist", ""
    if project['status'] != 'development':
        return False, f"Can't change fft {fftid}: Project {project['name']} is not in a development mode (status={project['status']})", ""

    fft = licco_db["ffts"].find_one({"_id": ObjectId(fftid)})
    if not fft:
        return False, f"Cannot find functional+fungible token for {fftid}", ""

    change_of_fft = 'fc' in fcupdate or 'fg' in fcupdate
    if not change_of_fft:
        # this is a regular update, and as such this method was not really used correctly, but it's not a bug
        # since we fallback to the regular fft update
        ok, err, _ = update_fft_in_project(licco_db, userid, prjid, fcupdate)
        return ok, err, fftid

    # When the user wants to update a device, but change it's fc or fg we have to:
    # 1) Create new fft if necessary
    # 2) Copy all latest values from the old fft together with the current user changes (if any)
    # 3) Delete old device

    # get old fft values
    old_values = get_project_attributes(licco_db, prjid, fftid=fftid)
    old_values = old_values[fftid]
    old_fft = old_values.pop('fft')
    new_fc_name = fcupdate.pop('fc', old_fft['fc'])
    new_fg_name = fcupdate.pop('fg', old_fft['fg'])

    # 1) create new fft if necessary
    ok, err, new_fft = find_or_create_fft(licco_db, new_fc_name, new_fg_name)
    if not ok:
        return False, err, ""

    # overwrite the old values
    for key, val in fcupdate.items():
        if key == 'discussion':
            old_discussion = old_values.get(key, [])
            if old_discussion:
                val = val + old_discussion
            old_values[key] = val
        else:
            old_values[key] = val

    # 2) insert new values into db and delete the values with old fft
    new_fft_id = str(new_fft["_id"])
    overwritten_values = old_values
    overwritten_values["_id"] = new_fft_id
    ok, err, inserts = update_fft_in_project(licco_db, userid, prjid, overwritten_values)
    if not ok:
        return False, f"Failed to change fft '{fftid}': failed to update ffts: {err}", ""

    # 3) delete old device from project
    old_fft = fftid
    ok, err = remove_ffts_from_project(licco_db, userid, prjid, [old_fft])
    if not ok:
        return False, f"Failed to change fft '{fftid}': failed to remove old device: {err}", ""

    # fft was successfully changed
    return True, "", new_fft_id


def update_fft_in_project(licco_db: MongoDb, userid: str, prjid: str, fcupdate: Dict[str, any], modification_time=None,
                          current_project_attributes=None) -> Tuple[bool, str, ImportCounter]:
    """
    Update the value(s) of an FFT in a project
    Returns: a tuple containing (success flag (true/false if error), error message (if any), and an insert count
    """
    insert_counter = ImportCounter()
    fftid = fcupdate["_id"]
    if not fftid:
        return False, "fft id is missing in updated values", insert_counter

    prj = licco_db["projects"].find_one({"_id": ObjectId(prjid)})
    if not prj:
        return False, f"Cannot find project for {prjid}", insert_counter

    fft = licco_db["ffts"].find_one({"_id": ObjectId(fftid)})
    if not fft:
        return False, f"Cannot find functional+fungible token for {fftid}", insert_counter

    current_attrs = current_project_attributes
    if current_attrs is None:
        # NOTE: current_project_attributes should be provided when lots of ffts are updated at the same time, e.g.:
        # for 100 ffts, we shouldn't query the entire project attributes 100 times as that is very slow
        # (cca 150-300 ms per query).
        current_attrs = get_project_attributes(licco_db, ObjectId(prjid)).get(str(fftid), {})

    if not modification_time:
        modification_time = datetime.datetime.now(datetime.UTC)
    # Make sure the timestamp on this server is monotonically increasing.
    latest_changes = list(licco_db["projects_history"].find({}).sort([("time", -1)]).limit(1))
    if latest_changes:
        # NOTE: not sure if this is the best approach, but when using mongomock for testing
        # we get an error (can't compare offset-naive vs offset aware timestamps), hence we
        # set the timezone info manually.
        if modification_time < latest_changes[0]["time"].replace(tzinfo=pytz.utc):
            return False, f"The time on this server {modification_time.isoformat()} is before the most recent change from the server {latest_changes[0]['time'].isoformat()}", insert_counter

    if "state" in fcupdate and fcupdate["state"] != "Conceptual":
        for attrname, attrmeta in fcattrs.items():
            if (attrmeta.get("is_required_dimension") is True) and ((current_attrs.get(attrname, None) is None) and (fcupdate.get(attrname, None) is None)):
                return False, "FFTs should remain in the Conceptual state while the dimensions are still being determined.", insert_counter

    fft_fields_to_insert = []
    for attrname, attrval in fcupdate.items():
        if attrname == "_id":
            continue
        if attrname == "fft":
            continue

        # special handling of discussion comments fields
        if attrname == "discussion" and isinstance(attrval, list):
            old_comments = current_attrs.get(attrname, [])
            old_comment_ids = [x['id'] for x in old_comments]

            for comment in attrval:
                comment_id = comment.get("id", "")
                if comment_id and comment_id in old_comment_ids:
                    # this comment already exists, hence we don't copy it
                    continue

                author = comment['author']
                newval = comment['comment']
                time = comment.get('time', modification_time)
                fft_fields_to_insert.append({
                    "prj": ObjectId(prjid),
                    "fft": ObjectId(fftid),
                    "key": attrname,
                    "val": newval,
                    "user": author,
                    "time": time,
                })
            continue

        try:
            attrmeta = fcattrs[attrname]
        except KeyError:
            logger.debug(f"Parameter {attrname} is not in DB. Skipping entry.")
            continue

        if attrmeta["required"] and not attrval:
            insert_counter.fail += 1
            return False, f"Parameter {attrname} is a required attribute", insert_counter

        try:
            newval = attrmeta["fromstr"](attrval)
        except ValueError:
            # <FFT>, <field>, invalid input rejected: [Wrong type| Out of range]
            insert_counter.fail += 1
            error_str = f"Wrong type - {attrname}, ('{attrval}')"
            return False, error_str, insert_counter

        # Check that values are within bounds
        range_err = validate_insert_range(attrname, newval)
        if range_err:
            insert_counter.fail += 1
            error_str = range_err
            return False, error_str, insert_counter

        prevval = current_attrs.get(attrname, None)
        if prevval != newval:
            fft_fields_to_insert.append({
                "prj": ObjectId(prjid),
                "fft": ObjectId(fftid),
                "key": attrname,
                "val": newval,
                "user": userid,
                "time": modification_time
            })

    if fft_fields_to_insert:
        logger.debug("Inserting %s documents into the history", len(fft_fields_to_insert))
        licco_db["projects_history"].insert_many(fft_fields_to_insert)
        insert_counter.success += 1
        return True, "", insert_counter

    # nothing to insert
    insert_counter.ignored += 1
    logger.debug("In update_fft_in_project, all_inserts is an empty list")
    return True, "", insert_counter


def validate_insert_range(attr, val) -> str:
    """
    Helper function to validate data prior to being saved in DB
    Returns an error in case of invalid range
    """
    try:
        if attr == "ray_trace":
            if val == '' or val is None:
                return ""
            if int(val) < 0:
                return f"invalid range of ray_trace: expected range [0,1], but got {int(val)}"

        # empty strings valid for angles, catch before other verifications
        if "nom" in attr:
            if val == "":
                return ""
            if attr == "nom_loc_z":
                v = float(val)
                if v < 0 or v > 2000:
                    return f"invalid range for {attr}: expected range [0,2000], but got {v}"
            if "nom_ang_" in attr:
                v = float(val)
                if (v < -(math.pi)) or (v > math.pi):
                    return f"invalid range for {attr}: expected range [-{math.pi:.2f}, {math.pi:.2f}], but got {v}"
    except ValueError:
        return f"value {val} is a wrong type for the attribute {attr}"
    except TypeError:
        return f"value {val} is not verified for attribute {attr}"

    # there is no error with this range
    return ""


def update_ffts_in_project(licco_db: MongoDb, userid: str, prjid: str, ffts, def_logger=None, remove_discussion_comments=False, ignore_user_permission_check=False) -> Tuple[bool, str, ImportCounter]:
    """
    Insert multiple FFTs into a project
    """
    if def_logger is None:
        def_logger = logger
    insert_counter = ImportCounter()
    if isinstance(ffts, dict):
        new_ffts = []
        for entry in ffts:
            new_ffts.append(ffts[entry])
        ffts = new_ffts

    project = get_project(licco_db, prjid)
    if project['name'] != MASTER_PROJECT_NAME:
        if project['status'] != 'development':
            return False, f"can't update ffts of a project that is not in a development mode (status = {project['status']})", ImportCounter()

    verify_user_permissions = not ignore_user_permission_check
    if verify_user_permissions:
        # check that only owner/editor/admin are allowed to update this project
        allowed_to_update = is_user_allowed_to_edit_project(licco_db, userid, project)
        if not allowed_to_update:
            return False, f"user '{userid}' is not allowed to update a project {project['name']}", ImportCounter()


    # TODO: ROBUSTNESS: we should validate ffts before insertion: right now it's possible that only some of the
    #       ffts will be inserted, while the ones with errors will not. This leaves the db in an inconsistent state.
    #
    # Iterate through parameter fft set
    project_ffts = get_project_ffts(licco_db, prjid)
    errormsg = ""
    for fft in ffts:
        if "_id" not in fft:
            # TODO: this lookup should be removed in the future
            # REVIEW: the database layer should return the kind of structure that you
            # need, so you don't have to fix it everyhwere that structure is used.
            # That fix should be already in the database layer.
            #
            # If the fft set comes from the database, unpack the fft ids
            if "fft" in fft:
                fft["_id"] = fft["fft"]["_id"]
                fft["fc"] = fft["fft"]["fc"]
                fft["fg"] = fft["fft"]["fg"]
            # Otherwise, look up the fft ids
            else:
                if "fg" not in fft:
                    fft["fg"] = ""
                fft["_id"] = str(get_fft_id_by_names(licco_db, fc=fft["fc"], fg=fft["fg"]))
        fftid = str(fft["_id"])

        # previous values
        db_values = get_fft_values_by_project(licco_db, fftid, prjid)
        fcupdate = {}
        fcupdate.update(fft)
        fcupdate["_id"] = fftid

        if empty_string_or_none(fcupdate.get("state", "")):
            if "state" in db_values:
                fcupdate["state"] = db_values["state"]
            else:
                fcupdate["state"] = "Conceptual"

        # If invalid, don't try to add to DB
        status, errormsg = validate_import_headers(licco_db, fcupdate, prjid)
        if not status:
            insert_counter.fail += 1
            def_logger.info(create_imp_msg(fft, False, errormsg=errormsg))
            continue

        for attr in ["name", "fc", "fg", "fft"]:
            if attr in fcupdate:
                del fcupdate[attr]

        # Performance: when updating fft in a project, we used to do hundreds of database calls
        # which was very slow. An import of a few ffts took 10 seconds. We speed this up, by
        # querying the current project attributes once and passing it to the update routine
        current_attributes = project_ffts.get(fftid, {})
        if remove_discussion_comments:
            # discussion comment will not be copied/updated
            if fcupdate.get('discussion', None):
                del fcupdate['discussion']

        status, errormsg, results = update_fft_in_project(licco_db, userid, prjid, fcupdate,
                                                          current_project_attributes=current_attributes)
        # Have smarter error handling here for different exit conditions
        def_logger.info(create_imp_msg(fft, status=status, errormsg=errormsg))

        # Add the individual FFT update results into overall count
        if results:
            insert_counter.add(results)

    # BUG: error message is not declared anywhere, so it will always be as empty string or set to the last value
    # that comes out of fft update loop
    return True, errormsg, insert_counter


def create_imp_msg(fft, status, errormsg=None):
    """
    Creates a message to be logged for the import report.
    """
    if status is None:
        res = "IGNORED"
    elif status is True:
        res = "SUCCESS"
    else:
        res = "FAIL"
    if 'fc' not in fft:
        fft['fc'] = "NO VALID FC"
    if 'fg' not in fft:
        fft['fg'] = ''
    msg = f"{res}: {fft['fc']}-{fft['fg']} - {errormsg}"
    return msg


def validate_import_headers(licco_db: MongoDb, fft: Dict[str, any], prjid: str):
    """
    Helper function to pre-validate that all required data is present
    fft: dictionary of field_name:values. '_id': '<fft_id>' is a necessary value
    """
    fftid = fft.get("_id", None)
    if not fftid:
        return False, "expected '_id' field in the fft values"

    db_values = get_fft_values_by_project(licco_db, fftid, prjid)
    if "state" not in fft:
        fft["state"] = db_values["state"]

    for attr in fcattrs:
        # If header is required for all, or if the FFT is non-conceptual and header is required
        if fcattrs[attr]["required"] or (fft["state"] != "Conceptual" and fcattrs[attr].get("is_required_dimension", False)):
            # If required header not present in upload dataset
            if attr not in fft:
                # Check if in DB already, continue to validate next if so
                if attr not in db_values:
                    error_str = f"Missing required header {attr}"
                    logger.debug(error_str)
                    return False, error_str
                fft[attr] = db_values[attr]

            # Header is a required value, but user is trying to null this value
            if fft[attr] == '':
                error_str = f"'{attr}' value is required for a Non-Conceptual device"
                logger.debug(error_str)
                return False, error_str

        if attr not in fft:
            continue

        try:
            val = fcattrs[attr]["fromstr"](fft[attr])
        except (ValueError, KeyError) as e:
            error_str = f"Invalid data type for '{attr}': '{fft[attr]}'"
            return False, error_str
    return True, ""


def copy_ffts_from_project(licco_db: MongoDb, srcprjid, destprjid, fftid, attrnames, userid):
    """
    Copy values for the fftid from srcprjid into destprjid for the specified attrnames
    """
    srcprj = licco_db["projects"].find_one({"_id": ObjectId(srcprjid)})
    if not srcprj:
        return False, f"Cannot find source project {srcprj}", None
    destprj = licco_db["projects"].find_one({"_id": ObjectId(destprjid)})
    if not destprj:
        return False, f"Cannot find destination project {destprjid}", None
    fft = licco_db["ffts"].find_one({"_id": ObjectId(fftid)})
    if not fft:
        return False, f"Cannot find FFT for {fftid}", None

    modification_time = datetime.datetime.now(datetime.UTC)
    # Make sure the timestamp on this server is monotonically increasing.
    latest_changes = list(licco_db["projects_history"].find({}).sort([("time", -1)]).limit(1))
    if latest_changes:
        if modification_time < latest_changes[0]["time"].replace(tzinfo=pytz.utc):
            return False, f"The time on this server {modification_time.isoformat()} is before the most recent change from the server {latest_changes[0]['time'].isoformat()}", None

    current_attrs = get_project_attributes(licco_db, ObjectId(destprjid))
    fftattrs = current_attrs.get(fftid, {})
    other_attrs = get_project_attributes(licco_db, ObjectId(srcprjid))
    oattrs = other_attrs.get(fftid, {})

    all_inserts = []
    for attrname, cnvattrval in oattrs.items():
        if not attrname in attrnames:
            continue
        attrmeta = fcattrs[attrname]
        if attrmeta["required"] and not cnvattrval:
            return False, f"Parameter {attrname} is a required attribute", None
        cnvattrval = attrmeta["fromstr"](cnvattrval)
        if fftattrs.get(attrname) != cnvattrval:
            logger.debug("Updating %s in prj %s to %s",
                         attrname, destprjid, cnvattrval)
            all_inserts.append({
                "prj": ObjectId(destprjid),
                "fft": ObjectId(fftid),
                "key": attrname,
                "val": cnvattrval,
                "user": userid,
                "time": modification_time
            })
    licco_db["projects_history"].insert_many(all_inserts)

    return True, "", get_project_attributes(licco_db, ObjectId(destprjid)).get(fftid, {})


def remove_ffts_from_project(licco_db: MongoDb, userid, prjid, fft_ids: List[str]) -> Tuple[bool, str]:
    project = get_project(licco_db, prjid)
    if not project:
        return False, f"Project {prjid} does not exist"
    if project["status"] != "development":
        return False, f"Project {project['name']} is not in a development state"

    user_is_editor = is_user_allowed_to_edit_project(licco_db, userid, project)
    if not user_is_editor:
        return False, f"You are not an editor and therefore can't remove the project devices"

    # this will delete every stored value (history of value changes and discussion comment for this device)
    ids = [ObjectId(x) for x in fft_ids]
    result = licco_db["projects_history"].delete_many({'$and': [{"prj": ObjectId(prjid)}, {"fft": {"$in": ids}}]})
    if result.deleted_count == 0:
        # this should never happen when using the GUI (the user can only delete a device if a device is displayed
        # in a GUI (with a valid id) - there should always be at least one such document.
        # Nevertheless, this situation can happen if someone decides to delete a device via a REST API
        # while providing a list of invalid ids.
        return False, f"Chosen ffts {fft_ids} do not exist"
    return True, ""

def _emails_to_usernames(emails: List[str]):
    return [email.split("@")[0] for email in emails]

def submit_project_for_approval(licco_db: MongoDb, project_id: str, userid: str, editors: List[str],
                                approvers: List[str], notifier: Notifier) -> Tuple[bool, str, Optional[McdProject]]:
    """
    Submit a project for approval.
    Set the status to submitted
    """
    prj = licco_db["projects"].find_one({"_id": ObjectId(project_id)})
    project_name = prj["name"]
    if not prj:
        return False, f"Cannot find project for '{project_name}'", None

    status = prj["status"]
    if status != "development" and status != "submitted":
        return False, f"Project '{project_name}' is not in development or submitted status", None

    # check if the user has a permissions for submitting a project
    user_is_allowed_to_edit = is_user_allowed_to_edit_project(licco_db, userid, prj)
    if not user_is_allowed_to_edit:
        return False, f"User {userid} is not allowed to submit a project '{project_name}'", None

    # the list of approvers could be empty, since we automatically add super approvers to this list
    #
    # an approver could be anyone with a SLAC account. These approvers could be given in the
    # form of an email (e.g., username@example.com), which we have to validate
    super_approvers = get_users_with_privilege(licco_db, "superapprover")
    approvers = list(set(approvers).union(super_approvers))
    approvers.sort()

    # validate a list of approvers
    if len(approvers) == 0:
        return False, f"Project '{project_name}' should have at least 1 approver", None
    for a in approvers:
        if not a:
            return False, f"Invalid project approver: '{a}'", None
    if userid in approvers:
        return False, f"Submitter {userid} is not allowed to also be a project approver", None
    if prj["owner"] in approvers:
        return False, f"A project owner {userid} is not allowed to also be a project approver", None

    # check if approver is also an editor (they are not allowed to be)
    approver_usernames = _emails_to_usernames(approvers)
    editor_usernames = _emails_to_usernames(editors)
    users_with_multiple_roles = []
    for i, approver in enumerate(approver_usernames):
        if approver in editor_usernames:
            # we want to return the name of the approver with the actual name that the user had sent us
            # otherwise the error message may look confusing (e.g., the user sent us 'user@example.com'
            # we return the same string back within the error message)
            users_with_multiple_roles.append(approvers[i])
    if users_with_multiple_roles:
        multiple_roles = ", ".join(users_with_multiple_roles)
        return False, f"The users are not allowed to be both editors and approvers: [{multiple_roles}]", None

    invalid_approver_accounts = []
    for a in approvers:
        if not notifier.validate_email(a):
            invalid_approver_accounts.append(a)

    if invalid_approver_accounts:
        invalid_accounts = ", ".join(invalid_approver_accounts)
        return False, f"Invalid approver emails/accounts: [{invalid_accounts}]", None

    # update editors (if necessary)
    editors_update_ok, err = update_project_details(licco_db, userid, project_id, {'editors': editors}, notifier)
    if not editors_update_ok:
        return editors_update_ok, err, None

    # store approval metadata
    # all approvers are valid, but we have to store their usernames since the application performs permission checks
    # via usernames (and not emails that the user may provide)
    licco_db["projects"].update_one({"_id": prj["_id"]}, {"$set": {
        "status": "submitted", "submitter": userid, "approvers": approver_usernames,
        "submitted_time": datetime.datetime.now(datetime.UTC)
    }})

    # send notifications (to the right approvers and project editors)
    old_approvers = prj.get("approvers", [])
    update_diff = diff_arrays(old_approvers, approvers)
    superapp_diff = diff_arrays(super_approvers, approvers)

    deleted_approvers = update_diff.removed
    if deleted_approvers:
        notifier.remove_project_approvers(deleted_approvers, project_name, project_id)

    if prj["status"] == "development":
        # project was submitted for the first time
        project_editors = list(set([prj["owner"]] + editors))
        # inform all editors, super approvers, and approvers
        notifier.project_submitted_for_approval(project_editors, project_name, project_id)
        notifier.add_project_superapprovers(list(superapp_diff.in_both), project_name, project_id)
        notifier.add_project_approvers(list(superapp_diff.new), project_name, project_id)

    else:
        # project was edited
        if update_diff.new:
            # update any new approvers
            notifier.add_project_approvers(list(update_diff.new), project_name, project_id)
        project_editors = list(set([prj["owner"]] + editors))
        approvers_have_changed = update_diff.new or deleted_approvers
        if approvers_have_changed:
            notifier.inform_editors_of_approver_change(project_editors, project_name, project_id, approvers)

    project = licco_db["projects"].find_one({"_id": ObjectId(project_id)})
    return True, "", project


def approve_project(licco_db: MongoDb, prjid: str, userid: str, notifier: Notifier) -> Tuple[bool, bool, str, Dict[str, any]]:
    """
    Approve a submitted project.
    Set the status to approved
    """
    prj = licco_db["projects"].find_one({"_id": ObjectId(prjid)})
    if not prj:
        return False, False, f"Cannot find project for {prjid}", {}
    if prj["status"] != "submitted":
        return False, False, f"Project {prjid} is not in submitted status", {}
    if prj["submitter"] == userid:
        return False, False, f"Project {prj['name']} cannot be approved by its submitter {userid}. Please ask someone other than the submitter to approve the project", {}

    assigned_approvers = prj.get("approvers", [])
    if userid not in assigned_approvers:
        # super approvers are stored as project approvers so we don't have an extra check just for them
        return False, False, f"User {userid} is not allowed to approve the project", {}

    # update the project metadata
    approved_by = prj.get("approved_by", [])
    if userid in approved_by:
        return False, False, f"User {userid} has already approved this project", {}

    approved_by = [userid] + approved_by
    updated_project_data = {
        "approved_by": approved_by
    }

    # user was allowed to approve, store the approvers for this project
    licco_db["projects"].update_one({"_id": prj["_id"]}, {"$set": updated_project_data})

    all_assigned_approvers_approved = set(assigned_approvers).issubset(set(approved_by))
    still_waiting_for_approval = not all_assigned_approvers_approved
    if still_waiting_for_approval:
        updated_project = get_project(licco_db, prj["_id"])
        return True, all_assigned_approvers_approved, "", updated_project

    # all assigned approvers have approved the project
    # now we merge the data changes into the master project and update the merged project's metadata

    # update fft data of master project
    master_project = licco_db["projects"].find_one({"name": MASTER_PROJECT_NAME})
    if not master_project:
        return False, False, "Failed to find an approved project: this is a programming bug", {}
    licco_db["projects"].update_one({"_id": master_project["_id"]}, {"$set": {
        "owner": "", "status": "approved", "approved_time": datetime.datetime.now(datetime.UTC)
    }})

    # master project should not inherit old discussion comments from a submitted project, hence the removal flag
    status, errormsg, update_status = update_ffts_in_project(licco_db, userid,
                                                             master_project["_id"],
                                                             get_project_ffts(licco_db, prjid),
                                                             remove_discussion_comments=True,
                                                             ignore_user_permission_check=True)
    if not status:
        # failed to insert changed fft data into master project
        return False, False, errormsg, {}

    store_project_approval(licco_db, prjid, prj["submitter"])

    # successfully inserted project ffts into a master project
    # send notifications that the project was approved
    project_name = prj["name"]
    notified_users = list(set([(prj["owner"])] + prj["editors"] + prj["approvers"]))
    notifier.project_approval_approved(notified_users, project_name, prjid)

    # once the project is approved and fully merged in, it goes back into the development status
    # we have only 1 approved project at a time, to which the ffts are copied
    updated_project_data["status"] = "development"
    updated_project_data['approved_time'] = datetime.datetime.now(datetime.UTC)
    # clean the project metadata as if it was freshly created project
    updated_project_data["editors"] = []
    updated_project_data["approvers"] = []
    updated_project_data["approved_by"] = []
    updated_project_data['notes'] = []
    licco_db["projects"].update_one({"_id": prj["_id"]}, {"$set": updated_project_data})
    updated_project = get_project(licco_db, prj["_id"])

    return True, all_assigned_approvers_approved, "", updated_project


def reject_project(licco_db: MongoDb, prjid: str, userid: str, reason: str, notifier: Notifier):
    """
    Do not approve a submitted project.
    Set the status to development
    """
    prj = licco_db["projects"].find_one({"_id": ObjectId(prjid)})
    if not prj:
        return False, f"Cannot find project for {prjid}", None
    if prj["status"] != "submitted":
        return False, f"Project {prjid} is not in submitted status", None

    allowed_to_reject = False
    allowed_to_reject |= userid == prj['owner']
    allowed_to_reject |= userid in prj['editors']
    allowed_to_reject |= userid in prj['approvers']
    if not allowed_to_reject and userid in get_users_with_privilege(licco_db, "admin"):
        # user is admin, and as such has the privilege to delete a project
        allowed_to_reject = True

    if not allowed_to_reject:
        return False, f"User {userid} is not allowed to reject this project", None

    # TODO: notes should probably be stored in a format (user: <username>, date: datetime, content: "")
    # so we can avoid rendering them when they are no longer relevant.
    now = datetime.datetime.now(datetime.UTC)
    licco_datetime = now.strftime("%b/%d/%Y %H:%M:%S")
    formatted_reason = f"{userid} ({licco_datetime}):\n{reason}"
    licco_db["projects"].update_one({"_id": prj["_id"]}, {"$set": {
                                                        "status": "development",
                                                        "approved_by": [],
                                                        "approved_time": None,
                                                        "notes": [formatted_reason] + prj.get("notes", [])}})
    updated_project = licco_db["projects"].find_one({"_id": ObjectId(prjid)})

    # send notifications
    project_id = updated_project["_id"]
    project_name = updated_project["name"]
    owner = updated_project["owner"]
    editors = updated_project["editors"]
    approvers = updated_project["approvers"]
    project_approver_emails = list(set([owner] + editors + approvers))
    user_who_rejected = userid
    notifier.project_approval_rejected(project_approver_emails, project_name, project_id,
                                               user_who_rejected, reason)
    return True, "", updated_project


def get_master_project(licco_db: MongoDb):
    """
    Get the current approved project by status
    """
    prj = licco_db["projects"].find_one({"name": MASTER_PROJECT_NAME})
    if prj and prj["status"] == "approved":
        return prj
    return None


def store_project_approval(licco_db: MongoDb, prjid: str, project_submitter: str):
    licco_db["switch"].insert_one({
        "prj": ObjectId(prjid),
        "requestor_uid": project_submitter,
        "switch_time": datetime.datetime.now(datetime.UTC)
    })


def get_projects_approval_history(licco_db: MongoDb, limit: int = 100):
    """
    Get the history of project approvals
    """
    hist = list(licco_db["switch"].aggregate([
        {"$sort": {"switch_time": -1}},
        {"$limit": limit},
        {"$lookup": {"from": "projects", "localField": "prj",
                     "foreignField": "_id", "as": "prjobj"}},
        {"$unwind": "$prjobj"},
        {"$project": {
            "_id": "$_id",
            "switch_time": "$switch_time",
            "requestor_uid": "$requestor_uid",
            "prj": "$prjobj.name",
            "description": "$prjobj.description",
            "owner": "$prjobj.owner"
        }}
    ]))
    return hist


def get_all_projects_last_edit_time(licco_db: MongoDb) -> Dict[str, Dict[str, datetime.datetime | str]]:
    """
    Gets the most recent time of edit for all projects in development status
    """
    edit_list = {}
    projects = licco_db["projects"].find()
    for project in projects:
        prjid = str(project["_id"])
        last_edit_time = get_project_last_edit_time(licco_db, prjid)
        if last_edit_time:
            edit_list[prjid] = {"_id": prjid, "time": last_edit_time}
        else:
            edit_list[prjid] = {"_id": "", "time": ""}
    return edit_list


def get_project_last_edit_time(licco_db: MongoDb, project_id: str) -> Optional[datetime.datetime]:
    most_recent = licco_db["projects_history"].find_one(
        {"prj": ObjectId(project_id)}, {"time": 1}, sort=[("time", DESCENDING)])
    if most_recent:
        return most_recent["time"]
    return None


def __flatten__(obj, prefix=""):
    """
    Flatten a dict into a list of key value pairs using dot notation.
    """
    ret = []
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            ret.extend(__flatten__(v, prefix + "." + k if prefix else k))
    elif isinstance(obj, list):
        for c, e in enumerate(obj):
            ret.extend(__flatten__(
                e, prefix + ".[" + str(c) + "]" if prefix else "[" + str(c) + "]"))
    else:
        ret.append((prefix, obj))
    return ret


def diff_project(licco_db: MongoDb, prjid, other_prjid, userid, approved=False):
    """
    Diff two projects
    """
    prj = licco_db["projects"].find_one({"_id": ObjectId(prjid)})
    if not prj:
        return False, f"Cannot find project for {prjid}", None

    otr = licco_db["projects"].find_one({"_id": ObjectId(other_prjid)})
    if not otr:
        return False, f"Cannot find project for {other_prjid}", None

    # we don't want to diff comments, hence we filter them out by setting the timestamp far into the future
    no_comment_timestamp = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=365 * 100)
    myfcs = get_project_attributes(licco_db, prjid, commentAfterTimestamp=no_comment_timestamp)
    thfcs = get_project_attributes(licco_db, other_prjid, commentAfterTimestamp=no_comment_timestamp)

    myflat = __flatten__(myfcs)
    thflat = __flatten__(thfcs)

    mydict = {x[0]: x[1] for x in myflat}
    thdict = {x[0]: x[1] for x in thflat}
    mykeys = set(mydict.keys())
    thkeys = set(thdict.keys())
    keys_u = mykeys.union(thkeys)
    keys_i = mykeys.intersection(thkeys)
    keys_l = mykeys - thkeys
    keys_r = thkeys - mykeys

    diff = []
    for k in keys_u:
        # skip keys that exist in the approved project, but not in submitted project
        if approved and (k in keys_r):
            continue
        if k in keys_i and mydict[k] == thdict[k]:
            diff.append({"diff": False, "key": k,
                        "my": mydict[k], "ot": thdict[k]})
        else:
            diff.append({"diff": True, "key": k, "my": mydict.get(
                k, None), "ot": thdict.get(k, None)})

    return True, "", sorted(diff, key=lambda x: x["key"])


def clone_project(licco_db: MongoDb, userid: str, prjid: str, name: str, description: str, editors: List[str], notifier: Notifier):
    """
    Clone the existing project specified by prjid as a new project with the name and description.
    """
    super_approvers = get_users_with_privilege(licco_db, "superapprover")
    if userid in super_approvers:
        # super approvers should not be editors or owner of projects
        return False, f"Super approver is not allowed to clone the project", None

    if editors:
        for e in editors:
            if e in super_approvers:
                return False, f"Selected editor {e} is also a super approver: super approvers are not allowed to be project editors", None

    # check if a project with this name already exists
    existing_project = licco_db["projects"].find_one({"name": name})
    if existing_project:
        return False, f"Project with name {name} already exists", None

    err, created_project = create_new_project(licco_db, userid, name, description, [], notifier)
    if err:
        return False, f"Failed to create a new project: {err}", None

    # we are cloning an existing project
    myfcs = get_project_attributes(licco_db, prjid)
    modification_time = created_project["creation_time"]
    all_inserts = []

    # Check for valid content, and copy over present data
    if myfcs.items():
        for fftid, attrs in myfcs.items():
            del attrs["fft"]
            for attrname, attrval in attrs.items():
                if attrname == "discussion":
                    # when cloning a project, we also want to clone all the comments
                    # discussion is returned as an array and therefore needs special handling
                    for comment in attrval:
                        all_inserts.append({
                            "prj": created_project["_id"],
                            "fft": ObjectId(fftid),
                            "key": attrname,
                            "val": comment['comment'],
                            "user": comment['author'],
                            "time": modification_time,
                        })
                else:
                    all_inserts.append({
                        "prj": created_project["_id"],
                        "fft": ObjectId(fftid),
                        "key": attrname,
                        "val": attrval,
                        "user": userid,
                        "time": modification_time
                    })
        licco_db["projects_history"].insert_many(all_inserts)

    if editors:
        status, err = update_project_details(licco_db, userid, created_project["_id"], {'editors': editors}, notifier)
        if not status:
            # there was an error while updating editors
            # see the explanation above why we still return success (True).
            logger.error(f"Failed to update editors of a new project {prjid}: {err}")
            return True, "", created_project

    # load the project together with editors
    created_project = get_project(licco_db, created_project["_id"])
    return True, "", created_project


def update_project_details(licco_db: MongoDb, userid: str, prjid: str, user_changes: Dict[str, any], notifier: Notifier) -> Tuple[bool, str]:
    """
    Just update the project name ands description
    """
    project = get_project(licco_db, prjid)
    project_owner = project["owner"]
    user_has_permission_to_edit = project_owner == userid or userid in project["editors"]
    if not user_has_permission_to_edit:
        name = project["name"]
        return False, f"You have no permissions to edit a project '{name}'"

    if len(user_changes) == 0:
        return False, f"Project update should not be empty"

    update = {}
    for key, val in user_changes.items():
        if key == "name":
            if not val:
                return False, f"Name cannot be empty"
            update["name"] = val
        elif key == "description":
            if not val:
                return False, f"Description cannot be empty"
            update["description"] = val
        elif key == "editors":
            editors = val
            err = validate_editors(licco_db, editors, notifier)
            if err:
                return False, err

            # all users are valid (or editor's list is empty)
            # For now we only store the usernames in the editors list, since permission
            # comparison is done by comparing usernames as well. This behavior might change
            # in the future to accomodate any email (even from outside of organization)
            updated_editors = _emails_to_usernames(editors)
            update["editors"] = updated_editors
        else:
            return False, f"Invalid update field '{key}'"

    licco_db["projects"].update_one({"_id": ObjectId(prjid)}, {"$set": update})

    # send notifications if necessary
    updated_editors = "editors" in user_changes
    if notifier and updated_editors:
        old_editors = project["editors"]
        updated_editors = update["editors"]
        diff = diff_arrays(old_editors, updated_editors)

        removed_editors = diff.removed
        new_editors = diff.new
        project_name = project["name"]
        project_id = project["_id"]
        if new_editors:
            notifier.add_project_editors(new_editors, project_name, project_id)
        if removed_editors:
            notifier.remove_project_editors(removed_editors, project_name, project_id)

    return True, ""


def delete_project(licco_db: MongoDb, userid, project_id):
    """
    Delete the chosen project and all related data (history of value changes, tags).
    """
    prj = get_project(licco_db, project_id)
    if not prj:
        return False, f"Project {project_id} does not exist"

    admins = get_users_with_privilege(licco_db, "admin")
    user_is_owner = userid == prj["owner"]
    user_is_admin = userid in admins

    allowed_to_delete = user_is_owner or user_is_admin
    if not allowed_to_delete:
        return False, f"You don't have permissions to delete the project {prj['name']}"

    if user_is_admin:
        # deletion for admin role means 'delete'
        licco_db["projects"].delete_one({'_id': ObjectId(project_id)})
        licco_db["projects_history"].delete_many({'prj': ObjectId(project_id)})
        licco_db["tags"].delete_many({'prj': ObjectId(project_id)})
        return True, ""

    new_project_name = 'hidden' + '_' + prj['name'] + '_'+ datetime.date.today().strftime('%m/%d/%Y')
    # user is just the owner, delete in this case means 'hide the project'
    licco_db["projects"].update_one({'_id': ObjectId(project_id)}, {'$set': {'status': 'hidden', 'name': new_project_name}})
    return True, ""


def get_tags_for_project(licco_db: MongoDb, prjid):
    """
    Get the tags for the specified project
    """
    prj = licco_db["projects"].find_one({"_id": ObjectId(prjid)})
    if not prj:
        return False, f"Cannot find project for {prjid}", None
    tags = list(licco_db["tags"].find({"prj": ObjectId(prjid)}))
    return True, "", tags


def add_project_tag(licco_db: MongoDb, prjid, tagname, asoftimestamp):
    """
    Add a tag at the specified time for the project.
    """
    prj = licco_db["projects"].find_one({"_id": ObjectId(prjid)})
    if not prj:
        return False, f"Cannot find project for {prjid}", None

    existing_tag = licco_db["tags"].find_one({"name": tagname, "prj": ObjectId(prjid)})
    if existing_tag:
        return False, f"Tag {tagname} already exists for project {prjid}", None

    licco_db["tags"].insert_one({"prj": ObjectId(prjid), "name": tagname, "time": asoftimestamp})
    tags = list(licco_db["tags"].find({"prj": ObjectId(prjid)}))
    return True, "", tags
