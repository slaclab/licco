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

def test_validate_field__empty_number_field():
    err = validator_mcd.validate_field("nom_ang_x", "1.0")
    assert err == "", "string field should not return an error"

    # empty values are not allowed by default
    err = validator_mcd.validate_field("nom_ang_x", "")
    assert err == "invalid 'nom_ang_x' value: value should be present"

    # no error if field is not required
    err = validator_mcd.validate_field("nom_ang_x", "", value_should_exist=False)
    assert err == ""

def test_validate_beamline_field():
    err = validator_mcd.validate_field("beamline", "TMO, RIX")
    assert err == "invalid 'beamline' value: expected an array of strings, but got str: 'TMO, RIX'"

    # beamline field stored in db should always be an array
    err = validator_mcd.validate_field("beamline", ["TMO", "RIX"])
    assert err == ""

def test_validate_invalid_beamline_field():
    err = validator_mcd.validate_field("beamline", ["XXX", "TMO", "ZZZ"])
    assert f"invalid 'beamline' value '['XXX', 'TMO', 'ZZZ']': invalid values ['XXX', 'ZZZ']: expected values are" in err

def test_validate_device__missing_always_required_fields():
    now = datetime.datetime.now()
    partial_device_data = {'fc': 'AA10', 'created': now, 'project_id': 'aa', 'device_type': DeviceType.MCD.value, 'nom_ang_x': 1.23}
    err = mcd_validate.validate_device(partial_device_data)
    assert err == "validation failed for a device MCD (fc: AA10):\nmissing required fields: ['device_id', 'state']"

def test_validate_device__optional_fields_in_draft_project():
    # coordinates could be missing in conceptual stage
    now = datetime.datetime.now()
    device_data = {'fc': 'AA10', 'project_id': 'aa', 'device_id': '123', 'created': now, 'state': 'Conceptual', 'device_type': DeviceType.MCD.value, 'discussion': [{'id': '123', 'author': "aaa", 'created': now, 'comment': "my comment"}]}
    err = mcd_validate.validate_device(device_data)
    assert err == "", "there should be no device coordinate errors in device with 'Conceptual' state"

def test_validate_device__missing_coordinate_fields():
    # checking if coordinates that should be present in a non-conceptual state are detected as required fields
    now = datetime.datetime.now()
    partial_device_data = {'fc': 'AA10', 'project_id': 'aa', 'device_id': '123', 'created': now, 'state': "Commissioned", 'device_type': DeviceType.MCD.value, 'nom_ang_x': 1.23, 'nom_ang_y': 1.23}
    err = mcd_validate.validate_device(partial_device_data)
    assert err == "validation failed for a device MCD (fc: AA10):\nmissing required fields: ['nom_ang_z', 'nom_loc_x', 'nom_loc_y', 'nom_loc_z']"

def test_validate_device__invalid():
    now = datetime.datetime.now()
    partial_device_data = {'fc': 'AA10', 'created': now, 'device_type': DeviceType.UNKNOWN.value, 'nom_ang_x': 1.23, 'non-existing-field': 'aaa'}
    err = mcd_validate.validate_device(partial_device_data)
    assert err == "", "validator should not report an error on an unknown device data"

def test_validate_device__discussion_thread():
    now = datetime.datetime.now()
    device_data = {'fc': 'BB10', 'project_id': 'aa', 'device_id': '123', 'created': now, 'state': 'Conceptual', 'device_type': DeviceType.MCD.value, 'discussion': [{'author': "aaa", 'comment': "my comment"}]}
    err = mcd_validate.validate_device(device_data)
    assert err == "validation failed for a device MCD (fc: BB10):\nfailed to validate 'discussion' field: failed to validate an element[0]: validation failed for a Discussion:\nmissing required fields: ['created', 'id']: Original data: {'author': 'aaa', 'comment': 'my comment'}"

def test_validate_device__invalid_subdevice():
    now = datetime.datetime.now()
    subdevice_1 = {'fc': 'SUB11', 'project_id': 'aa', 'created': now, 'device_id': '1234', 'device_type': DeviceType.APERTURE.value, 'nom_ang_x': 1.23, 'state': 'Conceptual'}
    subdevice_2 = {'fc': 'SUB10', 'project_id': 'aa', 'created': now, 'device_type': DeviceType.APERTURE.value, 'nom_ang_x': 1.23, 'state': 'Commissioned'}
    device_group = {'fc': 'AA10', 'project_id': 'aa', 'device_id': '123', 'created': now, 'device_type': DeviceType.GROUP.value, 'nom_ang_x': 1.23, 'state': 'Conceptual', 'subdevices': [subdevice_1, subdevice_2]}
    err = mcd_validate.validate_device(device_group)
    expected_msg = """
validation failed for a device Group (fc: AA10):
failed to validate 'subdevices' field: failed to validate an element[1]: validation failed for a device Aperture (fc: SUB10):
missing required fields: ['device_id', 'nom_ang_y', 'nom_ang_z', 'nom_loc_x', 'nom_loc_y', 'nom_loc_z']""".lstrip()
    assert expected_msg in err, "invalid error message"

def test_validate_device__nested_subdevices():
    # device group could have another group with devices. An error within the group should be detected and correctly reported
    now = datetime.datetime.now()
    subdevice_1 = {'fc': 'SUB10', 'project_id': 'aa', 'created': now, 'device_id': '1235', 'device_type': DeviceType.APERTURE.value, 'nom_ang_x': 1.23, 'state': 'Commissioned'}
    nested_device_group = {'fc': 'NESTED_AA10', 'project_id': 'aa', 'device_id': '1234', 'created': now, 'device_type': DeviceType.GROUP.value, 'state': 'Conceptual', 'subdevices': [subdevice_1]}
    device_group = {'fc': 'AA10', 'project_id': 'aa', 'device_id': '123', 'created': now, 'device_type': DeviceType.GROUP.value, 'nom_ang_x': 1.23, 'state': 'Conceptual', 'subdevices': [nested_device_group]}

    err = mcd_validate.validate_device(device_group)
    expected_err = """
validation failed for a device Group (fc: AA10):
failed to validate 'subdevices' field: failed to validate an element[0]: validation failed for a device Group (fc: NESTED_AA10):
failed to validate 'subdevices' field: failed to validate an element[0]: validation failed for a device Aperture (fc: SUB10):
missing required fields: ['nom_ang_y', 'nom_ang_z', 'nom_loc_x', 'nom_loc_y', 'nom_loc_z']""".lstrip()
    assert expected_err in err
