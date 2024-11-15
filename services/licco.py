'''
Web service endpoints for licco
'''
import csv
import json
import logging
import os
import fnmatch
import re
from io import BytesIO, StringIO
from datetime import datetime
from typing import Tuple, Dict

import pytz
import tempfile
from functools import wraps
import context

from flask import Blueprint, request, Response, send_file, render_template

from dal.utils import JSONEncoder
from dal.licco import get_fcattrs, get_project, get_project_ffts, get_fcs, \
    create_new_functional_component, update_fft_in_project, submit_project_for_approval, approve_project, \
    get_currently_approved_project, diff_project, FCState, clone_project, get_project_changes, \
    get_tags_for_project, add_project_tag, get_all_projects, get_all_users, update_project_details, get_project_by_name, \
    create_empty_project, reject_project, copy_ffts_from_project, get_fgs, create_new_fungible_token, get_ffts, \
    create_new_fft, \
    get_projects_approval_history, delete_fft, delete_fc, delete_fg, get_project_attributes, validate_insert_range, \
    get_fft_values_by_project, \
    get_users_with_privilege, get_fft_name_by_id, get_fft_id_by_names, get_projects_recent_edit_time

__author__ = 'mshankar@slac.stanford.edu'

licco_ws_blueprint = Blueprint('business_service_api', __name__)

logger = logging.getLogger(__name__)

KEYMAP = {
    # Column names defined in confluence
    "FC": "fc",
    "Fungible": "fg",
    "TC_part_no": "tc_part_no",
    "State": "state",
    "Comments": "comments",
    "LCLS_Z_loc": "nom_loc_z",
    "LCLS_X_loc": "nom_loc_x",
    "LCLS_Y_loc": "nom_loc_y",
    "Z_dim": "nom_dim_z",
    "X_dim": "nom_dim_x",
    "Y_dim": "nom_dim_y",
    "LCLS_Z_roll": "nom_ang_z",
    "LCLS_X_pitch": "nom_ang_x",
    "LCLS_Y_yaw": "nom_ang_y",
    "Must_Ray_Trace": "ray_trace"
}
KEYMAP_REVERSE = {value: key for key, value in KEYMAP.items()}


def logAndAbort(error_msg, ret_status=500):
    logger.error(error_msg)
    return Response(error_msg, status=ret_status)


def project_writable(wrapped_function):
    """
    Decorator to make sure the project is in a development state and can be written to.
    Assumes that the id of the project is called prjid.
    """
    @wraps(wrapped_function)
    def function_interceptor(*args, **kwargs):
        prjid = kwargs.get('prjid', None)
        if not prjid:
            raise Exception("Need to specify project id")
        prj = get_project(prjid)
        if not prj:
            raise Exception(f"Project with id {prjid} does not exist")
        if prj.get("status", "N/A") == "development":
            return wrapped_function(*args, **kwargs)
        raise Exception(
            f"Project with id {prjid} is not in development status")
    return function_interceptor


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


