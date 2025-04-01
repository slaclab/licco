import datetime
import enum
import math
from dataclasses import dataclass
from typing import Dict, Callable, Optional, List

import pytz

from .mcd_model import FCState

# the purpose of this file is to provide you with a common validators for MCD database

class FieldType(enum.Enum):
    FLOAT = 1
    INT = 2
    TEXT = 3
    COMMENT_THREAD = 4
    ISO_DATE = 5


class DeviceType(enum.Enum):
    """Defines what kind of device we are dealing with, so we can use the right validator for checking data before
       inserting it into db.

       NOTE: this is an append only enumeration. If you deprecate a device type, this device type enum
       should NEVER BE reused, or you will end up fetching invalid device type from history and validation will
       report it as a broken device when in fact was perfectly fine at the time of insertion.
    """
    # Alternatively we could use text instead of ints (which makes db easier to inspect at the cost of additional space)
    # NOTE: the reason why we have Unset and Unknown device is to do the right thing during validation.
    #   0 - type usually means somebody forgot to set a type (which is a bug in MCD 2.0)
    #   1 - type means somebody set the type to Unknown on purpose and device data will not be validated
    Unset = 0
    Unknown = 1
    Mcd = 2
    Source = 3
    Blank = 4
    Aperture = 5
    FlatMirror = 6
    KbMirror = 7
    Crl = 8
    Crystal = 9
    Grating = 10


@dataclass
class FieldValidator:
    name: str
    label: str
    data_type: FieldType
    fromstr: Callable[[str], any]
    required: bool = True
    range: Optional[List[float]] = None
    allowed_values: Optional[List[str] | List[int]] = None

    def validate(self, value: any) -> str:
        try:
            if self.data_type == FieldType.COMMENT_THREAD:
                # TODO: how do we validate a comment thread?
                return ""

            val = self.fromstr(value)

            # validate range if possible
            if self.range and self.data_type in [FieldType.INT, FieldType.FLOAT]:
                if val < self.range[0] or val > self.range[1]:
                    return f"invalid range of '{self.name}' value: expected value range [{self.range[0]}, {self.range[1]}], but got {val}"

            if self.allowed_values:
                if val not in self.allowed_values:
                    return f"invalid '{self.name}' value '{val}': expected values are {self.allowed_values}"

            # no error
            return ""
        except Exception as e:
            return f"invalid '{self.name}' value: {str(e)}"


@dataclass
class Validator:
    name: str  # mcd, aperture, mirror, etc...
    fields: Dict[str, FieldValidator]

    def validate_component(self, component_fields: Dict[str, any]):
        """Validate all fields of a component (e.g., a flat mirror)."""
        # TODO: when a component is in a certain state, we could set that field as required.
        required_fields = set([v.name for v in self.fields.values() if v.required])

        # validating entire component
        # 1) Validate that all provided keys are valid
        # 2) Validate provided values of component
        # 3) Validate that we didn't miss any of the required fields
        errors = []
        for field_name, field_val in component_fields.items():
            # remove field from required fields, so we know whether all required fields were present
            required_fields.discard(field_name)

            err = self.validate_field(field_name, field_val)
            if err:
                errors.append(err)

        if len(required_fields) != 0:
            missing_required_fields = sorted(list(required_fields))
            err = f"invalid device data: missing required fields: {missing_required_fields}"
            errors.append(err)

        if errors:  # report all errors at once
            return "\n".join(errors)
        return ""

    def validate_field(self, field: str, val: any) -> str:
        validator = self.fields.get(field, None)
        if validator is None:
            return f"{self.name} component does not contain field '{field}'"

        err = validator.validate(val)
        return err


class NoOpValidator(Validator):
    """Validator that accepts every change"""

    def validate_component(self, component_fields: Dict[str, any]):
        return ""

    def validate_field(self, field: str, val: any) -> str:
        return ""

class UnsetDeviceValidator(Validator):
    """This validator will always reject validation. If it's used, this usually means we have a programming bug
    and somebody forgot to set a device type."""

    def validate_component(self, component_fields: Dict[str, any]):
        return f"invalid device type {DeviceType.Unset} (unset device): you have probably forgot to set a valid device type"

    def validate_field(self, field: str, val: any) -> str:
        return f"invalid device type {DeviceType.Unset} (unset device): you have probably forgot to set a valid device type"

