import argparse
import os

import app_config
import logging
import sys
from json import JSONEncoder
from flask import Flask, Response
from flask_cors import CORS

import context

# load configuration
licco_config = os.environ.get("LICCO_CONFIG", None)
is_gunicorn_running = "gunicorn" in os.environ.get("SERVER_SOFTWARE", "")
if is_gunicorn_running:
    conf = app_config.load_config(licco_config)
else:
    if licco_config:
        conf = app_config.load_config(licco_config)
    else:
        parser = argparse.ArgumentParser(description="Licco CLI Options")
        parser.add_argument("-c", "--config", default="", help="Path to a Licco config file")
        args = parser.parse_args()
        conf = app_config.load_config(args.config)

print("================================= APP CONFIG ===================================")
print(conf)
print("================================================================================")
print("")

# setup a global logger
logger = logging.getLogger(__name__)
root = logging.getLogger()
root.setLevel(logging.getLevelName(conf.app_log_level))
# filter out server heartbeat logs
logging.getLogger('pymongo.topology').setLevel(level=logging.WARNING)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
root.addHandler(ch)

# init flask service
app = Flask("licco")
CORS(app, supports_credentials=True)
# set the expiration for static files
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = conf.app_send_file_max_age_default
app.secret_key = conf.app_secret_key
app.debug = str(conf.app_debug).lower()
app.config["TEMPLATES_AUTO_RELOAD"] = app.debug

# unexpected app exceptions are rendered as json
@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(e, exc_info=True)
    out = JSONEncoder().encode({'errormsg': str(e)})
    return Response(out, status=500, mimetype="application/json")


# setup global variables (db, email notifiers, security helpers). Also migrates db
context.init_context(conf)

# register routes (this should happen after initializing context, since controllers refer to those global variables)
from pages import pages_blueprint              # noqa: E402
from services.licco import licco_ws_blueprint  # noqa: E402
app.register_blueprint(pages_blueprint, url_prefix="")
app.register_blueprint(licco_ws_blueprint, url_prefix="/ws")


if __name__ == '__main__':
    print("Please use gunicorn for development as well.")
    sys.exit(-1)
