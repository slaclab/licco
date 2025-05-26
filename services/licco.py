"""
Web service endpoints for licco
"""
import datetime
import os
import uuid
from io import BytesIO
import tempfile
from functools import wraps
from typing import Tuple, Dict, List
from http import HTTPStatus

import pytz
import logging
import json


import context
from context import licco_db
from flask import Blueprint, request, Response, send_file

from dal import mcd_model, mcd_import, mcd_datatypes, mcd_db
from dal.utils import JSONEncoder

licco_ws_blueprint = Blueprint('business_service_api', __name__)
logger = logging.getLogger(__name__)

def json_response(data: Dict[str, any] | List[any], ret_status=200):
    # NOTE: in general it's better to always return a dictionary of elements (and not a plain array)
    # since a dictionary is easier to extend with new fields in the future
    #
    # we need to use our custom encoder, otherwise ObjectIds are not correctly serialized
    out = JSONEncoder().encode(data)
    return Response(out, mimetype="application/json", status=ret_status)


def json_error(error_msg: str, ret_status=400):
    out = JSONEncoder().encode({'errormsg': error_msg})
    return Response(out, mimetype="application/json", status=ret_status)

def parse_isodatetime_string(input: str) -> Tuple[datetime.datetime, str]:
    try:
        date = datetime.datetime.strptime(input, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=pytz.UTC)
        return date, ""
    except Exception as e:
        return datetime.datetime.now(), f"failed to parse a datetime string: {e}"


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
        status = prj.get("status", "N/A")
        if status == "development":
            return wrapped_function(*args, **kwargs)

        name = prj.get("name", "UnknownName")
        raise Exception(f"Project {name} (id: {prjid}) is not in a development status: current status: {status}")
    return function_interceptor


@licco_ws_blueprint.route("/backendkeymap/", methods=["GET"])
@context.security.authentication_required
def svc_get_keymap():
    """
    Returns the keymap responsible for mapping backend names to human readable ones
    (For frontend/react needs, adds in additional frontend attributes)
    Ex: nom_loc_x -> LCLS_X_loc or fg -> Fungible
    """
    return json_response(dict(
        discussion="Discussion",
        **mcd_datatypes.MCD_KEYMAP_REVERSE,
    ))

@licco_ws_blueprint.route("/users/", methods=["GET"])
@context.security.authentication_required
def svc_get_users():
    """
    Get the users in the system.
    For now, this is simply the owners of projects.
    """
    roles = request.args.get('roles', '')
    if not roles:
        out = {"all": mcd_model.get_all_users(licco_db)}
        return JSONEncoder().encode({"success": True, "value": out})

    # user wanted specific roles
    roles = roles.split(",")
    users = {}
    for role in roles:
        role = role.strip()
        if role == "all":
            users["all"] = mcd_model.get_all_users(licco_db)
        elif role == "admins":
            users["admins"] = mcd_model.get_users_with_privilege(licco_db, "admin")
        elif role == "editors":
            users["editors"] = mcd_model.get_users_with_privilege(licco_db, "edit")
        elif role == "approvers":
            users["approvers"] = mcd_model.get_users_with_privilege(licco_db, "approve")
        elif role == "super_approvers":
            users["super_approvers"] = mcd_model.get_users_with_privilege(licco_db, "superapprover")
        else:
            return json_error(f"invalid user role '{role}'")

    return json_response(users)


@licco_ws_blueprint.route("/users/<username>/", methods=["GET"])
@context.security.authentication_required
def svc_get_logged_in_user(username):
    """
    Get the user related data
    """
    if username == "WHOAMI":
        # get the currently logged in user data
        logged_in_user = context.security.get_current_user_id()
        return json_response(logged_in_user)

    # get the specified user data (for now we don't have any, so we just return username)
    return json_response(username)


