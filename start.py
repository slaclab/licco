from dal.licco import initialize_collections
from flask import Flask, current_app
import logging
import os
import sys
import json
import requests

from context import app, licco_db, security
from pages import pages_blueprint
from services.licco import licco_ws_blueprint
from dal.licco import initialize_collections

__author__ = 'mshankar@slac.stanford.edu'


# Initialize application.
app = Flask("licco")
# Set the expiration for static files
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 300

app.secret_key = "A secret key for licco"
app.debug = json.loads(os.environ.get("DEBUG", "false").lower())
app.config["TEMPLATES_AUTO_RELOAD"] = app.debug

root = logging.getLogger()
root.setLevel(logging.getLevelName(os.environ.get("LOG_LEVEL", "INFO")))
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
root.addHandler(ch)


# Register routes.
app.register_blueprint(pages_blueprint, url_prefix="")
app.register_blueprint(licco_ws_blueprint, url_prefix="/ws")

initialize_collections()

if __name__ == '__main__':
    print("Please use gunicorn for development as well.")
    sys.exit(-1)
