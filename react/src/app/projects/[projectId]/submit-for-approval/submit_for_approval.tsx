import { DividerWithText } from "@/app/components/divider";
import { ErrorDisplay, LoadingSpinner } from "@/app/components/loading";
import { MultiChoiceStringSelector } from "@/app/components/selector";
import { JsonErrorMsg } from "@/app/utils/fetching";
import { createLink } from "@/app/utils/path_utils";
import { AnchorButton, Button, Colors, Icon, NonIdealState } from "@blueprintjs/core";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Container, Row } from "react-bootstrap";
import { ProjectEditData, ProjectInfo, UserRoles, editProject, fetchUsers, isProjectInDevelopment, isProjectSubmitted, submitForApproval, whoAmI } from "../../project_model";
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
        const [whoami, users, diff] = await Promise.all([
            whoAmI(),
            fetchUsers(UserRoles.Approvers | UserRoles.Editors | UserRoles.SuperApprovers),
            fetchDiffWithMasterProject(projectId),
        ]);

        const projectInfo = diff.a;
        const superApprovers = users.super_approvers ?? [];

        let allEditors = users.editors ?? [];
        // super approver should not be selectable as an editor
        allEditors = allEditors.filter(editor => !superApprovers.includes(editor) && editor != diff.a.owner);

        let allApprovers = users.approvers ?? [];
        // super approver should not be selectable as an approver
        allApprovers = allApprovers.filter(approver => !superApprovers.includes(approver));
        return { projectInfo, whoami, allEditors, allApprovers, superApprovers, diff };
    }

    useEffect(() => {
        fetchData(projectId)
            .then((data) => {
                setProject(data.projectInfo);
                setDiff(data.diff);
                setLoggedInUser(data.whoami);

                // submitter or editor can't be an approver, that's why the currently logged in user should never appear in the list
                // of all available approvers
                setSuperApprovers(data.superApprovers);
                setAllApprovers(data.allApprovers.filter(e => e != data.whoami));
                setAllEditors(data.allEditors.filter(e => e != data.whoami));

                // remove already selected approvers and editors
                if (data.projectInfo.approvers) {
                    // We don't restrict approvers to just the ones with approval roles, since anyone with an account
                    // is elligible to be an approver. Account validity is tested on project edit
                    setSelectedApprovers(data.projectInfo.approvers)
                }

                if (data.projectInfo.editors) {
                    // we don't restrict editors to just the ones with edito role, since anyone with an account 
                    // could be an editor. The account validity is tested on project edit
                    setSelectedEditors(data.projectInfo.editors);
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

    const userCanSubmitTheProject = useCallback(() => {
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
    }, [diff?.a, loggedInUser])

    const disableEditActions = useMemo(() => {
        if (userCanSubmitTheProject()) {
            // user who can submit the project, should always be able to edit the project
            return false;
        }
        return !isProjectInDevelopment(project) || !userCanSubmitTheProject();
    }, [project, userCanSubmitTheProject])



    const renderSuperApprovers = (approvers: string[]) => {
        if (approvers.length == 0) {
            return <p style={{ color: Colors.GRAY1 }}>No Super Approvers Available</p>
        }

        return (
            <>
                <p className="mb-1" style={{ color: Colors.GRAY1 }}>These users will be automatically added as project approvers!</p>
                <ul className="list-unstyled">
                    {approvers.map(approver => {
                        return <li key={approver}><Icon icon="tick" color={Colors.GRAY1} className="me-1" />{approver}</li>
                    })}
                </ul>
            </>
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
                                    {diff.updated.length} Updated <br />
                                    {diff.identical.length} Identical <br />
                                </>
                            </td>
                        </tr>
                        <tr>
                            <td>Editors:</td>
                            <td>
                                <>
                                    <MultiChoiceStringSelector
                                        availableItems={availableEditors}
                                        defaultSelectedItems={selectedEditors}
                                        defaultValue=""
                                        placeholder={"Please select an editor..."}
                                        disabled={disableEditActions}
                                        noSelectionMessage={"No editors were selected"}
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
                                <MultiChoiceStringSelector
                                    availableItems={availableApprovers}
                                    defaultSelectedItems={selectedApprovers}
                                    placeholder={"Please select an approver..."}
                                    defaultValue=""
                                    disabled={disableEditActions}
                                    noSelectionMessage={"No approvers were selected"}
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
                                            Save Changes
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