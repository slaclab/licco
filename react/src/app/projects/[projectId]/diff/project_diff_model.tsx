import { isArrayEqual } from "@/app/utils/arr_utils";
import { JsonErrorMsg } from "@/app/utils/fetching";
import { sortString } from "@/app/utils/sort_utils";
import { useEffect, useState } from "react";
import { ProjectDeviceDetails, ProjectInfo, deviceHasChangedValue, fetchMasterProjectInfo, fetchProjectDevices, fetchProjectInfo } from "../../project_model";
import { sortDeviceDataByColumn } from "../project_details";

export interface ProjectFftDiff {
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


export const createFftDiff = (aProject: ProjectInfo, aFfts: ProjectDeviceDetails[], bProject: ProjectInfo, bFfts: ProjectDeviceDetails[]): ProjectFftDiff => {
    let fftDiff: ProjectFftDiff = {
        a: aProject,
        b: bProject,

        new: [],
        identical: [],
        missing: [],
        updated: [],
    }

    let fftGroup = new Map<string, { a?: ProjectDeviceDetails, b?: ProjectDeviceDetails }>();
    // assign fft elements to each group, so we can detect which one is new, deleted or changed
    for (let fft of aFfts) {
        let name = `${fft.fc}__${fft.fg}`;
        let group = fftGroup.get(name);
        if (!group) {
            group = {};
        }
        group.a = fft;
        fftGroup.set(name, group);
    }
    for (let fft of bFfts) {
        let name = `${fft.fc}__${fft.fg}`;
        let group = fftGroup.get(name);
        if (!group) {
            group = {};
        }
        group.b = fft;
        fftGroup.set(name, group);
    }

    for (let group of fftGroup.values()) {
        if (group.a == undefined) {
            // there is an element in b, but no in a - this means a is missing an element
            if (group.b != undefined) { // this should always execute
                fftDiff.missing.push(group.b);
            }
            continue;
        }

        if (group.b == undefined) {
            // there is an element in a but no in b - this means a has a new fft
            if (group.a != undefined) {
                fftDiff.new.push(group.a);
            }
            continue;
        }

        // both a & b are present
        // we have to determine if they were updated or unchanged by going through every key-value
        // pair and compare them
        let a = group.a!;
        let b = group.b!;
        if (deviceHasChangedValue(a, b)) {
            fftDiff.updated.push({ a: a, b: b });
        } else {
            fftDiff.identical.push(a);
        }
    }

    // sort in ascending order (based on fc, fg name fields)
    sortDeviceDataByColumn(fftDiff.new, 'fc', false);
    sortDeviceDataByColumn(fftDiff.missing, 'fc', false);
    sortDeviceDataByColumn(fftDiff.identical, 'fc', false);
    fftDiff.updated.sort((a, b) => {
        let first = a.a;
        let second = b.a;
        let diff = sortString(first.fc, second.fc, false);
        if (diff != 0) {
            return diff;
        }
        return sortString(first.fg, second.fg, false);
    })

    return fftDiff;
}


export interface DeviceValueDiff {
    fieldName: string;
    oldVal: any;
    newVal: any;
}

const IGNORED_DEVICE_METADATA_FIELDS: Set<keyof ProjectDeviceDetails> = new Set(["_id", "device_id", "project_id", "created", "discussion"])

export const diffDeviceFields = (a: ProjectDeviceDetails, b: ProjectDeviceDetails, ignoredFields: Set<string> = IGNORED_DEVICE_METADATA_FIELDS): DeviceValueDiff[] => {
    let diffs: Record<string, DeviceValueDiff> = {};

    // We have to iterate over each device, since it's possible that a device field is missing from one
    // device and is present in the other
    for (const [key, valA] of Object.entries(a) as [keyof ProjectDeviceDetails, any][]) {
        if (ignoredFields.has(key)) {
            continue;
        }

        const valB = b[key];
        if (valA === valB) {
            continue;
        }

        if (valA === '' && valB === undefined || valA === undefined && valB === '') {
            // empty fields should not be considered a diff
            continue;
        }

        if (Array.isArray(valA)) {
            if (isArrayEqual(valA as any[], valB as any[])) {
                continue;
            }
        }

        diffs[key] = { fieldName: key, oldVal: valA, newVal: valB };
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


export const loadProjectDiff = async (projectIdA: string, projectIdB: string): Promise<ProjectFftDiff> => {
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
    const [diff, setDiff] = useState<ProjectFftDiff>();

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


export async function fetchDiffWithMasterProject(projectId: string): Promise<ProjectFftDiff> {
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