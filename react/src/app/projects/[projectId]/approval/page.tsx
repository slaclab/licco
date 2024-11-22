'use client';
import { HtmlPage } from "@/app/components/html_page";
import { ProjectApprovalPage } from "./project_approval";

export default function ApprovalHomepage({ params }: { params: { projectId: string } }) {

    return (
        <HtmlPage>
            <div className="mt-4">
                <ProjectApprovalPage projectId={params.projectId} />
            </div>
        </HtmlPage>
    )
}