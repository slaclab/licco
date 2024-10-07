'''
The model level business logic goes here.
Most of the code here gets a connection to the database, executes a query and formats the results.
'''
import logging
import datetime
import collections
from enum import Enum
import copy
import json
import math
from typing import Tuple, Dict

import pytz
import tempfile

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
    Commissioned = "Commissioned"
    ReadyForInstallation = "ReadyForInstallation"
    Installed = "Installed"
    Operational = "Operational"
    NonOperational = "NonOperational"
    Decommissioned = "Decommissioned"
    Removed = "Removed"

    def describe(self):
        return descriptions[self]

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


class UDLR(Enum):
    U = "U"
    D = "D"
    L = "L"
    R = "R"


def initialize_collections():
    if 'name_1' not in licco_db[line_config_db_name]["projects"].index_information().keys():
        licco_db[line_config_db_name]["projects"].create_index(
            [("name", ASCENDING)], unique=True, name="name_1")
    if 'owner_1' not in licco_db[line_config_db_name]["projects"].index_information().keys():
        licco_db[line_config_db_name]["projects"].create_index(
            [("owner", ASCENDING)], name="owner_1")
    if 'editors_1' not in licco_db[line_config_db_name]["projects"].index_information().keys():
        licco_db[line_config_db_name]["projects"].create_index(
            [("editors", ASCENDING)], name="editors_1")
    if 'name_1' not in licco_db[line_config_db_name]["fcs"].index_information().keys():
        licco_db[line_config_db_name]["fcs"].create_index(
            [("name", ASCENDING)], unique=True, name="name_1")
    if 'name_1' not in licco_db[line_config_db_name]["fgs"].index_information().keys():
        licco_db[line_config_db_name]["fgs"].create_index(
            [("name", ASCENDING)], unique=True, name="name_1")
    if 'fc_fg_1' not in licco_db[line_config_db_name]["ffts"].index_information().keys():
        licco_db[line_config_db_name]["ffts"].create_index(
            [("fc", ASCENDING), ("fg", ASCENDING)], unique=True, name="fc_fg_1")
    if 'prj_time_1' not in licco_db[line_config_db_name]["projects_history"].index_information().keys():
        licco_db[line_config_db_name]["projects_history"].create_index(
            [("prj", ASCENDING), ("time", DESCENDING)], name="prj_time_1")
    if 'prj_fc_time_1' not in licco_db[line_config_db_name]["projects_history"].index_information().keys():
        licco_db[line_config_db_name]["projects_history"].create_index(
            [("prj", ASCENDING), ("fft", ASCENDING), ("time", DESCENDING)], name="prj_fft_time_1")
    if 'sw_time_1' not in licco_db[line_config_db_name]["switch"].index_information().keys():
        licco_db[line_config_db_name]["switch"].create_index(
            [("switch_time", DESCENDING)], unique=True, name="sw_time_1")
    if 'name_prj_1' not in licco_db[line_config_db_name]["tags"].index_information().keys():
        licco_db[line_config_db_name]["tags"].create_index(
            [("name", ASCENDING), ("prj", ASCENDING)], unique=True, name="name_prj_1")
    if 'app_1_name_1' not in licco_db[line_config_db_name]["roles"].index_information().keys():
        licco_db[line_config_db_name]["roles"].create_index(
            [("app", ASCENDING), ("name", ASCENDING)], unique=True, name="app_1_name_1")


def get_all_users():
    """
    For now, simply return all the owners and editors of projects.
    """
    prjs = list(licco_db[line_config_db_name]
                ["projects"].find({}, {"owner": 1, "editors": 1}))
    ret = set()
    for prj in prjs:
        ret.add(prj["owner"])
        for ed in prj.get("editors", []):
            ret.add(ed)
    return list(ret)

def get_fft_name_by_id(fftid):
    """
    Return string names of both FC and FG components of FFT
    based off of a provided ID. 
    :param: fftid - the id of the FFT
    :return: Tuple of string names FC, FG
    """
    fft = licco_db[line_config_db_name]["ffts"].find_one(
        {"_id": ObjectId(fftid)})
    fc = licco_db[line_config_db_name]["fcs"].find_one(
        {"_id": fft["fc"]})
    fg = licco_db[line_config_db_name]["fgs"].find_one(
        {"_id": fft["fg"]})
    return fc["name"], fg["name"]

