import { isArrayEqual } from "@/app/utils/arr_utils";
import { JsonErrorMsg } from "@/app/utils/fetching";
import { sortString } from "@/app/utils/sort_utils";
import { useEffect, useState } from "react";
import { ProjectDeviceDetails, ProjectInfo, fetchMasterProjectInfo, fetchProjectDevices, fetchProjectInfo } from "../../project_model";
import { sortDeviceDataByColumn } from "../project_details";

export interface ProjectDiff {
    a: ProjectInfo;
    b: ProjectInfo;

    // depending on which projects is compared to which, the ffts 
    // are either new (the a project does not have some of b project fields)
    //     or missing (the a project has extra fields compared to b project)
    new: ProjectDeviceDetails[];       // a project has extra rows
    missing: ProjectDeviceDetails[];   // a project does not have rows from b
    identical: ProjectDeviceDetails[]; // rows that are the same for every property
    updated: { a: ProjectDeviceDetails, b: ProjectDeviceDetails }[]; // rows where at least 1 property has changed (not checking id)
}


export const createFftDiff = (aProject: ProjectInfo, aDevices: ProjectDeviceDetails[], bProject: ProjectInfo, bDevices: ProjectDeviceDetails[]): ProjectDiff => {
    let diff: ProjectDiff = {
        a: aProject,
        b: bProject,

        new: [],
        identical: [],
        missing: [],
        updated: [],
    }

    let fftGroup = new Map<string, { a?: ProjectDeviceDetails, b?: ProjectDeviceDetails }>();
    // assign fft elements to each group, so we can detect which one is new, deleted or changed
    for (let device of aDevices) {
        let name = `${device.fc}`;
        let group = fftGroup.get(name);
        if (!group) {
            group = {};
        }
        group.a = device;
        fftGroup.set(name, group);
    }
    for (let device of bDevices) {
        let name = `${device.fc}`;
        let group = fftGroup.get(name);
        if (!group) {
            group = {};
        }
        group.b = device;
        fftGroup.set(name, group);
    }

    for (let group of fftGroup.values()) {
        if (group.a === undefined) {
            // there is an element in b, but no in a - this means a is missing an element
            if (group.b !== undefined) { // this should always execute
                diff.missing.push(group.b);
            }
            continue;
        }

        if (group.b === undefined) {
            // there is an element in a but no in b - this means a has a new fft
            if (group.a !== undefined) {
                diff.new.push(group.a);
            }
            continue;
        }

        // both a & b are present
        // we have to determine if they were updated or unchanged by going through every key-value
        // pair and compare them
        let a = group.a!;
        let b = group.b!;
        if (deviceHasChangedValue(a, b)) {
            diff.updated.push({ a: a, b: b });
        } else {
            diff.identical.push(a);
        }
    }

    // sort in ascending order (based on fc, fg name fields)
    sortDeviceDataByColumn(diff.new, 'fc', false);
    sortDeviceDataByColumn(diff.missing, 'fc', false);
    sortDeviceDataByColumn(diff.identical, 'fc', false);
    diff.updated.sort((a, b) => {
        let first = a.a;
        let second = b.a;
        let diff = sortString(first.fc, second.fc, false);
        if (diff != 0) {
            return diff;
        }
        return sortString(first.fg, second.fg, false);
    })

    return diff;
}


export interface DeviceValueDiff {
    fieldName: string;
    oldVal: any;
    newVal: any;
}

export const DEVICE_METADATA_FIELDS: Set<keyof ProjectDeviceDetails> = new Set(["_id", "device_id", "project_id", "created", "discussion"]);

export const diffDeviceFields = (a: ProjectDeviceDetails, b: ProjectDeviceDetails, ignoredFields: Set<string> = DEVICE_METADATA_FIELDS): DeviceValueDiff[] => {
    let diffs: Record<string, DeviceValueDiff> = {};

    // We have to iterate over each device, since it's possible that a device field is missing from one
    // device and is present in the other
    for (const [key, valA] of Object.entries(a) as [keyof ProjectDeviceDetails, any][]) {
        if (ignoredFields.has(key)) {
            continue;
        }

        if (isDeviceFieldDifferent(key, a, b)) {
            const valB = b[key];
            diffs[key] = { fieldName: key, oldVal: valA, newVal: valB };
            continue;
        }
    }

    // since 'a' and 'b' could be a different device, it's possible that 'a' does not have 
    // all of the 'b' fields. For this reason we have to iterate over 'b' as well and report
    // those missing fields
    const objA = a as Record<any, any>;
    for (const [key, valB] of Object.entries(b) as [keyof ProjectDeviceDetails, any][]) {
        if (key in objA) {
            continue;
        }

        // found the missing key (that is in 'b' but not in 'a')
        diffs[key] = { fieldName: key, oldVal: '', newVal: valB }
    }

    const fieldDiff = [...Object.values(diffs)];
    return fieldDiff;
}


