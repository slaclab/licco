"""
Web service endpoints for licco
"""
import datetime
import fnmatch
import os
import re
from io import BytesIO
import tempfile
from functools import wraps
from typing import Tuple

import pytz
import logging
import json
import context
from context import licco_db
from flask import Blueprint, request, Response, send_file

from dal import mcd_model, mcd_import
from dal.mcd_model import FCState
from dal.utils import JSONEncoder, ImportCounter

licco_ws_blueprint = Blueprint('business_service_api', __name__)

logger = logging.getLogger(__name__)


def logAndAbortJson(error_msg, ret_status=500):
    logger.error(error_msg)
    return {'status': False, 'errormsg': error_msg, 'value': None}, ret_status

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
        prj = mcd_model.get_project(licco_db, prjid)
        if not prj:
            raise Exception(f"Project with id {prjid} does not exist")
        if prj.get("status", "N/A") == "development":
            return wrapped_function(*args, **kwargs)
        raise Exception(
            f"Project with id {prjid} is not in development status")
    return function_interceptor


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
    return JSONEncoder().encode({"success": True, "value": mcd_model.get_fcattrs()})


@licco_ws_blueprint.route("/users/", methods=["GET"])
@context.security.authentication_required
def svc_get_users():
    """
    Get the users in the system.
    For now, this is simply the owners of projects.
    """
    logged_in_user = context.security.get_current_user_id()
    users = mcd_model.get_all_users(licco_db)
    return JSONEncoder().encode({"success": True, "value": users})


@licco_ws_blueprint.route("/users/<username>/", methods=["GET"])
@context.security.authentication_required
def svc_get_logged_in_user(username):
    """
    Get the user related data
    """
    if username == "WHOAMI":
        # get the currently logged in user data
        logged_in_user = context.security.get_current_user_id()
        return JSONEncoder().encode({"success": True, "value": logged_in_user})

    # get the specified user data (for now we don't have any, so we just return username)
    return JSONEncoder().encode({"success": True, "value": username})


@licco_ws_blueprint.route("/approvers/", methods=["GET"])
@context.security.authentication_required
def svc_get_users_with_approve_privilege():
    """
    Get the users in the system who have the approve privilege
    """
    users = mcd_model.get_users_with_privilege(licco_db, "approve")
    return JSONEncoder().encode({"success": True, "value": users})

@licco_ws_blueprint.route("/editors/", methods=["GET"])
@context.security.authentication_required
def svc_get_users_with_edit_privilege():
    """
    Get the users in the system who have the edit privilege
    """
    users = mcd_model.get_users_with_privilege(licco_db, "edit")
    return JSONEncoder().encode({"success": True, "value": users})

@licco_ws_blueprint.route("/projects/", methods=["GET"])
@context.security.authentication_required
def svc_get_projects_for_user():
    """
    Get the projects for a user
    """
    logged_in_user = context.security.get_current_user_id()
    sort_criteria = json.loads(request.args.get("sort", '[["start_time", -1]]'))
    projects = mcd_model.get_all_projects(licco_db, logged_in_user, sort_criteria)
    edits = mcd_model.get_projects_recent_edit_time(licco_db)
    for project in projects:
        project["edit_time"] = edits[(project["_id"])]["time"]
    if sort_criteria[0][0] == "edit_time":
        reverse = (sort_criteria[0][1] == -1)
        min_date = datetime.datetime.min.replace(tzinfo=pytz.UTC)
        projects = sorted(projects, key=lambda d: d['edit_time'] or min_date, reverse=reverse)
    return JSONEncoder().encode({"success": True, "value": projects})


@licco_ws_blueprint.route("/approved/", methods=["GET"])
@context.security.authentication_required
def svc_get_currently_approved_project():
    """ Get the currently approved project """
    logged_in_user = context.security.get_current_user_id()
    prj = mcd_model.get_master_project(licco_db)
    if not prj:
         # no currently approved project (this can happen when the project is submitted for the first time)
        return JSONEncoder().encode({"success": True, "value": None})
    prj_ffts = mcd_model.get_project_ffts(licco_db, prj["_id"])
    prj["ffts"] = prj_ffts
    return JSONEncoder().encode({"success": True, "value": prj})


