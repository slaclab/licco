import { Fetch } from "../utils/fetching";

export interface ProjectInfo {
    _id: string;
    name: string;
    description: string;
    owner: string;
    editors: string[];
    creation_time: Date;
    edit_time?: Date;
    status: string;
    approver?: string;
    submitted_time?: Date;
    submitter?: string;
}

// fetch data about all projects
export async function fetchAllProjectsInfo(): Promise<ProjectInfo[]> {
    const projects = await Fetch.get<ProjectInfo[]>("/ws/projects/");
    projects.forEach(p => projectTransformTimeIntoDates(p))
    return projects;
}

export async function fetchProjectInfo(projectId: string): Promise<ProjectInfo> {
    return Fetch.get<ProjectInfo>(`/ws/projects/${projectId}/`)
        .then(data => {
            projectTransformTimeIntoDates(data);
            return data;
        });
}

export function projectTransformTimeIntoDates(project: ProjectInfo) {
    project.creation_time = new Date(project.creation_time);
    if (project.edit_time) {
        project.edit_time = new Date(project.edit_time);
    }
    if (project.submitted_time) {
        project.submitted_time = new Date(project.submitted_time)
    }
}

export function isProjectSubmitted(project?: ProjectInfo): boolean {
    return project?.status === "submitted";
}

export function isProjectApproved(project?: ProjectInfo): boolean {
    return project?.status === "approved";
}

export function isProjectInDevelopment(project?: ProjectInfo): boolean {
    return project?.status === "development";
}

// device details used for frontend code; the reason why we don't use 
// the backend one is due to its nested fft fields; frontend code 
// and rendering data doesn't like nesting.
export interface ProjectDeviceDetails extends deviceDetailFields {
    id: string; // fft id
    fc: string; // fc id
    fg: string; // fg id
    // + the rest of device fields 
}

export interface ProjectDeviceDetailsBackend extends deviceDetailFields {
    fft: ProjectFFT;
}

export function deviceDetailsBackendToFrontend(details: ProjectDeviceDetailsBackend): ProjectDeviceDetails {
    // remove fft field from object, but copy every other field
    const { fft, ...copiedFields } = details;
    let data: ProjectDeviceDetails = {
        ...copiedFields,
        id: details.fft._id,
        fc: details.fft.fc,
        fg: details.fft.fg,
    }
    // turn dates into date objects
    // turn any number strings into undefined fields
    transformProjectDeviceDetails(data);
    return data;
}

interface deviceDetailFields {
    tc_part_no: string;
    comments: string;
    state: string;
    nom_ang_x?: number;
    nom_ang_y?: number;
    nom_ang_z?: number;
    nom_dim_x?: number;
    nom_dim_y?: number;
    nom_dim_z?: number;
    nom_loc_x?: number;
    nom_loc_y?: number;
    nom_loc_z?: number;
    ray_trace?: number;
}

export const ProjectDeviceDetailsNumericKeys: (keyof deviceDetailFields)[] = [
    'nom_ang_x', 'nom_ang_y', 'nom_ang_z',
    'nom_dim_x', 'nom_dim_y', 'nom_dim_z',
    'nom_loc_x', 'nom_loc_y', 'nom_loc_z',
    'ray_trace'
]

export async function fetchProjectFfts(projectId: string, showAllEntries: boolean = true, sinceTime?: Date): Promise<ProjectDeviceDetails[]> {
    const queryParams = new URLSearchParams();
    queryParams.set('showallentries', showAllEntries.toString());
    if (sinceTime != undefined) {
        queryParams.set("asoftimestamp", sinceTime.toISOString());
    }

    let url = `/ws/projects/${projectId}/ffts/`;
    if (queryParams.size > 0) {
        url += `?${queryParams.toString()}`;
    }


    return Fetch.get<Record<string, ProjectDeviceDetailsBackend>>(url)
        .then(data => {
            let devices = Object.values(data);
            return devices.map(d => deviceDetailsBackendToFrontend(d));
        });
}

function numberOrDefault(input: number | string | undefined, defaultVal: number | undefined): number | undefined {
    if (input == undefined) {
        return defaultVal;
    }

    if (typeof input == "string") {
        if (input == "") {
            return defaultVal;
        }
        return Number.parseFloat(input);
    }

    return input;
}


function transformProjectDeviceDetails(device: deviceDetailFields) {
    device.state = DeviceState.fromString(device.state).name;

    // empty numeric fields are sent through as strings
    // this transformation ensures we convert empty strings to undefined 
    let d = device as any;
    for (let k of ProjectDeviceDetailsNumericKeys) {
        d[k] = numberOrDefault(d[k], undefined);
    }
}

export interface ProjectFFT {
    _id: string;
    fc: string;
    fg: string;
}

export interface FFTDiff {
    diff: boolean;      // true if there is difference between same fft of 2 projects
    fftId: string;      // fft id (e.g, e321ads321d)
    fieldName: string;  // name of the field (e.g., nom_loc_x)
    my: string | number;
    other: string | number;
}

