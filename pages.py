import os
import json
import logging
import pkg_resources
import context
from flask import Blueprint, render_template, send_file, abort, request
from dal import mcd_model

pages_blueprint = Blueprint('pages_api', __name__)

logger = logging.getLogger(__name__)


@pages_blueprint.route("/")
@context.security.authentication_required
def index():
    privileges = { x : context.security.check_privilege_for_project(x, None) for x in [ "read", "write", "edit", "approve" ]}
    return render_template("licco.html",
                           logged_in_user=context.security.get_current_user_id(),
                           privileges=json.dumps(privileges))
