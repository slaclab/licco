import { MultiLineText } from "@/app/components/multiline_text";
import { formatToLiccoDateTime } from "@/app/utils/date_utils";
import { JsonErrorMsg } from "@/app/utils/fetching";
import { Button, ButtonGroup, Collapse, Colors, Dialog, DialogBody, DialogFooter, FormGroup, TextArea } from "@blueprintjs/core";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Container } from "react-bootstrap";
import { ProjectInfo, approveProject, fetchMasterProjectInfo, isProjectApproved, isProjectSubmitted, rejectProject } from "../../project_model";
import { ProjectDiffTables } from "../diff/project_diff";
import { ProjectFftDiff, loadProjectDiff } from "../diff/project_diff_model";


export const ProjectApprovalPage: React.FC<{ projectId: string }> = ({ projectId }) => {
    // loading has to be set to true, to show the loading symbol when the page is started initially 
    const [isLoading, setIsLoading] = useState(true);
    const [loadError, setLoadError] = useState('');
    const [diff, setDiff] = useState<ProjectFftDiff>();
    const [rejectDialogOpen, setIsRejectDialogOpen] = useState(false);
    const [userDecision, setUserDecision] = useState('');

    const [showingNotes, setShowingNotes] = useState(false);

    const [isApproving, setIsApproving] = useState(false);

    const fetchApprovalDiff = async () => {
        const masterProject = await fetchMasterProjectInfo();
        const projectDiff = await loadProjectDiff(projectId, masterProject._id);
        return projectDiff;
    }

    useEffect(() => {
        // get master project and fetch the diff between current project id and master project
        fetchApprovalDiff()
            .then(diff => {
                setDiff(diff);
                // TODO: set user decision based on the field (if any)
            }).catch((e: JsonErrorMsg) => {
                let msg = `Failed to fetch projects diff: ${e.error}`;
                console.error(msg, e)
                setLoadError(msg);
            }).finally(() => {
                setIsLoading(false);
            });
    }, [])

    const approveCallback = () => {
        if (!diff) {
            return;
        }

        setIsApproving(true);
        approveProject(projectId)
            .then(updatedProject => {
                let updatedDiff = structuredClone(diff);
                updatedDiff.a = updatedProject;
                setDiff(updatedDiff);
                setUserDecision("Approved");
            }).catch((e: JsonErrorMsg) => {
                // TODO: use a separate error state
                let msg = `Failed to accept the project: ${e.error}`
                setLoadError(msg);
            }).finally(() => {
                setIsApproving(false);
            })
    }

    const summaryTable = useMemo(() => {
        if (!diff) {
            return;
        }


        const renderDecisionField = () => {
            const project = diff.a;
            const submitedOrAproved = isProjectSubmitted(project) || isProjectApproved(project);
            if (!submitedOrAproved) {
                // if project is in development state, we should not render approval buttons
                return <b>You can't approve a project with status: {project.status}</b>
            }

            // TODO: if the project was already approved by this user, we should hide the buttons and display the text
            // (e.g., you have already approved)
            if (userDecision) {
                return <b>{userDecision}</b>
            }

            if (isProjectApproved(project)) {
                // @TODO: we don't know who rejected or approved the project, so there is nothing to do
                return 'This project is already approved';
            }

            return (
                <ButtonGroup>
                    <Button icon="tick" large={true} intent="danger" disabled={isApproving} loading={isApproving}
                        onClick={(e) => approveCallback()}>
                        Approve (accept changes)
                    </Button>
                    &ensp;
                    <Button icon="cross-circle" large={true} intent="primary" disabled={isApproving}
                        onClick={e => setIsRejectDialogOpen(true)}>
                        Reject (keep master values)
                    </Button>
                </ButtonGroup>
            )
        }

        let project = diff.a;
        const notes = project.notes;
        return (
            <Container className="mb-5">
                <table className="table table-nohead table-sm">
                    <thead></thead>
                    <tbody>
                        <tr>
                            <td className="text-nowrap pe-4">Project Name:</td>
                            <td className="w-100"><Link href={`/projects/${project._id}`}>{project.name}</Link></td>
                        </tr>
                        <tr>
                            <td>Submitter:</td>
                            <td>{project.submitter || "/"}</td>
                        </tr>
                        <tr>
                            <td className="text-nowrap">Submitted at:</td>
                            <td>{formatToLiccoDateTime(project.submitted_time) || "/"}</td>
                        </tr>
                        <tr>
                            <td>Summary:</td>
                            <td>
                                {diff.new.length} New <br />
                                {diff.missing.length > 0 ? <>{diff.missing.length} Missing <br /></> : null}
                                {diff.updated.length} Updated <br />
                                {diff.identical.length} Identical <br />
                            </td>
                        </tr>
                        <tr>
                            <td>Notes: </td>
                            <td>
                                {notes.length == 0 ? "/"
                                    :
                                    <>
                                        <Button small={true} onClick={e => setShowingNotes((c) => !c)}>{showingNotes ? "Hide Notes" : "Show Notes"} ({notes.length})</Button>
                                        <Collapse isOpen={showingNotes} keepChildrenMounted={true}>
                                            {notes.map((note, i) => {
                                                return <div key={i} className="user-note mb-2 p-2" style={{ backgroundColor: Colors.LIGHT_GRAY4 }}>
                                                    <MultiLineText text={note} />
                                                </div>
                                            })
                                            }
                                        </Collapse>
                                    </>
                                }
                            </td>
                        </tr>
                        <tr>
                            <td className="text-nowrap">Your Decision:</td>
                            <td>
                                {renderDecisionField()}
                            </td>
                        </tr>
                    </tbody>
                </table>
            </Container>
        )
    }, [userDecision, showingNotes, isApproving, diff])


    return (
        <>
            {isLoading ? null : summaryTable}
            <ProjectDiffTables isLoading={isLoading} loadError={loadError} diff={diff} />

            {diff ?
                <RejectProjectDialog
                    isOpen={rejectDialogOpen}
                    project={diff.a}
                    onClose={() => setIsRejectDialogOpen(false)}
                    onSubmit={(rejectedProject) => {
                        let updatedDiff = structuredClone(diff);
                        updatedDiff.a = rejectedProject;

                        setDiff(updatedDiff);
                        setUserDecision("Rejected");
                        setIsRejectDialogOpen(false);
                    }}
                />
                : null
            }
        </>
    )
}