export function fetchProjectDiff(currentProjectId: string, otherProjectId: string, approved?: boolean): Promise<FFTDiff[]> {
    let params = new URLSearchParams();
    params.set("other_id", otherProjectId);
    if (approved != undefined) {
        // TODO: inconsistent backend behavior: here backend expects 1/0, 
        // on some other endpoints it expects true/false
        let approvedValue = approved ? "1" : "0";
        params.set("approved", approvedValue);
    }

    let url = `/ws/projects/${currentProjectId}/diff_with?` + params.toString();
    return Fetch.get<fftDiffBackend[]>(url)
        .then(data => {
            return data.map(d => {
                let { id, field } = parseFftFieldsFromDiff(d);
                let fftDiff: FFTDiff = {
                    diff: d.diff,
                    fftId: id,
                    fieldName: field,
                    my: d.my,
                    other: d.ot,
                }
                return fftDiff;
            })
        });
}

interface fftDiffBackend {
    diff: boolean;
    key: string;          // <fft_id>.<field_name>
    my: string | number;  // our project value
    ot: string | number;  // other's project value
}

export interface Tag {
    _id: string,
    prj: string,
    name: string,
    time: Date
}

function parseFftFieldsFromDiff(diff: fftDiffBackend): { id: string, field: string } {
    let [id, ...rest] = diff.key.split(".",);
    let nameOfField = rest.join(".");
    if (!nameOfField) { // this should never happen
        throw new Error(`Invalid diff key ${diff.key}: diff key should consist of "<fft_id>.<key>"`);
    }
    return { id: id, field: nameOfField }
}

// helper class for transforming status strings into enums and back
export class DeviceState {
    private constructor(public readonly name: string, public readonly sortOrder: number, public readonly backendEnumName: string) {
    }

    static readonly Conceptual = new DeviceState("Conceptual", 0, "Conceptual");
    static readonly Planned = new DeviceState("Planned", 1, "Planned");
    static readonly ReadyForInstallation = new DeviceState("Ready For Installation", 2, "ReadyForInstallation");
    static readonly Installed = new DeviceState("Installed", 3, "Installed");
    static readonly Commisioned = new DeviceState("Commissioned", 4, "Commissioned");
    static readonly Operational = new DeviceState("Operational", 5, "Operational");
    static readonly NonOperational = new DeviceState("Non-operational", 6, "NonOperational");
    static readonly Decommissioned = new DeviceState("De-commissioned", 7, "Decommissioned");
    static readonly Removed = new DeviceState("Removed", 8, "Removed");
    static readonly UnknownState = new DeviceState("Unknown", -1, "Unknown");

    static readonly allStates = [
        DeviceState.Conceptual,
        DeviceState.Planned,
        DeviceState.ReadyForInstallation,
        DeviceState.Installed,
        DeviceState.Commisioned,
        DeviceState.Operational,
        DeviceState.NonOperational,
        DeviceState.Decommissioned,
        DeviceState.Removed,
    ]

    public static fromString(state: string): DeviceState {
        for (let s of DeviceState.allStates) {
            if (s.name == state || s.backendEnumName == state) {
                return s;
            }
        }
        return DeviceState.UnknownState;
    }
}

export async function syncDeviceUserChanges(projectId: string, fftId: string, changes: Record<string, any>): Promise<Record<string, ProjectDeviceDetailsBackend>> {
    // undefined values are not serialized, hence deleting a field (field == undefined) should be replaced with an empty string
    let data = { body: JSON.stringify(changes, (k, v) => v === undefined ? '' : v) };
    return Fetch.post<Record<string, ProjectDeviceDetailsBackend>>(`/ws/projects/${projectId}/fcs/${fftId}`, data);
}


export interface ProjectHistoryChange {
    _id: string;
    prj: string;
    fc: string;
    fg: string;
    key: string; // field name (attribute name)
    val: string | number;
    user: string; // user who made this change
    time: Date;
}

export function fetchHistoryOfChanges(projectId: string): Promise<ProjectHistoryChange[]> {
    return Fetch.get<ProjectHistoryChange[]>(`/ws/projects/${projectId}/changes/`)
        .then((data) => {
            // create date objects from given date
            data.forEach(d => d.time = new Date(d.time));
            return data;
        });
}

export interface ProjectApprovalHistory {
    _id: string;
    switch_time: Date;
    requestor_uid: string;
    prj: string; // project name
    description: string;
    owner: string;
}

export function addFftsToProject(projectId: string, ffts: ProjectFFT[]): Promise<ProjectDeviceDetails[]> {
    return Fetch.post<Record<string, ProjectDeviceDetailsBackend>>(`/ws/projects/${projectId}/ffts/`, { body: JSON.stringify(ffts) })
        .then(resp => {
            let data = [...Object.values(resp)];
            let frontendData = data.map(d => deviceDetailsBackendToFrontend(d));
            return frontendData;
        })
}