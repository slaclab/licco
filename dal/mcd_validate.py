import datetime
import enum
from enum import auto
import math
from dataclasses import dataclass
from typing import Dict, Callable, Optional, List

import pytz

from .mcd_datatypes import DeviceState, McdDevice, MCD_LOCATIONS, MCD_BEAMLINES


# the purpose of this file is to provide you with a common validators for MCD database

class FieldType(enum.Enum):
    FLOAT = auto()
    INT = auto()
    STRING = auto()
    BOOL = auto()
    ISO_DATE = auto()
    STRING_ARRAY = auto()
    CUSTOM_VALIDATOR = auto()


class Required(enum.Flag):
    """Determines if a field is optional or required in a certain device state"""
    OPTIONAL = 0                    # field is optional
    ALWAYS = 1 << 0                 # field is always required
    DEVICE_DEPLOYED = 1 << 1        # required when device is in a non-conceptual state
    OPTICAL_DATA_SELECTED = 1 << 2  # ray_tracing is selected and optical data should be there


class DeviceType(enum.Enum):
    """Defines what kind of device we are dealing with, so we can use the right validator for checking data before
       inserting it into db.

       NOTE: this is an append only enumeration. If you deprecate a device type, this device type enum
       should NEVER BE reused, or you will end up fetching invalid device type from history and validation will
       report it as a broken device when in fact was perfectly fine at the time of insertion.
    """
    # NOTE: the reason why we have Unset and Unknown device is to do the right thing during validation.
    #   0 - type usually means somebody forgot to set a type (which is a bug in MCD 2.0)
    #   1 - type means somebody set the type to Unknown on purpose and device data will not be validated
    #
    #   Alternatively we could use text instead of ints (which makes db easier to inspect at the cost of additional space)
    UNSET = 0
    UNKNOWN = 1
    MCD = 2
    SOURCE = 3
    BLANK = 4
    APERTURE = 5
    FLAT_MIRROR = 6
    KB_MIRROR = 7
    CRL = 8
    CRYSTAL = 9
    GRATING = 10
    GROUP = 11


@dataclass(frozen=True)
class FieldValidator:
    name: str
    label: str
    data_type: FieldType
    required: Required = Required.OPTIONAL
    fromstr: Optional[Callable[[str], any]] = None
    range: Optional[List[float]] = None
    allowed_values: Optional[List[str] | List[int]] = None
    validator: Optional[Callable[[any], str]] = None  # custom validator if necessary

    @staticmethod
    def default_fromstr(field_type: FieldType, value: any):
        if field_type == FieldType.FLOAT:
            if value == '':
                return None
            return float(value)
        if field_type == FieldType.INT:
            if value == '':
                return None
            return int(value)
        if field_type == FieldType.STRING:
            return str(value)
        if field_type == FieldType.STRING_ARRAY:
            if isinstance(value, str):
                return [e.strip() for e in value.split(",")]
            if isinstance(value, List):
                return [str(e).strip() for e in value]
            raise Exception(f"expected an array of strings, but got {type(value).__name__}")
        if field_type == FieldType.ISO_DATE:
            return str2date(value)
        if field_type == FieldType.BOOL:
            return bool(value)
        raise Exception(f"Unhandled field type {field_type.name} value from_str converter")

    def validate(self, value: any, value_should_exist: bool = True) -> str:
        try:
            if self.data_type == FieldType.CUSTOM_VALIDATOR and not self.validator:
                return f"field {self.name} demands a custom validator, but found none: this is a programming bug"

            if self.validator:
                err = self.validator(value)
                return err

            if self.fromstr:
                val = self.fromstr(value)
            else:
                val = self.default_fromstr(self.data_type, value)

            # some fields can be empty in certain state, unless the outside validator determined otherwise
            if val is None:
                if self.required.value & Required.ALWAYS.value > 0:
                    # empty field is not an error, unless the field is required
                    return f"invalid '{self.name}' value: value should be present"

                if value_should_exist:
                    return f"invalid '{self.name}' value: value should be present"

                # value doesn't have to exist, hence we don't further validate it
                return ""

            # validate range if possible
            if self.range and self.data_type in [FieldType.INT, FieldType.FLOAT]:
                if val < self.range[0] or val > self.range[1]:
                    return f"invalid range of '{self.name}' value: expected value range [{self.range[0]}, {self.range[1]}], but got {val}"

            if self.allowed_values:
                if self.data_type == FieldType.STRING_ARRAY:
                    invalid_values = []
                    for e in val:
                        if e not in self.allowed_values:
                            invalid_values.append(e)
                    if invalid_values:
                        return f"invalid '{self.name}' value '{val}': expected values are {self.allowed_values}"
                else:
                    if val not in self.allowed_values:
                        return f"invalid '{self.name}' value '{val}': expected values are {self.allowed_values}"

            if self.data_type == FieldType.STRING and self.required.value & Required.ALWAYS.value != 0:
                if not val:
                    return f"invalid '{self.name}' value: value can't be empty"

            # no error
            return ""
        except Exception as e:
            return f"invalid '{self.name}' value: {str(e)}"

