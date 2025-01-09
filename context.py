import logging
import os
from functools import wraps

from pymongo import MongoClient
from bson import ObjectId
from flask import abort

from modules.flask_authnz.flask_authnz import FlaskAuthnz, MongoDBRoles, UserGroups
from notifications.notifier import Notifier

logger = logging.getLogger(__name__)

__author__ = 'mshankar@slac.stanford.edu'

# Application context.
app = None

# Set up the Mongo connection.
MONGODB_URL = os.environ.get("MONGODB_URL", None)
if not MONGODB_URL:
    print("Please use the environment variable MONGODB_URL to configure the database connection.")
mongo_client = MongoClient(host=MONGODB_URL, tz_aware=True)
licco_db = mongo_client["lineconfigdb"]


class LiccoAuthnz(FlaskAuthnz):
    def __init__(self, roles_dal, application_name):
        super().__init__(roles_dal, application_name)
    def check_privilege_for_project(self, priv_name, prjid=None):
        if priv_name in ["read"]:
            return True
        if super().check_privilege_for_experiment(priv_name, None, None):
            return True
        if prjid and priv_name in ["write", "edit"]:            
            logged_in_user = super().get_current_user_id()
            oid = ObjectId(prjid)
            prj = licco_db["projects"].find_one({"_id": oid})
            if prj and (prj["owner"] == logged_in_user) or logged_in_user in prj.get("editors", []):
                return True
        return False
    def authorization_required(self, *params):
        '''
        Decorator for project specific authorization - decorate your function in this order
        To pass in an project id, use the variable name prjid in your flask variable names
        '''
        if len(params) < 1:
            raise Exception("Application privilege not specified when specifying the authorization")
        priv_name = params[0]
        if priv_name not in self.priv2roles:
            raise Exception("Please specify an appropriate application privilege for the authorization_required decorator " + ",".join(self.priv2roles.keys()))
        def wrapper(f):
            @wraps(f)
            def wrapped(*args, **kwargs):
                prjid = kwargs.get('prjid', None)
                logger.info("Looking to authorize %s for app %s for privilege %s for project %s" % (self.get_current_user_id(), self.application_name, priv_name, prjid))
                if not self.check_privilege_for_project(priv_name, prjid):
                    abort(403)
                return f(*args, **kwargs)
            return wrapped
        return wrapper
    


# Set up the security manager
usergroups = UserGroups()
roleslookup = MongoDBRoles(mongo_client, usergroups, "lineconfigdb")
security = LiccoAuthnz(roleslookup, "Licco")

# notifier is constructed in start.py, due to problems with passing around app context and
# its configuration. There is probably a better solution than this.
notifier: Notifier = None