def get_fft_id_by_names(fc, fg):
    """
    Return ID of FFT
    based off of a provided string FC and FG names. 
    :param: fft - dict of {fc, fg} with string names of fc, fg
    :return: Tuple of ids FC, FG
    """
    fc_obj = licco_db[line_config_db_name]["fcs"].find_one(
        {"name": fc})
    fg_obj = licco_db[line_config_db_name]["fgs"].find_one(
        {"name": fg})
    fft = licco_db[line_config_db_name]["ffts"].find_one(
        {"fc": ObjectId(fc_obj["_id"]), "fg": ObjectId(fg_obj["_id"])})
    return fft["_id"]

def get_users_with_privilege(privilege):
    """
    From the roles database, get all the users with the necessary privilege. 
    For now we do not take into account group memberships. 
    We return a unique list of userid's, for example, [ "awallace", "klafortu", "mlng" ]
    """
    ret = set()
    for role in licco_db[line_config_db_name]["roles"].find({"privileges": privilege}):
        for player in role.get("players", []):
            if player.startswith("uid:"):
                ret.add(player.replace("uid:", ""))
    return sorted(list(ret))


def get_fft_values_by_project(fftid, prjid):
    """
    Return newest data connected with the provided Project and FFT
    :param fftid - the id of the FFT
    :param prjid - the id of the project
    :return: Dict of FFT Values
    """
    fft_pairings = {}
    results = list(licco_db[line_config_db_name]["projects_history"].find(
        {"prj": ObjectId(prjid), "fft": ObjectId(fftid)}).sort("time", 1))
    for res in results:
        fft_pairings[res["key"]] = res["val"]
    return fft_pairings


def get_all_projects(sort_criteria):
    """
    Return all the projects in the system.
    :return: List of projects
    """
    all_projects = list(licco_db[line_config_db_name]
                        ["projects"].find({}).sort(sort_criteria))
    return all_projects


def get_projects_for_user(username):
    """
    Return all the projects for which the user is an owner or an editor.
    :param username - the userid of the user from authn
    :return: List of projects
    """
    owned_projects = list(
        licco_db[line_config_db_name]["projects"].find({"owner": username}))
    editable_projects = list(
        licco_db[line_config_db_name]["projects"].find({"editors": username}))
    return owned_projects + editable_projects


def get_project(id):
    """
    Get the details for the project given its id.
    """
    oid = ObjectId(id)
    prj = licco_db[line_config_db_name]["projects"].find_one({"_id": oid})
    return prj


def get_project_by_name(name):
    """
    Get the details for the project given its name.
    """
    prj = licco_db[line_config_db_name]["projects"].find_one({"name": name})
    return prj


def get_project_ffts(prjid, showallentries=True, asoftimestamp=None):
    """
    Get the FFTs for a project given its id.
    """
    oid = ObjectId(prjid)
    logger.info("Looking for project details for %s", oid)
    return get_project_attributes(licco_db[line_config_db_name], prjid, skipClonedEntries=False if showallentries else True, asoftimestamp=asoftimestamp)


def get_project_changes(prjid):
    """
    Get a history of changes to the project.
    """
    oid = ObjectId(prjid)
    logger.info("Looking for project details for %s", prjid)
    return get_all_project_changes(licco_db[line_config_db_name], oid)


def get_fcs():
    """
    Get the functional component objects - typically just the name and description.
    """
    fcs = list(licco_db[line_config_db_name]["fcs"].find({}))
    fcs_used = set(licco_db[line_config_db_name]["ffts"].distinct("fc"))
    for fc in fcs:
        fc["is_being_used"] = fc["_id"] in fcs_used
    return fcs


def delete_fc(fcid):
    """
    Delete an FC if it is not currently being used by any FFT.
    """
    fcid = ObjectId(fcid)
    fcs_used = set(licco_db[line_config_db_name]["ffts"].distinct("fc"))
    if fcid in fcs_used:
        return False, "This FC is being used by an FFT", None
    logger.info(f"Deleting FC with id {str(fcid)}")
    licco_db[line_config_db_name]["fcs"].delete_one({"_id": fcid})
    return True, "", None


