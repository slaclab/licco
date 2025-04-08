import logging
from functools import wraps
from typing import Mapping, Any

from bson import ObjectId
from flask import abort
from pymongo import MongoClient

from app_config import AppConfig, EmailConfig
from dal import db_utils
from dal.mcd_model import initialize_collections
from modules.flask_authnz.flask_authnz import FlaskAuthnz, MongoDBRoles, UserGroups
from notifications.email_sender import EmailSenderMock, EmailSettings, EmailSender
from notifications.notifier import Notifier

logger = logging.getLogger(__name__)

# global context variables that are used within API controllers
mongo_client: MongoClient[Mapping[str, Any]] = None
licco_db = None
security: FlaskAuthnz = None
notifier: Notifier = None


def create_notifier(conf: EmailConfig) -> Notifier:
    if not conf:
        return Notifier("", EmailSenderMock(), "")

    email_sender = EmailSenderMock()
    production_mode = conf.send_emails
    if production_mode:
        email_sender = EmailSender(EmailSettings(
            conf.url, conf.port,
            conf.email_auth,
            conf.user, conf.password,
            conf.username_to_email_service
        ))

    service_url = conf.licco_service_url
    admin_email = conf.admin_email
    return Notifier(service_url, email_sender, admin_email)


def init_context(config: AppConfig):
    """Initialize global context variables"""
    global mongo_client
    global licco_db
    global security
    global notifier

    # Set up the Mongo connection.
    mongo_client = db_utils.create_mongo_client(config.mongo_url, config.mongo_connection_timeout)
    licco_db = mongo_client["lineconfigdb"]
    initialize_collections(licco_db)

    notifier = create_notifier(config.email_config)

    logged_in_as_user = config.app_logged_in_as_user

    class LiccoAuthnz(FlaskAuthnz):
        def __init__(self, roles_dal, application_name):
            super().__init__(roles_dal, application_name)

        def check_privilege_for_project(self, priv_name, prjid=None):
            if priv_name in ["read"]:
                return True
            if self.check_privilege_for_experiment(priv_name, None, None):
                return True
            if prjid and priv_name in ["write", "edit"]:
                logged_in_user = self.get_current_user_id()
                oid = ObjectId(prjid)
                prj = licco_db["projects"].find_one({"_id": oid})
                if prj and (prj["owner"] == logged_in_user) or logged_in_user in prj.get("editors", []):
                    return True
            return False

        def get_current_user_id(self):
            if logged_in_as_user:
                return logged_in_as_user
            return super().get_current_user_id()

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
