import logging
from typing import List, Dict
from bson import ObjectId

logger = logging.getLogger(__name__)



def get_project_attributes(db, projectid, fftid=None, skipClonedEntries=False, asoftimestamp=None, commentAfterTimestamp=None):
    # get correct project ID
    project = db["projects"].find_one({"_id": ObjectId(projectid)})
    if not project:
        logger.error("Cannot find project for id %s", projectid)
        return {}

    # find most recent project snapshot
    status, snapshot = get_recent_snapshot(db, projectid)
    if not status:
        logger.debug(f"No recent snapshot found for project {projectid}")
        return {}

    # get information for one specified FFT
    if fftid:
        device_information = get_one_device_from_snapshot(db, projectid=projectid, device_id=fftid)
    else:
        # get information for each device
        device_information = get_all_devices_from_snapshot(db, projectid=projectid, snapshot=snapshot)

    return device_information


def get_all_project_changes(propdb, projectid):
    snapshots = propdb["project_snapshots"].find({"project_id": ObjectId(projectid)})
    if not snapshots:
        logger.error("No projects with project ID %s", projectid)
    changelist = []
    for snap in snapshots:
        if "made_changes" in snap:
            changelist += snap["made_changes"]
    return changelist

def get_recent_snapshot(db, prjid: str):
    """
    Gets the newest snapshot for any one project
    """
    snapshot = db["project_snapshots"].find_one({"project_id": ObjectId(prjid)}, sort=[("created", -1)])
    if not snapshot:
        logger.debug(f"No database entry for project ID: {prjid}")
        return False, {}
    return True, snapshot

def get_all_devices_from_snapshot(db, projectid, snapshot):
    proj_devices = {}
    devices = db["device_history"].find({"_id": {"$in": snapshot["devices"]}})
    # TODO: handle subdevices, for now we dump all info, no filter
    for device in devices:
        proj_devices[device["fc"]] = device
    return proj_devices

def get_one_device_from_snapshot(db, projectid, device_id):
    device = db["device_history"].find_one({"_id": ObjectId(device_id)})
    return device
