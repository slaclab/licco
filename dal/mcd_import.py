import csv
import logging
import os
import tempfile
from dataclasses import dataclass
import datetime
from io import StringIO
from logging import Logger
from typing import Tuple
import re
import json

from dal import mcd_model
from dal.mcd_types import MongoDb, KEYMAP, KEYMAP_REVERSE
from dal.utils import ImportCounter

@dataclass
class McdDataImport:
    success: bool = False
    error: str = ""
    import_log = ""
    import_counter = ImportCounter()

def import_project(licco_db: MongoDb, userid: str, prjid: str, filestring: str, logger: Logger) -> Tuple[bool, str, ImportCounter]:
    import_counter = ImportCounter()
    with StringIO(filestring) as fp:
        fp.seek(0)
        # Find the header row
        loc = 0
        req_headers = False
        for line in fp:
            if 'FC' in line and 'Fungible' in line:
                if not "," in line:
                    continue
                req_headers = True
                break
            loc = fp.tell()

        # Ensure FC and FG (required headers) are present
        if not req_headers:
            error_msg = "Import Rejected: FC and Fungible headers are required in a CSV format for import."
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

    prj_name = mcd_model.get_project(licco_db, prjid)['name']
    log_time = datetime.datetime.now().strftime("%m%d%Y.%H%M%S")
    log_name = f"{userid}_{prj_name.replace('/', '_')}_{log_time}"
    imp_log, imp_handler = create_logger(log_name)

    if import_counter.fail > 0:
        imp_log.debug(f"FAIL: {import_counter.fail} FFTS malformed. (FC values likely missing)")

    fc2id = {
        value["name"]: value["_id"]
        for value in json.loads(mcd_model.get_fcs(licco_db))["value"]
    }

    for nm, fc_list in fcs.items():
        current_list = []
        for fc in fc_list:
            if fc["FC"] not in fc2id:
                status, errormsg, newfc = mcd_model.create_new_functional_component(licco_db, name=fc["FC"], description="Generated from " + nm)
                # FFT creation successful, add to data to import list
                if status:
                    fc2id[fc["FC"]] = newfc["_id"]
                    current_list.append(fc)
                # Tried to create a new FFT and failed - don't include in dataset
                else:
                    # Count failed imports - excluding FC & FG
                    import_counter.fail += 1
                    error_str = f"Import for fft {fc['FC']}-{fc['Fungible']} failed: {errormsg}"
                    logger.debug(error_str)
                    imp_log.info(error_str)
            else:
                current_list.append(fc)
        fcs[nm] = current_list

    fg2id = {
        fgs["name"]: fgs["_id"]
        for fgs in json.loads(mcd_model.get_fgs(licco_db))["value"]
    }

    for nm, fc_list in fcs.items():
        for fc in fc_list:
            if fc["Fungible"] and fc["Fungible"] not in fg2id:
                status, errormsg, newfg = mcd_model.create_new_fungible_token(licco_db, name=fc["Fungible"], description="Generated from " + nm)
                fg2id[fc["Fungible"]] = newfg["_id"]

    ffts = {(fft["fc"]["name"], fft["fg"]["name"]): fft["_id"] for fft in mcd_model.get_ffts(licco_db)}
    for fc_list in fcs.values():
        for fc in fc_list:
            if (fc["FC"], fc["Fungible"]) not in ffts:
                status, errormsg, newfft = mcd_model.create_new_fft(licco_db, fc=fc["FC"], fg=fc["Fungible"], fcdesc=None, fgdesc=None)
                ffts[(newfft["fc"]["name"], newfft["fg"]["name"]
                if "fg" in newfft else None)] = newfft["_id"]

    fcuploads = []
    for nm, fc_list in fcs.items():
        for fc in fc_list:
            fcupload = {}
            fcupload["_id"] = ffts[(fc["FC"], fc["Fungible"])]
            for k, v in KEYMAP.items():
                if k not in fc:
                    continue
                fcupload[v] = fc[k]
            fcuploads.append(fcupload)

    status, errormsg, update_status = mcd_model.update_ffts_in_project(licco_db, userid, prjid, fcuploads, imp_log)

    # Include imports failed from bad FC/FGs
    prj_name = mcd_model.get_project(licco_db, prjid)["name"]
    if update_status:
        import_counter.add(update_status)

    # number of recognized headers minus the id used for DB reference
    import_counter.headers = len(fcuploads[0].keys())-1
    #status_str = create_status_update(prj_name, import_counter)
    #logger.debug(re.sub('[\n_]', '', status_str))
    imp_log.info(status_str)
    imp_log.removeHandler(imp_handler)
    imp_handler.close()
    return True, "", import_counter


def export_project(licco_db: MongoDb, prjid: str) -> Tuple[bool, str, str]:
    with StringIO() as stream:
        writer = csv.DictWriter(stream, fieldnames=KEYMAP.keys())
        writer.writeheader()
        prj_ffts = mcd_model.get_project_ffts(licco_db, prjid)

        for fft in prj_ffts:
            row_dict = {}
            fft_dict = prj_ffts[fft]
            for key in fft_dict:
                # Check for keys we handle later, or dont want the end user downloading
                if key in ["fft", "discussion"]:
                    continue
                row_dict[KEYMAP_REVERSE[key]] = fft_dict[key]
            for key in fft_dict["fft"]:
                if key == "_id":
                    continue
                row_dict[KEYMAP_REVERSE[key]] = fft_dict["fft"][key]

            # Download file will have column order of KEYMAP var
            writer.writerow(row_dict)

        csv_string = stream.getvalue()
        return True, "", csv_string