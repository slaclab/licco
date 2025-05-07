import logging
from typing import List, Dict, Tuple
from bson import ObjectId

logger = logging.getLogger(__name__)



def get_latest_project_data(db, projectid, device_id=None, skipClonedEntries=False, asoftimestamp=None, commentAfterTimestamp=None):
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
    if device_id:
        device = get_device(db, device_id=device_id)
        return {device["fc"]: device}

    # get information of every snapshot device
    device_information = get_devices(db, snapshot["devices"])
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


def get_recent_snapshot(db, prjid: str) -> Tuple[bool, Dict[str, any]]:
    """
    Gets the newest snapshot for any one project
    """
    snapshot = db["project_snapshots"].find_one({"project_id": ObjectId(prjid)}, sort=[("created", -1)])
    if not snapshot:
        logger.debug(f"No database entry for project ID: {prjid}")
        return False, {}
    return True, snapshot


def get_devices(db, device_ids: List[str]):
    device_id_mapping = {}
    ids = [ObjectId(id) for id in device_ids]
    devices = db["device_history"].find({"_id": {"$in": ids}})
    for device in devices:
        device_id_mapping[device["fc"]] = device
    return device_id_mapping

def get_device(db, device_id):
    device = db["device_history"].find_one({"_id": ObjectId(device_id)})
    return device