def update_ffts_in_project(prjid, ffts, def_logger=None) -> Tuple[bool, str, Dict[str, int]]:
    """
    Insert multiple FFTs into a project
    """
    if def_logger is None:
        def_logger = logger
    userid = context.security.get_current_user_id()
    update_status = {"success": 0, "fail": 0, "ignored": 0}
    if isinstance(ffts, dict):
        new_ffts = []
        for entry in ffts:
            new_ffts.append(ffts[entry])
        ffts = new_ffts

    project_ffts = get_project_ffts(prjid)

    # Iterate through parameter fft set
    for fft in ffts:
        if "_id" not in fft:
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
                fft["_id"] = get_fft_id_by_names(fc=fft["fc"], fg=fft["fg"])
        fftid = fft["_id"]
        # previous values
        db_values = get_fft_values_by_project(fft["_id"], prjid)
        fcupdate = {}
        fcupdate.update(fft)
        if ("state" not in fcupdate) or (not fcupdate["state"]):
            if "state" in db_values:
                fcupdate["state"] = db_values["state"]
            else:
                fcupdate["state"] = "Conceptual"
        # If invalid, don't try to add to DB
        status, errormsg = validate_import_headers(fcupdate, prjid, fftid)
        if not status:
            update_status["fail"] += 1
            def_logger.info(create_imp_msg(fft, False, errormsg=errormsg))
            continue
        for attr in ["_id", "name", "fc", "fg", "fft"]:
            if attr in fcupdate:
                del fcupdate[attr]

        # Performance: when updating fft in a project, we used to do hundreds of database calls
        # which was very slow. An import of a few ffts took 10 seconds. We speed this up, by
        # querying the current project attributes once and passing it to the update routine
        current_attributes = project_ffts.get(str(fftid), {})
        status, errormsg, results = update_fft_in_project(prjid, fftid, fcupdate, userid,
                                                          current_project_attributes=current_attributes)
        # Have smarter error handling here for different exit conditions
        def_logger.info(create_imp_msg(fft, status=status, errormsg=errormsg))

        # Add the individual FFT update results into overall count
        if results:
            update_status = {k: update_status[k]+results[k]
                             for k in update_status.keys()}

    # BUG: error message is not declared anywhere, so it will always be None or set to the last value
    # that comes out of fft update loop
    return True, errormsg, update_status


def validate_import_headers(fft, prjid, fftid=None):
    """
    Helper function to pre-validate that all required data is present
    """
    attrs = get_fcattrs(fromstr=True)
    if not fftid:
        fftid = fft["_id"]
    db_values = get_fft_values_by_project(fftid, prjid)
    if not "state" in fft:
        fft["state"] = db_values["state"]
    for header in attrs:
        # If header is required for all, or if the FFT is non-conceptual and header is required
        if attrs[header]["required"] or ((fft["state"] != "Conceptual") and ("is_required_dimension" in attrs[header] and attrs[header]["is_required_dimension"] == True)):
            # If required header not present in upload dataset
            if not header in fft:
                # Check if in DB already, continue to validate next if so
                if header not in db_values:
                    error_str = f"Missing Required Header {header}"
                    logger.debug(error_str)
                    return False, error_str
                fft[header] = db_values[header]
            # Header is a required value, but user is trying to null this value
            if (fft[header] == ''):
                error_str = f"Header {header} Value Required for a Non-Conceptual Device"
                logger.debug(error_str)
                return False, error_str

        # Header not in data
        if not header in fft:
            continue
        try:
            val = attrs[header]["fromstr"](fft[header])
        except (ValueError, KeyError) as e:
            error_str = f"Invalid Data {fft[header]} For Type of {header}."
            return False, error_str
    return True, "Success"

def create_status_update(prj_name, status):
    """
    Helper function to make the import status message based on the dictionary results
    """
    line_brk = "_"*40
    status_str = '\n'.join([
        f'{line_brk}',
        f'Summary of Results:',
        f'Project Name: {prj_name}.',
        f'Valid headers recognized: {status["headers"]}.',
        f'{line_brk}',
        f'Successful row imports: {status["success"]}.',
        f'Failed row imports: {status["fail"]}.',
        f'Ignored row imports: {status["ignored"]}.',
    ])
    return status_str

def create_logger(logname):
    """
    Create and return a logger that writes to a provided file
    """
    dir_path = f"{tempfile.gettempdir()}/mcd"
    if not os.path.exists(dir_path):
        os.mkdir(dir_path)
    # create a file 
    handler = logging.FileHandler(f'{dir_path}/{logname}.log')
    logger.debug(f"Creating log file {dir_path}/{logname}.log")

    new_logger = logging.getLogger(logname)
    new_logger.addHandler(handler)
    new_logger.propagate = False
    return new_logger, handler

