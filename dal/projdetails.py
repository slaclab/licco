import os
import logging

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)

def get_project_attributes(propdb, projectid, skipClonedEntries=False, asoftimestamp=None):
    project = propdb["projects"].find_one({"_id": ObjectId(projectid)})
    if not project:
        logger.error("Cannot find project for id %s", projectid)
        return {}

    mtch = { "$match": {"$and": [ { "prj": ObjectId(projectid)} ]}}
    if skipClonedEntries:
        mtch["$match"]["$and"].append({"time": {"$gt": project["creation_time"]}})
    if asoftimestamp:
        mtch["$match"]["$and"].append({"time": {"$lte": asoftimestamp}})

    histories = [ x for x in propdb["projects_history"].aggregate([
        mtch,
        { "$sort": { "time": -1 }},
        { "$group": {
            "_id": {"fft": "$fft", "key": "$key"},
            "latestkey": {"$first":  "$key"},
            "latestval": {"$first":  "$val"}
        }},
        { "$project": {
            "prj": "$prj",
            "fft": "$_id.fft",
            "latestkey": "$latestkey",
            "latestval": "$latestval",
        }},
        { "$lookup": { "from": "ffts", "localField": "fft", "foreignField": "_id", "as": "fftobj"}},
        { "$unwind": "$fftobj" },
        {"$lookup": { "from": "fcs", "localField": "fftobj.fc", "foreignField": "_id", "as": "fcobj" }},
        {"$unwind": "$fcobj"},
        {"$lookup": { "from": "fgs", "localField": "fftobj.fg", "foreignField": "_id", "as": "fgobj" }},
        {"$unwind": "$fgobj"},
        { "$sort": {"prj": 1, "fcobj.name": 1, "fgobj.name": 1, "latestkey": 1}}
    ])]
    details = {}
    for hist in histories:
        fft = str(hist["fftobj"]["_id"])
        if fft not in details:
            details[fft] = { "fft": { "_id": fft, "fc": hist["fcobj"]["name"], "fg": hist["fgobj"]["name"] } }
        details[fft][hist["latestkey"]] = hist["latestval"]
    return details


def get_all_project_changes(propdb, projectid):
    project = propdb["projects"].find_one({"_id": ObjectId(projectid)})
    if not project:
        logger.error("Cannot find project for id %s", projectid)
        return {}

    mtch = { "$match": {"$and": [ { "prj": ObjectId(projectid)} ]}}

    histories = [ x for x in propdb["projects_history"].aggregate([
        mtch,
        { "$sort": { "time": -1 }},
        { "$lookup": { "from": "projects", "localField": "prj", "foreignField": "_id", "as": "prjobj"}},
        { "$unwind": "$prjobj" },
        { "$lookup": { "from": "ffts", "localField": "fft", "foreignField": "_id", "as": "fftobj"}},
        { "$unwind": "$fftobj" },
        {"$lookup": { "from": "fcs", "localField": "fftobj.fc", "foreignField": "_id", "as": "fcobj" }},
        {"$unwind": "$fcobj"},
        { "$lookup": { "from": "fgs", "localField": "fftobj.fg", "foreignField": "_id", "as": "fgobj" }},
        { "$unwind": "$fgobj"},
        { "$project": {
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