export function isDeviceFieldDifferent(key: keyof ProjectDeviceDetails, a: ProjectDeviceDetails, b: ProjectDeviceDetails): boolean {
    const valA = a[key];
    const valB = b[key];
    if (valA === valB) {
        return false;
    }

    // values are different, check how they are different
    if ((valA === undefined && valB === '') || (valA === '' && valB === undefined)) {
        // both fields are empty, and we shouldn't display them as a change of value 
        // since that would cause <empty>-<empty> to be displayed in the GUI which
        // would look confusing.
        //
        // In this case we do nothing and simply retry this check for another key
        return false;
    }

    if (Array.isArray(valA)) {
        // it's possible that one field is an empty array, while the other is undefined (array was not set)
        // In this case we determine that the fields are the same 
        if (valA.length === 0 && valB === undefined) {
            return false;
        }

        if (!isArrayEqual(valA as any[], valB as any[])) {
            return true;
        }
        return false;
    }

    // a is not an array, but b is
    // perform the same array check as above
    if (Array.isArray(valB)) {
        if (valA === undefined && valB.length === 0) {
            return false;
        }
    }

    // field is different
    return true;
}


export function deviceHasChangedValue(a: ProjectDeviceDetails, b: ProjectDeviceDetails): boolean {
    // NOTE: it's possible that device 'a' and device 'b' are of different types and have different fields
    // We don't check for both device fields, since devices will also have a different 'device_type' field
    // and that will detect a change in value.
    let key: keyof ProjectDeviceDetails;
    for (key in a) {
        if (DEVICE_METADATA_FIELDS.has(key)) { // ignore device metadata fields
            continue;
        }

        const isDifferent = isDeviceFieldDifferent(key, a, b);
        if (isDifferent) {
            return true;
        }
    }

    // there was no difference in values
    return false;
}



export const loadProjectDiff = async (projectIdA: string, projectIdB: string): Promise<ProjectDiff> => {
    let projectAInfo = fetchProjectInfo(projectIdA);
    let projectBInfo = fetchProjectInfo(projectIdB);

    // get ffts for both projects
    let projectAFfts = fetchProjectDevices(projectIdA);
    let projectBFfts = fetchProjectDevices(projectIdB);

    return Promise.all([projectAInfo, projectBInfo, projectAFfts, projectBFfts])
        .then((values) => {
            let aProject = values[0];
            let bProject = values[1];
            let aFfts: ProjectDeviceDetails[] = values[2];
            let bFfts: ProjectDeviceDetails[] = values[3];
            let diff = createFftDiff(aProject, aFfts, bProject, bFfts)
            return diff;
        });
}


export const useFetchProjectDiffDataHook = (projectIdA: string, projectIdB: string) => {
    const [isLoading, setIsLoading] = useState(true);
    const [loadError, setLoadError] = useState('');
    const [diff, setDiff] = useState<ProjectDiff>();

    useEffect(() => {
        setIsLoading(true);
        loadProjectDiff(projectIdA, projectIdB).then(diff => {
            setDiff(diff);
            setLoadError('');
        }).catch((e: JsonErrorMsg) => {
            let msg = "Failed to fetch all project diff data: " + e.error;
            setLoadError(msg);
        }).finally(() => {
            setIsLoading(false);
        })
    }, [projectIdA, projectIdB])

    return { isLoading: isLoading, loadError: loadError, diff: diff };
}


export async function fetchDiffWithMasterProject(projectId: string): Promise<ProjectDiff> {
    const masterProject = await fetchMasterProjectInfo();

    if (!masterProject) {
        // there is no master project and there was also no error:
        // this can happen when the user displays the approval page for the first time (before
        // any other project was approved; e.g., on a fresh database). In this case we will simply
        // compare the same project ids, which is handled correctly internally in the diff algorithm.
        return await loadProjectDiff(projectId, projectId);
    }

    const projectDiff = await loadProjectDiff(projectId, masterProject._id);
    return projectDiff;
}


