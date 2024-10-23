'use client';
import { HtmlPage } from "@/app/components/html_page";
import { useSearchParams } from "next/navigation";
import { ProjectDiffPage } from "./project_diff";

export default function DiffHomepage({ params }: { params: { projectId: string } }) {
    const queryParams = useSearchParams();

    return (
        <HtmlPage>
            <div className="mb-2" />
            <ProjectDiffPage projectIdA={params.projectId} projectIdB={queryParams.get("with") || "ERROR"} />
        </HtmlPage>
    )
}