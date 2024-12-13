import { DividerWithText } from "@/app/components/divider";
import { ErrorDisplay, LoadingSpinner } from "@/app/components/loading";
import { MultiChoiceSelector } from "@/app/components/selector";
import { JsonErrorMsg } from "@/app/utils/fetching";
import { createLink } from "@/app/utils/path_utils";
import { AnchorButton, Button, Colors, NonIdealState } from "@blueprintjs/core";
import { useEffect, useMemo, useState } from "react";
import { Container, Row } from "react-bootstrap";
import { ProjectEditData, ProjectInfo, editProject, fetchProjectApprovers, fetchProjectEditors, fetchProjectInfo, isProjectInDevelopment, isProjectSubmitted, submitForApproval, whoAmI } from "../../project_model";
import { ProjectDiffTables } from "../diff/project_diff";
import { ProjectFftDiff, fetchDiffWithMasterProject } from "../diff/project_diff_model";

export const SubmitProjectForApproval: React.FC<{ projectId: string }> = ({ projectId }) => {
    const [loading, setLoading] = useState(true);
    const [loadError, setLoadError] = useState('');
    const [project, setProject] = useState<ProjectInfo>();
    const [diff, setDiff] = useState<ProjectFftDiff>();
    const [loggedInUser, setLoggedInUser] = useState('');

    // approvers
    const [allApprovers, setAllApprovers] = useState<string[]>([]);
    const [selectedApprovers, setSelectedApprovers] = useState<string[]>([]);

    // editors
    const [allEditors, setAllEditors] = useState<string[]>([]);
    const [selectedEditors, setSelectedEditors] = useState<string[]>([]);

    // super approvers
    const [superApprovers, setSuperApprovers] = useState<string[]>([]);

    const [submittingForm, setSubmittingForm] = useState(false);
    const [submitError, setSubmitError] = useState('');
    const [editEditorsError, setEditEditorsError] = useState('');

    const fetchData = async (projectId: string) => {
        let projectInfo = await fetchProjectInfo(projectId);
        let whoami = await whoAmI();
        let allApprovers = await fetchProjectApprovers(projectInfo.owner);
        let allEditors = await fetchProjectEditors(projectInfo.owner);
        let diff = await fetchDiffWithMasterProject(projectId);
        return { projectInfo, whoami, allEditors, allApprovers, diff };
    }

    useEffect(() => {
        fetchData(projectId)
            .then((data) => {
                setProject(data.projectInfo);
                setDiff(data.diff);
                setLoggedInUser(data.whoami);

                // submitter or editor can't be an approver, that's why the currently logged in user should never appear in the list
                // of all available approvers
                const allApprovers = data.allApprovers.filter(e => e != data.whoami);
                setAllApprovers(allApprovers);

                const allEditors = data.allEditors;
                setAllEditors(allEditors);

                // remove already selected approvers and editors
                if (data.projectInfo.approvers) {
                    // select approvers which are allowed to approve and who are not currently selected as editors
                    let selectedEditors = data.projectInfo.editors ?? [];
                    let selectedApprovers = allApprovers.filter(a => data.projectInfo.approvers?.includes(a) && !selectedEditors.includes(a));
                    setSelectedApprovers(selectedApprovers);
                }

                if (data.projectInfo.editors) {
                    // only select editors which are allowed to edit and are in the current list of editors
                    let selectedEditors = allEditors.filter(a => data.projectInfo.editors?.includes(a));
                    setSelectedEditors(selectedEditors);
                }
            }).catch((e: JsonErrorMsg) => {
                setLoadError(e.error);
            }).finally(() => {
                setLoading(false);
            });
    }, [projectId])

    let { availableApprovers, availableEditors } = useMemo(() => {
        // approver can be someone who is not the currently selected editor
        // editor is someone who is not the currently selected approver
        let availableApprovers = allApprovers.filter(a => !selectedEditors.includes(a));
        let availableEditors = allEditors.filter(a => !(selectedApprovers.includes(a)))
        return { availableApprovers, availableEditors }
    }, [allApprovers, selectedApprovers, allEditors, selectedEditors])

    const userCanSubmitTheProject = () => {
        if (!diff?.a) {
            return false;
        }

        if (diff.a.owner === loggedInUser) {
            return true;
        }

        if (diff.a.editors.includes(loggedInUser)) {
            return true;
        }

        return false;
    }

    const disableEditActions = useMemo(() => {
        if (userCanSubmitTheProject()) {
            // user who can submit the project, should always be able to edit the project
            return false;
        }
        return !isProjectInDevelopment(project) || !userCanSubmitTheProject();
    }, [project, loggedInUser])



    const renderSuperApprovers = (approvers: string[]) => {
        if (approvers.length == 0) {
            return <p style={{ color: Colors.GRAY1 }}>No Super Approvers Available</p>
        }

        return (
            <ul className="list-unstyled">
                {approvers.map(approver => {
                    return <li key={approver}>{approver}</li>
                })}
            </ul>
        )
    }

    const submitButtonClicked = () => {
        if (!project) {
            // this should never happen
            return;
        }

        setSubmittingForm(true);
        setSubmitError('');
        setEditEditorsError('');

        // We are sending editors together with a list of approvers, since it's possible that someone will update
        // the editors and forget to click on the "Update Editors" button. Later on they will be wondering why
        // the list of editors has not changed, when they have clearly submitted a project.
        //
        // While editors do not have much of a role while the project is in a submitted state,
        // we want to avoid the potential confusion described above, hence we send both lists.
        submitForApproval(projectId, selectedEditors, selectedApprovers)
            .then(updatedProject => {
                // update fields to show that the project was already approved
                setProject(updatedProject);
            }).catch((e: JsonErrorMsg) => {
                setSubmitError(`Failed to submit a project for approval: ${e.error}`);
            }).finally(() => {
                setSubmittingForm(false);
            })
    }

    const editButtonClicked = () => {
        if (!project) {
            // this should never happen
            return;
        }

        setSubmittingForm(true);
        setEditEditorsError('');

        const editData: ProjectEditData = {
            'editors': selectedEditors
        }
        editProject(projectId, editData)
            .then(updatedProject => {
                setProject(updatedProject);
            }).catch((e: JsonErrorMsg) => {
                let msg = "Failed to edit the project editors: " + e.error;
                console.error(msg, e);
                setEditEditorsError(msg);
            }).finally(() => {
                setSubmittingForm(false);
            });
    }


    if (loading) {
        return <LoadingSpinner isLoading={loading} title="Loading" description={"Fetching project data..."} />
    }
    if (loadError) {
        return <ErrorDisplay description={loadError} />
    }
    if (!project || !diff) {
        return <NonIdealState icon="clean" title="No Data Found" description={"No project data found"} />
    }

    return (
        <>
            <Container>
                <h4>Submit Project for Approval</h4>
                <table className="table table-nohead table-sm">
                    <thead></thead>
                    <tbody>
                        <tr>
                            <td>Project:</td>
                            <td className="w-100"><a href={createLink(`/projects/${project._id}`)} style={{ color: Colors.RED2 }}>{project.name}</a></td>
                        </tr>
                        <tr>
                            <td>Owner:</td>
                            <td>{project.owner}</td>
                        </tr>
                        <tr>
                            <td>Status:</td>
                            <td>{project.status}</td>
                        </tr>
                        <tr>
                            <td>Summary:</td>
                            <td>
                                <>
                                    {diff.new.length} New <br />
                                    {diff.missing.length > 0 ? <>{diff.missing.length} Missing <br /></> : null}
                                    {diff.updated.length} Updated <br />
                                    {diff.identical.length} Identical <br />
                                </>
                            </td>
                        </tr>
                        <tr>
                            <td>Editors:</td>
                            <td>
                                <>
                                    <MultiChoiceSelector
                                        availableItems={availableEditors}
                                        defaultSelectedItems={selectedEditors}
                                        defaultValue={"Please select an editor..."}
                                        renderer={(s) => s}
                                        disabled={disableEditActions}
                                        noSelectionMessage={"No Editors Were Selected"}
                                        onChange={newEditors => setSelectedEditors(newEditors)}
                                    />

                                    <Button intent="danger" icon="edit" loading={submittingForm} disabled={disableEditActions}
                                        onClick={(e) => editButtonClicked()}>
                                        Update Editors
                                    </Button>

                                    {editEditorsError ? <p className="error">ERROR: {editEditorsError}</p> : null}
                                </>
                            </td>
                        </tr>
                        <tr>
                            <td>Approvers:</td>
                            <td>
                                <MultiChoiceSelector
                                    availableItems={availableApprovers}
                                    defaultSelectedItems={selectedApprovers}
                                    defaultValue={"Please select an approver..."}
                                    renderer={(s) => s}
                                    disabled={disableEditActions}
                                    noSelectionMessage={"No Approvers Were Selected"}
                                    onChange={newApprovers => setSelectedApprovers(newApprovers)}
                                />
                            </td>
                        </tr>
                        <tr>
                            <td className="text-nowrap">Super Approvers:</td>
                            <td>{renderSuperApprovers(superApprovers)}</td>
                        </tr>
                    </tbody>
                </table>

                <Row className="mt-4">
                    {userCanSubmitTheProject() ?
                        <>
                            <div>
                                {isProjectInDevelopment(project) ?
                                    <Button icon="tick" intent="danger" large={true}
                                        loading={submittingForm}
                                        disabled={selectedApprovers.length == 0}
                                        onClick={e => submitButtonClicked()}>
                                        Submit for Approval
                                    </Button>
                                    :
                                    null
                                }

                                {isProjectSubmitted(project) ?
                                    <>
                                        <Button large={true} icon="edit" intent="danger" className="me-2"
                                            loading={submittingForm}
                                            disabled={selectedApprovers.length == 0}
                                            onClick={e => submitButtonClicked()}
                                        >
                                            Edit Submitted Project
                                        </Button>

                                        <AnchorButton intent="none" href={createLink(`/projects/${diff.a._id}/approval`)} large={true} icon="arrow-right">See Approval Page</AnchorButton>
                                    </>
                                    : null
                                }
                            </div>

                            {submitError ? <p className="error">ERROR: {submitError}</p> : null}
                        </>
                        :
                        <NonIdealState icon="user" className="pb-4 mb-4" title="No Permissions" description={"You don't have permissions to submit a project for approval"} />
                    }
                </Row>
            </Container>

            <DividerWithText className="m-4" text={`Project ${project.name} diff with Master Project`} />

            <ProjectDiffTables isLoading={loading} loadError={loadError} user={loggedInUser} diff={diff} />
        </>
    )
}