@licco_ws_blueprint.route("/projects/<prjid>/", methods=["GET"])
@context.security.authentication_required
def svc_get_project(prjid):
    """
    Get the project details given a project id.
    """
    logged_in_user = context.security.get_current_user_id()
    project_details = mcd_model.get_project(licco_db, prjid)
    return JSONEncoder().encode({"success": True, "value": project_details})


@licco_ws_blueprint.route("/projects/", methods=["POST"])
@context.security.authentication_required
def svc_create_project():
    """
    Create an empty project
    """
    logged_in_user = context.security.get_current_user_id()
    prjdetails = request.json
    if not prjdetails.get("name", None):
        return JSONEncoder().encode({"success": False, "errormsg": "Name cannot be empty"})
    if not prjdetails.get("description", None):
        return JSONEncoder().encode({"success": False, "errormsg": "Description cannot be empty"})
    prj = mcd_model.create_new_project(licco_db, prjdetails["name"], prjdetails["description"], logged_in_user)
    return JSONEncoder().encode({"success": True, "value": prj})


@licco_ws_blueprint.route("/projects/<prjid>/", methods=["POST"])
@context.security.authentication_required
def svc_update_project(prjid):
    """
    Update the project details (project name, description, editors)
    """
    logged_in_user = context.security.get_current_user_id()
    prjdetails = request.json
    status, err = mcd_model.update_project_details(licco_db, logged_in_user, prjid, prjdetails, context.notifier)
    if not status:
        return JSONEncoder().encode({"success": False, "errormsg": err})

    return JSONEncoder().encode({"success": True, "value": mcd_model.get_project(licco_db, prjid)})


@licco_ws_blueprint.route("/projects/<prjid>/", methods=["DELETE"])
@context.security.authentication_required
def svc_delete_project(prjid):
    """
    Get the project details given a project id.
    """
    logged_in_user = context.security.get_current_user_id()
    status, err = mcd_model.delete_project(licco_db, logged_in_user, prjid)
    if not status:
        return JSONEncoder().encode({"success": False, "errormsg": err})
    return JSONEncoder().encode({"success": True})


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
        asoftimestamp = datetime.datetime.strptime(asoftimestampstr, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=pytz.UTC)
    else:
        asoftimestamp = None
    project_fcs = mcd_model.get_project_ffts(licco_db, prjid, showallentries=showallentries, asoftimestamp=asoftimestamp)

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
    changes = mcd_model.get_project_changes(licco_db, prjid)
    return JSONEncoder().encode({"success": True, "value": changes})


@licco_ws_blueprint.route("/fcs/", methods=["GET"])
@context.security.authentication_required
def svc_get_fcs():
    """
    Get the functional component objects
    """
    fcs = mcd_model.get_fcs(licco_db)
    return JSONEncoder().encode({"success": True, "value": fcs})


@licco_ws_blueprint.route("/fgs/", methods=["GET"])
@context.security.authentication_required
def svc_get_fgs():
    """
    Get the fungible tokens
    """
    fgs = mcd_model.get_fgs(licco_db)
    return JSONEncoder().encode({"success": True, "value": fgs})


@licco_ws_blueprint.route("/ffts/", methods=["GET"])
@context.security.authentication_required
def svc_get_ffts():
    """
    Get a list of functional fungible tokens
    """
    ffts = mcd_model.get_ffts(licco_db)
    return JSONEncoder().encode({"success": True, "value": ffts})


@licco_ws_blueprint.route("/fcs/", methods=["POST"])
@context.security.authentication_required
def svc_create_fc():
    """
    Create a functional component
    """
    newfc = request.json
    status, errormsg, fc = mcd_model.create_new_functional_component(licco_db,
        name=newfc.get("name", ""), description=newfc.get("description", ""))
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": fc})


