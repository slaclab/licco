import os
import logging

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)

def get_project_attributes(propdb, projectid, skipClonedEntries=True, asoftimestamp=None):
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
            "_id": {"fc": "$fc", "key": "$key"},
            "latestkey": {"$first":  "$key"},
            "latestval": {"$first":  "$val"}
        }},
        { "$project": {
            "prj": "$prj",
            "fc": "$_id.fc",
            "latestkey": "$latestkey",
            "latestval": "$latestval",
        }},
        { "$lookup": { "from": "fcs", "localField": "fc", "foreignField": "_id", "as": "fcobj"}},
        { "$unwind": "$fcobj" },
        { "$sort": {"prj": 1, "fc": 1, "latestkey": 1}}
    ])]
    details = {}
    for hist in histories:
        fc = str(hist["fc"])
        if fc not in details:
            details[fc] = { "name": hist["fcobj"]["name"] }
        details[fc][hist["latestkey"]] = hist["latestval"]
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
        { "$lookup": { "from": "fcs", "localField": "fc", "foreignField": "_id", "as": "fcobj"}},
        { "$unwind": "$fcobj" },
        { "$project": {
            "prj": "$prjobj.name",
            "fc": "$fcobj.name",
            "key": "$key",
            "val": "$val",
            "user": "$user",
            "time": "$time"
        }},
    ])]
    return histories
