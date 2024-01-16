#!/usr/bin/env python

"""
Load the sample data from cxi_sample_data.tsv into the line_config database.
"""
import io
import sys
import logging
import argparse
import csv

import requests
from requests.auth import HTTPBasicAuth
from urllib.parse import urlparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action='store_true', help="Turn on verbose logging")
    parser.add_argument("--url", help="The licco endpoint", default="https://pswww.slac.stanford.edu/ws-kerb/mtest")
    # parser.add_argument("--user", help="The userid for basic authentication")
    # parser.add_argument("--password", help="The password for basic authentication")
    parser.add_argument("projectname", help="The name of a project; we check to see if the project already exists")
    parser.add_argument("lineconfigfile", help="A .tsv export of the Google sheet")

    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    if not args.url.endswith("/"):
        args.url = args.url + "/"


    logger = logging.getLogger(__name__)

    keymap = {
        "TC_part_no" : "tc_part_no",
        "State" : "state",
        "Comments": "comments",
        "LCLS_Z_loc": "nom_loc_z",
        "LCLS_X_loc": "nom_loc_x",
        "LCLS_Y_loc": "nom_loc_y",
        "Z_dim" : "nom_dim_z",
        "Y_dim" : "nom_dim_x",
        "X_dim" : "nom_dim_y",
        "LCLS_X_pitch": "nom_ang_x",
        "LCLS_Y_yaw": "nom_ang_y",
        "LCLS_Z_roll": "nom_ang_z",
        "Must_Ray_Trace": "ray_trace"
    }

    project_name  = args.projectname
    session = requests.Session()

    # if args.user and args.password:
    #     logger.debug("Using HTTP basic auth ...")
    #     session.auth = (args.user, args.password)
    # else:
    #     from krtc import KerberosTicket
    #     logger.debug("Using Kerberos ...")
    #     host = urlparse(args.url).hostname
    #     session.headers.update(KerberosTicket('HTTP@' + host).getAuthHeaders())

    filename = args.lineconfigfile

    # Parse expected file format
    csvfile = open(filename, newline='')
    with open(filename, "r") as csvfile:
        body = csvfile.read()
        lines = body.split('\n')
        # Find the header row
        for index, line in enumerate(lines):
            if 'FC' in line and 'Fungible' in line:
                break
        else:
            raise RuntimeError("Incorrect upload file format. Please include headers.")
        data = '\n'.join(lines[index:])

    with io.StringIO(data) as fp:
        reader = csv.DictReader(fp)
        fcs = { x["FC"]: x for x in reader }

    projects = session.get(args.url + "ws/projects/").json()["value"]
    prjs = list(filter(lambda x: x["name"] == project_name, projects))
    if not prjs:
        prj = session.post(args.url + "ws/projects/", json={"name": project_name, "description": project_name}).json()["value"]
    else:
        prj = prjs[0]

    fc2id = {
        x["name"] : x["_id"]
        for x in session.get(args.url + "ws/fcs/").json()["value"]
    }
    for nm, fc in fcs.items():
        if fc["FC"] not in fc2id:
            newfc = session.post(args.url + "ws/fcs/", json={"name": fc["FC"], "description": "Generated from " + nm}).json()["value"]
            fc2id[fc["FC"]] = newfc["_id"]

    fg2id = {
        x["name"] : x["_id"] 
        for x in session.get(args.url + "ws/fgs/").json()["value"]
    }

    for nm, fc in fcs.items():
        if fc["Fungible"] and fc["Fungible"] not in fg2id:
            newfg = session.post(args.url + "ws/fgs/", json={"name": fc["Fungible"], "description": "Generated from " + nm}).json()["value"]
            fg2id[fc["Fungible"]] = newfg["_id"]

    ffts = {(x["fc"]["name"], x["fg"]["name"]) : x["_id"] for x in session.get(args.url + "ws/ffts/").json()["value"]}
    for fc in fcs.values():
        if (fc["FC"], fc["Fungible"]) not in ffts:
            resp = session.post(args.url + "ws/ffts/", json={"fc": fc["FC"], "fg": fc["Fungible"]})
            resp.raise_for_status()
            ret = resp.json()
            if not ret["success"]:
                raise Exception(ret["errormsg"])
            newfft = ret["value"]
            ffts[(newfft["fc"]["name"], newfft["fg"]["name"] if "fg" in newfft else None )] = newfft["_id"]

    fcuploads = []
    for nm, fc in fcs.items():
        fcupload = {}
        fcupload["_id"] = ffts[(fc["FC"], fc["Fungible"])]
        for k, v in keymap.items():
            if k not in fc:
                continue
            fcupload[v] = fc[k]
        fcuploads.append(fcupload)
    resp = session.post(args.url + "ws/projects/"+prj["_id"]+"/ffts/", json=fcuploads)
    resp.raise_for_status()