@licco_ws_blueprint.route("/enums/<enumName>", methods=["GET"])
@context.security.authentication_required
def svc_get_enum_descriptions(enumName):
    """
    Get the labels and descriptions for the specified enum
    """
    emumMappings = {
        "FCState": FCState
    }
    descs = emumMappings[enumName].descriptions()
    return JSONEncoder().encode({"success": True, "value": {k.value: v for k, v in descs.items()}})


@licco_ws_blueprint.route("/fcattrs/", methods=["GET"])
@context.security.authentication_required
def svc_get_fcattrs():
    """
    Get the metadata for the attributes for the functional components
    """
    return JSONEncoder().encode({"success": True, "value": get_fcattrs()})


@licco_ws_blueprint.route("/users/", methods=["GET"])
@context.security.authentication_required
def svc_get_users():
    """
    Get the users in the system.
    For now, this is simply the owners of projects.
    """
    logged_in_user = context.security.get_current_user_id()
    users = get_all_users()
    return JSONEncoder().encode({"success": True, "value": users})

@licco_ws_blueprint.route("/approvers/", methods=["GET"])
@context.security.authentication_required
def svc_get_users_with_approve_privilege():
    """
    Get the users in the system who have the approve privilege
    """
    users = get_users_with_privilege("approve")
    return JSONEncoder().encode({"success": True, "value": users})


@licco_ws_blueprint.route("/projects/", methods=["GET"])
@context.security.authentication_required
def svc_get_projects_for_user():
    """
    Get the projects for a user
    """
    logged_in_user = context.security.get_current_user_id()
    sort_criteria = json.loads(
        request.args.get("sort", '[["start_time", -1]]'))
    projects = get_all_projects(sort_criteria)
    edits = get_projects_recent_edit_time()
    for project in projects:
        project["edit_time"] = edits[(project["_id"])]["time"]
    if sort_criteria[0][0] == "edit_time":
        reverse = (sort_criteria[0][1] == -1)
        min_date = datetime.min.replace(tzinfo=pytz.UTC)
        projects = sorted(projects, key=lambda d: d['edit_time'] or min_date, reverse=reverse)
    return JSONEncoder().encode({"success": True, "value": projects})


@licco_ws_blueprint.route("/approved/", methods=["GET"])
@context.security.authentication_required
def svc_get_currently_approved_project():
    """ Get the currently approved project """
    logged_in_user = context.security.get_current_user_id()
    prj = get_currently_approved_project()
    if not prj:
        return JSONEncoder().encode({"success": False, "value": None})
    prj_ffts = get_project_ffts(prj["_id"])
    prj["ffts"] = prj_ffts
    return JSONEncoder().encode({"success": True, "value": prj})


@licco_ws_blueprint.route("/projects/<prjid>/", methods=["GET"])
@context.security.authentication_required
def svc_get_project(prjid):
    """
    Get the project details given a project id.
    """
    logged_in_user = context.security.get_current_user_id()
    project_details = get_project(prjid)
    return JSONEncoder().encode({"success": True, "value": project_details})


@licco_ws_blueprint.route("/projects/", methods=["POST"])
@context.security.authentication_required
def svc_create_project():
    """
    Create an empty project; do we really have a use case for this?
    """
    logged_in_user = context.security.get_current_user_id()
    prjdetails = request.json
    if not prjdetails.get("name", None):
        return JSONEncoder().encode({"success": False, "errormsg": "Name cannot be empty"})
    if not prjdetails.get("description", None):
        return JSONEncoder().encode({"success": False, "errormsg": "Description cannot be empty"})

    prj = create_empty_project(
        prjdetails["name"], prjdetails["description"], logged_in_user)
    return JSONEncoder().encode({"success": True, "value": prj})


