'use client';

import { ProjectDetails } from "./project_details";

export default function ProjectPage({ params }: { params: { projectId: string } }) {
    return (<ProjectDetails projectId={params.projectId} />)
}