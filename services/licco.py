'''
Web service endpoints for licco
'''
import csv
import json
import logging
import fnmatch
import re
from io import BytesIO, StringIO
from datetime import datetime
import pytz
import copy
from functools import wraps

import context

from flask import Blueprint, request, Response

from dal.utils import JSONEncoder
from dal.licco import get_fcattrs, get_project, get_project_ffts, get_fcs, \
    create_new_functional_component, update_fft_in_project, submit_project_for_approval, approve_project, \
    get_currently_approved_project, diff_project, FCState, clone_project, get_project_changes, \
    get_tags_for_project, add_project_tag, get_all_projects, get_all_users, update_project_details, get_project_by_name, \
    create_empty_project, reject_project, copy_ffts_from_project, get_fgs, create_new_fungible_token, get_ffts, create_new_fft, \
    get_projects_approval_history, delete_fft, delete_fc, delete_fg, get_project_attributes, validate_insert_range, get_fft_values_by_project


__author__ = 'mshankar@slac.stanford.edu'

licco_ws_blueprint = Blueprint('business_service_api', __name__)

logger = logging.getLogger(__name__)

KEYMAP = {
    # Column names defined in confluence
    "TC_part_no": "tc_part_no",
    "FC": "fc",
    "Fungible": "fg",
    "State": "state",
    "Comments": "comments",
    "LCLS_Z_loc": "nom_loc_z",
    "LCLS_X_loc": "nom_loc_x",
    "LCLS_Y_loc": "nom_loc_y",
    "Z_dim": "nom_dim_z",
    "Y_dim": "nom_dim_x",
    "X_dim": "nom_dim_y",
    "LCLS_X_pitch": "nom_ang_x",
    "LCLS_Y_yaw": "nom_ang_y",
    "LCLS_Z_roll": "nom_ang_z",
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


def update_ffts_in_project(prjid, ffts):
    """
    Insert multiple FFTs into a project
    """
    prj = get_currently_approved_project()
    prj_ffts = get_project_ffts(prj["_id"]) if prj else {}
    userid = context.security.get_current_user_id()
    update_status = {"total": 0, "success": 0, "fail": 0, "fftedit": 0}

    for fft in ffts:
        fftid = fft["_id"]
        fcupdate = copy.copy(prj_ffts.get(fftid, {}))
        fcupdate.update(fft)
        # If invalid, don't try to add to DB
        if not validate_import_headers(fft, prjid):
            errormsg = "invalid import"
            continue
        for attr in ["_id", "name", "fc", "fg"]:
            if attr in fcupdate:
                del fcupdate[attr]
        if not fcupdate["state"]:
            fcupdate["state"] = "Conceptual"
        status, errormsg, fft, results = update_fft_in_project(
            prjid, fftid, fcupdate, userid)
        # Have smarter error handling here for different exit conditions
        if not status:
            return status, errormsg, fft, None
        # Add the individual FFT update results into overall count
        update_status = {k: update_status[k]+results[k]
                         for k in update_status.keys()}
    return True, errormsg, get_project_ffts(prjid, showallentries=True, asoftimestamp=None), update_status


def validate_import_headers(fft, prjid):
    """
    Helper function to pre-validate that all required data is present
    """
    state_default = "Conceptual"
    attrs = get_fcattrs(fromstr=True)
    db_values = get_fft_values_by_project(fft["_id"], prjid)
    # If state is missing, set to default
    if ("state" not in fft) or (not fft["state"]):
        if ("state" not in db_values):
            fft["state"] = state_default
        else:
            fft["state"] = db_values["state"]
    for header in attrs:
        # If header is required for all, or if the FFT is non-conceptual and header is required
        if attrs[header]["required"] or ((fft["state"] != "Conceptual") and ("is_required_dimension" in attrs[header] and attrs[header]["is_required_dimension"] == True)):
            # If required header not present in upload dataset
            if not header in fft:
                # Check if in DB already, continue to validate next if so
                if header not in db_values:
                    logger.debug(
                        f"FFT Import Rejected{fft['fc']}-{fft['fg']}: Missing Required Header {header}")
                    return False
                continue
            # Check for missing or invalid data
            try:
                val = attrs[header]["fromstr"](fft[header])
            except (ValueError, KeyError) as e:
                logger.debug(
                    f"FFT Import Rejected{fft['fc']}-{fft['fg']}: Invalid Data For {header}")
                return False
            if (not fft[header]) or (not validate_insert_range(header, val)):
                # Check if in DB already, continue to validate next if so
                if header not in db_values:
                    logger.debug(
                        f"FFT Import Rejected{fft['fc']}-{fft['fg']}: Missing Required Header {header}")
                    return False
                continue
    return True


def create_status_changes(status):
    """
    Helper function to make the status message for import based on the dictionary results
    """
    status_str = '\n'.join([
        f'Identified changes: {status["total"]}.',
        f'Successful changes: {status["success"]}.',
        f'Failed changes: {status["fail"]}.',
    ])
    return status_str


def create_status_header(status):
    """
    Helper function to make the header for the import status message
    """
    status_str = '\n'.join([
        f'Valid headers recognized: {status["headers"]}.',
        f'Added FFT: {status["fftnew"]}.',
        f'Modified FFT: {status["fftedit"]}.',
        f'{"_"*40}\n',
    ])
    return status_str


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


@licco_ws_blueprint.route("/fcattrs", methods=["GET"])
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
    return JSONEncoder().encode({"success": True, "value": projects})


@licco_ws_blueprint.route("/approved", methods=["GET"])
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
        print(asoftimestamp)
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
        "location": lambda _, v: fnmatch.fnmatch(v.get("location", ""), request.args["location"]),
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
    status, errormsg, fc, results = update_fft_in_project(
        prjid, fftid, fcupdate, userid)
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
    status, errormsg, fft, update_status = update_ffts_in_project(prjid, ffts)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": fft})


@licco_ws_blueprint.route("/projects/<prjid>/import/", methods=["POST"])
@project_writable
@context.security.authentication_required
def svc_import_project(prjid):
    """
    Import project data from csv file
    """
    status_str = f'Import Results for:  {get_project(prjid)["name"]}\n'
    status_val = {"headers": 0, "fftnew": 0}

    with BytesIO() as stream:
        request.files['file'].save(stream)
        filestring = stream.getvalue().decode()

    with StringIO(filestring) as fp:
        fp.seek(0)
        # Find the header row
        loc = 0
        for line in fp:
            if 'FC' in line and 'Fungible' in line:
                break
            loc = fp.tell()
        # Set reader at beginning of header row
        fp.seek(loc)
        reader = csv.DictReader(fp)
        fcs = {}
        for line in reader:
            if line["FC"] in fcs.keys():
                fcs[line["FC"]].append(line)
            else:
                fcs[line["FC"]] = [line]

    fc2id = {
        value["name"]: value["_id"]
        for value in json.loads(svc_get_fcs())["value"]
    }
    for nm, fc_list in fcs.items():
        for fc in fc_list:
            if fc["FC"] not in fc2id:
                status, errormsg, newfc = create_new_functional_component(
                    name=fc["FC"], description="Generated from " + nm)
                fc2id[fc["FC"]] = newfc["_id"]

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
                status_val["fftnew"] += 1
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

    # number of recognized headers minus the id used for DB reference
    status_val["headers"] = len(fcuploads[0].keys())-1

    status, errormsg, fft, update_status = update_ffts_in_project(
        prjid, fcuploads)
    # Avoid double counting new ffts
    status_val["fftedit"] = update_status["fftedit"] - status_val["fftnew"]
    status_str = (create_status_header(status_val) +
                  create_status_changes(update_status))

    logger.debug(re.sub('\n|_', '', status_str))
    return status_str


@licco_ws_blueprint.route("/projects/<prjid>/export/", methods=["GET"])
@project_writable
@context.security.authentication_required
def svc_export_project(prjid):
    """
    Export project into a cvs that downloads
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
    status, errormsg, prj = submit_project_for_approval(
        prjid, userid, approver)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": prj})


@licco_ws_blueprint.route("/projects/<prjid>/approve_project", methods=["GET", "POST"])
@context.security.authentication_required
def svc_approve_project(prjid):
    """
    Approve a project
    """
    userid = context.security.get_current_user_id()
    status, errormsg, prj = approve_project(prjid, userid)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": prj})


@licco_ws_blueprint.route("/projects/<prjid>/reject_project", methods=["GET", "POST"])
@context.security.authentication_required
def svc_reject_project(prjid):
    """
    Do not approve a project
    """
    userid = context.security.get_current_user_id()
    reason = request.args.get("reason", None)
    if not reason:
        return logAndAbort("Please provide a reason for why this project is not being approved")
    status, errormsg, prj = reject_project(prjid, userid, reason)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": prj})


@licco_ws_blueprint.route("/projects/<prjid>/diff_with", methods=["GET"])
@context.security.authentication_required
def svc_project_diff(prjid):
    """
    Get a list of diff between this project and the specified project.
    """
    userid = context.security.get_current_user_id()
    other_prjid = request.args.get("other_id", None)
    if not other_prjid:
        return logAndAbort("Please specify the other project id using the parameter other_id")
    status, errormsg, diff = diff_project(prjid, other_prjid, userid)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": diff})


@licco_ws_blueprint.route("/projects/<prjid>/clone", methods=["POST"])
@context.security.authentication_required
def svc_clone_project(prjid):
    """
    Clone the specified project into the new project; name and description of the new project specified as JSON
    """
    userid = context.security.get_current_user_id()
    newprjdetails = request.json
    if not newprjdetails["name"] or not newprjdetails["description"]:
        return JSONEncoder().encode({"success": False, "errormsg": "Please specify a project name and description"})
    if get_project_by_name(newprjdetails["name"]):
        return JSONEncoder().encode({"success": False, "errormsg": "Project with the name " + newprjdetails["name"] + " already exists"})

    status, erorrmsg, newprj = clone_project(
        prjid, newprjdetails["name"], newprjdetails["description"], userid)
    return JSONEncoder().encode({"success": status, "errormsg": erorrmsg, "value": newprj})


@licco_ws_blueprint.route("/projects/<prjid>/tags", methods=["GET"])
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
