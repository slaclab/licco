#!/bin/bash

PRNT_DIR=`dirname $PWD`
G_PRNT_DIR=`dirname $PRNT_DIR`;
GG_PRNT_DIR=`dirname $G_PRNT_DIR`;
GGG_PRNT_DIR=`dirname $GG_PRNT_DIR`;
EXTERNAL_CONFIG_FILE="${GGG_PRNT_DIR}/appdata/licco_config/licco_config.sh"


if [[ -f "${EXTERNAL_CONFIG_FILE}" ]]
then
   echo "Sourcing deployment specific configuration from ${EXTERNAL_CONFIG_FILE}"
   source "${EXTERNAL_CONFIG_FILE}"
else
   echo "Did not find external deployment specific configuration - ${EXTERNAL_CONFIG_FILE}"
fi


export ACCESS_LOG_FORMAT='%(h)s %(l)s %({REMOTE_USER}i)s %(t)s "%(r)s" "%(q)s" %(s)s %(b)s %(D)s'
export LOG_LEVEL=${LOG_LEVEL:-"INFO"}
export SERVER_IP_PORT=${SERVER_IP_PORT:-"0.0.0.0:5000"}

export PYTHONPATH="${PWD}/modules/flask_authnz":"${PYTHONPATH}"

# The exec assumes you are calling this from supervisord. If you call this from the command line; your bash shell is proabably gone and you need to log in.
exec gunicorn start:app -b ${SERVER_IP_PORT} --worker-class gthread --reload \
       --log-level=${LOG_LEVEL} --capture-output --enable-stdio-inheritance \
       --access-logfile - --access-logformat "${ACCESS_LOG_FORMAT}"