# --------------------------  converters --------------------------------

def no_transform(val: str):
    return val


def str2float(val: str):
    return float(val)


def str2int(val: str):
    return int(val)


def str2date(val: str):
    if isinstance(val, datetime.datetime):
        return val
    d = datetime.datetime.strptime(val, "%Y-%m-%dT%H:%M:%S.%fZ")
    return d.replace(tzinfo=pytz.UTC)


# --------------------- validators of known types ----------------------

def build_validator_fields(field_validators: List[FieldValidator]) -> Dict[str, FieldValidator]:
    # if the validator fields are shared with another device, that's not a problem
    # since validators should be immutable and stateless.
    d = {}
    for v in field_validators:
        d[v.name] = v
    return d


validator_unset = UnsetDeviceValidator("Unset", fields=build_validator_fields([]))
validator_noop = NoOpValidator("Unknown", fields=build_validator_fields([]))

common_component_fields = build_validator_fields([
    # marks device type (mcd, mirror, aperture, ...)
    FieldValidator(name="device_type", label="Device Type", data_type=FieldType.INT, allowed_values=[t.value for t in DeviceType], fromstr=str2int, required=True),
    # timestamp when change was introduced
    FieldValidator(name="created", label="Created", data_type=FieldType.ISO_DATE, fromstr=str2date, required=True),
    # discussion thread that every device should support
    FieldValidator(name='discussion', label="Discussion", data_type=FieldType.COMMENT_THREAD, fromstr=no_transform, required=False),
])

validator_mcd = Validator("MCD", fields=common_component_fields | build_validator_fields([
    FieldValidator(name='fc', label="FC", data_type=FieldType.TEXT, fromstr=str),
    FieldValidator(name='fg', label="FG", data_type=FieldType.TEXT, fromstr=str, required=False),
    FieldValidator(name='tc_part_no', label="TC Part No.", data_type=FieldType.TEXT, fromstr=str, required=False),
    FieldValidator(name='state', label="State", data_type=FieldType.TEXT, fromstr=str, allowed_values=[v.value for v in FCState]),
    FieldValidator(name='stand', label="Stand/Nearest Stand", data_type=FieldType.TEXT, fromstr=str, required=False),
    FieldValidator(name='comment', label="Comment", data_type=FieldType.TEXT, fromstr=str, required=False),

    FieldValidator(name='nom_loc_x', label='Nom Loc X', data_type=FieldType.FLOAT, fromstr=str2float),
    FieldValidator(name='nom_loc_y', label='Nom Loc X', data_type=FieldType.FLOAT, fromstr=str2float),
    FieldValidator(name='nom_loc_z', label='Nom Loc Z', data_type=FieldType.FLOAT, fromstr=str2float, range=[0, 2000]),

    FieldValidator(name='nom_ang_x', label='Nom Ang X', data_type=FieldType.FLOAT, fromstr=str2float, range=[-math.pi, math.pi]),
    FieldValidator(name='nom_ang_y', label='Nom Ang Y', data_type=FieldType.FLOAT, fromstr=str2float, range=[-math.pi, math.pi]),
    FieldValidator(name='nom_ang_z', label='Nom Ang Z', data_type=FieldType.FLOAT, fromstr=str2float, range=[-math.pi, math.pi]),

    FieldValidator(name='ray_trace', label='Ray Trace', data_type=FieldType.INT, fromstr=str2int, range=[0, 1]),
]))

_mirror_geometry_fields = build_validator_fields([
    FieldValidator(name="geom_len", label="Geometry Length", data_type=FieldType.FLOAT, fromstr=str2float),
    FieldValidator(name="geom_width", label="Geometry Width", data_type=FieldType.FLOAT, fromstr=str2float),
    FieldValidator(name="thickness", label="Thickness", data_type=FieldType.FLOAT, fromstr=str2float),
    FieldValidator(name="geom_center_x", label="Geometry Center X", data_type=FieldType.FLOAT, fromstr=str2float),
    FieldValidator(name="geom_center_y", label="Geometry Center Y", data_type=FieldType.FLOAT, fromstr=str2float),
    FieldValidator(name="geom_center_z", label="Geometry Center Z", data_type=FieldType.FLOAT, fromstr=str2float),
])

