import logging
from typing import List, Dict
from bson import ObjectId

logger = logging.getLogger(__name__)

def get_project_attributes(db, projectid, fftid=None, skipClonedEntries=False, asoftimestamp=None, commentAfterTimestamp=None):
    project = db["projects"].find_one({"_id": ObjectId(projectid)})
    if not project:
        logger.error("Cannot find project for id %s", projectid)
        return {}

    mtch = { "$match": {"$and": [ { "prj": ObjectId(projectid)} ]}}
    if skipClonedEntries:  # skip initial values (when cloning a project)
        mtch["$match"]["$and"].append({"time": {"$gt": project["creation_time"]}})
    if asoftimestamp:   # find the values before a specific timestamp
        mtch["$match"]["$and"].append({"time": {"$lte": asoftimestamp}})
    if fftid:  # only values of a specific fftid should be returned
        mtch["$match"]["$and"].append({"fft": ObjectId(fftid)})

    histories = [x for x in db["projects_history"].aggregate([
        mtch,
        {"$match": {"key": {"$ne": "discussion"}}},
        {"$sort": {"time": -1}},
        {"$group": {
            "_id": {"fft": "$fft", "key": "$key"},
            "latestkey": {"$first":  "$key"},
            "latestval": {"$first":  "$val"},
        }},
        {"$project": {
            "prj": "$prj",
            "fft": "$_id.fft",
            "latestkey": "$latestkey",
            "latestval": "$latestval",
        }},
        {"$lookup": {"from": "ffts", "localField": "fft", "foreignField": "_id", "as": "fftobj"}},
        {"$unwind": "$fftobj"},
        {"$lookup": {"from": "fcs", "localField": "fftobj.fc", "foreignField": "_id", "as": "fcobj"}},
        {"$unwind": "$fcobj"},
        {"$lookup": {"from": "fgs", "localField": "fftobj.fg", "foreignField": "_id", "as": "fgobj"}},
        {"$unwind": "$fgobj"},
        {"$sort": {"prj": 1, "fcobj.name": 1, "fgobj.name": 1, "latestkey": 1}}
    ])]
    details = {}
    for hist in histories:
        fft = hist["fftobj"]
        fft_id = str(fft["_id"])

        if fft_id not in details:
            details[fft_id] = { "fft": { "_id": fft_id, "fc": hist["fcobj"]["name"], "fg": hist["fgobj"]["name"] } }
        field_name = hist["latestkey"]
        field_val = hist["latestval"]

        # all other fields are primitive types (scalars, strings) and only the latest values are important
        if field_name == 'beamline':
            # turn single string beamlines into an array (initially beamlines were a single string)
            # This should be handled in the migration script for MCD 2.0
            if field_val and isinstance(field_val, str):
                field_val = [field_val]

        if field_name == "location":
            if details[fft_id].get('area'):
                # area was already found and inserted, this location field should be skipped
                continue
            field_name = 'area'

        details[fft_id][field_name] = field_val

    if len(details) == 0:
        # we found nothing for this set of filters, early return
        return details

    # fetch and aggregate comments for all ffts
    commentFilter = {"$match": {"$and": [{"key": "discussion"}]}}
    if commentAfterTimestamp:
        commentFilter["$match"]["$and"].append({"time": {"$gt": commentAfterTimestamp}})

    comments: List[Dict[str, any]] = [x for x in db["projects_history"].aggregate([
        mtch,
        commentFilter,
        {"$sort": {"time": -1}},
        {"$project": {
            "prj": "$prj",
            "fft": "$fft",
            "key": "$key",
            "val": "$val",
            "user": "$user",
            "time": "$time",
        }},
    ])]

    for c in comments:
        field_name = "discussion"
        fft_id = str(c["fft"])
        comment_id = str(c["_id"])
        user = c["user"]
        timestamp = c["time"]
        val = c["val"]

        device = details.get(fft_id, None)
        if not device:
            # this comment is not relevant since the project no longer has this device
            continue

        device_comments = device.get(field_name, [])
        device_comments.append({'id': comment_id, 'author': user, 'time': timestamp, 'comment': val})
        details[fft_id][field_name] = device_comments

    for device in details.values():
        # ensures discussion field is always present (at least as an empty array)
        if not device.get("discussion"):
            device["discussion"] = []

    return details


def get_all_project_changes(propdb, projectid):
    project = propdb["projects"].find_one({"_id": ObjectId(projectid)})
    if not project:
        logger.error("Cannot find project for id %s", projectid)
        return {}

    mtch = { "$match": {"$and": [ { "prj": ObjectId(projectid)} ]}}

    histories = [ x for x in propdb["projects_history"].aggregate([
        mtch,
        {"$sort": { "time": -1}},
        {"$lookup": { "from": "projects", "localField": "prj", "foreignField": "_id", "as": "prjobj"}},
        {"$unwind": "$prjobj"},
        {"$lookup": { "from": "ffts", "localField": "fft", "foreignField": "_id", "as": "fftobj"}},
        {"$unwind": "$fftobj"},
        {"$lookup": { "from": "fcs", "localField": "fftobj.fc", "foreignField": "_id", "as": "fcobj"}},
        {"$unwind": "$fcobj"},
        {"$lookup": { "from": "fgs", "localField": "fftobj.fg", "foreignField": "_id", "as": "fgobj"}},
        {"$unwind": "$fgobj"},
        {"$project": {
            "prj": "$prjobj.name",
            "fc": "$fcobj.name",
            "fg": "$fgobj.name",
            "key": "$key",
            "val": "$val",
            "user": "$user",
            "time": "$time"
        }},
    ])]
    return histories
