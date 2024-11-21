'use client';
import { HtmlPage } from "@/app/components/html_page";
import { SubmitProjectForApproval } from "./submit_for_approval";

/**
 * Handling submit for approving page
 */
export default function SubmitForApprovalPage({ params }: { params: { projectId: string } }) {
    return (
        <HtmlPage>
            <div className="mt-4">
                <SubmitProjectForApproval projectId={params.projectId} />
            </div>
        </HtmlPage>
    )
}


