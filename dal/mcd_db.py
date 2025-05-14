import logging
from typing import List, Dict, Tuple, Optional
from bson import ObjectId

from dal.mcd_datatypes import McdDevice, McdSnapshot

logger = logging.getLogger(__name__)



def get_latest_project_data(db, projectid, device_id=None, asoftimestamp=None, commentAfterTimestamp=None) -> Dict[str, McdDevice]:
    # get correct project ID
    project = db["projects"].find_one({"_id": ObjectId(projectid)})
    if not project:
        logger.error("Cannot find project for id %s", projectid)
        return {}

    # find most recent project snapshot
    snapshot = get_recent_snapshot(db, projectid, asoftimestamp=asoftimestamp)
    if not snapshot:
        logger.debug(f"No recent snapshot found for project {projectid}")
        return {}

    # get information for one specified FFT
    if device_id:
        device = get_device(db, device_id=device_id)
        return {device["fc"]: device}

    # get information of every snapshot device
    device_information = get_devices(db, snapshot["devices"])
    return device_information


def get_recent_snapshot(db, prjid: str, asoftimestamp=None) -> Optional[McdSnapshot]:
    """
    Gets the newest snapshot for any one project
    """
    query = {"project_id": ObjectId(prjid)}
    if asoftimestamp:
        query["created"] = {"$lte": asoftimestamp}

    snapshot = db["project_snapshots"].find_one(query, sort=[("created", -1)])
    if not snapshot:
        return None
    return snapshot


def get_devices(db, device_ids: List[str | ObjectId]) -> Dict[str, McdDevice]:
    device_id_mapping = {}
    ids = [ObjectId(id) for id in device_ids]
    devices = db["device_history"].find({"_id": {"$in": ids}})
    for device in devices:
        device_id_mapping[device["fc"]] = device
    return device_id_mapping

def get_device_fcs(db, device_ids: List[str|ObjectId]) -> List[str]:
    devices = db["device_history"].find({"_id": {"$in": [ObjectId(x) for x in device_ids]}}, projection={"_id": 0, "fc": 1})
    fcs = [dev['fc'] for dev in devices]
    return fcs

def get_device(db, device_id) -> Optional[McdDevice]:
    device = db["device_history"].find_one({"_id": ObjectId(device_id)})
    return device

def get_recent_device(db, prjid, device_id) -> Tuple[McdDevice, str]:
    """Get latest device values if they exist"""
    snapshot = get_recent_snapshot(db, prjid)
    if snapshot:
        return {}, f"snapshot for {prjid} does not exist"
    if ObjectId(device_id) in snapshot["devices"]:
        return get_device(db, device_id), ""

    # device was not found in the recent snapshot
    return {}, f"device {device_id} was not found in the recent snapshot"