@licco_ws_blueprint.route("/projects/", methods=["GET"])
@context.security.authentication_required
def svc_get_projects_for_user():
    """
    Get the projects for a user
    """
    logged_in_user = context.security.get_current_user_id()
    sort_criteria = json.loads(request.args.get("sort", '[["creation_time", -1]]'))
    projects = mcd_model.get_all_projects(licco_db, logged_in_user, sort_criteria)
    edits = mcd_model.get_all_projects_last_edit_time(licco_db)
    for project in projects:
        project["edit_time"] = edits[str(project["_id"])]["time"]
    if sort_criteria[0][0] == "edit_time":
        reverse = (sort_criteria[0][1] == -1)
        min_date = datetime.datetime.min.replace(tzinfo=pytz.UTC)
        projects = sorted(projects, key=lambda d: d['edit_time'] or min_date, reverse=reverse)
    return json_response(projects)


@licco_ws_blueprint.route("/approved/", methods=["GET"])
@context.security.authentication_required
def svc_get_currently_approved_project():
    """ Get the currently approved project """
    logged_in_user = context.security.get_current_user_id()
    prj = mcd_model.get_master_project(licco_db)
    if not prj:
         # no currently approved project (this can happen when the project is submitted for the first time)
        return json_response({}, ret_status=HTTPStatus.NO_CONTENT)

    prj_ffts = mcd_model.get_project_devices(licco_db, prj["_id"])
    prj["ffts"] = prj_ffts
    return json_response(prj)


@licco_ws_blueprint.route("/projects/<prjid>/", methods=["GET"])
@context.security.authentication_required
def svc_get_project(prjid):
    """
    Get the project details given a project id.
    """
    logged_in_user = context.security.get_current_user_id()
    project_details = mcd_model.get_project(licco_db, prjid)
    return json_response(project_details)


@licco_ws_blueprint.route("/projects/", methods=["POST"])
@context.security.authentication_required
def svc_create_project():
    """
    Create an empty project
    """
    logged_in_user = context.security.get_current_user_id()
    prjdetails = request.json
    if not prjdetails.get("name", None):
        return json_error("Name cannot be empty")
    if not prjdetails.get("description", None):
        return json_error("Description cannot be empty")
    # editors are optional
    editors = prjdetails.get("editors", [])

    err, prj = mcd_model.create_new_project(licco_db, logged_in_user, prjdetails["name"], prjdetails["description"], editors, context.notifier)
    if err:
        return json_error(err)
    return json_response(prj)


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
        return json_error(err)

    project = mcd_model.get_project(licco_db, prjid)
    return json_response(project)


@licco_ws_blueprint.route("/projects/<prjid>/", methods=["DELETE"])
@context.security.authentication_required
def delete_project(prjid):
    """
    Get the project details given a project id.
    """
    logged_in_user = context.security.get_current_user_id()
    status, err = mcd_model.delete_project(licco_db, logged_in_user, prjid)
    if not status:
        return json_error(err)
    return json_response({}, ret_status=HTTPStatus.NO_CONTENT)


@licco_ws_blueprint.route("/projects/<prjid>/ffts/", methods=["GET"])
@context.security.authentication_required
def get_project_devices(prjid):
    """
    Get the project's FFT's given a project id.
    """
    asoftimestampstr = request.args.get("asoftimestamp", None)
    if asoftimestampstr:
        asoftimestamp, err = parse_isodatetime_string(asoftimestampstr)
        if err:
            return json_error(f"failed to get project devices: {err}")
    else:
        asoftimestamp = None
    project_fcs = mcd_model.get_project_devices(licco_db, prjid, asoftimestamp=asoftimestamp)
    return json_response(project_fcs)


