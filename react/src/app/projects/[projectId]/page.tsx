'use client';

import { ProjectSpecificPage } from "./project_details";

export default function ProjectPage({ params }: { params: { projectId: string } }) {
    return (<ProjectSpecificPage projectId={params.projectId} />)
}