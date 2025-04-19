"""
Various small utilities.
"""
import json
import math
import collections
from dataclasses import dataclass
from typing import List

from bson import ObjectId
from datetime import datetime, timezone

class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        elif isinstance(o, float) and not math.isfinite(o):
            return str(o)
        elif isinstance(o, datetime):
            # Use var d = new Date(str) in JS to deserialize
            # d.toJSON() in JS to convert to a string readable by datetime.strptime(str, '%Y-%m-%dT%H:%M:%S.%fZ')
            return o.replace(tzinfo=timezone.utc).isoformat()
        return json.JSONEncoder.default(self, o)


def replaceInfNan(d):
    """
    Javascript cannot really handle NaN's and Infinite in JSON.
    If you could potentially encounter these in the data being sent over, use this function to massage the data.
    """
    for k, v in d.items():
        if isinstance(v, collections.Mapping):
            d[k] = replaceInfNan(v)
        elif isinstance(v, float) and not math.isfinite(v):
            d[k] = str(v)
        else:
            d[k] = v
    return d


def empty_string_or_none(val: str) -> bool:
    is_empty = not val or (isinstance(val, str) and val.strip() == "")
    return is_empty


def escape_chars_for_mongo(attrname):
    '''
    Mongo uses the '$' and '.' characters for query syntax. So, if your attributes have these characters, they get converted to dictionaires etc.
    EPICS variables use the '.' character quite a bit.
    We replace these with their unicode equivalents
    '.' gets replaced with U+FF0E
    '$' gets replaced with U+FF04
    This will cause interesting query failures; but there does not seem to be a better choice.
    For example, use something like so to find the param - db.runs.findOne({}, {"params.AMO:HFP:MMS:72\uFF0ERBV": 1})
    '''
    return attrname.replace(".", u"\uFF0E").replace("$", u"\uFF04")


@dataclass
class ImportCounter:
    headers: int = 0
    fail: int = 0
    success: int = 0
    ignored: int = 0

    def add(self, counter: "ImportCounter"):
        self.headers += counter.headers
        self.fail += counter.fail
        self.success += counter.success
        self.ignored += counter.ignored


class Difference:
    def __init__(self, in_both: List[any], new: List[any], removed: List[any]):
        self.in_both = in_both
        self.new = new
        self.removed = removed

    def __str__(self):
        return str(self.__dict__)

def diff_arrays(old_elements: List[any], new_elements: List[any]) -> Difference:
    """
    Make a diff between two arrays to find out which elements are new, which were deleted
    and which elements are in both arrays.
    """
    old = set(old_elements)
    both = []
    new = []
    missing = []

    for e in new_elements:
        if e in old:
            both.append(e)
        else:
            new.append(e)

    for e in old_elements:
        if e not in new_elements:
            missing.append(e)

    return Difference(both, new, missing)