@licco_ws_blueprint.route("/projects/<prjid>/snapshots/", methods=["GET"])
@context.security.authentication_required
def get_project_snapshots(prjid):
    """
    Get a history of project changes (snapshots)
    """
    start_time = request.args.get("start", None)
    if start_time:
        start_time, err = parse_isodatetime_string(start_time)
        if err:
            return json_error(f"failed to fetch project snapshots: invalid 'start' time boundary: {err}")

    end_time = request.args.get("end", None)
    if end_time:
        end_time, err = parse_isodatetime_string(end_time)
        if err:
            return json_error(f"failed to fetch project snapshots: invalid 'end' time boundary: {err}")

    limit = int(request.args.get("limit", 0))

    snapshots, err = mcd_model.get_project_snapshots(licco_db, prjid, limit=limit, start_time=start_time, end_time=end_time)
    if err:
        return json_error(err)
    return json_response(snapshots)


@licco_ws_blueprint.route("/projects/<prjid>/snapshots/<snapshot_id>/", methods=["GET"])
@context.security.authentication_required
def get_snapshot(prjid, snapshot_id):
    """
    Get project snapshot
    """
    userid = context.security.get_current_user_id()
    if snapshot_id == "latest":
        snapshot = mcd_model.get_recent_snapshot(licco_db, prjid)
    else:
        snapshot = mcd_db.get_snapshot(licco_db, snapshot_id)

    if snapshot:
        return json_response(snapshot)
    return json_error(f"there was no snapshot found for {snapshot_id}", ret_status=404)


@licco_ws_blueprint.route("/projects/<prjid>/snapshots/<snapshot_id>/", methods=["POST"])
@context.security.authentication_required
def edit_snapshot_name(prjid, snapshot_id):
    """Change snapshot name"""
    name = request.args.get("name", "")
    if not name:
        return json_error("name parameter was not set")

    userid = context.security.get_current_user_id()
    updated_snapshot, err = mcd_model.edit_snapshot_name(licco_db, userid, prjid, snapshot_id, name)
    if err:
        return json_error(err)
    return json_response(updated_snapshot)


@licco_ws_blueprint.route("/fcs/", methods=["GET"])
@context.security.authentication_required
def get_fcs():
    """
    Get a list of FC strings from a master project. This is generally used for autocompletion of FCs
    (when creating or updating an existing device)
    """
    ffts = mcd_model.get_fcs(licco_db)
    return json_response(ffts)


@licco_ws_blueprint.route("/projects/<prjid>/fcs/<fc>", methods=["GET"])
@context.security.authentication_required
def get_latest_project_device_data(prjid, fc):
    # NOTE: fc could be either id or a FC name of a device
    # This is controlled by the '?name=true' flag
    name = request.args.get("name", False)
    if name:
        device, err = mcd_model.get_recent_device_by_fc_name(licco_db, prjid, fc)
        if err:
            return json_error(err, ret_status=404)
        return json_response(device)

    # fc is an id
    device = mcd_model.get_device(licco_db, fc)
    if not device:
        return json_error(f"Device {fc} does not exist", ret_status=404)
    return device


@licco_ws_blueprint.route("/projects/<prjid>/fcs/<fftid>", methods=["POST"])
@context.security.authentication_required
@project_writable
def update_device_in_project(prjid, fftid):
    """
    Update the values of a device in a project
    """
    fcupdate = request.json
    fcupdate["_id"] = fftid
    userid = context.security.get_current_user_id()

    discussion = fcupdate.get('discussion', None)
    if discussion:
        if not isinstance(discussion, str):
            return json_error(f"discussion field should be a string, but got {type(discussion).__name__}")

        # our fft update expects an array of discussion comments hence the transform into an array of objects
        fcupdate['discussion'] = [{
            'id': str(uuid.uuid4()),
            'author': userid,
            'comment': discussion,
            'created': datetime.datetime.now(datetime.UTC)
        }]

    fc = fcupdate.get("fc", None)
    if fc:
        device_id, err = mcd_model.change_device_fc(licco_db, userid, prjid, fcupdate)
        if err:
            return json_error(err)
    else:
        # get the fc of the fftid, before using the update function
        device = mcd_model.get_device(licco_db, fftid)
        if device:
            fc = device['fc']
            fcupdate['fc'] = fc

        ok, err, changed_fields, device_id = mcd_model.update_device_in_project(licco_db, userid, prjid, fcupdate)
        if err:
            return json_error(err)

    if not device_id:   # device fields have not changed.
        device_id = fftid

    # it's possible that another user made a change just after we made ours: in this case we want to
    # pull out this device fc from the latest snapshot
    updated_devices = mcd_model.get_project_devices(licco_db, prjid, device_id=device_id)
    device = updated_devices.get(fc, None)
    if not device:
        return json_error(f"device '{fc}' was not found in the database after updating: this should never happen unless someone has just deleted it (or deleted an entire project)")
    return json_response(device)


