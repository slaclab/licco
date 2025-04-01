import datetime

from dal import mcd_validate
from dal.mcd_validate import DeviceType, validator_mcd

# tests for mcd validation routines

def validate_field__valid_field():
    err = validator_mcd.validate_field("nom_ang_x", 1.2351)
    assert err == ""

def test_validate_field__outside_range():
    err = validator_mcd.validate_field("nom_loc_z", 3000)
    assert err == "invalid range of 'nom_loc_z' value: expected value range [0, 2000], but got 3000.0"

def test_validate_field__unknown_value():
    err = validator_mcd.validate_field("state", "XXXX")
    assert err == "invalid 'state' value: expected values are ['Conceptual', 'Planned', 'Commissioned', 'ReadyForInstallation', 'Installed', 'Operational', 'NonOperational', 'Decommissioned', 'Removed'], but got: 'XXXX'"

def test_validate_device():
    now = datetime.datetime.now()
    partial_device_data = {'fc': 'AA10', 'created': now, 'device_type': DeviceType.Mcd.value, 'nom_ang_x': 1.23}
    err = mcd_validate.validate_device(partial_device_data)
    assert err == "invalid device data: missing required fields: ['nom_ang_y', 'nom_ang_z', 'nom_loc_x', 'nom_loc_y', 'nom_loc_z', 'ray_trace', 'state']"

def test_validate_device__invalid():
    now = datetime.datetime.now()
    partial_device_data = {'fc': 'AA10', 'created': now, 'device_type': DeviceType.Unknown.value, 'nom_ang_x': 1.23}
    err = mcd_validate.validate_device(partial_device_data)
    assert err == "", "validator should not report an error on an unknown device data"