@licco_ws_blueprint.route("/projects/<prjid>/", methods=["POST"])
@context.security.authentication_required
def svc_update_project(prjid):
    """
    Get the project details given a project id.
    """
    logged_in_user = context.security.get_current_user_id()
    prjdetails = request.json
    if not prjdetails.get("name", None):
        return JSONEncoder().encode({"success": False, "errormsg": "Name cannot be empty"})
    if not prjdetails.get("description", None):
        return JSONEncoder().encode({"success": False, "errormsg": "Description cannot be empty"})

    update_project_details(prjid, prjdetails)
    return JSONEncoder().encode({"success": True, "value": get_project(prjid)})


@licco_ws_blueprint.route("/projects/<prjid>/ffts/", methods=["GET"])
@context.security.authentication_required
def svc_get_project_ffts(prjid):
    """
    Get the project's FFT's given a project id.
    """
    logged_in_user = context.security.get_current_user_id()
    showallentries = json.loads(request.args.get("showallentries", "true"))
    asoftimestampstr = request.args.get("asoftimestamp", None)
    if asoftimestampstr:
        asoftimestamp = datetime.strptime(
            asoftimestampstr, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=pytz.UTC)
    else:
        asoftimestamp = None
    project_fcs = get_project_ffts(
        prjid, showallentries=showallentries, asoftimestamp=asoftimestamp)

    def __filter__(f, d):
        """ Apply f onto d as a filter """
        r = {}
        for k, v in d.items():
            if f(k, v):
                r[k] = v
        return r
    filt2fn = {
        "fc": lambda _, v: fnmatch.fnmatch(v.get("fft", {}).get("fc", ""), request.args["fc"]),
        "fg": lambda _, v: fnmatch.fnmatch(v.get("fft", {}).get("fg", ""), request.args["fg"]),
        "state": lambda _, v: v["state"] == request.args["state"]
    }
    for attrname, lmda in filt2fn.items():
        if request.args.get(attrname, None):
            logger.info("Applying filter for " + attrname +
                        " " + request.args.get(attrname, ""))
            project_fcs = __filter__(lmda, project_fcs)

    return JSONEncoder().encode({"success": True, "value": project_fcs})


@licco_ws_blueprint.route("/projects/<prjid>/changes/", methods=["GET"])
@context.security.authentication_required
def svc_get_project_changes(prjid):
    """
    Get the functional component objects
    """
    changes = get_project_changes(prjid)
    return JSONEncoder().encode({"success": True, "value": changes})


@licco_ws_blueprint.route("/fcs/", methods=["GET"])
@context.security.authentication_required
def svc_get_fcs():
    """
    Get the functional component objects
    """
    fcs = get_fcs()
    return JSONEncoder().encode({"success": True, "value": fcs})


@licco_ws_blueprint.route("/fgs/", methods=["GET"])
@context.security.authentication_required
def svc_get_fgs():
    """
    Get the fungible tokens
    """
    fgs = get_fgs()
    return JSONEncoder().encode({"success": True, "value": fgs})


@licco_ws_blueprint.route("/ffts/", methods=["GET"])
@context.security.authentication_required
def svc_get_ffts():
    """
    Get a list of functional fungible tokens
    """
    ffts = get_ffts()
    return JSONEncoder().encode({"success": True, "value": ffts})


@licco_ws_blueprint.route("/fcs/", methods=["POST"])
@context.security.authentication_required
def svc_create_fc():
    """
    Create a functional component
    """
    newfc = request.json
    status, errormsg, fc = create_new_functional_component(
        name=newfc.get("name", ""), description=newfc.get("description", ""))
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": fc})


@licco_ws_blueprint.route("/fgs/", methods=["POST"])
@context.security.authentication_required
def svc_create_fg():
    """
    Create a fungible token
    """
    newfg = request.json
    status, errormsg, fg = create_new_fungible_token(
        name=newfg.get("name", ""), description=newfg.get("description", ""))
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": fg})


@licco_ws_blueprint.route("/ffts/", methods=["POST"])
@context.security.authentication_required
def svc_create_fft():
    """
    Create a new functional fungible token.
    For now, we expect the ID's of the functional component and the fungible token ( and not the names )
    """
    newfft = request.json
    status, errormsg, fft = create_new_fft(fc=newfft["fc"], fg=newfft["fg"], fcdesc=newfft.get(
        "fc_description", None), fgdesc=newfft.get("fg_description", None))
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": fft})