@licco_ws_blueprint.route("/projects/<prjid>/fcs/<fftid>/comment", methods=["POST"])
@context.security.authentication_required
def add_device_comment(prjid, fftid):
    """
    Endpoint for adding a comment into a device fft, despite the project not being in a development mode
    (approval comments and discussions should always be available, regardless of the project status)
    """
    update = request.json
    comment = update.get('comment')
    if comment is None:
        return json_error("Comment field does not exist")
    comment = comment.strip()
    if comment == "":
        return json_error("Comment should not be empty")

    userid = context.security.get_current_user_id()
    status, errormsg = mcd_model.add_fft_comment(licco_db, userid, prjid, fftid, comment)
    if not status:
        return json_error(errormsg)

    data = mcd_model.get_project_devices(licco_db, prjid, device_id=fftid)
    for key, val in data.items():
        if str(val['_id']) == fftid:
            return json_response(val)
    return json_error(f"failed to find the device {fftid}: another user has probably changed or deleted this device")



@licco_ws_blueprint.route("/projects/<prjid>/fcs/<fftid>/comment", methods=["DELETE"])
@context.security.authentication_required
def remove_device_comment(prjid, fftid):
    """Remove a specific fft device comment or a set of comments"""
    userid = context.security.get_current_user_id()

    if True:
        # @TODO: implement this
        # NOTE: every comment should have an id and a device id so we can locate it within the array
        raise NotImplementedError("this endpoint is not yet implemented")

    comment_ids = request.json().get('comments')
    if not comment_ids:
        return json_error("Comment field should not be empty")

    errors = []
    for comment_id in comment_ids:
        device_id = "missing"
        deleted, errormsg = mcd_model.delete_fft_comment(licco_db, userid, prjid, device_id, comment_id)
        if not deleted:
            errors.append(errormsg)

    if len(errors) != 0:
        err = "\n".join(errors)
        msg = f"There were errors while deleting comments: {err}"
        return json_error(msg)

    return json_response({}, ret_status=HTTPStatus.NO_CONTENT)


@licco_ws_blueprint.route("/projects/copy_from_project", methods=["POST"])
@context.security.authentication_required
def copy_fc_from_project():
    """
    Copy values of a device from a different project. Most of the time, that would be 'master' project.
    """
    userid = context.security.get_current_user_id()
    reqparams = request.json

    src_project_id = reqparams.get("src_project", None)
    if not src_project_id:
        return json_error(f"missing 'src_project' body parameter")

    dest_project_id = reqparams.get("dest_project", None)
    if not dest_project_id:
        return json_error("missing 'dest_project' body parameter")

    fc = reqparams.get("fc", None)
    if not fc:
        return json_error(f"missing 'fc' body parameter")

    attr = reqparams.get("attrnames", None)
    if not attr:
        return json_error(f"missing 'attrnames' body parameter")

    if not isinstance(attr, List):
        return json_error(f"attrnames parameter should be an array of device fields, but got {type(attr).__name__}")

    updated_device, err = mcd_model.copy_device_values_from_project(licco_db, userid, src_project_id, dest_project_id, fc, attr)
    if err:
        return json_error(err)
    return json_response(fc)


