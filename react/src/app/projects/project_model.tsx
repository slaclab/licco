import { useEffect, useState } from "react";
import { toUnixSeconds } from "../utils/date_utils";
import { Fetch, JsonErrorMsg } from "../utils/fetching";

export interface ProjectInfo {
    _id: string;
    name: string;
    description: string;
    owner: string;
    editors: string[];
    creation_time: Date;
    edit_time?: Date;
    status: "hidden" | "development" | "submitted" | "approved";
    approvers?: string[];
    approved_by?: string[];
    approved_time?: Date;
    submitted_time?: Date;
    submitter?: string;
    notes: string[];
}

// Determines if the user is an approver of the chosen project. The user is considered an approver if:
//
// - the project was submitted for approval and the logged in user was selected as an approver 
// - the currently logged in user is a super approver (or admin)
export function isUserAProjectApprover(project: ProjectInfo, username: string): boolean {
    if (isProjectSubmitted(project)) {
        if (project.approvers?.includes(username)) {
            return true;
        }
    }
    return false;
}

export function isUserAProjectEditor(project: ProjectInfo, username: string): boolean {
    return project.owner === username || project.editors.includes(username);
}

export const MASTER_PROJECT_NAME = "LCLS Machine Configuration Database";

// fetch data about all projects
export async function fetchAllProjectsInfo(): Promise<ProjectInfo[]> {
    const projects = await Fetch.get<ProjectInfo[]>("/ws/projects/");
    let pArr = [];
    for (let p of projects) {
        if (p.name !== MASTER_PROJECT_NAME) {
            pArr.push(p);
            continue;
        }
        // it's master project, it should only be visibile if it's approved
        if (isProjectApproved(p)) {
            pArr.push(p)
        }
    }
    pArr.forEach(p => transformProjectForFrontendUse(p))
    return pArr;
}

export async function fetchMasterProjectInfo(): Promise<ProjectInfo | undefined> {
    const project = await Fetch.get<ProjectInfo>("/ws/approved/");
    if (!project) {
        // there is no master project. This can only happen on a fresh database
        return undefined;
    }
    transformProjectForFrontendUse(project);
    return project;
}

export async function fetchProjectInfo(projectId: string): Promise<ProjectInfo> {
    return Fetch.get<ProjectInfo>(`/ws/projects/${projectId}/`)
        .then(data => {
            transformProjectForFrontendUse(data);
            return data;
        });
}

export async function fetchKeymap(): Promise<Record<string, string>> {
    return Fetch.get<Record<string, string>>(`/ws/backendkeymap/`)
        .then((response) => {
            return response;
        });
}


interface UsersByRole {
    all?: string[];
    editors?: string[];
    approvers?: string[];
    super_approvers?: string[];
    admins?: string[];
}

export enum UserRoles {
    All = 1 << 0,
    Editors = 1 << 1,
    Approvers = 1 << 2,
    SuperApprovers = 1 << 3,
    Admins = 1 << 4,
}

export async function fetchUsers(flags: UserRoles = UserRoles.All): Promise<UsersByRole> {
    let roles: string[] = [];
    if (flags & UserRoles.All) {
        roles.push("all");
    }
    if (flags & UserRoles.Editors) {
        roles.push("editors");
    }
    if (flags & UserRoles.Admins) {
        roles.push("admins");
    }
    if (flags & UserRoles.Approvers) {
        roles.push("approvers");
    }
    if (flags & UserRoles.SuperApprovers) {
        roles.push("super_approvers");
    }

    let url = "/ws/users/";
    if (roles.length) {
        let queryParams = new URLSearchParams();
        queryParams.set('roles', roles.join(","))
        url += `?${queryParams.toString()}`
    }

    return Fetch.get<UsersByRole>(url);
}

export async function fetchProjectApprovers(projectOwner?: string): Promise<string[]> {
    return fetchUsers(UserRoles.Approvers)
        .then(data => {
            if (projectOwner) {
                return data.approvers!.filter(username => username != projectOwner);
            }
            return data.approvers!;
        })
}