def get_fgs():
    """
    Get the fungible token objects - typically just the name and description.
    """
    fgs = list(licco_db[line_config_db_name]["fgs"].find({}))
    fgs_used = set(licco_db[line_config_db_name]["ffts"].distinct("fg"))
    for fg in fgs:
        fg["is_being_used"] = fg["_id"] in fgs_used

    return fgs


def delete_fg(fgid):
    """
    Delete an FG if it is not currently being used by any FFT.
    """
    fgid = ObjectId(fgid)
    fgs_used = set(licco_db[line_config_db_name]["ffts"].distinct("fg"))
    if fgid in fgs_used:
        return False, "This FG is being used by an FFT", None
    logger.info("Deleting FG with id " + str(fgid))
    licco_db[line_config_db_name]["fgs"].delete_one({"_id": fgid})
    return True, "", None


def get_ffts():
    """
    Get the functional fungible token objects.
    In addition to id's we also return the fc and fg name and description
    """
    ffts = list(licco_db[line_config_db_name]["ffts"].aggregate([
        {"$lookup": {"from": "fcs", "localField": "fc",
                     "foreignField": "_id", "as": "fc"}},
        {"$unwind": "$fc"},
        {"$lookup": {"from": "fgs", "localField": "fg",
                     "foreignField": "_id", "as": "fg"}},
        {"$unwind": "$fg"}
    ]))
    ffts_used = set(licco_db[line_config_db_name]
                    ["projects_history"].distinct("fft"))
    for fft in ffts:
        fft["is_being_used"] = fft["_id"] in ffts_used
    return ffts


def delete_fft(fftid):
    """
    Delete an FFT if it is not currently being used by any project.
    """
    fftid = ObjectId(fftid)
    ffts_used = set(licco_db[line_config_db_name]
                    ["projects_history"].distinct("fft"))
    if fftid in ffts_used:
        return False, "This FFT is being used in a project", None
    logger.info("Deleting FFT with id " + str(fftid))
    licco_db[line_config_db_name]["ffts"].delete_one({"_id": fftid})
    return True, "", None


def create_new_project(name, description, userid):
    """
    Create a new project belonging to the specified user.
    """
    newprjid = licco_db[line_config_db_name]["projects"].insert_one({"name": name, "description": description, "owner": userid, "editors": [
    ], "status": "development", "creation_time": datetime.datetime.utcnow()}).inserted_id
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
        fcid = licco_db[line_config_db_name]["fcs"].insert_one(
            {"name": name, "description": description}).inserted_id
        return True, "", licco_db[line_config_db_name]["fcs"].find_one({"_id": fcid})
    except Exception as e:
        return False, str(e), None


def create_new_fungible_token(name, description):
    """
    Create a new fungible token
    """
    if not name:
        name = ""
    if not description:
        return False, "The description is a required field", None
    if licco_db[line_config_db_name]["fgs"].find_one({"name": name}):
        return False, f"Fungible token {name} already exists", None
    try:
        fgid = licco_db[line_config_db_name]["fgs"].insert_one(
            {"name": name, "description": description}).inserted_id
        return True, "", licco_db[line_config_db_name]["fgs"].find_one({"_id": fgid})
    except Exception as e:
        return False, str(e), None


def create_new_fft(fc, fg, fcdesc=None, fgdesc=None):
    """
    Create a new functional component + fungible token based on their names
    If the FC or FT don't exist; these are created if the associated descriptions are also passed in.
    """
    logger.info("Creating new fft with %s and %s", fc, fg)
    fcobj = licco_db[line_config_db_name]["fcs"].find_one({"name": fc})
    if not fcobj:
        if not fcdesc:
            return False, f"Could not find functional component {fc}", None
        else:
            logger.debug(f"Creating a new FC as part of creating an FFT {fc}")
            _, _, fcobj = create_new_functional_component(fc, fcdesc)
    if not fg:
        fg = ""
        fgdesc = "The default null fg to accommodate outer joins"
    fgobj = licco_db[line_config_db_name]["fgs"].find_one({"name": fg})
    if not fgobj:
        if not fgdesc:
            return False, f"Could not find fungible token with id {fg}", None
        else:
            logger.debug(f"Creating a new FG as part of creating an FFT {fg}")
            _, _, fgobj = create_new_fungible_token(fg, fgdesc)
    if licco_db[line_config_db_name]["ffts"].find_one({"fc": ObjectId(fcobj["_id"]), "fg": fgobj["_id"]}):
        return False, f"FFT with {fc}-{fg} has already been registered", None

    try:
        fftid = licco_db[line_config_db_name]["ffts"].insert_one(
            {"fc": fcobj["_id"], "fg": fgobj["_id"]}).inserted_id
        fft = licco_db[line_config_db_name]["ffts"].find_one({"_id": fftid})
        fft["fc"] = licco_db[line_config_db_name]["fcs"].find_one(
            {"_id": fft["fc"]})
        fft["fg"] = licco_db[line_config_db_name]["fgs"].find_one(
            {"_id": fft["fg"]})
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


