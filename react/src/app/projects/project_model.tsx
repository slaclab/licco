
export interface ProjectInfo {
    _id: string;
    name: string;
    description: string;
    owner: string;
    editors: string[];
    creation_time: Date;
    edit_time: Date;
    status: string;
    approver?: string;
    submitted_time?: string;
    submitter?: string;
}

export function isProjectSubmitted(project?: ProjectInfo): boolean {
    if (!project) {
        return false;
    }
    return project.status === "submitted";
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