import csv
import uuid
from dataclasses import dataclass
from io import StringIO
from logging import Logger
from typing import Tuple, List
import re

from dal import mcd_model, mcd_datatypes, mcd_validate
from dal.mcd_datatypes import MongoDb
from dal.mcd_validate import DeviceType
from dal.utils import ImportCounter

@dataclass
class McdDataImport:
    success: bool = False
    error: str = ""
    import_log = ""
    import_counter = ImportCounter()


def create_status_update(prj_name, status: ImportCounter):
    """
    Helper function to make the import status message based on the dictionary results
    """
    line_break = "_"*40
    status_str = '\n'.join([
        f'{line_break}',
        f'Summary of Results:',
        f'Project Name: {prj_name}.',
        f'Valid headers recognized: {status.headers}.',
        f'{line_break}',
        f'Successful row imports: {status.success}.',
        f'Failed row imports: {status.fail}.',
        f'Ignored row imports: {status.ignored}.',
    ])
    return status_str


def import_project(licco_db: MongoDb, userid: str, prjid: str, csv_content: str, import_logger: Logger) -> Tuple[bool, str, ImportCounter]:
    import_counter = ImportCounter()

    devices = {}
    universalNewline = None  # avoids csv parsing errors if csv file contains carriage return \r at the end of the line
    with StringIO(csv_content, newline=universalNewline) as fp:
        fp.seek(0)
        # Find the header row
        loc = 0
        req_headers = False
        for line in fp:
            if 'FC' in line:
                if not "," in line:
                    continue
                req_headers = True
                break
            loc = fp.tell()

        # Ensure FC (required headers) is present
        if not req_headers:
            error_msg = "Import Rejected: FC header is required in a CSV format for import."
            return False, error_msg, import_counter

        # Set reader at beginning of header row
        fp.seek(loc)
        reader = csv.DictReader(fp)
        # Add each valid line of data to import dictionary
        line_num = 1
        try:
            for line in reader:
                # No FC present in the data line
                if not line["FC"]:
                    import_counter.fail += 1
                    continue

                # NOTE: if fc already exists, we will simply overwrite values with the later values
                # Sanitize/replace unicode quotes
                clean_fc = re.sub(u'[\u201c\u201d\u2018\u2019]', '', line["FC"])
                if not clean_fc:
                    import_counter.fail += 1
                    continue
                devices[clean_fc] = line
            line_num += 1
        except Exception as e:
            msg = f"Failed to parse csv device data (line: {line_num}): str{e}"
            return False, msg, import_counter

        if not devices:
            err = "Import Error: No data detected in import file."
            return False, err, import_counter

    if import_counter.fail > 0:
        import_logger.error(f"FAIL: {import_counter.fail} FCs malformed. (FC values likely missing)")

    device_changes = []
    # Pull out columns we define in keymap
    for _, device in devices.items():
        # We have to parse every known field into their correct type first (e.g., beamline csv string turned into an array of strings)
        # If one field is invalid, an entire device (csv row) will be marked as invalid and won't be inserted.
        fcupload = {}
        parse_errors = []
        for csv_col_name, db_col_name in mcd_datatypes.MCD_KEYMAP.items():
            if csv_col_name not in device:
                continue

            # we need to parse each field, since fields from csv are strings (beamline string should be parsed into an array)
            # in order to be inserted into a database; datetimes should be parsed into datetime objects as well)
            field_value = device[csv_col_name]
            parsed_field_value, err = mcd_validate.validator_mcd.parse_field(db_col_name, field_value)
            if err:
                parse_errors.append(err)
                continue

            # field was parsed successfully
            fcupload[db_col_name] = parsed_field_value

        if parse_errors:
            import_counter.fail += 1
            errors = "\n".join(parse_errors)
            import_logger.error(f"FAIL: device '{device['FC']}' field parse errors:\n{errors}\n")
            continue

        # device fields were parsed successfully, add them to the list
        device_changes.append(fcupload)
        import_counter.headers = len(fcupload)


    # in mcd 1.0 csv files we don't have device_type field, therefore we use a default mcd_device type
    # this may have to change, for MCD 2.0, but we still don't have a defined csv format.
    for fc in device_changes:
        device_type = fc.get('device_type', None)
        if device_type is None:
            fc['device_type'] = DeviceType.MCD.value

        device_id = fc.get('device_id', None)
        if device_id is None:
            # importing csv file does not have a device_id (that is internal), so we create one on our own
            # to pass the validation test. This id will only be used if the device is new.
            fc['device_id'] = str(uuid.uuid4())

    status, errormsg, update_status = mcd_model.update_ffts_in_project(licco_db, userid=userid, prjid=prjid, devices=device_changes,
                                                                       keep_going_on_error=True,
                                                                       def_logger=import_logger)
    if errormsg:
        import_logger.error(errormsg)

    # Include imports failed from bad FC/FGs
    prj_name = mcd_model.get_project(licco_db, prjid)["name"]
    if update_status:
        import_counter.add(update_status)

    status_str = create_status_update(prj_name, import_counter)
    import_logger.info(status_str)
    return True, "", import_counter


def export_project(licco_db: MongoDb, prjid: str) -> Tuple[bool, str, str]:
    with StringIO() as stream:
        # Write column names for data we provide for users to download
        download_fields = [key for key in mcd_datatypes.MCD_KEYMAP.keys() if key != "FG"]
        writer = csv.DictWriter(stream, fieldnames=download_fields)
        writer.writeheader()
        devices = mcd_model.get_project_devices(licco_db, prjid)
        ignore_fields = ["_id", "discussion", "project_id", "created"]

        for fc, device in devices.items():
            row_dict = {}
            for key in device:
                # Check for keys we handle later, or don't want the end user downloading
                if (key in ignore_fields) or (key not in mcd_datatypes.MCD_KEYMAP_REVERSE):
                    continue

                value = device[key]
                if isinstance(value, List):
                    # list values should be serialized as "A, B" without '[]' symbols
                    value = ", ".join(value)
                row_dict[mcd_datatypes.MCD_KEYMAP_REVERSE[key]] = value

            # Download file will have column order of KEYMAP var
            writer.writerow(row_dict)

        csv_string = stream.getvalue()
        return True, "", csv_string
