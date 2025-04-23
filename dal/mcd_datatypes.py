import json
import types
from enum import Enum
from typing import TypeAlias, Dict

from pymongo.synchronous.database import Database

# This file will contain shared mcd datatypes. The main purpose of having a separate file instead of
# adding them directly into mcd_model is to avoid circular imports when files imported by mcd_model
# are using the enums defined in mcd_model.

MASTER_PROJECT_NAME = 'LCLS Machine Configuration Database'
MongoDb: TypeAlias = Database[Dict[str, any]]
McdProject: TypeAlias = Dict[str, any]
McdDevice: TypeAlias = Dict[str, any]

MCD_LOCATIONS = ["EBD", "FEE", "H1.1", "H1.2", "H1.3", "H2", "XRT", "Alcove", "H4", "H4.5", "H5", "H6"]
MCD_BEAMLINES = ["TMO", "RIX", "TXI-SXR", "TXI-HXR", "XPP", "DXS", "MFX", "CXI", "MEC"]

KEYMAP = {
    # Column names defined in confluence
    "FC": "fc",
    "FG": "fg",
    "Fungible": "fg_desc",
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
KEYMAP_REVERSE = {value: key for key, value in KEYMAP.items()}


class FCState(Enum):
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
            FCState.Conceptual: {"sortorder": 0, "label": "Conceptual", "description": "There are no firm plans to proceed with applying this configuration, it is still under heavy development. Configuration changes are frequent."},
            FCState.Planned: {"sortorder": 1, "label": "Planned", "description": "A planned configuration, installation planning is underway. Configuration changes are less frequent."},
            FCState.ReadyForInstallation: {"sortorder": 2, "label": "Ready for installation", "description": "Configuration is designated as ready for installation. Installation is imminent. Installation effort is planned and components may be fully assembled and bench-tested."},
            FCState.Installed: {"sortorder": 3, "label": "Installed", "description": "Component is physically installed but not fully operational"},
            FCState.Commissioned: {"sortorder": 4, "label": "Commissioned", "description": "Component is commissioned."},
            FCState.Operational: {"sortorder": 5, "label": "Operational", "description": "Component is operational, commissioning and TTO is complete"},
            FCState.NonOperational: {"sortorder": 6, "label": "Non-operational", "description": "Component remains installed but is slated for removal"},
            FCState.Decommissioned: {"sortorder": 7, "label": "De-commissioned", "description": "Component is de-commissioned."},
            FCState.Removed: {"sortorder": 8, "label": "Removed", "description": "Component is no longer a part of the configuration, record is maintained"},
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

def beamline_locations(arr):
    if not arr:
        return

    if isinstance(arr, str):
        arr = [field.strip() for field in arr.split(",")]
        return arr

    if not isinstance(arr, list):
        raise Exception(f"beamline locations should be an array, but got {arr}")

    # @FUTURE: verify beamline locations
    #for e in arr:
    #    if not e in MCD_BEAMLINES:
    #        raise Exception(f"'{e}' is not a valid beamline location")
    return arr


# mcd 1.0 data types. This should be removed in favor of Validator routines
FC_ATTRS = types.MappingProxyType({
    "fg_desc": {
        "name": "fg_desc",
        "type": "text",
        "fromstr": str,
        "label": "Fungible",
        "desc": "Fungible_user",
        "required": False
    },
    "tc_part_no": {
        "name": "tc_part_no",
        "type": "text",
        "fromstr": str,
        "label": "TC Part No.",
        "desc": "TC_part_no",
        "required": False
    },
    "area": {
        "name": "area",
        "type": "enum",
        "fromstr": str,
        "enumvals": MCD_LOCATIONS,
        "label": "Area",
        "desc": "Device location",
        "required": False,
        "default": ""
    },
    "beamline": {
        "name": "beamline",
        "type": "enum",
        "fromstr": beamline_locations,
        "enumvals": MCD_BEAMLINES,
        "label": "Beamline",
        "desc": "Device beamline location",
        "required": False,
        "default": ""
    },
    "state": {
        "name": "state",
        "type": "enum",
        "fromstr": lambda x: FCState[x].value,
        "enumvals": [name for (name, _) in FCState.__members__.items()],
        "label": "State",
        "desc": "The current state of the functional component",
        "required": True,
        "default": "Conceptual"
    },
    "stand": {
        "name": "stand",
        "type": "text",
        "fromstr": str,
        "label": "Stand/Nearest Stand",
        "desc": "Stand/Nearest Stand",
        "required": False,
    },
    "comments": {
        "name": "comments",
        "type": "text",
        "fromstr": str,
        "label": "Comments",
        "desc": "Comments",
        "required": False
    },
    "nom_loc_z": {
        "name": "nom_loc_z",
        "type": "text",
        "fromstr": default_wrapper(str2float, ""),
        "rendermacro": "prec7float",
        "label": "Z",
        "category": {"label": "Nominal Location (meters in LCLS coordinates)", "span": 3},
        "desc": "Nominal Location Z",
        "required": False,
        "is_required_dimension": True
    },
    "nom_loc_x": {
        "name": "nom_loc_x",
        "type": "text",
        "fromstr": default_wrapper(str2float, ""),
        "rendermacro": "prec7float",
        "label": "X",
        "category": {"label": "Nominal Location (meters in LCLS coordinates)"},
        "desc": "Nominal Location X",
        "required": False,
        "is_required_dimension": True
    },
    "nom_loc_y": {
        "name": "nom_loc_y",
        "type": "text",
        "fromstr": default_wrapper(str2float, ""),
        "rendermacro": "prec7float",
        "label": "Y",
        "category": {"label": "Nominal Location (meters in LCLS coordinates)"},
        "desc": "Nominal Location Y",
        "required": False,
        "is_required_dimension": True
    },
    "nom_ang_z": {
        "name": "nom_ang_z",
        "type": "text",
        "fromstr": default_wrapper(str2float, ""),
        "rendermacro": "prec7float",
        "label": "Z",
        "category": {"label": "Nominal Angle (radians)", "span": 3},
        "desc": "Nominal Angle Z",
        "required": False,
        "is_required_dimension": True
    },
    "nom_ang_x": {
        "name": "nom_ang_x",
        "type": "text",
        "fromstr": default_wrapper(str2float, ""),
        "rendermacro": "prec7float",
        "label": "X",
        "category": {"label": "Nominal Angle (radians)"},
        "desc": "Nominal Angle X",
        "required": False,
        "is_required_dimension": True
    },
    "nom_ang_y": {
        "name": "nom_ang_y",
        "type": "text",
        "fromstr": default_wrapper(str2float, ""),
        "rendermacro": "prec7float",
        "label": "Y",
        "category": {"label": "Nominal Angle (radians)"},
        "desc": "Nominal Angle Y",
        "required": False,
        "is_required_dimension": True
    },
    "ray_trace": {
        "name": "ray_trace",
        "type": "text",
        "fromstr": default_wrapper(str2int, None),
        "label": "Must Ray Trace",
        "desc": "Must Ray Trace",
        "required": False
    },
    "discussion": {
        # NOTE: everytime the user changes a device value, a discussion comment is added to the database
        # as a separate document. On load, however, we have to parse all the comments into a structured
        # array of all comments for that specific device.
        "name": "discussion",
        "type": "text",
        "fromstr": str,
        "label": "Discussion",
        "desc": "User discussion about the device value change",
        "required": False,
    }
})