@dataclass
class Validator:
    """Base device validator for validating device fields"""
    name: str  # mcd, aperture, mirror, etc...
    fields: Dict[str, FieldValidator]

    def _find_required_fields(self, device_fields: McdDevice):
        required_fields = set()
        device_state = device_fields.get("state", None)

        for name, validator in self.fields.items():
            if validator.required.value & Required.ALWAYS.value > 0:
                required_fields.add(name)
                continue

            # NOTE: if device state does not exist (is None), an error will be raised
            # anyway for missing "state" since it's an ALWAYS required field
            if device_state and validator.required.value & Required.DEVICE_DEPLOYED.value > 0:
                if device_state != DeviceState.Conceptual.value:
                    required_fields.add(name)
                    continue

            # TODO: other validation edge cases (e.g., for optics data)
            # @FUTURE: certain validators expect different fields depending on the type of a device (circular, rectangular)
            # Such validators should override the validation method and add additional fields...
        return required_fields

    def validate_device(self, device_fields: McdDevice):
        """Validate all fields of a component (e.g., a flat mirror)."""
        if not isinstance(device_fields, dict):
            return f"invalid device data: expected a dictionary data type, but got {type(device_fields)}"

        required_fields = self._find_required_fields(device_fields)

        # validating entire component
        # 1) Validate that all provided keys are valid
        # 2) Validate provided values of component
        # 3) Validate that we didn't miss any of the required fields
        errors = []
        for field_name, field_val in device_fields.items():
            # remove field from required fields, so we know whether all required fields were present
            value_should_exist = field_name in required_fields
            required_fields.discard(field_name)

            err = self.validate_field(field_name, field_val, value_should_exist)
            if err:
                errors.append(err)

        # validation done
        if len(required_fields) != 0:
            missing_required_fields = sorted(list(required_fields))
            err = f"missing required fields: {missing_required_fields}"
            errors.append(err)

        if errors:
            # NOTE: the given device_fields could contain anything really, so we can't expect
            # any of the fields to be present in the given dictionary.
            #
            # - If we are validating a device, they will usually have an 'fc' field which we report
            #   to produce a better / more specific error message of what went wrong.
            #
            # - We could also be validating an array of 'device' components in which case the 'fc'
            #   field will not be present. In such case we only report the validator name and
            #   relevant errors
            err = "\n".join(errors)

            fc = device_fields.get('fc', '')
            if fc:
                return f"validation failed for a device {self.name} (fc: {fc}):\n{err}"
            else:
                return f"validation failed for a {self.name}:\n{err}"

        # successful device validation
        return ""

    def validate_field(self, field: str, val: any, value_should_exist: bool = True) -> str:
        validator = self.fields.get(field, None)
        if validator is None:
            return f"unexpected field '{field}'"

        err = validator.validate(val, value_should_exist)
        return err


class NoOpValidator(Validator):
    """Validator that accepts every change"""

    def validate_device(self, component_fields: Dict[str, any]):
        return ""

    def validate_field(self, field: str, val: any, value_should_exist: bool = True) -> str:
        return ""

