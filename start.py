import configparser
from json import JSONEncoder

from flask import Flask, Response
import logging
import os
import sys
import json
from flask_cors import CORS

import context
from notifications.email_sender import EmailSettings, EmailSender, EmailSenderMock
from notifications.notifier import Notifier
from pages import pages_blueprint
from services.licco import licco_ws_blueprint
from dal.mcd_model import initialize_collections

logger = logging.getLogger(__name__)

# Initialize application.
app = Flask("licco")
CORS(app, supports_credentials=True)
# Set the expiration for static files
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 300

app.secret_key = "A secret key for licco"
app.debug = json.loads(os.environ.get("DEBUG", "false").lower())
app.config["TEMPLATES_AUTO_RELOAD"] = app.debug

# unexpected app exceptions are rendered as json
@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(e, exc_info=True)
    out = JSONEncoder().encode({'errormsg': str(e)})
    return Response(out, status=500, mimetype="application/json")


send_smtp_emails = os.environ.get("LICCO_SEND_EMAILS", False)

# read credentials file for notifications module
credentials_file = os.environ.get("LICCO_CREDENTIALS_FILE", "./credentials.ini")

if not os.path.exists(credentials_file):
    print(f"'credentials.ini' file was not found (path: {credentials_file}), email user notifications are disabled")
    app.config["NOTIFICATIONS"] = {"service_url": "http://localhost:3000"}
    app.config["NOTIFICATIONS"]["email"] = {
        "development_mode": not send_smtp_emails,
        "admin_email": ""
    }
else:
    config = configparser.ConfigParser()
    config.read(credentials_file)
    app.config["NOTIFICATIONS"] = {"service_url": config["email"]["service_url"]}

    app.config["NOTIFICATIONS"]["email"] = {
        "url": config["email"]["url"],
        "port": config["email"]["port"],
        "email_auth": config["email"].getboolean("email_auth"),
        "user": config["email"]["user"],
        "password": config["email"]["password"],
        "admin_email": config["email"]["admin_email"],
        "username_to_email_service": config["email"]["username_to_email_service"],
        "development_mode": send_smtp_emails,
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
        return Notifier("", EmailSenderMock(), "")

    email_sender = EmailSenderMock()
    email_config = notifications_config["email"]
    if email_config and not email_config["development_mode"]:
        email_sender = EmailSender(EmailSettings(email_config["url"], email_config["port"],
                                                 email_config["email_auth"],
                                                 email_config["user"], email_config["password"],
                                                 email_config["username_to_email_service"]))
    service_url = notifications_config["service_url"]
    admin_email = notifications_config["email"]["admin_email"]

    return Notifier(service_url, email_sender, admin_email)


context.notifier = create_notifier(app)

initialize_collections(context.licco_db)


if __name__ == '__main__':
    print("Please use gunicorn for development as well.")
    sys.exit(-1)