@licco_ws_blueprint.route("/fgs/", methods=["POST"])
@context.security.authentication_required
def svc_create_fg():
    """
    Create a fungible token
    """
    newfg = request.json
    status, errormsg, fg = mcd_model.create_new_fungible_token(licco_db,
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
    status, errormsg, fft = mcd_model.create_new_fft(licco_db,
        fc=newfft["fc"], fg=newfft["fg"], fcdesc=newfft.get(
        "fc_description", None), fgdesc=newfft.get("fg_description", None))
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": fft})


@licco_ws_blueprint.route("/ffts/<fftid>", methods=["DELETE"])
@context.security.authentication_required
def svc_delete_fft(fftid):
    """
    Delete a FFT if it is not being used in any project
    """
    status, errormsg, _ = mcd_model.delete_fft(licco_db, fftid)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": None})


@licco_ws_blueprint.route("/fcs/<fcid>", methods=["DELETE"])
@context.security.authentication_required
def svc_delete_fc(fcid):
    """
    Delete a FC if it is not being used by an FFT
    """
    status, errormsg, _ = mcd_model.delete_fc(licco_db, fcid)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": None})


@licco_ws_blueprint.route("/fgs/<fgid>", methods=["DELETE"])
@context.security.authentication_required
def svc_delete_fg(fgid):
    """
    Delete a FG if it is not being used by an FFT
    """
    status, errormsg, _ = mcd_model.delete_fg(licco_db, fgid)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": None})


@licco_ws_blueprint.route("/projects/<prjid>/fcs/<fftid>", methods=["POST"])
@context.security.authentication_required
@project_writable
def svc_update_fc_in_project(prjid, fftid):
    """
    Update the values of a functional component in a project
    """
    fcupdate = request.json
    fcupdate["_id"] = fftid
    userid = context.security.get_current_user_id()
    status, msg = mcd_model.validate_import_headers(licco_db, fcupdate, prjid)
    if not status:
        return logAndAbortJson(msg)

    discussion = fcupdate.get('discussion', '')
    if discussion:
        # our fft update expects an array of discussion comments hence the transform into an array of objects
        fcupdate['discussion'] = [{
            'author': userid,
            'comment': discussion
        }]

    change_of_device = 'fc' in fcupdate or 'fg' in fcupdate
    if change_of_device:
        status, errormsg, new_fft_id = mcd_model.change_of_fft_in_project(licco_db, userid, prjid, fcupdate)
        if not status:
            return logAndAbortJson(errormsg)
        fc = mcd_model.get_project_ffts(licco_db, prjid, fftid=new_fft_id)[new_fft_id]
        return JSONEncoder().encode({"success": status, "value": fc})

    status, errormsg, results = mcd_model.update_fft_in_project(licco_db, userid, prjid, fcupdate)
    fc = mcd_model.get_project_ffts(licco_db, prjid, fftid=fftid)[fftid]
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": fc})

@licco_ws_blueprint.route("/projects/<prjid>/fcs/<fftid>/comment", methods=["POST"])
@context.security.authentication_required
def svc_add_fft_comment(prjid, fftid):
    """
    Endpoint for adding a comment into a device fft, despite the project not being in a development mode
    (approval comments and discussions should always be available, regardless of the project status)
    """
    update = request.json
    comment = update.get('comment')
    if comment is None:
        return logAndAbortJson("Comment field does not exist", ret_status=400)
    comment = comment.strip()
    if comment == "":
        return logAndAbortJson("Comment should not be empty", ret_status=400)

    userid = context.security.get_current_user_id()
    status, errormsg, results = mcd_model.add_fft_comment(licco_db, userid, prjid, fftid, comment)
    if not status:
        return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": None})

    # TODO: refactor: we should be able to get just one specific device (and not fetch all devices everytime we want one)
    fc = mcd_model.get_project_ffts(licco_db, prjid)
    val = fc[fftid]
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": val})


@licco_ws_blueprint.route("/projects/<prjid>/fcs/<fftid>/comment", methods=["DELETE"])
@context.security.authentication_required
def svc_remove_fft_comment(prjid, fftid):
    """Remove a specific fft device comment or a set of comments"""
    comment_ids = request.json().get('comments')
    if not comment_ids:
        return logAndAbortJson("Comment field should not be empty")

    errors = []
    for comment_id in comment_ids:
        deleted, errormsg = mcd_model.delete_fft_comment(licco_db, prjid, comment_id)
        if not deleted:
            errors.append(errormsg)

    if len(errors) != 0:
        err = "\n".join(errors)
        msg = f"There were errors while deleting comments: {err}"
        return JSONEncoder().encode({"success": False, "errormsg": msg})

    return JSONEncoder().encode({"success": True, "errormsg": ""})


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
    :param: attrnames - List of attribute names to copy over. If this is a string "ALL", then all the attributes that
    are set are copied over.
    """
    userid = context.security.get_current_user_id()
    reqparams = request.json
    logger.info(reqparams)
    status, errormsg, fc = mcd_model.copy_ffts_from_project(licco_db,
        destprjid=prjid, srcprjid=reqparams["other_id"], fftid=fftid, attrnames=[
        x["name"] for x in mcd_model.get_fcattrs()] if reqparams["attrnames"] == "ALL" else reqparams["attrnames"],
        userid=userid)
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

    userid = context.security.get_current_user_id()
    status, errormsg, update_status = mcd_model.update_ffts_in_project(licco_db, userid, prjid, ffts)
    fft = mcd_model.get_project_ffts(licco_db, prjid)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": fft})

@licco_ws_blueprint.route("/projects/<prjid>/ffts/", methods=["DELETE"])
@project_writable
@context.security.authentication_required
def svc_remove_ffts_from_project(prjid):
    """
    Remove multiple ffts/devices from a project
    """
    userid = context.security.get_current_user_id()
    fft_ids = request.json.get('ids', [])
    status, errormsg = mcd_model.remove_ffts_from_project(licco_db, userid, prjid, fft_ids)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg})


def create_logger(logname: str) -> Tuple[logging.Logger, logging.FileHandler]:
    """
    Create and return a logger that writes to a provided file. This logger has to be manually closed
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


@licco_ws_blueprint.route("/projects/<prjid>/import/", methods=["POST"])
@project_writable
@context.security.authentication_required
def svc_import_project(prjid):
    """
    Import project data from csv file
    """
    userid = context.security.get_current_user_id()
    with BytesIO() as stream:
        request.files['file'].save(stream)
        try:
            filestring = stream.getvalue().decode("utf-8", "ignore")
        except UnicodeDecodeError as e:
            error_msg = "Import Rejected: File not fully in Unicode (utf-8) Format."
            logger.debug(error_msg)
            response_value = {"status_str": error_msg, "log_name": None}
            return JSONEncoder().encode({"success": False, "value": response_value})

    prj_name = mcd_model.get_project(licco_db, prjid)['name']
    log_time = datetime.datetime.now().strftime("%m%d%Y.%H%M%S")
    log_name = f"{userid}_{prj_name.replace('/', '_')}_{log_time}"
    log, log_handler = create_logger(log_name)

    ok, err, import_status = mcd_import.import_project(context.licco_db, userid, prjid, filestring, log)
    if not ok:
        return JSONEncoder().encode({"success": False, "errormsg": err})
    log.removeHandler(log_handler)
    log_handler.close()

    prj_name = mcd_model.get_project(licco_db, prjid)["name"]
    status_str = mcd_import.create_status_update(prj_name, import_status)
    response_value = {"status_str": status_str, "log_name": log_name}
    return JSONEncoder().encode({"success": True, "value": response_value})

@licco_ws_blueprint.route("/projects/<report>/download/", methods=["GET", "POST"])
@context.security.authentication_required
def svc_download_report(report):
    # TODO: who is deleting those temp reports? Why we don't just return the logger output
    # directly back to the user as part of the export request (and we can delete this function)
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
    project = mcd_model.get_project(licco_db, prjid)
    if not project:
        return logAndAbortJson(f"project '{prjid}' does not exist")
    project_name = project["name"]

    ok, err, csv_string = mcd_import.export_project(licco_db, prjid)
    if not ok:
        return logAndAbortJson(f"failed to export a project {project['name']}: {err}")

    return Response(csv_string, mimetype="text/csv", headers={"Content-disposition": f"attachment; filename={project_name}.csv"})


@licco_ws_blueprint.route("/projects/<prjid>/submit_for_approval", methods=["GET", "POST"])
@context.security.authentication_required
def svc_submit_for_approval(prjid):
    """
    Submit a project for approval
    """
    approvers = []
    editors = []
    if request.json:
        approvers = request.json.get("approvers", [])
        if len(approvers) == 0:
            return JSONEncoder().encode({"success": False, "errormsg": "At least 1 approver is expected"})
        editors = request.json.get("editors", [])
    else:
        # TODO: DEPRECATED: old gui approved project this way
        # Once old GUI is removed, this else statement should go away as well
        # We should remove the "GET" option as well: only POST should be used (or PUT)
        approver = request.args.get("approver", None)
        if approver:
            approvers.append(approver)
        old_prj = mcd_model.get_project(licco_db, prjid)
        editors = old_prj["editors"]

    userid = context.security.get_current_user_id()
    status, errormsg, prj = mcd_model.submit_project_for_approval(licco_db, prjid, userid, editors, approvers, context.notifier)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": prj})


@licco_ws_blueprint.route("/projects/<prjid>/approve_project", methods=["GET", "POST"])
@context.security.authentication_required
def svc_approve_project(prjid):
    """
    Approve a project
    """
    userid = context.security.get_current_user_id()
    status, all_approved, errormsg, prj = mcd_model.approve_project(licco_db, prjid, userid, context.notifier)
    if not status:
        return JSONEncoder().encode({"success": status, "errormsg": errormsg})
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": prj})


@licco_ws_blueprint.route("/projects/<prjid>/reject_project", methods=["GET", "POST"])
@context.security.authentication_required
def svc_reject_project(prjid):
    """
    Do not approve a project
    """
    userid = context.security.get_current_user_id()
    reason = request.args.get("reason", None)
    if not reason and request.json:
        reason = request.json.get("reason")
    if not reason:
        return logAndAbortJson("Please provide a reason for why this project is not being approved")

    status, errormsg, prj = mcd_model.reject_project(licco_db, prjid, userid, reason, context.notifier)
    if not status:
        return JSONEncoder().encode({"success": status, "errormsg": errormsg})
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
    status, errormsg, diff = mcd_model.diff_project(licco_db, prjid, other_prjid, userid, approved=approved)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": diff})


@licco_ws_blueprint.route("/projects/<prjid>/clone/", methods=["POST"])
@context.security.authentication_required
def svc_clone_project(prjid):
    """
    Clone the specified project into the new project; 
    Name and description of the new project specified as JSON
    """
    userid = context.security.get_current_user_id()
    project_data = request.json
    project_name = project_data.get("name", "")
    project_description = project_data.get("description", "")
    project_editors = project_data.get("editors", [])

    if not project_name or not project_description:
        return JSONEncoder().encode({"success": False, "errormsg": "Please specify a project name and description"})

    status, erorrmsg, newprj = mcd_model.clone_project(licco_db, userid, prjid, project_name, project_description, project_editors, context.notifier)
    return JSONEncoder().encode({"success": status, "errormsg": erorrmsg, "value": newprj})


@licco_ws_blueprint.route("/projects/<prjid>/tags/", methods=["GET"])
@context.security.authentication_required
def svc_project_tags(prjid):
    """
    Get the tags for the project
    """
    status, errormsg, tags = mcd_model.get_tags_for_project(licco_db, prjid)
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
        changes = mcd_model.get_project_changes(licco_db, prjid)
        if not changes:
            return JSONEncoder().encode({"success": False, "errormsg": "Cannot tag a project without a change", "value": None})
        logger.info("Latest change is at " + str(changes[0]["time"]))
        asoftimestamp = changes[0]["time"]
    logger.debug(f"Adding a tag for {prjid} at {asoftimestamp} with name {tagname}")
    status, errormsg, tags = mcd_model.add_project_tag(licco_db, prjid, tagname, asoftimestamp)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": tags})


@licco_ws_blueprint.route("/history/project_approvals", methods=["GET"])
@context.security.authentication_required
def svc_get_projects_approval_history():
    """
    Get the approval history of projects in the system
    """
    return JSONEncoder().encode({"success": True, "value": mcd_model.get_projects_approval_history(licco_db, limit=100)})