class UnsetDeviceValidator(Validator):
    """This validator will always reject validation. If it's used, this usually means we have a programming bug
    and somebody forgot to set a device type."""

    def validate_device(self, component_fields: Dict[str, any]):
        return f"invalid device type {DeviceType.UNSET} (unset device): you have probably forgot to set a valid device type"

    def validate_field(self, field: str, val: any, value_should_exist: bool = True) -> str:
        return f"invalid device type {DeviceType.UNSET} (unset device): you have probably forgot to set a valid device type"


# --------------------------  converters --------------------------------

def no_transform(val: str):
    return val

def str2date(val: str):
    if isinstance(val, datetime.datetime):
        return val
    d = datetime.datetime.strptime(val, "%Y-%m-%dT%H:%M:%S.%fZ")
    return d.replace(tzinfo=pytz.UTC)


# ------------------------------- modelling validators ----------------------------------------

def build_validator_fields(field_validators: List[FieldValidator]) -> Dict[str, FieldValidator]:
    # if the validator fields are shared with another device, that's not a problem
    # since validators should be immutable and stateless.
    d = {}
    for v in field_validators:
        d[v.name] = v
    return d


validator_unset = UnsetDeviceValidator("Unset", fields=build_validator_fields([]))
validator_noop = NoOpValidator("Unknown", fields=build_validator_fields([]))

def validate_array_of_elements(field: str, input: any, validator: Validator) -> str:
    if not isinstance(input, list):
        return f"invalid '{field}' field: expected a list, but got {type(input)})"

    errors = []
    for i, element in enumerate(input):
        if not isinstance(element, dict):
            errors.append(f"invalid element[{i}] type: expected a dictionary, but got ({element})")
            continue

        err = validator.validate_device(element)
        if err:
            errors.append(f"failed to validate an element[{i}]: {err}: Original data: {element}")
            continue

    if errors:
        e = "\n".join(errors)
        return f"failed to validate '{field}' field: {e}"
    return ""

def validate_discussion_thread(input: any) -> str:
    err = validate_array_of_elements('discussion', input, discussion_thread_validator)
    return err

discussion_thread_validator = Validator("Discussion", build_validator_fields([
    FieldValidator(name="id", label="id", data_type=FieldType.STRING, required=Required.ALWAYS),
    FieldValidator(name="author", label="Author", data_type=FieldType.STRING, required=Required.ALWAYS),
    FieldValidator(name="created", label="Created", data_type=FieldType.ISO_DATE, required=Required.ALWAYS),
    FieldValidator(name="comment", label="Comment", data_type=FieldType.STRING, required=Required.ALWAYS),
]))

common_component_fields = build_validator_fields([
    # every stored device has an '_id' field, which is how we identify the device document within mongodb
    # we mark it as optional field since new devices will not have this field, while the ones fetched from db
    # will have it.
    FieldValidator(name="_id", label="Mongo Document ID", data_type=FieldType.STRING, required=Required.OPTIONAL),
    # project id to which a device belongs to: not sure if we need to keep track of that for now?
    FieldValidator(name="project_id", label="Project ID", data_type=FieldType.STRING, required=Required.ALWAYS),
    # device id (uuid) that is here just so we can keep track of which device that was
    FieldValidator(name="device_id", label="Device ID", data_type=FieldType.STRING, required=Required.ALWAYS),
    # marks device type (mcd, mirror, aperture, ...)
    FieldValidator(name="device_type", label="Device Type", data_type=FieldType.INT, allowed_values=[t.value for t in DeviceType], required=Required.ALWAYS),
    # timestamp when change was introduced
    FieldValidator(name="created", label="Created", data_type=FieldType.ISO_DATE, required=Required.ALWAYS),
    # discussion thread that every device should support
    FieldValidator(name='discussion', label="Discussion", data_type=FieldType.CUSTOM_VALIDATOR, validator=validate_discussion_thread),
])