@licco_ws_blueprint.route("/ffts/<fftid>", methods=["DELETE"])
@context.security.authentication_required
def svc_delete_fft(fftid):
    """
    Delete a FFT if it is not being used in any project
    """
    status, errormsg, _ = delete_fft(fftid)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": None})


@licco_ws_blueprint.route("/fcs/<fcid>", methods=["DELETE"])
@context.security.authentication_required
def svc_delete_fc(fcid):
    """
    Delete a FC if it is not being used by an FFT
    """
    status, errormsg, _ = delete_fc(fcid)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": None})


@licco_ws_blueprint.route("/fgs/<fgid>", methods=["DELETE"])
@context.security.authentication_required
def svc_delete_fg(fgid):
    """
    Delete a FG if it is not being used by an FFT
    """
    status, errormsg, _ = delete_fg(fgid)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": None})


@licco_ws_blueprint.route("/projects/<prjid>/fcs/<fftid>", methods=["POST"])
@context.security.authentication_required
@project_writable
def svc_update_fc_in_project(prjid, fftid):
    """
    Update the values of a functional component in a project
    """
    fcupdate = request.json
    userid = context.security.get_current_user_id()
    status, msg = validate_import_headers(fcupdate, prjid, fftid)
    if not status:
        return JSONEncoder().encode({"success": False, "errormsg": msg})
    status, errormsg, results = update_fft_in_project(prjid, fftid, fcupdate, userid)
    fc = get_project_ffts(prjid)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": fc})


@licco_ws_blueprint.route(
    "/projects/<prjid>/ffts/<fftid>/copy_from_project", methods=["POST"])
@context.security.authentication_required
@project_writable
def svc_sync_fc_from_approved_in_project(prjid, fftid):
    """
    Update the values of an FFT in this project from the specified project.
    Most of the time this is the currently approved project.
    Pass in a JSON with
    :param: other_id - Project id of the other project
    "param: attrnames - List of attribute names to copy over. If this is a string "ALL", then all the attributes that are set are copied over.
    """
    userid = context.security.get_current_user_id()
    reqparams = request.json
    logger.info(reqparams)
    status, errormsg, fc = copy_ffts_from_project(destprjid=prjid, srcprjid=reqparams["other_id"], fftid=fftid, attrnames=[
        x["name"] for x in get_fcattrs()] if reqparams["attrnames"] == "ALL" else reqparams["attrnames"], userid=userid)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": fc})


@licco_ws_blueprint.route("/projects/<prjid>/ffts/", methods=["POST"])
@project_writable
@context.security.authentication_required
def svc_update_ffts_in_project(prjid):
    """
    Insert multiple FFTs into a project
    """
    ffts = request.json
    if isinstance(ffts, dict):
        ffts = [ffts]
    status, errormsg, update_status = update_ffts_in_project(prjid, ffts)
    fft = get_project_ffts(prjid)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": fft})


