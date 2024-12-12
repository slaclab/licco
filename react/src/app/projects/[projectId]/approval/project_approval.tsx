import { formatToLiccoDateTime } from "@/app/utils/date_utils";
import { JsonErrorMsg } from "@/app/utils/fetching";
import { createLink } from "@/app/utils/path_utils";
import { AnchorButton, Button, ButtonGroup, Colors, Dialog, DialogBody, DialogFooter, FormGroup, Icon, TextArea } from "@blueprintjs/core";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Container } from "react-bootstrap";
import { ProjectInfo, approveProject, isProjectApproved, isProjectSubmitted, isUserAProjectApprover, isUserAProjectEditor, rejectProject, whoAmI } from "../../project_model";
import { ProjectDiffTables } from "../diff/project_diff";
import { ProjectFftDiff, fetchDiffWithMasterProject } from "../diff/project_diff_model";

import { CollapsibleProjectNotes } from "../../projects_overview";


export const ProjectApprovalPage: React.FC<{ projectId: string }> = ({ projectId }) => {
    // loading has to be set to true, to show the loading symbol when the page is started initially 
    const [isLoading, setIsLoading] = useState(true);
    const [loadError, setLoadError] = useState('');
    const [diff, setDiff] = useState<ProjectFftDiff>();
    const [rejectDialogOpen, setIsRejectDialogOpen] = useState(false);
    const [userDecision, setUserDecision] = useState('');

    const [isApproving, setIsApproving] = useState(false);
    const [userActionError, setUserActionError] = useState('');

    const [loggedInUser, setLoggedInUser] = useState('');

    useEffect(() => {
        // get master project and fetch the diff between current project id and master project
        fetchDiffWithMasterProject(projectId)
            .then(diff => {
                setDiff(diff);

                return whoAmI().then(user => {
                    setLoggedInUser(user);
                });
            }).catch((e: JsonErrorMsg) => {
                let msg = `Failed to fetch projects diff: ${e.error}`;
                console.error(msg, e)
                setLoadError(msg);
            }).finally(() => {
                setIsLoading(false);
            });
    }, [])

    const userIsEditor = useMemo(() => {
        return diff?.a.owner === loggedInUser || diff?.a.editors.includes(loggedInUser);
    }, [loggedInUser, diff])

    const approveCallback = () => {
        if (!diff) {
            return;
        }

        setIsApproving(true);
        approveProject(projectId)
            .then(approvedProject => {
                // refetch the entire diff
                return fetchDiffWithMasterProject(projectId)
                    .then(updatedDiff => {
                        setUserDecision("Approved")
                        setDiff(updatedDiff)
                        setUserActionError('');
                    })
            }).catch((e: JsonErrorMsg) => {
                setUserActionError(e.error);
            }).finally(() => {
                setIsApproving(false);
            })
    }

    const summaryTable = useMemo(() => {
        if (!diff) {
            return;
        }


        const renderDecisionField = () => {
            if (diff.a.approved_by?.includes(loggedInUser)) {
                return <b>Approved</b>
            }

            if (userDecision) {
                return <b>{userDecision}</b>
            }

            const project = diff.a;
            const submitedOrAproved = isProjectSubmitted(project) || isProjectApproved(project);
            if (!submitedOrAproved) {
                // if project is in development state, we should not render approval buttons
                return <b>You can't approve a project with status: {project.status}</b>
            }

            if (isProjectApproved(project)) {
                return 'This project is already approved';
            }

            if (isUserAProjectEditor(diff.a, loggedInUser) && diff.a.status === "submitted") {
                // project editors are only allowed to reject the project
                return (
                    <Button icon="cross-circle" large={true} intent="primary" disabled={isApproving}
                        onClick={e => setIsRejectDialogOpen(true)}>
                        Reject (keep master values)
                    </Button>
                )
            }

            if (!isUserAProjectApprover(diff.a, loggedInUser)) {
                // regular userse (not editors and not approvers) are not allowed to do any action
                return "/";
            }

            // project approvers
            return (
                <>
                <ButtonGroup>
                    <Button icon="tick" large={true} intent="danger" disabled={isApproving} loading={isApproving}
                        onClick={(e) => approveCallback()}>
                        Approve (accept changes)
                    </Button>
                    &ensp;
                    <Button icon="cross-circle" large={true} intent="primary" disabled={isApproving}
                            onClick={e => {
                                setIsRejectDialogOpen(true);
                            }}>
                        Reject (keep master values)
                    </Button>
                </ButtonGroup>

                    {userActionError ? <p className="error m-0 mt-2 error">{userActionError}</p> : null}
                </>
            )
        }

        let project = diff.a;
        const notes = project.notes;
        return (
            <Container className="mb-5">
                <h4>Approve Project</h4>
                <table className="table table-nohead table-sm">
                    <thead></thead>
                    <tbody>
                        <tr>
                            <td className="text-nowrap pe-4">Project Name:</td>
                            <td className="w-100"><Link href={`/projects/${project._id}`} style={{ color: Colors.RED2 }}>{project.name}</Link></td>
                        </tr>
                        <tr>
                            <td>Submitter:</td>
                            <td>{project.submitter || "/"}</td>
                        </tr>
                        <tr>
                            <td className="text-nowrap">Submitted at:</td>
                            <td>{formatToLiccoDateTime(project.submitted_time) || "/"}</td>
                        </tr>
                        {project.approved_time ?
                            <tr>
                                <td>Approved at:</td>
                                <td>{formatToLiccoDateTime(project.approved_time)}</td>
                            </tr>
                            : null
                        }
                        <tr>
                            <td>Approvers:</td>
                            <td>
                                {project.approvers ?
                                    <>
                                        {`${project.approved_by?.length || 0} / ${project.approvers?.length || 0}`}
                                        <br />
                                        <ul className="list-unstyled">
                                            {project.approvers.map(a => {
                                                // TODO: if currently logged in user is project owner or editor, we should render a button to remove the approver
                                                const alreadyApproved = project.approved_by?.includes(a) || false;
                                                return <li key={a}>{alreadyApproved ? <Icon className="me-1" icon="tick" size={14} /> : null}{a}</li>
                                            })}
                                        </ul>

                                        {userIsEditor ?
                                            <AnchorButton small={true} href={createLink(`/projects/${project._id}/submit-for-approval`)}>
                                                Edit Approvers
                                            </AnchorButton>
                                            : null
                                        }
                                    </>
                                    :
                                    <>No approvers selected</>
                                }
                            </td>
                        </tr>
                        <tr>
                            <td>Summary:</td>
                            <td>
                                {/* same ids case only happens on a fresh database where there are no approved projects yet */}
                                {diff.a._id == diff.b._id ?
                                    <>{diff.identical.length} New <br /></>
                                    :
                                    <>
                                        {diff.new.length} New <br />
                                        {diff.missing.length > 0 ? <>{diff.missing.length} Missing <br /></> : null}
                                        {diff.updated.length} Updated <br />
                                        {diff.identical.length} Identical <br />
                                    </>
                                }
                            </td>
                        </tr>
                        <tr>
                            <td>Notes: </td>
                            <td>
                                <CollapsibleProjectNotes notes={notes} />
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
    }, [userDecision, userActionError, isApproving, diff])


    return (
        <>
            {isLoading ? null : summaryTable}

            <ProjectDiffTables user={loggedInUser} isLoading={isLoading} loadError={loadError} diff={diff} />

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
                        // clear any error on success, any error on reject action will be shown in dialog
                        setUserActionError(''); 
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