# We could perhaps use dataclasses here but we're not really storing the document as it is.
# So, let's try explicit metadata for the fc attrs
fcattrs = {
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
    "nom_dim_z": {
        "name": "nom_dim_z",
        "type": "text",
        "fromstr": default_wrapper(str2float, ""),
        "rendermacro": "prec7float",
        "label": "Z",
        "category": {"label": "Nominal Dimension (meters)", "span": 3},
        "desc": "Nominal Dimension Z",
        "required": False,
        "is_required_dimension": False
    },
    "nom_dim_x": {
        "name": "nom_dim_x",
        "type": "text",
        "fromstr": default_wrapper(str2float, ""),
        "rendermacro": "prec7float",
        "label": "X",
        "category": {"label": "Nominal Dimension (meters)"},
        "desc": "Nominal Dimension X",
        "required": False,
        "is_required_dimension": False
    },
    "nom_dim_y": {
        "name": "nom_dim_y",
        "type": "text",
        "fromstr": default_wrapper(str2float, ""),
        "rendermacro": "prec7float",
        "label": "Y",
        "category": {"label": "Nominal Dimension (meters)"},
        "desc": "Nominal Dimension Y",
        "required": False,
        "is_required_dimension": False
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
    }
}


def get_fcattrs(fromstr=False):
    """
    Return the FC attribute metadata.
    Since functions cannot be serialized into JSON, 
    we make a copy and delete the fromstr and other function parts
    """
    fcattrscopy = copy.deepcopy(fcattrs)
    if not fromstr:
        for k, v in fcattrscopy.items():
            del v["fromstr"]
    return fcattrscopy