@licco_ws_blueprint.route("/projects/<prjid>/import/", methods=["POST"])
@project_writable
@context.security.authentication_required
def svc_import_project(prjid):
    """
    Import project data from csv file
    """
    prj_name = get_project(prjid)["name"]
    status_str = f'Import Results for:  {prj_name}\n'
    status_val = {"headers": 0, "fail": 0, "success": 0, "ignored": 0}

    with BytesIO() as stream:
        request.files['file'].save(stream)
        try:
            filestring = stream.getvalue().decode("utf-8", "ignore")
        except UnicodeDecodeError as e:
            error_msg = "Import Rejected: File not fully in Unicode (utf-8) Format."
            logger.debug(error_msg)
            return {"status_str": error_msg, "log_name": None}

    with StringIO(filestring) as fp:
        fp.seek(0)
        # Find the header row
        loc = 0
        req_headers = False
        for line in fp:
            if 'FC' in line and 'Fungible' in line:
                if not "," in line:
                    continue
                req_headers = True
                break
            loc = fp.tell()

        # Ensure FC and FG (required headers) are present
        if not req_headers:
            error_msg = "Import Rejected: FC and Fungible headers are required in a CSV format for import."
            logger.debug(error_msg)
            return {"status_str": error_msg, "log_name": None}

        # Set reader at beginning of header row
        fp.seek(loc)
        reader = csv.DictReader(fp)
        fcs = {}
        # Add each valid line of data to import dictionary
        for line in reader:
            # No FC present in the data line
            if not line["FC"]:
                status_val["fail"] += 1
                continue
            if line["FC"] in fcs.keys():
                fcs[line["FC"]].append(line)
            else:
                # Sanitize/replace unicode quotes
                clean_line = re.sub(
                    u'[\u201c\u201d\u2018\u2019]', '', line["FC"])
                if not clean_line:
                    status_val["fail"] += 1
                    continue
                fcs[clean_line] = [line]
        if not fcs:
            return {"status_str": "Import Error: No data detected in import file.", "log_name": None}

    log_time = datetime.now().strftime("%m%d%Y.%H%M%S")
    log_name = f"{context.security.get_current_user_id()}_{prj_name.replace('/', '_')}_{log_time}"
    imp_log, imp_handler = create_logger(log_name)

    if status_val["fail"] > 0:
        imp_log.debug(f"FAIL: {status_val['fail']} FFTS malformed. (FC values likely missing)")

    fc2id = {
        value["name"]: value["_id"]
        for value in json.loads(svc_get_fcs())["value"]
    }

    for nm, fc_list in fcs.items():
        current_list = []
        for fc in fc_list:
            if fc["FC"] not in fc2id:
                status, errormsg, newfc = create_new_functional_component(
                    name=fc["FC"], description="Generated from " + nm)
                # FFT creation successful, add to data to import list
                if status:
                    fc2id[fc["FC"]] = newfc["_id"]
                    current_list.append(fc)
                # Tried to create a new FFT and failed - don't include in dataset
                else:
                    # Count failed imports - excluding FC & FG
                    status_val["fail"] += 1
                    error_str = f"Import for fft {fc['FC']}-{fc['Fungible']} failed: {errormsg}"
                    logger.debug(error_str)
                    imp_log.info(error_str)
            else:
                current_list.append(fc)
        fcs[nm] = current_list

    fg2id = {
        fgs["name"]: fgs["_id"]
        for fgs in json.loads(svc_get_fgs())["value"]
    }

    for nm, fc_list in fcs.items():
        for fc in fc_list:
            if fc["Fungible"] and fc["Fungible"] not in fg2id:
                status, errormsg, newfg = create_new_fungible_token(
                    name=fc["Fungible"], description="Generated from " + nm)
                fg2id[fc["Fungible"]] = newfg["_id"]

    ffts = {(fft["fc"]["name"], fft["fg"]["name"]): fft["_id"]
            for fft in get_ffts()}
    for fc_list in fcs.values():
        for fc in fc_list:
            if (fc["FC"], fc["Fungible"]) not in ffts:
                status, errormsg, newfft = create_new_fft(
                    fc=fc["FC"], fg=fc["Fungible"], fcdesc=None, fgdesc=None)
                ffts[(newfft["fc"]["name"], newfft["fg"]["name"]
                      if "fg" in newfft else None)] = newfft["_id"]

    fcuploads = []
    for nm, fc_list in fcs.items():
        for fc in fc_list:
            fcupload = {}
            fcupload["_id"] = ffts[(fc["FC"], fc["Fungible"])]
            for k, v in KEYMAP.items():
                if k not in fc:
                    continue
                fcupload[v] = fc[k]
            fcuploads.append(fcupload)

    status, errormsg, update_status = update_ffts_in_project(
        prjid, fcuploads, imp_log)

    # Include imports failed from bad FC/FGs
    prj_name = get_project(prjid)["name"]
    if update_status:
        status_val = {k: update_status[k]+status_val[k]
                            for k in update_status.keys()}

    # number of recognized headers minus the id used for DB reference
    status_val["headers"] = len(fcuploads[0].keys())-1
    status_str = create_status_update(prj_name, status_val)
    logger.debug(re.sub('\n|_', '', status_str))
    imp_log.info(status_str)
    imp_log.removeHandler(imp_handler)
    imp_handler.close()
    return {"status_str": status_str, "log_name": log_name}


