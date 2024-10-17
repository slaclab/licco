import { Fetch } from "../utils/fetching";

export interface ProjectInfo {
    _id: string;
    name: string;
    description: string;
    owner: string;
    editors: string[];
    creation_time: Date;
    edit_time?: Date;
    status: string; // TODO: state all the possible project statuses
    approver?: string;
    submitted_time?: Date;
    submitter?: string;
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

// fetch data about all projects
export async function fetchAllProjects(): Promise<ProjectInfo[]> {
    const projects = await Fetch.get<ProjectInfo[]>("/ws/projects/");
    for (let p of projects) {
        projectTransformTimeIntoDates(p);
    }
    return projects;
}

export function isProjectSubmitted(project?: ProjectInfo): boolean {
    if (!project) {
        return false;
    }
    return project.status === "submitted";
}
export function isProjectApproved(project?: ProjectInfo): boolean {
    return project?.status === "approved";
}


export interface ProjectDeviceDetails {
    fft: FFT;
    comments: string;
    nom_ang_x?: number;
    nom_ang_y?: number;
    nom_ang_z?: number;
    nom_dim_x?: number;
    nom_dim_y?: number;
    nom_dim_z?: number;
    nom_loc_x?: number;
    nom_loc_y?: number;
    nom_loc_z?: number;
    state: string; // Conceptual | XX | YY | TODO:
    tc_part_no: string;
    ray_trace?: number;
}

export const ProjectDeviceDetailsNumericKeys: (keyof ProjectDeviceDetails)[] = [
    'nom_ang_x', 'nom_ang_y', 'nom_ang_z',
    'nom_dim_x', 'nom_dim_y', 'nom_dim_z',
    'nom_loc_x', 'nom_loc_y', 'nom_loc_z',
    'ray_trace'
]

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


export function transformProjectDeviceDetails(device: ProjectDeviceDetails) {
    device.state = DeviceState.fromString(device.state).name;

    // empty numeric fields are sent through as strings
    // this transformation ensures we convert empty strings to undefined 
    let d = device as any;
    for (let k of ProjectDeviceDetailsNumericKeys) {
        d[k] = numberOrDefault(d[k], undefined);
    }
}


export interface FFT {
    _id: string;
    fc: string;
    fg: string;
}

interface FFTDiffBackend {
    diff: boolean;
    key: string;          // <fft_id>.<field_name>
    my: string | number;  // our project value
    ot: string | number;  // other's project value
}

export interface FFTDiff {
    diff: boolean;      // true if there is difference between same fft of 2 projects
    fftId: string;      // fft id (e.g, e321ads321d)
    fieldName: string;  // name of the field (e.g., nom_loc_x)
    my: string | number;
    other: string | number;
}

function parseFftFieldsFromDiff(diff: FFTDiffBackend): { id: string, field: string } {
    let [id, ...rest] = diff.key.split(".",);
    let nameOfField = rest.join(".");
    if (!nameOfField) { // this should never happen
        throw new Error(`Invalid diff key ${diff.key}: diff key should consist of "<fft_id>.<key>"`);
    }
    return { id: id, field: nameOfField }
}

export function fetchProjectDiff(currentProjectId: string, otherProjectId: string, approved?: boolean): Promise<FFTDiff[]> {
    let params = new URLSearchParams();
    params.set("other_id", otherProjectId);
    if (approved != undefined) {
        let approvedValue = approved ? "1" : "0";
        params.set("approved", approvedValue);
    }

    let url = `/ws/projects/${currentProjectId}/diff_with?` + params.toString();
    return Fetch.get<FFTDiffBackend[]>(url)
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

export async function syncDeviceUserChanges(projectId: string, fftId: string, changes: Record<string, any>): Promise<Record<string, ProjectDeviceDetails>> {
    return Fetch.post<Record<string, ProjectDeviceDetails>>(`/ws/projects/${projectId}/fcs/${fftId}`, { body: JSON.stringify(changes) });
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