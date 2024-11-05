import configparser

from flask import Flask
import logging
import os
import sys
import json
from flask_cors import CORS

import context
from notifications.email_sender import EmailSettings
from notifications.notifier import Notifier
from pages import pages_blueprint
from services.licco import licco_ws_blueprint
from dal.licco import initialize_collections

__author__ = 'mshankar@slac.stanford.edu'

# Initialize application.
app = Flask("licco")
CORS(app, supports_credentials=True)
# Set the expiration for static files
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 300

app.secret_key = "A secret key for licco"
app.debug = json.loads(os.environ.get("DEBUG", "false").lower())
app.config["TEMPLATES_AUTO_RELOAD"] = app.debug

app.config["NOTIFICATIONS"] = {"service_url": "http://localhost:3000"}

# read credentials file for notifications module
credentials_file = "./credentials.ini"
if not os.path.exists(credentials_file):
    print("'credentials.ini' file was not found, user notifications are disabled")
else:
    config = configparser.ConfigParser()
    config.read(credentials_file)
    app.config["NOTIFICATIONS"]["email"] = {
        "url": config["email"]["url"],
        "port": config["email"]["port"],
        "user": config["email"]["user"],
        "password": config["email"]["password"],
    }

root = logging.getLogger()
root.setLevel(logging.getLevelName(os.environ.get("LOG_LEVEL", "INFO")))
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
root.addHandler(ch)


# Register routes.
app.register_blueprint(pages_blueprint, url_prefix="")
app.register_blueprint(licco_ws_blueprint, url_prefix="/ws")


def create_notifier(app: Flask) -> Notifier:
    notifications_config = app.config["NOTIFICATIONS"]
    if not notifications_config:
        # empty notifier without configuration will not send any notifications
        return Notifier("")

    service_url = notifications_config["service_url"]
    email_config = notifications_config["email"]
    if email_config:
        return Notifier(service_url, EmailSettings(email_config["url"], email_config["port"],
                                      email_config["user"], email_config["password"]))
    return Notifier(service_url)


context.notifier = create_notifier(app)

initialize_collections()


if __name__ == '__main__':
    print("Please use gunicorn for development as well.")
    sys.exit(-1)