@licco_ws_blueprint.route("/projects/<report>/download/", methods=["GET", "POST"])
@context.security.authentication_required
def svc_download_report(report):
    """
    Download a status report from a project file import.

    :param: report- full filename of single import log file
    """
    #This is set in the create_logger function-need to be identical paths
    dir_path = f"{tempfile.gettempdir()}/mcd"
    try:
        repfile = f"{dir_path}/{report}.log"
        return send_file(f"{repfile}",as_attachment=True,mimetype="text/plain")
    except FileNotFoundError:
        return JSONEncoder().encode({"success": False, "errormsg": "Something went wrong.", "value": None})

@licco_ws_blueprint.route("/projects/<prjid>/export/", methods=["GET"])
@context.security.authentication_required
def svc_export_project(prjid):
    """
    Export project into a csv that downloads
    """
    with StringIO() as stream:
        writer = csv.DictWriter(stream, fieldnames=KEYMAP.keys())
        writer.writeheader()
        prj_ffts = get_project_ffts(prjid)
        prj_name = get_project(prjid)["name"]

        for fft in prj_ffts:
            row_dict = {}
            fft_dict = prj_ffts[fft]
            for key in fft_dict:
                if key == "fft":
                    continue
                row_dict[KEYMAP_REVERSE[key]] = fft_dict[key]
            for key in fft_dict["fft"]:
                if key == "_id":
                    continue
                row_dict[KEYMAP_REVERSE[key]] = fft_dict["fft"][key]

            # Download file will have column order of KEYMAP var
            writer.writerow(row_dict)

        csv_string = stream.getvalue()

    return Response(csv_string, mimetype="text/csv", headers={"Content-disposition": f"attachment; filename={prj_name}.csv"})


@licco_ws_blueprint.route("/projects/<prjid>/submit_for_approval",
                          methods=["GET", "POST"])
@context.security.authentication_required
def svc_submit_for_approval(prjid):
    """
    Submit a project for approval
    """
    approver = request.args.get("approver", None)
    userid = context.security.get_current_user_id()
    status, errormsg, prj = submit_project_for_approval(prjid, userid, approver)
    if status:
        project_name = prj["name"]
        project_id = prj["_id"]
        approver_username = approver
        context.notifier.add_project_approvers([approver_username], project_name, project_id)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": prj})


@licco_ws_blueprint.route("/projects/<prjid>/approve_project", methods=["GET", "POST"])
@context.security.authentication_required
@context.security.authorization_required("approve")
def svc_approve_project(prjid):
    """
    Approve a project
    """
    userid = context.security.get_current_user_id()
    # See if approval confitions are good
    status, errormsg, prj = approve_project(prjid, userid)
    if status is True:
        approved = get_currently_approved_project()
        if not approved:
            return {"success": False, "errormsg": errormsg}
    else:
        return JSONEncoder().encode({"success": status, "errormsg": errormsg})
    # merge project in to previously approved project
    current_ffts = get_project_ffts(prjid)
    status, errormsg, update_status = update_ffts_in_project(approved["_id"], current_ffts)
    updated_ffts = get_project_ffts(prjid)
    logger.debug(errormsg)
    logger.debug(update_status)
    if status and False:
        # TODO: only send a notification when all approvers approved the project
        project_name = prj["name"]
        notified_user_emails = []  # project_owner + editor_approval
        context.notifier.project_approval_approved(notified_user_emails, project_name, prjid)

    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": updated_ffts})