def update_fft_in_project(prjid, fftid, fcupdate, userid,
                          modification_time=None,
                          current_project_attributes=None) -> Tuple[bool, str, Dict[str, int]]:
    """
    Update the value(s) of an FFT in a project
    Returns: a tuple containing (success flag (true/false if error), error message (if any), and an insert count
    """
    insert_count = {"success": 0, "fail": 0, "ignored": 0}
    prj = licco_db[line_config_db_name]["projects"].find_one(
        {"_id": ObjectId(prjid)})
    if not prj:
        return False, f"Cannot find project for {prjid}", insert_count
    fft = licco_db[line_config_db_name]["ffts"].find_one(
        {"_id": ObjectId(fftid)})
    if not fft:
        return False, f"Cannot find functional+fungible token for {fftid}", insert_count

    current_attrs = current_project_attributes
    if current_attrs is None:
        # NOTE: current_project_attributes should be provided when lots of ffts are updated at the same time, e.g.:
        # for 100 ffts, we shouldn't query the entire project attributes 100 times as that is very slow
        # (cca 150-300 ms per query).
        current_attrs = get_project_attributes(
            licco_db[line_config_db_name], ObjectId(prjid)).get(str(fftid), {})

    if not modification_time:
        modification_time = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
    # Make sure the timestamp on this server is monotonically increasing.
    latest_changes = list(licco_db[line_config_db_name]["projects_history"].find(
        {}).sort([("time", -1)]).limit(1))
    if latest_changes:
        if modification_time < latest_changes[0]["time"]:
            return False, f"The time on this server {modification_time.isoformat()} is before the most recent change from the server {latest_changes[0]['time'].isoformat()}", insert_count

    if "state" in fcupdate and fcupdate["state"] != "Conceptual":
        for attrname, attrmeta in fcattrs.items():
            if (attrmeta.get("is_required_dimension") is True) and ((current_attrs.get(attrname, None) is None) and (fcupdate[attrname] is None)):
                return False, "FFTs should remain in the Conceptual state while the dimensions are still being determined.", insert_count

    error_str = ""
    all_inserts = []
    fft_edits = set()
    for attrname, attrval in fcupdate.items():
        if attrname == "fft":
            continue
        attrmeta = fcattrs[attrname]
        if attrmeta["required"] and not attrval:
            return False, f"Parameter {attrname} is a required attribute", insert_count
        try:
            newval = attrmeta["fromstr"](attrval)
        except ValueError:
            # <FFT>, <field>, invalid input rejected: [Wrong type| Out of range]
            insert_count["fail"] += 1
            error_str = f"Wrong type - {attrname}, {attrval}"
            break
        # Check that values are within bounds
        if not validate_insert_range(attrname, newval):
            insert_count["fail"] += 1
            error_str = f"Value out of range - {attrname}, {attrval}"
            break
        prevval = current_attrs.get(attrname, None)
        if prevval != newval:
            all_inserts.append({
                "prj": ObjectId(prjid),
                "fft": ObjectId(fftid),
                "key": attrname,
                "val": newval,
                "user": userid,
                "time": modification_time
            })
            fft_edits.add(ObjectId(fftid))

    #If one of the fields is invalid, and we have an error
    if error_str != "":
        return False, error_str, insert_count
    if all_inserts:
        logger.debug("Inserting %s documents into the history", len(all_inserts))
        insert_count["success"] += 1
        licco_db[line_config_db_name]["projects_history"].insert_many(all_inserts)
    else:
        insert_count["ignored"] += 1
        logger.debug("In update_fft_in_project, all_inserts is an empty list")
        error_str = "No changes detected."
        return True, error_str, insert_count
    return True, error_str, insert_count


def validate_insert_range(attr, val):
    """
    Helper function to validate data prior to being saved in DB
    """
    try:
        if attr == "ray_trace":
            if val == '' or val is None:
                return True
            return bool(int(val) >= 0)
        # empty strings valid for angles, catch before other verifications
        if "nom" in attr:
            if val == "":
                return True
            if attr == "nom_loc_z":
                if float(val) < 0 or float(val) > 2000:
                    return False
            if "nom_ang_" in attr:
                if (float(val) > math.pi) or (float(val) < -(math.pi)):
                    return False
    except ValueError:
        logger.debug(f'Value {val} wrong type for attribute {attr}.')
        return False
    except TypeError:
        logger.debug(f'Value {val} not verified for attribute {attr}.')
        return False
    return True


def copy_ffts_from_project(srcprjid, destprjid, fftid, attrnames, userid):
    """
    Copy values for the fftid from srcprjid into destprjid for the specified attrnames
    """
    srcprj = licco_db[line_config_db_name]["projects"].find_one(
        {"_id": ObjectId(srcprjid)})
    if not srcprj:
        return False, f"Cannot find project for {srcprj}", None
    destprj = licco_db[line_config_db_name]["projects"].find_one(
        {"_id": ObjectId(destprjid)})
    if not destprj:
        return False, f"Cannot find project for {destprjid}", None
    fft = licco_db[line_config_db_name]["ffts"].find_one(
        {"_id": ObjectId(fftid)})
    if not fft:
        return False, f"Cannot find FFT for {fftid}", None

    modification_time = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
    # Make sure the timestamp on this server is monotonically increasing.
    latest_changes = list(licco_db[line_config_db_name]["projects_history"].find(
        {}).sort([("time", -1)]).limit(1))
    if latest_changes:
        if modification_time < latest_changes[0]["time"]:
            return False, f"The time on this server {modification_time.isoformat()} is before the most recent change from the server {latest_changes[0]['time'].isoformat()}", None

    current_attrs = get_project_attributes(
        licco_db[line_config_db_name], ObjectId(destprjid))
    fftattrs = current_attrs.get(fftid, {})
    other_attrs = get_project_attributes(
        licco_db[line_config_db_name], ObjectId(srcprjid))
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
    licco_db[line_config_db_name]["projects_history"].insert_many(all_inserts)

    return True, "", get_project_attributes(licco_db[line_config_db_name], ObjectId(destprjid)).get(fftid, {})


