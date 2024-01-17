import json
import logging
import os

from pymongo import MongoClient
from modules.flask_authnz.flask_authnz import FlaskAuthnz, MongoDBRoles, UserGroups

logger = logging.getLogger(__name__)

__author__ = 'mshankar@slac.stanford.edu'

# Application context.
app = None

# Set up the Mongo connection.
MONGODB_URL=os.environ.get("MONGODB_URL", None)
if not MONGODB_URL:
    print("Please use the enivironment variable MONGODB_URL to configure the database connection.")
licco_db = MongoClient(host=MONGODB_URL, tz_aware=True)

ROLEDB_URL=os.environ.get("ROLEDB_URL", None)
roledbclient = licco_db
if ROLEDB_URL:
    print("Using a different database for the roles")
    roledbclient = MongoClient(host=ROLEDB_URL, tz_aware=True)
else:
    print("Using the same database for the roles")

# Set up the security manager
usergroups = UserGroups()
roleslookup = MongoDBRoles(roledbclient, usergroups)
security = FlaskAuthnz(roleslookup, "LogBook")
