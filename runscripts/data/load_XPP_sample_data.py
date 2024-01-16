#!/usr/bin/env python

"""
Load the sample data from cxi_sample_data.tsv into the line_config database.
"""
import sys
import logging
import argparse
import csv
import json

import requests
from requests.auth import HTTPBasicAuth
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

keymap = {
    "NL_Z": "nom_loc_z",
    "NL_X": "nom_loc_x",
    "NL_Y": "nom_loc_y",
    "ND_Z": "nom_dim_z",
    "ND_X": "nom_dim_x",
    "ND_Y": "nom_dim_z",
    "R_z": "nom_ang_z",
    "R_x": "nom_ang_x",
    "R_y": "nom_ang_y",
    "Must Ray Trace": "ray_trace",
    "Comments": "comments"
}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action='store_true',
                        help="Turn on verbose logging")
    parser.add_argument("--url", help="The licco endpoint",
                        default="https://pswww.slac.stanford.edu/ws-kerb/mtest")
    parser.add_argument("--user", help="The userid for basic authentication")
    parser.add_argument(
        "--password", help="The password for basic authentication")
    parser.add_argument(
        "projectname", help="The name of a project; we check to see if the project already exists")
    parser.add_argument(
        "lineconfigfile", help="A .tsv export of the Google sheet")

    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    if not args.url.endswith("/"):
        args.url = args.url + "/"

    session = requests.Session()

    if args.user and args.password:
        logger.debug("Using HTTP basic auth ...")
        session.auth = (args.user, args.password)
    else:
        from krtc import KerberosTicket
        logger.debug("Using Kerberos ...")
        host = urlparse(args.url).hostname
        session.headers.update(KerberosTicket('HTTP@' + host).getAuthHeaders())

    with open(args.lineconfigfile, newline='') as csvfile:
        lines = csvfile.readlines()
        reader = csv.DictReader(lines[1:], delimiter="\t")
        fcs = {x["FC"] + "_" + x.get("Fungible", ""): x for x in reader}

    # Per Alex, the First two taxons, delineated by : are the functional and fungible resp.
    for k, v in fcs.items():
        v["Functional"] = v["FC"]
        v["Fungible"] = v.get("Fungible", "")

    projects = session.get(args.url + "ws/projects/").json()["value"]
    prjs = list(filter(lambda x: x["name"] == args.projectname, projects))
    if not prjs:
        prj = session.post(args.url + "ws/projects/", json={
                           "name": args.projectname, "description": args.projectname}).json()["value"]
    else:
        prj = prjs[0]

    fc2id = {x["name"]: x["_id"]
             for x in session.get(args.url + "ws/fcs/").json()["value"]}
    for nm, fc in fcs.items():
        if fc["Functional"] not in fc2id:
            newfc = session.post(args.url + "ws/fcs/", json={
                                 "name": fc["Functional"], "description": "Generated from " + nm}).json()["value"]
            fc2id[fc["Functional"]] = newfc["_id"]

    fg2id = {x["name"]: x["_id"]
             for x in session.get(args.url + "ws/fgs/").json()["value"]}
    for nm, fc in fcs.items():
        if fc["Fungible"] and fc["Fungible"] not in fg2id:
            newfg = session.post(args.url + "ws/fgs/", json={
                                 "name": fc["Fungible"], "description": "Generated from " + nm}).json()["value"]
            fg2id[fc["Fungible"]] = newfg["_id"]

    ffts = {(x["fc"]["name"], x["fg"]["name"]): x["_id"]
            for x in session.get(args.url + "ws/ffts/").json()["value"]}
    for fc in fcs.values():
        if (fc["Functional"], fc["Fungible"]) not in ffts:
            resp = session.post(
                args.url + "ws/ffts/", json={"fc": fc["Functional"], "fg": fc["Fungible"]})
            resp.raise_for_status()
            ret = resp.json()
            if not ret["success"]:
                raise Exception(ret["errormsg"])
            newfft = ret["value"]
            ffts[(newfft["fc"]["name"], newfft["fg"]["name"]
                  if "fg" in newfft else None)] = newfft["_id"]

    fcuploads = []
    for nm, fc in fcs.items():
        fcupload = {}
        fcupload["_id"] = ffts[(fc["Functional"], fc["Fungible"])]
        for k, v in keymap.items():
            if not fc[k]:
                continue
            fcupload[v] = fc[k]
        fcuploads.append(fcupload)
    print(fcuploads)
    resp = session.post(args.url + "ws/projects/" +
                        prj["_id"]+"/ffts/", json=fcuploads)
    resp.raise_for_status()
