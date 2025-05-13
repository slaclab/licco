import datetime
import json
import types
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

class McdSnapshot(TypedDict):
    _id: ObjectId
    project_id: ObjectId
    author: str    # username of the user who created this snapshot (e.g., updated a device)
    created: datetime.datetime
    devices: List[ObjectId]
    changelog: Dict[str, any]
    name: str      # if the user creates a permanent snapshot to go back in time, this name field will be set
    description: str



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

    def describe(self):
        d = self.descriptions()
        return d[self]

    @classmethod
    def descriptions(cls):
        return {
            DeviceState.Conceptual: {"sortorder": 0, "label": "Conceptual", "description": "There are no firm plans to proceed with applying this configuration, it is still under heavy development. Configuration changes are frequent."},
            DeviceState.Planned: {"sortorder": 1, "label": "Planned", "description": "A planned configuration, installation planning is underway. Configuration changes are less frequent."},
            DeviceState.ReadyForInstallation: {"sortorder": 2, "label": "Ready for installation", "description": "Configuration is designated as ready for installation. Installation is imminent. Installation effort is planned and components may be fully assembled and bench-tested."},
            DeviceState.Installed: {"sortorder": 3, "label": "Installed", "description": "Component is physically installed but not fully operational"},
            DeviceState.Commissioned: {"sortorder": 4, "label": "Commissioned", "description": "Component is commissioned."},
            DeviceState.Operational: {"sortorder": 5, "label": "Operational", "description": "Component is operational, commissioning and TTO is complete"},
            DeviceState.NonOperational: {"sortorder": 6, "label": "Non-operational", "description": "Component remains installed but is slated for removal"},
            DeviceState.Decommissioned: {"sortorder": 7, "label": "De-commissioned", "description": "Component is de-commissioned."},
            DeviceState.Removed: {"sortorder": 8, "label": "Removed", "description": "Component is no longer a part of the configuration, record is maintained"},
        }


def default_wrapper(func, default):
    def wrapped_func(val):
        if val == '':
            return default
        else:
            return func(val)
    return wrapped_func


def str2bool(val):
    return json.loads(str(val).lower())


def str2float(val):
    return float(val)


def str2int(val):
    return int(val)


def _verify_beamline_locations(arr):
    for e in arr:
        if e not in MCD_BEAMLINES:
            raise Exception(f"{e} is not a valid beamline location")


def beamline_locations(arr):
    if not arr:
        return

    if isinstance(arr, str):
        arr = [field.strip() for field in arr.split(",")]
        _verify_beamline_locations(arr)
        return arr

    if not isinstance(arr, list):
        raise Exception(f"beamline locations should be an array, but got {arr}")

    _verify_beamline_locations(arr)
    return arr
