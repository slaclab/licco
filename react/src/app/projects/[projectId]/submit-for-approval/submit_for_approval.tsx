import { DividerWithText } from "@/app/components/divider";
import { ErrorDisplay, LoadingSpinner } from "@/app/components/loading";
import { JsonErrorMsg } from "@/app/utils/fetching";
import { sortString } from "@/app/utils/sort_utils";
import { AnchorButton, Button, ButtonGroup, Colors, ControlGroup, FormGroup, HTMLSelect, NonIdealState } from "@blueprintjs/core";
import { useEffect, useMemo, useState } from "react";
import { Container, Row } from "react-bootstrap";
import { ProjectInfo, fetchProjectApprovers, fetchProjectInfo, isProjectInDevelopment, isProjectSubmitted, submitForApproval, whoAmI } from "../../project_model";
import { ProjectDiffTables } from "../diff/project_diff";
import { ProjectFftDiff, fetchDiffWithMasterProject } from "../diff/project_diff_model";

export const SubmitProjectForApproval: React.FC<{ projectId: string }> = ({ projectId }) => {
    const [loading, setLoading] = useState(true);
    const [loadError, setLoadError] = useState('');
    const [project, setProject] = useState<ProjectInfo>();
    const [diff, setDiff] = useState<ProjectFftDiff>();
    const [loggedInUser, setLoggedInUser] = useState('');

    // state 
    const DEFAULT_USER = "Please select an approver...";
    const [allApprovers, setAllApprovers] = useState<string[]>([]);
    const [currentApprover, setCurrentApprover] = useState(DEFAULT_USER);
    const [selectedApprovers, setSelectedApprovers] = useState<string[]>([]);
    const [superApprovers, setSuperApprovers] = useState<string[]>([]);

    const [submittingForm, setSubmittingForm] = useState(false);
    const [submitError, setSubmitError] = useState('');

    const fetchData = async (projectId: string) => {
        let projectInfo = await fetchProjectInfo(projectId);
        let availableApprovers = await fetchProjectApprovers(projectInfo.owner);
        let diff = await fetchDiffWithMasterProject(projectId);
        return { projectInfo, approvers: availableApprovers, diff };
    }

    useEffect(() => {
        fetchData(projectId)
            .then((data) => {
                // TODO: how do we find superapprovers that should be always present?
                setProject(data.projectInfo);
                setDiff(data.diff);
                if (data.projectInfo.approvers) {
                    setSelectedApprovers([...data.projectInfo.approvers])
                }

                return whoAmI().then(loggedInUser => {
                    let filteredApprovers = [];
                    for (let approver of data.approvers) {
                        // project editors, owners, or submitters should not be allowed
                        // to approve the project
                        if (diff?.a.owner === approver) {
                            continue;
                        }

                        if (diff?.a.editors.includes(approver)) {
                            continue;
                        }

                        filteredApprovers.push(approver);
                    }
                    // user who approves
                    setAllApprovers(filteredApprovers);
                    setLoggedInUser(loggedInUser);
                });
            }).catch((e: JsonErrorMsg) => {
                setLoadError(e.error);
            }).finally(() => {
                setLoading(false);
            });
    }, [projectId])

    const addUser = (username: string) => {
        let index = availableApprovers.indexOf(username);
        if (index == availableApprovers.length - 1) {
            // user is set as last element, find previous index
            index--;
        } else {
            index++;
        }
        if (index >= 0 && index <= availableApprovers.length - 1) {
            setCurrentApprover(availableApprovers[index])
        } else {
            setCurrentApprover(DEFAULT_USER);
        }

        let updatedApprovers = [...selectedApprovers, username];
        updatedApprovers.sort((a, b) => sortString(a, b, false));
        setSelectedApprovers(updatedApprovers);
    }

    const removeUser = (username: string) => {
        let index = selectedApprovers.indexOf(username);
        if (index < 0) { // this should never happen
            return;
        }
        selectedApprovers.splice(index, 1);
        setSelectedApprovers([...selectedApprovers]);
    }

    let availableApprovers = useMemo(() => {
        let leftoverApprovers = allApprovers.filter(a => !selectedApprovers.includes(a));
        return [DEFAULT_USER, ...leftoverApprovers];
    }, [selectedApprovers, allApprovers])


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

    const disableActions = !isProjectInDevelopment(project) || !userCanSubmitTheProject()

    const renderApprovers = (approvers: string[]) => {
        if (approvers.length == 0) {
            return <p style={{ color: Colors.GRAY1 }}>No Approvers Were Selected</p>
        }

        return (
            <ul className="list-unstyled">
                {approvers.map((approver) => {
                    return <li key={approver}>
                        <ControlGroup>
                            <Button icon="cross" small={true} minimal={true}
                                disabled={disableActions}
                                onClick={(e) => removeUser(approver)} />
                            {approver}
                        </ControlGroup>
                    </li>
                })}
            </ul>
        )
    }

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
        submitForApproval(projectId, selectedApprovers)
            .then(updatedProject => {
                // update fields to show that the project was already approved
                setProject(updatedProject);
                setSubmitError('');
            }).catch((e: JsonErrorMsg) => {
                setSubmitError(`Failed to submit a project for approval: ${e.error}`);
            }).finally(() => {
                setSubmittingForm(false);
            })
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

    // TODO: check if the currently logged in user has permissions

    return (
        <>
            <Container>
                <h4>Submit Project for Approval</h4>
                <table className="table table-nohead table-sm">
                    <thead></thead>
                    <tbody>
                        <tr>
                            <td>Project:</td>
                            <td className="w-100"><a href={`/projects/${project._id}`} style={{ color: Colors.RED2 }}>{project.name}</a></td>
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
                            <td>Approvers:</td>
                            <td>
                                <FormGroup inline={false} className="m-0">
                                    <ControlGroup>
                                        <HTMLSelect
                                            iconName="caret-down"
                                            value={currentApprover}
                                            options={availableApprovers}
                                            autoFocus={true}
                                            disabled={disableActions}
                                            onChange={(e) => setCurrentApprover(e.target.value)}
                                        />
                                        <Button icon="add"
                                            disabled={currentApprover === DEFAULT_USER || disableActions}
                                            onClick={e => addUser(currentApprover)}>
                                            Add
                                        </Button>
                                    </ControlGroup>
                                    {renderApprovers(selectedApprovers)}
                                </FormGroup>
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
                            <ButtonGroup>
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
                                    <AnchorButton intent="danger" href={`/projects/${diff.a._id}/approval`} large={true} icon="arrow-right">See Approval Page</AnchorButton>
                                    : null
                                }
                            </ButtonGroup>

                            {submitError ? <p className="error">ERROR: {submitError}</p> : null}
                        </>
                        :
                        <NonIdealState icon="user" className="pb-4 mb-4" title="No Permissions" description={"You don't have permissions to submit a project for approval"} />
                    }
                </Row>
            </Container>

            <DividerWithText className="m-4" text={`Project ${project.name} diff with Master Project`} />

            <ProjectDiffTables isLoading={loading} loadError={loadError} diff={diff} />
        </>
    )
}