validator_mcd = Validator("MCD", fields=common_component_fields | build_validator_fields([
    FieldValidator(name='fc', label="FC", data_type=FieldType.STRING, required=Required.ALWAYS),
    FieldValidator(name='fg', label="FG", data_type=FieldType.STRING),
    FieldValidator(name='tc_part_no', label="TC Part No.", data_type=FieldType.STRING),
    FieldValidator(name='state', label="State", data_type=FieldType.STRING, fromstr=str, allowed_values=[v.value for v in DeviceState], required=Required.ALWAYS),
    FieldValidator(name='stand', label="Stand/Nearest Stand", data_type=FieldType.STRING),
    FieldValidator(name='comments', label="Comments", data_type=FieldType.STRING),
    FieldValidator(name='area', label="Area", data_type=FieldType.STRING),
    FieldValidator(name='beamline', label="Beamline", data_type=FieldType.STRING_ARRAY, allowed_values=MCD_BEAMLINES),

    FieldValidator(name='nom_loc_x', label='Nom Loc X', data_type=FieldType.FLOAT, required=Required.DEVICE_DEPLOYED),
    FieldValidator(name='nom_loc_y', label='Nom Loc Y', data_type=FieldType.FLOAT, required=Required.DEVICE_DEPLOYED),
    FieldValidator(name='nom_loc_z', label='Nom Loc Z', data_type=FieldType.FLOAT, range=[0, 2000], required=Required.DEVICE_DEPLOYED),

    FieldValidator(name='nom_ang_x', label='Nom Ang X', data_type=FieldType.FLOAT, range=[-math.pi, math.pi], required=Required.DEVICE_DEPLOYED),
    FieldValidator(name='nom_ang_y', label='Nom Ang Y', data_type=FieldType.FLOAT, range=[-math.pi, math.pi], required=Required.DEVICE_DEPLOYED),
    FieldValidator(name='nom_ang_z', label='Nom Ang Z', data_type=FieldType.FLOAT, range=[-math.pi, math.pi], required=Required.DEVICE_DEPLOYED),

    FieldValidator(name='ray_trace', label='Ray Trace', data_type=FieldType.INT, range=[0, 1]),
]))

_geometry_center_fields = build_validator_fields([
    FieldValidator(name="geom_center_x", label="Geometry Center X", data_type=FieldType.FLOAT),
    FieldValidator(name="geom_center_y", label="Geometry Center Y", data_type=FieldType.FLOAT),
    FieldValidator(name="geom_center_z", label="Geometry Center Z", data_type=FieldType.FLOAT),
])

_mirror_geometry_fields = _geometry_center_fields | build_validator_fields([
    FieldValidator(name="geom_len", label="Geometry Length", data_type=FieldType.FLOAT),
    FieldValidator(name="geom_width", label="Geometry Width", data_type=FieldType.FLOAT),
    FieldValidator(name="thickness", label="Thickness", data_type=FieldType.FLOAT),
])

_motion_range_fields = build_validator_fields([
    FieldValidator(name="motion_min_x", label="Motion Min X", data_type=FieldType.FLOAT),
    FieldValidator(name="motion_max_x", label="Motion Max X", data_type=FieldType.FLOAT),
    FieldValidator(name="motion_min_y", label="Motion Min Y", data_type=FieldType.FLOAT),
    FieldValidator(name="motion_max_y", label="Motion Max Y", data_type=FieldType.FLOAT),
    FieldValidator(name="motion_min_z", label="Motion Min Z", data_type=FieldType.FLOAT),
    FieldValidator(name="motion_max_z", label="Motion Max Z", data_type=FieldType.FLOAT),

    FieldValidator(name="motion_min_rx", label="Motion Min Rx", data_type=FieldType.FLOAT),
    FieldValidator(name="motion_max_rx", label="Motion Max Rx", data_type=FieldType.FLOAT),
    FieldValidator(name="motion_min_ry", label="Motion Min Ry", data_type=FieldType.FLOAT),
    FieldValidator(name="motion_max_ry", label="Motion Max Ry", data_type=FieldType.FLOAT),
    FieldValidator(name="motion_min_rz", label="Motion Min Rz", data_type=FieldType.FLOAT),
    FieldValidator(name="motion_max_rz", label="Motion Max Rz", data_type=FieldType.FLOAT),
])

