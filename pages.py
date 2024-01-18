import os
import json
import logging
import pkg_resources

import context

from flask import Blueprint, render_template, send_file, abort, request

from dal.licco import get_project

pages_blueprint = Blueprint('pages_api', __name__)

logger = logging.getLogger(__name__)


@pages_blueprint.route("/")
@context.security.authentication_required
def index():
    return render_template("licco.html", logged_in_user=context.security.get_current_user_id())


@pages_blueprint.route("/projects/<prjid>/index.html")
@context.security.authentication_required
def project(prjid):
    prjobj = get_project(prjid)
    return render_template("project.html", logged_in_user=context.security.get_current_user_id(), project_id=prjid, prjstatus=prjobj["status"], template_name="project.html")


@pages_blueprint.route("/projects/<prjid>/diff.html")
@context.security.authentication_required
def project_diff(prjid):
    prjobj = get_project(prjid)
    otherprjid = request.args["otherprjid"]
    return render_template("project.html", logged_in_user=context.security.get_current_user_id(), project_id=prjid, prjstatus=prjobj["status"], template_name="projectdiff.html", otherprjid=otherprjid)


@pages_blueprint.route('/js/<path:path>')
def send_js(path):
    pathparts = os.path.normpath(path).split(os.sep)
    if pathparts[0] == 'python':
        # This is code for gettting the JS file from the package data of the python module.
        filepath = pkg_resources.resource_filename(
            pathparts[1], os.sep.join(pathparts[2:]))
        if os.path.exists(filepath):
            return send_file(filepath)

    filepath = os.path.join("node_modules", path)
    if not os.path.exists(filepath):
        filepath = os.path.join(
            "node_modules", pathparts[0], "dist", *pathparts[1:])
    if os.path.exists(filepath):
        return send_file(filepath)
    else:
        logger.error("Cannot find static file %s in %s", path, filepath)
        abort(403)
        return None