export async function fetchProjectEditors(projectOwner?: string): Promise<string[]> {
    return fetchUsers(UserRoles.Editors)
        .then(data => {
            if (projectOwner) {
                return data.editors!.filter(username => username != projectOwner);
            }
            return data.editors!;
        })
}


export function transformProjectForFrontendUse(project: ProjectInfo) {
    project.creation_time = new Date(project.creation_time);
    if (project.edit_time) {
        project.edit_time = new Date(project.edit_time);
    }
    if (project.submitted_time) {
        project.submitted_time = new Date(project.submitted_time);
    }
    if (project.approved_time) {
        project.approved_time = new Date(project.approved_time);
    }
    if (project.notes == undefined) {
        project.notes = [];
    }
}

export function isProjectSubmitted(project?: ProjectInfo): boolean {
    return project?.status === "submitted";
}

export function isProjectApproved(project?: ProjectInfo): boolean {
    return project?.status === "approved";
}

export function isProjectHidden(project?: ProjectInfo): boolean {
    return project?.status === "hidden";
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

export interface deviceDetailFields {
    fg_desc: string,
    tc_part_no: string;
    comments: string;
    stand: string,
    state: string;
    location: string;
    beamline: string;
    nom_ang_x?: number;
    nom_ang_y?: number;
    nom_ang_z?: number;
    nom_loc_x?: number;
    nom_loc_y?: number;
    nom_loc_z?: number;
    ray_trace?: number;
    discussion: ChangeComment[];
}

// used for displaying comment threads
interface ChangeComment {
    id: string;
    author: string;
    time: Date;
    comment: string;
}

export const ProjectDevicePositionKeys: (keyof deviceDetailFields)[] = [
    'nom_ang_x', 'nom_ang_y', 'nom_ang_z',
    'nom_loc_x', 'nom_loc_y', 'nom_loc_z',
]

export const ProjectDeviceDetailsNumericKeys: (keyof deviceDetailFields)[] = [
    ...ProjectDevicePositionKeys,
    'ray_trace'
]


// compare every value field for a change 
export function deviceHasChangedValue(a: ProjectDeviceDetails, b: ProjectDeviceDetails): boolean {
    let key: keyof ProjectDeviceDetails;
    for (key in a) {
        if (key == "id" || key == "fc" || key == "fg" || key == "discussion") { // ignored 
            continue;
        }

        const aVal = a[key];
        const bVal = b[key];
        if (aVal != bVal) {
            if ((aVal == undefined && bVal == '') || (aVal == '' && bVal == undefined)) {
                // both fields are empty, and we shouldn't display them as a change of value 
                // since that would cause <empty>-<empty> to be displayed in the GUI which 
                // would look confusing.
                // 
                // In this case we do nothing and simply retry this check for another key
            } else {
                // there is a difference in value
                return true;
            }
        }
    }
    return false;
}

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

    if (device.discussion) {
        for (let comment of device.discussion) {
            comment.time = new Date(comment.time);
        }
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

export interface ImportResult {
    log_name: string,
    status_str: string
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

export async function syncDeviceUserChanges(projectId: string, fftId: string, changes: Record<string, any>): Promise<ProjectDeviceDetails> {
    // undefined values are not serialized, hence deleting a field (field == undefined) should be replaced with an empty string
    let data = { body: JSON.stringify(changes, (k, v) => v === undefined ? '' : v) };
    return Fetch.post<ProjectDeviceDetailsBackend>(`/ws/projects/${projectId}/fcs/${fftId}`, data)
        .then(d => deviceDetailsBackendToFrontend(d));
}

export async function addDeviceComment(projectId: string, fftId: string, comment: string): Promise<ProjectDeviceDetails> {
    const data = { 'comment': comment };
    return Fetch.post<ProjectDeviceDetailsBackend>(`/ws/projects/${projectId}/fcs/${fftId}/comment`, { body: JSON.stringify(data) })
        .then(device => {
            return deviceDetailsBackendToFrontend(device);
        });
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

export function removeFftsFromProject(projectId: string, fft: ProjectFFT[]): Promise<void> {
    let ids = fft.map(fft => fft._id);
    let data = { 'ids': ids };
    return Fetch.delete<void>(`/ws/projects/${projectId}/ffts/`, { body: JSON.stringify(data) })
}

export async function approveProject(projectId: string): Promise<ProjectInfo> {
    return Fetch.post<ProjectInfo>(`/ws/projects/${projectId}/approve_project`)
        .then((project) => {
            transformProjectForFrontendUse(project);
            return project;
        })
}

export async function rejectProject(projectId: string, rejectionMsg: string): Promise<ProjectInfo> {
    let d = { "reason": rejectionMsg };
    return Fetch.post<ProjectInfo>(`/ws/projects/${projectId}/reject_project`, { body: JSON.stringify(d) })
        .then(project => {
            transformProjectForFrontendUse(project);
            return project;
        })
}

export function submitForApproval(projectId: string, editors: string[], approvers: string[], approveUntil?: Date): Promise<ProjectInfo> {
    let data = {
        'editors': editors,
        'approvers': approvers,
        'approve_until': approveUntil ? toUnixSeconds(approveUntil) : 0,
    }
    return Fetch.post<ProjectInfo>(`/ws/projects/${projectId}/submit_for_approval`, { body: JSON.stringify(data) })
        .then(project => {
            transformProjectForFrontendUse(project);
            return project;
        });
}

export interface ProjectEditData {
    // Note: all project fields are optional, since you could change just one of them.
    name?: string; // project name
    description?: string; // project description
    editors?: string[];
    approvers?: string[];
}

export function editProject(projectId: string, data: ProjectEditData): Promise<ProjectInfo> {
    return Fetch.post<ProjectInfo>(`/ws/projects/${projectId}/`, { body: JSON.stringify(data) })
        .then(project => {
            transformProjectForFrontendUse(project);
            return project;
        });
}

export function deleteProject(projectId: string): Promise<void> {
    return Fetch.delete<void>(`/ws/projects/${projectId}/`);
}

// returns the username of the currently logged in user
export async function whoAmI(): Promise<string> {
    return Fetch.get<string>(`/ws/users/WHOAMI/`);
}

export function useWhoAmIHook() {
    const [user, setUser] = useState('');
    const [isUserDataLoading, setIsUserDataLoading] = useState(false);
    const [userLoadingError, setUserLoadingError] = useState('');
    useEffect(() => {
        setIsUserDataLoading(true);
        whoAmI()
            .then(u => setUser(u))
            .catch((e: JsonErrorMsg) => {
                let msg = "Failed to fetch 'whoami' data: " + e.error;
                console.error(msg, e);
                setUserLoadingError(msg);
            }).finally(() => {
                setIsUserDataLoading(false);
            })
    }, []);
    return { user, userLoadingError, isUserDataLoading };
}


export interface FFTInfo {
    _id: string;
    is_being_used: boolean;
    fc: FC;
    fg: FG;
}

interface FC {
    _id: string;
    name: string;
    description: string;
}

interface FG {
    _id: string;
    name: string;
    description: string;
}

export function fetchFfts(): Promise<FFTInfo[]> {
    return Fetch.get<FFTInfo[]>("/ws/ffts/");
}

export function deleteFft(fftId: string): Promise<void> {
    return Fetch.delete<void>(`/ws/ffts/${fftId}`);
}

export function fetchFcs(): Promise<FC[]> {
    return Fetch.get<FC[]>("/ws/fcs/");
}

export function fetchFgs(): Promise<FG[]> {
    return Fetch.get<FG[]>("/ws/fgs/");
}