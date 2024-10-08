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

export interface FFT {
    _id: string;
    fc: string;
    fg: string;
}

export interface FFTDiff {
    diff: boolean;
    key: string;
    my: string | number;  // our project value
    ot: string | number;  // other's project value
}

export function fetchProjectDiff(currentProjectId: string, otherProjectId: string): Promise<FFTDiff[]> {
    return Fetch.get<FFTDiff[]>(`/ws/projects/${currentProjectId}/diff_with?other_id=${otherProjectId}`)
}