@licco_ws_blueprint.route("/projects/<prjid>/ffts/", methods=["POST"])
@project_writable
@context.security.authentication_required
def svc_update_ffts_in_project(prjid):
    """
    Insert one, or multiple devices into a project
    """
    ffts = request.json
    if isinstance(ffts, dict):
        ffts = [ffts]

    # TODO: verify that device id does not already exist in the project snapshot
    # The user should select a device_type: MCD (at least)

    userid = context.security.get_current_user_id()
    status, errormsg, update_status = mcd_model.update_ffts_in_project(licco_db, userid, prjid, ffts)
    fft = mcd_model.get_project_devices(licco_db, prjid)
    if errormsg:
        return json_error(errormsg)
    return json_response(fft)


@licco_ws_blueprint.route("/projects/<prjid>/ffts/", methods=["DELETE"])
@project_writable
@context.security.authentication_required
def svc_remove_devices_from_project(prjid):
    """
    Remove multiple ffts/devices from a project
    """
    userid = context.security.get_current_user_id()
    fft_ids = request.json.get('ids', [])
    status, errormsg = mcd_model.delete_devices_from_project(licco_db, userid, prjid, fft_ids)
    if errormsg:
        return json_error(errormsg)
    return json_response({}, ret_status=HTTPStatus.NO_CONTENT)


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
            return json_error(error_msg)

    prj_name = mcd_model.get_project(licco_db, prjid)['name']
    log_time = datetime.datetime.now().strftime("%m%d%Y.%H%M%S")
    log_name = f"{userid}_{prj_name.replace('/', '_')}_{log_time}"
    log, log_handler = create_logger(log_name)

    ok, err, import_status = mcd_import.import_project(context.licco_db, userid, prjid, filestring, log)
    if err:
        return json_error(err)
    log.removeHandler(log_handler)
    log_handler.close()

    prj_name = mcd_model.get_project(licco_db, prjid)["name"]
    status_str = mcd_import.create_status_update(prj_name, import_status)
    response_value = {"status_str": status_str, "log_name": log_name}
    return json_response(response_value)


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
        return json_error(f"Something went wrong: file {report} was not found")


@licco_ws_blueprint.route("/projects/<prjid>/export/", methods=["GET"])
@context.security.authentication_required
def svc_export_project(prjid):
    """
    Export project into a csv that downloads
    """
    project = mcd_model.get_project(licco_db, prjid)
    if not project:
        return json_error(f"Project '{prjid}' does not exist")
    project_name = project["name"]

    ok, err, csv_string = mcd_import.export_project(licco_db, prjid)
    if not ok:
        return json_error(f"Failed to export a project {project['name']}: {err}")

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
            return json_error("At least 1 approver is expected")
        editors = request.json.get("editors", [])

    userid = context.security.get_current_user_id()
    status, err, prj = mcd_model.submit_project_for_approval(licco_db, prjid, userid, editors, approvers, context.notifier)
    if err:
        return json_error(err)
    return json_response(prj)


@licco_ws_blueprint.route("/projects/<prjid>/approve_project", methods=["GET", "POST"])
@context.security.authentication_required
def svc_approve_project(prjid):
    """
    Approve a project
    """
    userid = context.security.get_current_user_id()
    status, all_approved, errormsg, prj = mcd_model.approve_project(licco_db, prjid, userid, context.notifier)
    if not status:
        return json_error(errormsg)
    return json_response(prj)


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
        return json_error("Please provide a reason for why this project is not being approved")

    status, errormsg, prj = mcd_model.reject_project(licco_db, prjid, userid, reason, context.notifier)
    if errormsg:
        return json_error(errormsg)
    return json_response(prj)


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
        return json_error("Please specify a project name and description")

    status, err, newprj = mcd_model.clone_project(licco_db, userid, prjid, project_name, project_description, project_editors, context.notifier)
    if not status:
        return json_error(err)
    return json_response(newprj)


@licco_ws_blueprint.route("/history/project_approvals", methods=["GET"])
@context.security.authentication_required
def svc_get_projects_approval_history():
    """
    Get the approval history of projects in the system
    """
    history = mcd_model.get_projects_approval_history(licco_db, limit=100)
    return json_response(history)