_tolerance_fields = build_validator_fields([
    FieldValidator(name="tolerance_x", label="Tolerance X", data_type=FieldType.FLOAT),
    FieldValidator(name="tolerance_y", label="Tolerance Y", data_type=FieldType.FLOAT),
    FieldValidator(name="tolerance_z", label="Tolerance Z", data_type=FieldType.FLOAT),

    FieldValidator(name="tolerance_rx", label="Tolerance Rx", data_type=FieldType.FLOAT),
    FieldValidator(name="tolerance_ry", label="Tolerance Ry", data_type=FieldType.FLOAT),
    FieldValidator(name="tolerance_rz", label="Tolerance Rz", data_type=FieldType.FLOAT),
])

validator_source = Validator("Source", fields=validator_mcd.fields | build_validator_fields([
    FieldValidator(name="geom_len_z", label="Geometry Length Z", data_type=FieldType.FLOAT),
    FieldValidator(name="geom_width_x", label="Geometry Width X", data_type=FieldType.FLOAT),
    FieldValidator(name="geom_thickness_y", label="Geometry Thickness Y", data_type=FieldType.FLOAT),
    FieldValidator(name="geom_divergence_angle", label="Geometry Divergence Angle", data_type=FieldType.FLOAT),

    FieldValidator(name="tolerance_x", label="Tolerance X", data_type=FieldType.FLOAT),
    FieldValidator(name="tolerance_y", label="Tolerance Y", data_type=FieldType.FLOAT),
    FieldValidator(name="tolerance_z", label="Tolerance Z", data_type=FieldType.FLOAT),
]))

validator_blank = Validator("Blank", fields=validator_mcd.fields | _geometry_center_fields | _tolerance_fields | build_validator_fields([
    FieldValidator(name="geom_type", label="Geometry Type", data_type=FieldType.STRING, allowed_values=["CIRCULAR", "RECTANGULAR"]),

    # circular fields only
    FieldValidator(name="geom_od", label="Geometry OD", data_type=FieldType.FLOAT),

    # rectangular fields only
    FieldValidator(name="geom_length", label="Geometry Length", data_type=FieldType.FLOAT),
    FieldValidator(name="geom_width", label="Geometry Width", data_type=FieldType.FLOAT),

    # all fields
    FieldValidator(name="geom_thickness", label="Geometry Thickness", data_type=FieldType.FLOAT),
]))

validator_aperture = Validator("Aperture", fields=validator_mcd.fields | _geometry_center_fields | _tolerance_fields | build_validator_fields([
    FieldValidator(name="geom_type", label="Geometry Type", data_type=FieldType.STRING, allowed_values=["CIRCULAR", "RECTANGULAR"]),
    # NOTE: geometry type could be either circular or rectangular in which case different fields are required
    # Right now, it's not exactly clear how to model and verify such a configuration state, so we make all geometry
    # fields optional

    # circular fields only
    FieldValidator(name="geom_id", label="Geometry ID", data_type=FieldType.FLOAT),
    FieldValidator(name="geom_od", label="Geometry OD", data_type=FieldType.FLOAT),

    # rectangular fields only
    FieldValidator(name="geom_length", label="Geometry Length", data_type=FieldType.FLOAT),
    FieldValidator(name="geom_width", label="Geometry Width", data_type=FieldType.FLOAT),

    # all fields
    FieldValidator(name="geom_thickness", label="Geometry Thickness", data_type=FieldType.FLOAT),
]))

validator_flat_mirror = Validator("Flat Mirror", fields=validator_mcd.fields | _mirror_geometry_fields | _motion_range_fields | _tolerance_fields | build_validator_fields([
]))

validator_kb_mirror = Validator("KB Mirror", fields=validator_mcd.fields | _mirror_geometry_fields | _motion_range_fields | _tolerance_fields | build_validator_fields([
    FieldValidator(name="focus_min_p", label="Focus Min P", data_type=FieldType.FLOAT),
    FieldValidator(name="focus_max_p", label="Focus Max P", data_type=FieldType.FLOAT),

    FieldValidator(name="focus_min_q", label="Focus Min Q", data_type=FieldType.FLOAT),
    FieldValidator(name="focus_max_q", label="Focus Max Q", data_type=FieldType.FLOAT),

    FieldValidator(name="focus_theta", label="Focus Theta", data_type=FieldType.FLOAT),
]))