def submit_project_for_approval(prjid, userid, approver):
    """
    Submit a project for approval.
    Set the status to submitted
    """
    prj = licco_db[line_config_db_name]["projects"].find_one(
        {"_id": ObjectId(prjid)})
    if not prj:
        return False, f"Cannot find project for {prjid}", None
    if prj["status"] != "development":
        return False, f"Project {prjid} is not in development status", None
    licco_db[line_config_db_name]["projects"].update_one({"_id": prj["_id"]}, {"$set": {
                                                         "status": "submitted", "submitter": userid, "approver": approver, "submitted_time": datetime.datetime.utcnow()}})
    return True, "", prj


def approve_project(prjid, userid):
    """
    Approve a submitted project.
    Set the status to approved
    """
    prj = licco_db[line_config_db_name]["projects"].find_one(
        {"_id": ObjectId(prjid)})
    approved = get_currently_approved_project()
    if not prj:
        return False, f"Cannot find project for {prjid}", None
    if prj["status"] != "submitted":
        return False, f"Project {prjid} is not in submitted status", None
    if prj["submitter"] == userid:
        return False, f"Project {prj['name']} cannot be approved by its submitter {userid}. Please ask someone other than the submitter to approve the project", None
    # update the most recent approved time
    licco_db[line_config_db_name]["projects"].update_one({"_id": approved["_id"]}, {"$set": {
                                                         "approver": userid, "approved_time": datetime.datetime.utcnow()}})
    # change the project status to development instead of submitted
    licco_db[line_config_db_name]["projects"].update_one({"_id": prj["_id"]}, {"$set": {
                                                         "status": "development", "approver": userid, "approved_time": datetime.datetime.utcnow()}})
    return True, f"Project {prj['name']} approved by {prj['submitter']}.", prj


def reject_project(prjid, userid, reason):
    """
    Do not approve a submitted project.
    Set the status to development
    """
    prj = licco_db[line_config_db_name]["projects"].find_one(
        {"_id": ObjectId(prjid)})
    if not prj:
        return False, f"Cannot find project for {prjid}", None
    if prj["status"] != "submitted":
        return False, f"Project {prjid} is not in submitted status", None
    licco_db[line_config_db_name]["projects"].update_one({"_id": prj["_id"]}, {"$set": {
                                                         "status": "development", "approver": userid, "approved_time": datetime.datetime.utcnow(), "notes": [reason] + prj.get("notes", [])}})
    return True, "", prj


def get_currently_approved_project_by_switch():
    """
    Get the current approved project.
    This is really the most recently approved project
    """
    prjs = list(licco_db[line_config_db_name]["switch"].find(
        {}).sort([("switch_time", -1)]).limit(1))
    if prjs:
        current_id = prjs[0]["prj"]
        return licco_db[line_config_db_name]["projects"].find_one({"_id": current_id})
    return None

def get_currently_approved_project():
    """
    Get the current approved project by status
    """
    prj = licco_db[line_config_db_name]["projects"].find_one(
        {"status": "approved"})
    return prj if prj else None

