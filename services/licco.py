'''
Web service endpoints for licco
'''

import os
import json
import logging
import fnmatch
from datetime import datetime
import pytz

import requests
import context

from flask import Blueprint, jsonify, request, url_for, Response

from dal.utils import JSONEncoder
from dal.licco import get_projects_for_user, get_project, get_project_fcs, get_fcs, \
    create_new_functional_component, update_functional_component_in_project, submit_project_for_approval, approve_project, \
    get_currently_approved_project, diff_project, FCState, clone_project, get_project_changes, \
    get_tags_for_project, add_project_tag


__author__ = 'mshankar@slac.stanford.edu'

licco_ws_blueprint = Blueprint('business_service_api', __name__)

logger = logging.getLogger(__name__)

def logAndAbort(error_msg, ret_status=500):
    logger.error(error_msg)
    return Response(error_msg, status=ret_status)

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
    return JSONEncoder().encode({"success": True, "value": { k.value : v for k,v in descs.items() }})


@licco_ws_blueprint.route("/projects/", methods=["GET"])
@context.security.authentication_required
def svc_get_projects_for_user():
    """
    Get the projects for a user
    """
    logged_in_user = context.security.get_current_user_id()
    projects = get_projects_for_user(logged_in_user)
    return JSONEncoder().encode({"success": True, "value": projects})

@licco_ws_blueprint.route("/approved", methods=["GET"])
@context.security.authentication_required
def svc_get_currently_approved_project():
    """ Get the currently approved project """
    logged_in_user = context.security.get_current_user_id()
    prj = get_currently_approved_project()
    prj_fcs = get_project_fcs(prj["_id"])
    prj["fcs"] = prj_fcs
    return JSONEncoder().encode({"success": True, "value": prj})

@licco_ws_blueprint.route("/projects/<id>/", methods=["GET"])
@context.security.authentication_required
def svc_get_project(id):
    """
    Get the project details given a project id.
    """
    logged_in_user = context.security.get_current_user_id()
    project_details = get_project(id)
    return JSONEncoder().encode({"success": True, "value": project_details})

@licco_ws_blueprint.route("/projects/<id>/fcs/", methods=["GET"])
@context.security.authentication_required
def svc_get_project_fcs(id):
    """
    Get the project functional components given a project id.
    """
    logged_in_user = context.security.get_current_user_id()
    showallentries = json.loads(request.args.get("showallentries", "true"))
    asoftimestampstr = request.args.get("asoftimestamp", None)
    if asoftimestampstr:
        asoftimestamp = datetime.strptime(asoftimestampstr, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=pytz.UTC)
        print(asoftimestamp)
    else:
        asoftimestamp=None
    project_fcs = get_project_fcs(id, showallentries=showallentries, asoftimestamp=asoftimestamp)
    def __filter__(f, d):
        """ Apply f onto d as a filter """
        r = {}
        for k, v in d.items():
            if f(k, v):
                r[k] = v
        return r

    if request.args.get("name", ""):
        project_fcs = __filter__(lambda k,v: fnmatch.fnmatch(v["name"], request.args["name"]), project_fcs)
    if request.args.get("state", ""):
        project_fcs = __filter__(lambda k,v: v["state"] == request.args["state"], project_fcs)
    return JSONEncoder().encode({"success": True, "value": project_fcs})

@licco_ws_blueprint.route("/projects/<id>/changes/", methods=["GET"])
@context.security.authentication_required
def svc_get_project_changes(id):
    """
    Get the functional component objects
    """
    changes = get_project_changes(id)
    return JSONEncoder().encode({"success": True, "value": changes})

@licco_ws_blueprint.route("/fcs/", methods=["GET"])
@context.security.authentication_required
def svc_get_fcs():
    """
    Get the functional component objects
    """
    fcs = get_fcs()
    return JSONEncoder().encode({"success": True, "value": fcs})

@licco_ws_blueprint.route("/fcs/", methods=["POST"])
@context.security.authentication_required
def svc_create_fc():
    """
    Create a functional component
    """
    newfc = request.json
    status, errormsg, fc = create_new_functional_component(name=newfc.get("name", ""), description=newfc.get("description", ""))
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": fc})

@licco_ws_blueprint.route("/projects/<prjid>/fcs/<fcid>", methods=["POST"])
@context.security.authentication_required
def svc_update_fc_in_project(prjid, fcid):
    """
    Update the values of a functional component in a project
    """
    fcupdate = request.json
    userid = context.security.get_current_user_id()
    status, errormsg, fc = update_functional_component_in_project(prjid, fcid, fcupdate, userid)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": fc})

@licco_ws_blueprint.route("/projects/<prjid>/submit_for_approval", methods=["GET", "POST"])
@context.security.authentication_required
def svc_submit_for_approval(prjid):
    """
    Submit a project for approval
    """
    userid = context.security.get_current_user_id()
    status, errormsg, prj = submit_project_for_approval(prjid, userid)
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
    status, erorrmsg, newprj = clone_project(prjid, newprjdetails["name"], newprjdetails["description"], userid)
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
    changeid = request.args.get("change_id", None)
    if not tagname:
        return JSONEncoder().encode({"success": False, "errormsg": "Please specify the tag_name", "value": None})
    if not changeid:
        changes = get_project_changes(prjid)
        if not changes:
            return JSONEncoder().encode({"success": False, "errormsg": "Cannot tag a project without a change", "value": None})
        logger.info("Latest change is at " + str(changes[0]["time"]))
        changeid = changes[0]["_id"]

    status, errormsg, tags = add_project_tag(prjid, tagname, changeid)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": tags})