_mirror_motion_range_fields = build_validator_fields([
    FieldValidator(name="motion_min_x", label="Motion Min X", data_type=FieldType.FLOAT, fromstr=str2float),
    FieldValidator(name="motion_max_x", label="Motion Max X", data_type=FieldType.FLOAT, fromstr=str2float),
    FieldValidator(name="motion_min_y", label="Motion Min Y", data_type=FieldType.FLOAT, fromstr=str2float),
    FieldValidator(name="motion_max_y", label="Motion Max Y", data_type=FieldType.FLOAT, fromstr=str2float),
    FieldValidator(name="motion_min_z", label="Motion Min Z", data_type=FieldType.FLOAT, fromstr=str2float),
    FieldValidator(name="motion_max_z", label="Motion Max Z", data_type=FieldType.FLOAT, fromstr=str2float),

    FieldValidator(name="motion_min_pitch", label="Motion Min Pitch", data_type=FieldType.FLOAT, fromstr=str2float),
    FieldValidator(name="motion_max_pitch", label="Motion Max Pitch", data_type=FieldType.FLOAT, fromstr=str2float),
    FieldValidator(name="motion_min_roll", label="Motion Min Roll", data_type=FieldType.FLOAT, fromstr=str2float),
    FieldValidator(name="motion_max_roll", label="Motion Max Roll", data_type=FieldType.FLOAT, fromstr=str2float),
    FieldValidator(name="motion_min_yaw", label="Motion Min Yaw", data_type=FieldType.FLOAT, fromstr=str2float),
    FieldValidator(name="motion_max_yaw", label="Motion Max Yaw", data_type=FieldType.FLOAT, fromstr=str2float),
])

validator_flat_mirror = Validator("Flat Mirror", fields=validator_mcd.fields | _mirror_geometry_fields | _mirror_motion_range_fields | build_validator_fields([
    FieldValidator(name="focus_min_p", label="Focus Min P", data_type=FieldType.FLOAT, fromstr=str2float),
    FieldValidator(name="focus_max_p", label="Focus Max P", data_type=FieldType.FLOAT, fromstr=str2float),

    FieldValidator(name="focus_min_q", label="Focus Min Q", data_type=FieldType.FLOAT, fromstr=str2float),
    FieldValidator(name="focus_max_q", label="Focus Max Q", data_type=FieldType.FLOAT, fromstr=str2float),

    FieldValidator(name="focus_theta", label="Focus Theta", data_type=FieldType.FLOAT, fromstr=str2float),
]))

# TODO: do the same for all other devices...
validator_aperture = Validator("Aperture", fields=validator_mcd.fields | _mirror_geometry_fields | _mirror_motion_range_fields | build_validator_fields([
]))

type_validator: Dict[int, Validator] = {
    DeviceType.Unset.value: validator_unset,
    DeviceType.Unknown.value: validator_noop,
    DeviceType.Mcd.value: validator_mcd,
    DeviceType.FlatMirror.value: validator_flat_mirror,
    DeviceType.Aperture.value: validator_aperture,
}

def validate_device(device: Dict[str, any]) -> str:
    device_type = device.get("device_type", None)
    if device_type is None:
        return "provided device does not have a required 'device_type' field"

    # or just display a giant switch here
    validator = type_validator.get(device_type, None)
    if validator is None:
        return f"can't validate provided device: device_type value '{device_type}' does not have an implemented validator"

    err = validator.validate_component(device)
    return err


def validate_project_devices(devices: List[Dict[str, any]]):
    # TODO: we have to support two modes
    # 1) User submits a project (reject if there is any error)
    # 2) User imports a project (and rejected devices are simply not imported)
    #    In this case we need to know if there are any failed devices
    #
    # TODO: edge case: if the user tries to merge a device from existing data, it's possible that
    # existing data is no longer valid under the new term.
    raise Exception("Not implemented")
