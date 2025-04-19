import csv
from dataclasses import dataclass
from io import StringIO
from logging import Logger
from typing import Tuple
import re

from dal import mcd_model
from dal.mcd_model import MongoDb
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

def import_project(licco_db: MongoDb, userid: str, prjid: str, csv_content: str, imp_log: Logger) -> Tuple[bool, str, ImportCounter]:
    import_counter = ImportCounter()

    with StringIO(csv_content) as fp:
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
        fcs = {}
        # Add each valid line of data to import dictionary
        for line in reader:
            # No FC present in the data line
            if not line["FC"]:
                import_counter.fail += 1
                continue
            if line["FC"] in fcs.keys():
                fcs[line["FC"]].append(line)
            else:
                # Sanitize/replace unicode quotes
                clean_line = re.sub(u'[\u201c\u201d\u2018\u2019]', '', line["FC"])
                if not clean_line:
                    import_counter.fail += 1
                    continue
                fcs[clean_line] = [line]
        if not fcs:
            err = "Import Error: No data detected in import file."
            return False, err, import_counter

    if import_counter.fail > 0:
        imp_log.debug(f"FAIL: {import_counter.fail} FCs malformed. (FC values likely missing)")


    fcuploads = []
    # Pull out columns we define in keymap
    for nm, fc_list in fcs.items():
        for fc in fc_list:
            fcupload = {}
            for k, v in mcd_model.KEYMAP.items():
                if k not in fc:
                    continue
                fcupload[v] = fc[k]
            fcuploads.append(fcupload)

    status, errormsg, update_status = mcd_model.update_ffts_in_project(licco_db, userid=userid, prjid=prjid, devices=fcuploads, def_logger=imp_log )

    # Include imports failed from bad FC/FGs
    prj_name = mcd_model.get_project(licco_db, prjid)["name"]
    if update_status:
        import_counter.add(update_status)

    # number of recognized headers minus the DB reference entries
    # _id, prjid, discussion, created 
    import_counter.headers = len(fcuploads[0].keys())-4

    status_str = create_status_update(prj_name, import_counter)
    imp_log.info(status_str)
    return True, "", import_counter


def export_project(licco_db: MongoDb, prjid: str) -> Tuple[bool, str, str]:
    with StringIO() as stream:
        # Write column names for data we provide for users to download
        download_fields = [key for key in mcd_model.KEYMAP.keys() if key != "FG"]
        writer = csv.DictWriter(stream, fieldnames=download_fields)
        writer.writeheader()
        prj_ffts = mcd_model.get_project_ffts(licco_db, prjid)
        ignore = ["_id", "discussion", "project_id", "created"]

        for device in prj_ffts:
            row_dict = {}
            dev_info = prj_ffts[device]
            for key in dev_info:
                # Check for keys we handle later, or don't want the end user downloading
                if (key in ignore) or (key not in mcd_model.KEYMAP_REVERSE):
                    continue
                row_dict[mcd_model.KEYMAP_REVERSE[key]] = dev_info[key]

            # Download file will have column order of KEYMAP var
            writer.writerow(row_dict)

        csv_string = stream.getvalue()
        return True, "", csv_string
