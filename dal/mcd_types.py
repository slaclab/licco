from typing import TypeAlias, Dict
from pymongo.synchronous.database import Database

# this file contains shared Python types and structures to avoid circular imports between files and modules

MongoDb: TypeAlias = Database[Dict[str, any]]
McdProject: Dict[str, any]

KEYMAP = {
    # Column names defined in confluence
    "FC": "fc",
    "Fungible": "fg",
    "TC_part_no": "tc_part_no",
    "State": "state",
    "Comments": "comments",
    "LCLS_Z_loc": "nom_loc_z",
    "LCLS_X_loc": "nom_loc_x",
    "LCLS_Y_loc": "nom_loc_y",
    "Z_dim": "nom_dim_z",
    "X_dim": "nom_dim_x",
    "Y_dim": "nom_dim_y",
    "LCLS_Z_roll": "nom_ang_z",
    "LCLS_X_pitch": "nom_ang_x",
    "LCLS_Y_yaw": "nom_ang_y",
    "Must_Ray_Trace": "ray_trace"
}
KEYMAP_REVERSE = {value: key for key, value in KEYMAP.items()}