@licco_ws_blueprint.route("/projects/<prjid>/reject_project", methods=["GET", "POST"])
@context.security.authentication_required
@context.security.authorization_required("approve")
def svc_reject_project(prjid):
    """
    Do not approve a project
    """
    userid = context.security.get_current_user_id()
    reason = request.args.get("reason", None)
    if not reason:
        return logAndAbort("Please provide a reason for why this project is not being approved")

    status, errormsg, prj = reject_project(prjid, userid, reason)
    if status and False:   # TODO: send notification on successful rejection
        project_id = prj["_id"]
        project_name = prj["name"]
        project_approver_emails = []  # TODO: we don't have them in the db right now
        user_who_rejected = userid    # TODO: we don't have an email of our user
        context.notifier.project_approval_rejected(project_approver_emails, project_name, project_id, user_who_rejected)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": prj})


@licco_ws_blueprint.route("/projects/<prjid>/diff_with", methods=["GET"])
@context.security.authentication_required
def svc_project_diff(prjid):
    """
    Get a list of diff between this project and the specified project.
    """
    userid = context.security.get_current_user_id()
    other_prjid = request.args.get("other_id", None)
    approved = request.args.get("approved", None)

    if not other_prjid:
        return logAndAbort("Please specify the other project id using the parameter other_id")
    status, errormsg, diff = diff_project(prjid, other_prjid, userid, approved=approved)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": diff})


@licco_ws_blueprint.route("/projects/<prjid>/clone/", methods=["POST"])
@context.security.authentication_required
def svc_clone_project(prjid):
    """
    Clone the specified project into the new project; 
    Name and description of the new project specified as JSON
    """
    userid = context.security.get_current_user_id()
    newprjdetails = request.json
    if not newprjdetails["name"] or not newprjdetails["description"]:
        return JSONEncoder().encode(
            {"success": False, "errormsg": "Please specify a project name and description"})

    # Set new to true if a new project is requested
    new = (prjid == "NewBlankProjectClone")
    status, erorrmsg, newprj = clone_project(
        prjid, newprjdetails["name"], newprjdetails["description"], userid, new)
    return JSONEncoder().encode({"success": status, "errormsg": erorrmsg, "value": newprj})


@licco_ws_blueprint.route("/projects/<prjid>/tags/", methods=["GET"])
@context.security.authentication_required
def svc_project_tags(prjid):
    """
    Get the tags for the project
    """
    status, errormsg, tags = get_tags_for_project(prjid)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": tags})


@licco_ws_blueprint.route("/projects/<prjid>/add_tag", methods=["GET"])
@context.security.authentication_required
def svc_add_project_tag(prjid):
    """
    Add a new tag to the project.
    The changeid is optional; if not, specified, we add a tag to the latest change.
    """
    tagname = request.args.get("tag_name", None)
    asoftimestamp = request.args.get("asoftimestamp", None)
    if not tagname:
        return JSONEncoder().encode({"success": False, "errormsg": "Please specify the tag_name", "value": None})
    if not asoftimestamp:
        changes = get_project_changes(prjid)
        if not changes:
            return JSONEncoder().encode({"success": False, "errormsg": "Cannot tag a project without a change", "value": None})
        logger.info("Latest change is at " + str(changes[0]["time"]))
        asoftimestamp = changes[0]["time"]
    logger.debug(
        f"Adding a tag for {prjid} at {asoftimestamp} with name {tagname}")
    status, errormsg, tags = add_project_tag(prjid, tagname, asoftimestamp)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": tags})


@licco_ws_blueprint.route("/history/project_approvals", methods=["GET"])
@context.security.authentication_required
def svc_get_projects_approval_history():
    """
    Get the approval history of projects in the system
    """
    return JSONEncoder().encode({"success": True, "value": get_projects_approval_history()})