validator_crl = Validator("CRL", fields=validator_mcd.fields | _motion_range_fields | _tolerance_fields | _geometry_center_fields | build_validator_fields([
    FieldValidator("geom_enable", label="Geometry Enable", data_type=FieldType.BOOL),
    FieldValidator("geom_od", label="Geometry OD", data_type=FieldType.FLOAT),
    FieldValidator("geom_thickness", label="Geometry Thickness", data_type=FieldType.FLOAT),

    FieldValidator("focus_min_p", label="Focus Min P", data_type=FieldType.FLOAT),
    FieldValidator("focus_max_p", label="Focus Max P", data_type=FieldType.FLOAT),
    FieldValidator("focus_min_q", label="Focus Min Q", data_type=FieldType.FLOAT),
    FieldValidator("focus_max_q", label="Focus Max Q", data_type=FieldType.FLOAT),
]))

validator_crystal = Validator("Crystal", fields=validator_mcd.fields | _mirror_geometry_fields | _motion_range_fields | _tolerance_fields | build_validator_fields([
]))

validator_grating = Validator("Grating", fields=validator_mcd.fields | _mirror_geometry_fields | _motion_range_fields | _tolerance_fields | build_validator_fields([
]))

def validate_subdevices(input: any) -> str:
    err = validate_array_of_elements('subdevices', input, DEVICE_VALIDATOR)
    return err

validator_group = Validator("Group", fields=validator_mcd.fields | build_validator_fields([
    # group is a collection of subdevices (mirrors, apertures, crystals, etc...).
    # A group could also contain another group (nested groups of devices)
    FieldValidator(name='subdevices', label="Subdevices", data_type=FieldType.CUSTOM_VALIDATOR, validator=validate_subdevices)
]))


class DeviceValidator(Validator):
    """This is a container for all validator types"""
    devices = {
        DeviceType.UNSET.value: validator_unset,
        DeviceType.UNKNOWN.value: validator_noop,
        DeviceType.MCD.value: validator_mcd,
        DeviceType.SOURCE.value: validator_source,
        DeviceType.BLANK.value: validator_blank,
        DeviceType.APERTURE.value: validator_aperture,
        DeviceType.FLAT_MIRROR.value: validator_flat_mirror,
        DeviceType.KB_MIRROR.value: validator_kb_mirror,
        DeviceType.CRL.value: validator_crl,
        DeviceType.CRYSTAL.value: validator_crystal,
        DeviceType.GRATING.value: validator_grating,
        DeviceType.GROUP.value: validator_group,
    }

    def __init__(self):
        self.name = "Device Validator"
        self.fields = {}

    def validate_field(self, field: str, val: any, value_should_exist: bool = True) -> str:
        raise Exception("this method should never be called on device validator: this is a programming bug")

    def validate_device(self, device: McdDevice):
        device_type = device.get("device_type", None)
        if device_type is None:
            return "provided device does not have a required 'device_type' field"

        # or just display a giant switch here
        validator = DeviceValidator.devices.get(device_type, None)
        if validator is None:
            return f"can't validate provided device: invalid device type '{device_type}'"
        err = validator.validate_device(device)
        return err


# ------------------------------------- end of validator types --------------------------------


DEVICE_VALIDATOR = DeviceValidator()

@dataclass
class DeviceValidationError:
    device: McdDevice
    error: str

@dataclass
class ValidationResult:
    ok: List[McdDevice]
    errors: List[DeviceValidationError]

def validate_device(device: McdDevice) -> str:
    return DEVICE_VALIDATOR.validate_device(device)

def validate_project_devices(devices: List[McdDevice]) -> ValidationResult:
    """General method for validating project devices (on project import or when submitting the project for approval)"""
    results = ValidationResult([], [])
    for device in devices:
        validation_err = validate_device(device)
        if validation_err:
            results.errors.append(DeviceValidationError(device, validation_err))
            continue
        results.ok.append(device)
    return results