export const RejectProjectDialog: React.FC<{ isOpen: boolean, project: ProjectInfo, onClose: () => void, onSubmit: (rejectedProject: ProjectInfo) => void }> = ({ isOpen, project, onClose, onSubmit }) => {
    const [dialogError, setDialogError] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [rejectionMsg, setRejectionMsg] = useState('');

    const submit = () => {
        setIsSubmitting(true);
        rejectProject(project._id, rejectionMsg.trim())
            .then((project) => {
                console.log("project:", project);
                onSubmit(project);
            }).catch((e: JsonErrorMsg) => {
                let msg = `Failed to reject a project: ${e.error}`;
                setDialogError(msg);
            }).finally(() => {
                setIsSubmitting(false);
            })
    }

    return (
        <Dialog isOpen={isOpen} onClose={onClose} title={`Reject Project "${project.name}"?`} autoFocus={true} style={{ width: "70ch" }}>
            <DialogBody useOverflowScrollContainer>
                <FormGroup label="Reason for Rejection:" labelInfo="(required)" labelFor="description">
                    <TextArea id="description"
                        autoFocus={true}
                        placeholder="Rejection message..."
                        fill={true}
                        value={rejectionMsg}
                        rows={6}
                        onChange={(e) => setRejectionMsg(e.target.value)}
                    />
                </FormGroup>
                {dialogError ? <p className="error">ERROR: {dialogError}</p> : null}
            </DialogBody>
            <DialogFooter actions={
                <>
                    <Button onClick={(e) => onClose()}>Cancel</Button>
                    <Button onClick={(e) => submit()} intent="primary" loading={isSubmitting} disabled={rejectionMsg.trim().length == 0}>Reject Project</Button>
                </>
            }>
            </DialogFooter>
        </Dialog>
    )
}