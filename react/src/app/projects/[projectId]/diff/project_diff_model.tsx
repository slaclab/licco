import { sortString } from "@/app/utils/sort_utils";
import { ProjectDeviceDetails, ProjectInfo, deviceHasChangedValue, fetchProjectFfts, fetchProjectInfo } from "../../project_model";
import { sortDeviceDataByColumn } from "../project_details";

export interface ProjectFftDiff {
    a: ProjectInfo;
    b: ProjectInfo;

    // depending on which projects is compared to which, the ffts 
    // are either new (the a project does not have some of b project fields)
    //     or missing (the a project has extra fields compared to b project)
    new: ProjectDeviceDetails[];       // a project has extra rows
    missing: ProjectDeviceDetails[];   // a project does not have rows from b
    unchanged: ProjectDeviceDetails[]; // rows that are the same for every property
    changed: { a: ProjectDeviceDetails, b: ProjectDeviceDetails }[]; // rows where at least 1 property has changed (not checking id)
}


export const createFftDiff = (aProject: ProjectInfo, aFfts: ProjectDeviceDetails[], bProject: ProjectInfo, bFfts: ProjectDeviceDetails[]): ProjectFftDiff => {
    let fftDiff: ProjectFftDiff = {
        a: aProject,
        b: bProject,

        new: [],
        unchanged: [],
        missing: [],
        changed: [],
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
            fftDiff.changed.push({ a: a, b: b });
        } else {
            fftDiff.unchanged.push(a);
        }
    }

    // sort in ascending order (based on fc, fg name fields)
    sortDeviceDataByColumn(fftDiff.new, 'fc', false);
    sortDeviceDataByColumn(fftDiff.missing, 'fc', false);
    sortDeviceDataByColumn(fftDiff.unchanged, 'fc', false);
    fftDiff.changed.sort((a, b) => {
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

export const loadProjectDiff = async (projectIdA: string, projectIdB: string): Promise<ProjectFftDiff> => {
    let projectAInfo = fetchProjectInfo(projectIdA);
    let projectBInfo = fetchProjectInfo(projectIdB);

    // get ffts for both projects
    let projectAFfts = fetchProjectFfts(projectIdA);
    let projectBFfts = fetchProjectFfts(projectIdB);

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


