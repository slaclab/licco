import csv
import datetime
import io
import logging
import os
import uuid
from typing import List, Dict
import pytest
from bson import ObjectId
from pymongo import MongoClient

# ----------------------------------------------------------------------------------------------
# This script is used for migrating from: MCD 1.0 -> MCD 2.0
# ----------------------------------------------------------------------------------------------

DB_NAME = "_TEST_MIGRATION"
logger = logging.getLogger(__name__)

def create_mongo_client(mongodb_url: str = "", timeout: int = 5000):
    if not mongodb_url:
        mongodb_url = os.environ.get("MONGODB_URL", None)

    if not mongodb_url:
        logger.info("Connecting to MongoDB on localhost:27017")
    return MongoClient(host=mongodb_url, tz_aware=True, serverSelectionTimeoutMS=timeout)

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
        if field_name == "beamline":
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



def group_project_histories_by_timestamp(db, project_id):
    changes_by_timestamp: Dict[int, List[any]] = {}
    changes = get_all_project_changes(db, project_id)
    # get all the changes together according ot the timestamp
    for change in changes:
        # drop seconds so we merge changes by minute: this lets us group all changes during a csv import into one
        timestamp = change['time'].replace(second=0, microsecond=0)
        changes = changes_by_timestamp.get(timestamp, [])
        changes.append(change)
        changes_by_timestamp[timestamp] = changes
    return changes_by_timestamp

def create_new_device_format(project_id, old_values, creation_time = None):
    MCD = 2
    if creation_time is None:
        creation_time = datetime.datetime.now(datetime.UTC)
    values = {
        'device_id': str(uuid.uuid4()),
        'device_type': MCD,
        'created': creation_time,
        'project_id': str(project_id),  # TODO: not sure if we want a project id in device history or not?
        'fc': old_values['fft']['fc'],
        'fg': old_values['fft']['fg'],
        'discussion': [],
    }
    for key, val in old_values.items():
        if key == 'fft':
            continue
        if key == 'discussion':
            for discussion in val:
                t = discussion.pop('time')
                discussion['created'] = t
        values[key] = val
    return values

def migrate_project(old_db, new_db, project,  output_dir):
    project_name = project['name']
    project_id = project['_id']
    # store latest device values into a database
    created = datetime.datetime.now(datetime.UTC)
    latest_device_values = get_project_attributes(old_db, project_id)
    devices = []
    for _, old_device_format in latest_device_values.items():
        new_device = create_new_device_format(project_id, old_device_format, creation_time=created)
        devices.append(new_device)

    # we have to get back the document ids in order to reference devices in a project snapshot
    if devices:
        out = new_db['device_history'].insert_many(devices)
        ids = list(out.inserted_ids)
        project_snapshot = {
            'project_id': project_id,
            'name': '',                  # optional name (tag)
            'author': project['owner'],  # snapshot author
            'created': datetime.datetime.now(datetime.UTC),  # created timestamp
            'devices': ids,
            'description': "Migration from MCD 1.0",   # explanation if necessary
            'made_changes': {},
        }
        new_db['project_snapshots'].insert_one(project_snapshot)

    # diffs will be stored in a csv file for every project
    changes_by_timestamp = group_project_histories_by_timestamp(old_db, project_id)
    timestamps = sorted(changes_by_timestamp.keys())  # in desc order

    # create a history diff into a csv file
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    writer.writerow([f"Project diff: {project_name}", f"Exported: datetime.datetime.now()", "", "", "", ""])
    for time in timestamps:
        writer.writerow([])
        writer.writerow([f"*** Changes ({time}) ***"])
        writer.writerow(['FC', 'FG', 'User', 'Timestamp', 'Key', 'Value'])

        aggregated_changes = changes_by_timestamp[time]
        aggregated_changes.sort(key=lambda x: x['time'])
        for change in aggregated_changes:
            writer.writerow([
                change['fc'], change['fg'], change['user'], change['time'].replace(microsecond=0), change['key'], change['val']
            ])
        writer.writerows([[], []])  # 2 empty rows to separate diffs

    os.makedirs(output_dir, exist_ok=True)
    csv_name = f"{project_name.replace(' ', '_')}.csv"
    fpath = f'{output_dir}/{csv_name}'
    with open(fpath, 'w') as f:
        f.write(buffer.getvalue())

    print(f"Project '{project_name}' stored in MCD 2.0 format.    Diff file: {fpath}")


if __name__ == '__main__':
    client = create_mongo_client(timeout=500)

    _db_id = 'lineconfigdb'
    old_db = client[_db_id]
    new_db_id = _db_id

    testing = True
    if testing:
        new_db_id = "_TEST_MIGRATION_DB"
        try:
            print("")
            print(f"===== DROPPING OLD TESTING DB ({new_db_id}) =====")
            print("")
            client.drop_database(new_db_id)
        except Exception as e:
            print(e)

    new_db = client[new_db_id]

    # 1. get list of projects
    # 2. for every project in a list:
    #   - get historic data (just the timestamps of changes)
    # 3. query project data as if it was at the timestamp and enter in a new table
    projects = list(old_db['projects'].find())
    for project in projects:
        migrate_project(old_db, new_db, project, "/tmp/migration_test_folder")