def get_projects_approval_history():
    """
    Get the history of project approvals
    """
    hist = list(licco_db[line_config_db_name]["switch"].aggregate([
        {"$sort": {"switch_time": -1}},
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

def get_projects_recent_edit_time():
    """
    Gets the most recent time of edit for all projects in development status
    """
    edit_list = {}
    projects = licco_db[line_config_db_name]["projects"].find()
    for project in projects:
        most_recent = licco_db[line_config_db_name]["projects_history"].find_one(
        {"prj":ObjectId(project["_id"])}, {"time": 1 }, sort=[("time", DESCENDING )])
        if not most_recent:
            most_recent = {"_id": "", "time": ""}
        edit_list[project["_id"]] = most_recent
    return edit_list


def __flatten__(obj, prefix=""):
    """
    Flatten a dict into a list of key value pairs using dot notation.
    """
    ret = []
    if isinstance(obj, collections.abc.Mapping):
        for k, v in obj.items():
            ret.extend(__flatten__(v, prefix + "." + k if prefix else k))
    elif isinstance(obj, list):
        for c, e in enumerate(obj):
            ret.extend(__flatten__(
                e, prefix + ".[" + str(c) + "]" if prefix else "[" + str(c) + "]"))
    else:
        ret.append((prefix, obj))
    return ret


def __replace_fc__(fcs):
    """
    Replace the object id for the FC with the FC's name for readibility
    """
    ret = {}
    for k, v in fcs.items():
        if isinstance(v, collections.abc.Mapping):
            ret[v["name"]] = v
        else:
            ret[k] = v
    return ret


def diff_project(prjid, other_prjid, userid, approved=False):
    """
    Diff two projects
    """
    prj = licco_db[line_config_db_name]["projects"].find_one(
        {"_id": ObjectId(prjid)})
    if not prj:
        return False, f"Cannot find project for {prjid}", None

    otr = licco_db[line_config_db_name]["projects"].find_one(
        {"_id": ObjectId(other_prjid)})
    if not otr:
        return False, f"Cannot find project for {other_prjid}", None

    myfcs = get_project_attributes(licco_db[line_config_db_name], prjid)
    thfcs = get_project_attributes(licco_db[line_config_db_name], other_prjid)

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


def clone_project(prjid, name, description, userid, new=False):
    """
    Clone the existing project specified by prjid as a new project with the name and description.
    """
    if new != True:
        prj = licco_db[line_config_db_name]["projects"].find_one(
            {"_id": ObjectId(prjid)})
        if not prj:
            return False, f"Cannot find project for {prjid}", None

    otr = licco_db[line_config_db_name]["projects"].find_one({"name": name})
    if otr:
        return False, f"Project with {name} already exists", None

    newprj = create_new_project(name, description, userid)
    if not newprj:
        return False, "Created a project but could not get the object from the database", None

    if new == True:
        return True, "", newprj

    myfcs = get_project_attributes(licco_db[line_config_db_name], prjid)

    modification_time = newprj["creation_time"]
    all_inserts = []
    for fftid, attrs in myfcs.items():
        del attrs["fft"]
        for attrname, attrval in attrs.items():
            all_inserts.append({
                "prj": newprj["_id"],
                "fft": ObjectId(fftid),
                "key": attrname,
                "val": attrval,
                "user": userid,
                "time": modification_time
            })
    licco_db[line_config_db_name]["projects_history"].insert_many(all_inserts)

    return True, "", newprj


def create_empty_project(name, description, logged_in_user):
    """
    Empty project with name project name ands description
    """
    prjid = licco_db[line_config_db_name]["projects"].insert_one({"name": name, "description": description, "owner": logged_in_user, "editors": [
    ], "status": "development", "creation_time": datetime.datetime.utcnow()}).inserted_id
    return get_project(prjid)


def update_project_details(prjid, prjdetails):
    """
    Just update the project name ands description
    """
    licco_db[line_config_db_name]["projects"].update_one({"_id": ObjectId(prjid)}, {
                                                         "$set": {"name": prjdetails["name"], "description": prjdetails["description"]}})
    return True


def get_tags_for_project(prjid):
    """
    Get the tags for the specified project
    """
    prj = licco_db[line_config_db_name]["projects"].find_one(
        {"_id": ObjectId(prjid)})
    if not prj:
        return False, f"Cannot find project for {prjid}", None
    tags = list(licco_db[line_config_db_name]
                ["tags"].find({"prj": ObjectId(prjid)}))
    return True, "", tags


def add_project_tag(prjid, tagname, asoftimestamp):
    """
    Add a tag at the specified time for the project.
    """
    prj = licco_db[line_config_db_name]["projects"].find_one(
        {"_id": ObjectId(prjid)})
    if not prj:
        return False, f"Cannot find project for {prjid}", None

    extsting_tag = licco_db[line_config_db_name]["tags"].find_one({
                                                                  "name": tagname})
    if extsting_tag:
        return False, f"Tag {tagname} already exists for project {prjid}", None

    licco_db[line_config_db_name]["tags"].insert_one(
        {"prj": ObjectId(prjid), "name": tagname, "time": asoftimestamp})
    tags = list(licco_db[line_config_db_name]
                ["tags"].find({"prj": ObjectId(prjid)}))
    return True, "", tags
