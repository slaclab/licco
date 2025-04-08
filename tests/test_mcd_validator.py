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
    assert err == "invalid 'state' value 'XXXX': expected values are ['Conceptual', 'Planned', 'Commissioned', 'ReadyForInstallation', 'Installed', 'Operational', 'NonOperational', 'Decommissioned', 'Removed']"

def test_validate_device__missing_always_required_fields():
    now = datetime.datetime.now()
    partial_device_data = {'fc': 'AA10', 'created': now, 'device_type': DeviceType.MCD.value, 'nom_ang_x': 1.23}
    err = mcd_validate.validate_device(partial_device_data)
    assert err == "invalid device data: missing required fields: ['device_id', 'state']"

def test_validate_device__optional_fields_in_draft_project():
    # coordinates could be missing in conceptual stage
    now = datetime.datetime.now()
    device_data = {'fc': 'AA10', 'device_id': '123', 'created': now, 'state': 'Conceptual', 'device_type': DeviceType.MCD.value, 'discussion': [{'id': '123', 'author': "aaa", 'created': now, 'comment': "my comment"}]}
    err = mcd_validate.validate_device(device_data)
    assert err == "", "there should be no device coordinate errors in device with 'Conceptual' state"

def test_validate_device__missing_coordinate_fields():
    # checking if coordinates that should be present in a non-conceptual state are detected as required fields
    now = datetime.datetime.now()
    partial_device_data = {'fc': 'AA10', 'device_id': '123', 'created': now, 'state': "Commissioned", 'device_type': DeviceType.MCD.value, 'nom_ang_x': 1.23, 'nom_ang_y': 1.23}
    err = mcd_validate.validate_device(partial_device_data)
    assert err == "invalid device data: missing required fields: ['nom_ang_z', 'nom_loc_x', 'nom_loc_y', 'nom_loc_z']"

def test_validate_device__invalid():
    now = datetime.datetime.now()
    partial_device_data = {'fc': 'AA10', 'created': now, 'device_type': DeviceType.UNKNOWN.value, 'nom_ang_x': 1.23, 'non-existing-field': 'aaa'}
    err = mcd_validate.validate_device(partial_device_data)
    assert err == "", "validator should not report an error on an unknown device data"

def test_validate_device__discussion_thread():
    now = datetime.datetime.now()
    device_data = {'fc': 'AA10', 'device_id': '123', 'created': now, 'state': 'Conceptual', 'device_type': DeviceType.MCD.value, 'discussion': [{'author': "aaa", 'comment': "my comment"}]}
    err = mcd_validate.validate_device(device_data)
    assert err == "failed to validate 'discussion' field: failed to validate an element[0]: invalid device data: missing required fields: ['created', 'id']: Original data: {'author': 'aaa', 'comment': 'my comment'}"
