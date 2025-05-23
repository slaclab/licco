import datetime
from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias, Dict, TypedDict, List

from bson import ObjectId
from pymongo.synchronous.database import Database

# This file will contain shared mcd datatypes. The main purpose of having a separate file instead of
# adding them directly into mcd_model is to avoid circular imports when files imported by mcd_model
# are using the enums defined in mcd_model.

MASTER_PROJECT_NAME = 'LCLS Machine Configuration Database'
MongoDb: TypeAlias = Database[Dict[str, any]]
class McdProject(TypedDict):
    _id: ObjectId
    name: str
    description: str
    owner: str
    status: str
    creation_time: datetime.datetime
    editors: List[str]
    approved_time: datetime.datetime
    approvers: List[str]
    approved_by: List[str]
    notes: List[str]
    submitted_time: datetime.datetime
    submitter: str

McdDevice: TypeAlias = Dict[str, any]

@dataclass
class Changelog:
    """Class for storing user modification changelog (names of devices that have changed)"""
    created: List[str]
    updated: List[str]
    deleted: List[str]

    def __init__(self):
        self.created = []
        self.updated = []
        self.deleted = []

    def add_created(self, fc: str):
        self._add_el(self.created, fc)

    def add_updated(self, fc: str):
        self._add_el(self.updated, fc)

    def add_deleted(self, fc: str):
        self._add_el(self.deleted, fc)

    def _add_el(self, arr, el):
        if el not in arr:
            arr.append(el)

    def join(self, change: 'Changelog'):
        for dev in change.created:
            self.add_updated(dev)

        for dev in change.updated:
            self.add_updated(dev)

        for dev in change.deleted:
            self.add_deleted(dev)

    def sort(self):
        # sort device names in A-Z order
        self.created.sort()
        self.updated.sort()
        self.deleted.sort()

    def to_dict(self):
        return {
            "created": self.created,
            "updated": self.updated,
            "deleted": self.deleted,
        }


class McdSnapshot(TypedDict):
    _id: ObjectId
    project_id: ObjectId
    author: str    # username of the user who created this snapshot (e.g., updated a device)
    created: datetime.datetime
    devices: List[ObjectId]
    changelog: Dict[str, any]
    name: str      # if the user creates a permanent snapshot to go back in time, this name field will be set
    description: str


@dataclass
class McdProjectHistory:
    project_id: str
    created: datetime.datetime
    changelog: Changelog
    name: str
    author: str


MCD_LOCATIONS = ["EBD", "FEE", "H1.1", "H1.2", "H1.3", "H2", "XRT", "Alcove", "H4", "H4.5", "H5", "H6"]
MCD_BEAMLINES = ["TMO", "RIX", "TXI-SXR", "TXI-HXR", "XPP", "DXS", "MFX", "CXI", "MEC"]

MCD_KEYMAP = {
    # Column names defined in confluence
    "FC": "fc",
    "Fungible": "fg",
    "TC_part_no": "tc_part_no",
    "Stand": "stand",
    "Area": "area",
    "Beamline": "beamline",
    "State": "state",
    "LCLS_Z_loc": "nom_loc_z",
    "LCLS_X_loc": "nom_loc_x",
    "LCLS_Y_loc": "nom_loc_y",
    "LCLS_Z_roll": "nom_ang_z",
    "LCLS_X_pitch": "nom_ang_x",
    "LCLS_Y_yaw": "nom_ang_y",
    "Must_Ray_Trace": "ray_trace",
    "Comments": "comments"
}
MCD_KEYMAP_REVERSE = {value: key for key, value in MCD_KEYMAP.items()}


class DeviceState(Enum):
    Conceptual = "Conceptual"
    Planned = "Planned"
    Commissioned = "Commissioned"
    ReadyForInstallation = "ReadyForInstallation"
    Installed = "Installed"
    Operational = "Operational"
    NonOperational = "NonOperational"
    Decommissioned = "Decommissioned"
    Removed = "Removed"
