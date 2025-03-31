import enum
import math
from dataclasses import dataclass
from typing import Dict, Callable, Optional, List


# this file contains validators for common MCD types
class FieldType(enum.Enum):
    FLOAT = 1
    INT = 2
    TEXT = 3
    COMMENT_THREAD = 4


@dataclass
class FieldValidator:
    name: str
    label: str
    data_type: FieldType
    fromstr: Callable[[str], any]
    required: bool = True
    range: Optional[List[float]] = None

    def validate(self, value: any) -> str:
        try:
            if self.data_type == FieldType.COMMENT_THREAD:
                # TODO: we don't have to validate?
                return ""

            val = self.fromstr(value)

            # validate range if possible
            if self.range and self.data_type in [FieldType.INT, FieldType.FLOAT]:
                if val < self.range[0] or val > self.range[1]:
                    return f"invalid range of {self.name}: expected range [{self.range[0], self.range[1]}], but got {val}"

            # no error
            return ""
        except Exception as e:
            return f"invalid value of {self.name}: {str(e)}"


@dataclass
class Validator:
    name: str  # mcd, aperture, mirror, etc...
    fields: Dict[str, FieldValidator]

    def validate_component(self, component_fields: Dict[str, any]):
        found_fields = set()
        required_fields = set([v for v in self.fields.values() if v.required])
        print(required_fields)
        # TODO: finish validation

    def validate_field(self, field: str, val: any) -> str:
        validator = self.fields.get(field, None)
        if validator is None:
            return f"{self.name} component does not contain field '{field}'"

        err = validator.validate(val)
        return err


# --------------------------  converters --------------------------------

def no_transform(val: str):
    return val

def str2float(val: str):
    return float(val)

def str2int(val: str):
    return int(val)


# --------------------- validators of known types ----------------------

def build_validator_fields(field_validators: List[FieldValidator]) -> Dict[str, FieldValidator]:
    d = {}
    for v in field_validators:
        d[v.name] = v
    return d

validator_noop = Validator("Unknown", fields=build_validator_fields([]))

validator_mcd = Validator("MCD", fields=build_validator_fields([
    FieldValidator(name='fc', label="FC", data_type=FieldType.TEXT, fromstr=str),
    FieldValidator(name='fg', label="FG", data_type=FieldType.TEXT, fromstr=str, required=False),
    FieldValidator(name='tc_part_no', label="TC Part No.", data_type=FieldType.TEXT, fromstr=str, required=False),
    FieldValidator(name='stand', label="Stand/Nearest Stand", data_type=FieldType.TEXT, fromstr=str, required=False),
    FieldValidator(name='comment', label="Comment", data_type=FieldType.TEXT, fromstr=str),

    FieldValidator(name='nom_loc_x', label='Nom Loc X', data_type=FieldType.FLOAT, fromstr=str2float),
    FieldValidator(name='nom_loc_y', label='Nom Loc X', data_type=FieldType.FLOAT, fromstr=str2float),
    FieldValidator(name='nom_loc_z', label='Nom Loc Z', data_type=FieldType.FLOAT, fromstr=str2float, range=[0, 2000]),

    FieldValidator(name='nom_ang_x', label='Nom Ang X', data_type=FieldType.FLOAT, fromstr=str2float, range=[-math.pi, math.pi]),
    FieldValidator(name='nom_ang_y', label='Nom Ang Y', data_type=FieldType.FLOAT, fromstr=str2float, range=[-math.pi, math.pi]),
    FieldValidator(name='nom_ang_z', label='Nom Ang Z', data_type=FieldType.FLOAT, fromstr=str2float, range=[-math.pi, math.pi]),

    FieldValidator(name='ray_trace', label='Ray Trace', data_type=FieldType.INT, fromstr=str2int, range=[0, 1]),

    # discussion thread
    FieldValidator(name='discussion', label="Discussion", data_type=FieldType.COMMENT_THREAD, fromstr=no_transform),
]))

validator_flat_mirror = Validator("Flat Mirror", fields=validator_mcd.fields | build_validator_fields([
    FieldValidator(name="geom_len", label="Geometry Length", data_type=FieldType.FLOAT, fromstr=str2float),
    FieldValidator(name="geom_width", label="Geometry Width", data_type=FieldType.FLOAT, fromstr=str2float),
    FieldValidator(name="thickness", label="Thickness", data_type=FieldType.FLOAT, fromstr=str2float),

    FieldValidator(name="geom_center_x", label="Geometry Center X", data_type=FieldType.FLOAT, fromstr=str2float),
    FieldValidator(name="geom_center_y", label="Geometry Center Y", data_type=FieldType.FLOAT, fromstr=str2float),
    FieldValidator(name="geom_center_z", label="Geometry Center Z", data_type=FieldType.FLOAT, fromstr=str2float),
]))

validator_aperture = Validator("Aperture", fields=validator_mcd.fields | build_validator_fields([
    FieldValidator(name="geom_loc_y", label="Geometry Location Y", data_type=FieldType.FLOAT, fromstr=str2float),
]))


type_validator: Dict[int, Validator] = {
    0: validator_noop,
    1: validator_mcd,
    2: validator_flat_mirror,
    3: validator_aperture,
}


# TODO: remove me
if __name__ == '__main__':
    # out = validator_mirror.validate_field("nom_ang_x", "test")
    # print(out)

    out = validator_mcd.validate_field("geom_loc_x", "123")
    print(out)
