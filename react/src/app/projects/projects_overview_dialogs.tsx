import { AnchorButton, Button, Dialog, DialogBody, DialogFooter, FormGroup, HTMLSelect, InputGroup, Label, NonIdealState, Spinner } from "@blueprintjs/core";
import { useEffect, useMemo, useState } from "react";
import { formatToLiccoDateTime } from "../utils/date_utils";
import { Fetch, JsonErrorMsg } from "../utils/fetching";
import { sortString } from "../utils/sort_utils";
import { ProjectApprovalHistory, ProjectInfo, projectTransformTimeIntoDates } from "./project_model";


type projectApprovers = string[];

export const ProjectApprovalDialog: React.FC<{ isOpen: boolean, projectTitle: string, projectId: string, projectOwner: string, onClose: () => void, onSubmit: (updatedProject: ProjectInfo) => void }> = ({ isOpen, projectTitle, projectId, projectOwner, onClose, onSubmit }) => {
    const DEFAULT_USER = "Please select an approver";
    const [selectedApprover, setSelectedApprover] = useState(DEFAULT_USER);
    const [approvers, setApprovers] = useState<string[]>([]);
    const [submittingForm, setSubmittingForm] = useState(false);
    const [disableSubmit, setDisableSubmit] = useState(true);

    const [dialogErr, setDialogErr] = useState("");

    useEffect(() => {
        if (isOpen) {
            Fetch.get<projectApprovers>('/ws/approvers/')
                .then(projectApprovers => {
                    let approvers = [DEFAULT_USER, ...projectApprovers.filter(a => a != projectOwner)];
                    setApprovers(approvers);
                }).catch((e) => {
                    let err = e as JsonErrorMsg;
                    let msg = `Failed to fetch project approvers: ${err.error}`;
                    console.error(msg, e);
                    setDialogErr(msg);
                })
        }
    }, [isOpen, projectOwner]);

    useEffect(() => {
        const userNotSelected = !selectedApprover || selectedApprover === DEFAULT_USER;
        const emptyProjectId = !projectId;
        setDisableSubmit(userNotSelected || emptyProjectId);
    }, [selectedApprover, projectId]);


    const submitApprover = () => {
        if (!selectedApprover || selectedApprover == DEFAULT_USER) {
            setDialogErr("Please select a valid approver");
            return;
        }

        if (!projectId) {
            // in general this should never happen, if it does we have a bug
            setDialogErr(`Invalid project id '${projectId}'`);
            return;
        }

        setSubmittingForm(true);
        Fetch.post<ProjectInfo>(`/ws/projects/${projectId}/submit_for_approval?approver=${selectedApprover}`)
            .then((newProject) => {
                onSubmit(newProject);
                setDialogErr('');
            }).catch((e) => {
                let err = e as JsonErrorMsg;
                let msg = `Failed to submit the '${selectedApprover}' for approver: ${err.error}`;
                setDialogErr(msg);
                console.error(msg, e);
            }).finally(() => {
                setSubmittingForm(false);
            });
    }

    return (
        <Dialog onClose={onClose} isOpen={isOpen} title={`Submit Project for Approval (${projectTitle})`}>
            <DialogBody>
                <FormGroup label="Project Approver:">
                    <HTMLSelect
                        iconName="caret-down"
                        value={selectedApprover}
                        options={approvers}
                        autoFocus={true}
                        onChange={(e) => setSelectedApprover(e.target.value)}
                    />
                </FormGroup>

                {dialogErr ? <p className="error">ERROR: {dialogErr}</p> : null}
            </DialogBody>
            <DialogFooter actions={
                <>
                    <Button onClick={(e) => onClose()} disabled={submittingForm}>Cancel</Button>
                    <Button intent="primary"
                        loading={submittingForm}
                        disabled={disableSubmit}
                        onClick={(e) => submitApprover()}
                    >Submit for Approval</Button>
                </>
            } />
        </Dialog>
    )
}



// dialog for adding new projects
export const AddProjectDialog: React.FC<{ isOpen: boolean, onClose: () => void, onSubmit: (projectInfo: ProjectInfo) => void }> = ({ isOpen, onClose, onSubmit }) => {
    const DEFAULT_TEMPLATE = "Blank Project";

    const [projectTemplates, setProjectTemplates] = useState<string[]>([DEFAULT_TEMPLATE]);
    const [selectedTemplate, setSelectedTemplate] = useState<string>(DEFAULT_TEMPLATE);
    const [projectName, setProjectName] = useState('');
    const [description, setDescription] = useState('');

    const [dialogError, setDialogError] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);

    useEffect(() => {
        if (isOpen) {
            // TODO: load project templates if necessary, we don't seem to have them right now...
        }
    }, [isOpen])

    const submit = () => {
        if (!projectName) {
            setDialogError("Project name should not be empty");
            return;
        }
        setDialogError("");

        let projectUrl = ""
        if (selectedTemplate == DEFAULT_TEMPLATE) {
            projectUrl = "/ws/projects/NewBlankProjectClone/clone/";
        } else {
            projectUrl = `/ws/projects/${selectedTemplate}/clone/`;
        }

        setIsSubmitting(true);
        let body = { "name": projectName, "description": description }
        Fetch.post<ProjectInfo>(projectUrl, { body: JSON.stringify(body) })
            .then(newProjectInfo => {
                onSubmit(newProjectInfo);
            }).catch(err => {
                let e = err as JsonErrorMsg;
                setDialogError(`Failed to create a new project: ${e.error}`);
            }).finally(() => {
                setIsSubmitting(false);
            });
    }

    const submitOnEnter = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === "Enter") {
            submit();
        }
    }

    const disableSubmit = projectName.trim() == "" || description.trim() == ""

    return (
        <Dialog isOpen={isOpen} onClose={onClose} title="Create a New Project" autoFocus={true}>
            <DialogBody useOverflowScrollContainer>
                <FormGroup label="Select a Project Template:">
                    <HTMLSelect
                        value={selectedTemplate}
                        options={projectTemplates}
                        onChange={(e) => setSelectedTemplate(e.currentTarget.value)}
                        fill={true} iconName="caret-down"
                        autoFocus={true}
                    />
                </FormGroup>

                <FormGroup label="Project Name:">
                    <InputGroup id="project-name"
                        placeholder=""
                        value={projectName}
                        onKeyUp={submitOnEnter}
                        onValueChange={(val: string) => setProjectName(val)} />
                </FormGroup>

                <FormGroup label="Description:">
                    <InputGroup id="project-description"
                        placeholder=""
                        value={description}
                        onKeyUp={submitOnEnter}
                        onValueChange={(val: string) => setDescription(val)} />
                </FormGroup>
                {dialogError ? <p className="error">ERROR: {dialogError}</p> : null}
            </DialogBody>
            <DialogFooter actions={
                <>
                    <Button onClick={(e) => onClose()}>Cancel</Button>
                    <Button onClick={(e) => submit()} intent="primary" loading={isSubmitting} disabled={disableSubmit}>Create Project</Button>
                </>
            } />
        </Dialog>
    )
}


export const CloneProjectDialog: React.FC<{ isOpen: boolean, project: ProjectInfo, onClose: () => void, onSubmit: (updatedProject: ProjectInfo) => void }> = ({ isOpen, project, onClose, onSubmit }) => {
    const [projectName, setProjectName] = useState('');
    const [projectDescription, setProjectDescription] = useState('');

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [dialogError, setDialogError] = useState('');


    useEffect(() => {
        if (!isOpen) {
            return;
        }
        setProjectName('');
        setProjectDescription('');
    }, [isOpen])

    const submit = () => {
        let data = { "name": projectName, "description": projectDescription }
        setIsSubmitting(true);
        Fetch.post<ProjectInfo>(`/ws/projects/${project._id}/clone/`, { body: JSON.stringify(data) })
            .then((clonedProject) => {
                projectTransformTimeIntoDates(clonedProject);
                onSubmit(clonedProject);
            }).catch((e) => {
                let err = e as JsonErrorMsg;
                let msg = `Failed to clone project '${project.name}': ${err.error}`;
                setDialogError(msg);
            }).finally(() => {
                setIsSubmitting(false);
            })
    }

    return (
        <Dialog isOpen={isOpen} onClose={onClose} title={`Clone Project (${project.name})`} autoFocus={true}>
            <DialogBody useOverflowScrollContainer>
                <FormGroup label="Cloned Project Name:" labelInfo="(required)">
                    <InputGroup id="project-name"
                        placeholder=""
                        value={projectName}
                        autoFocus={true}
                        onValueChange={(val: string) => setProjectName(val)}
                    />
                </FormGroup>

                <FormGroup label="Cloned Project Description:" labelInfo="(required)">
                    <InputGroup id="project-description"
                        placeholder=""
                        value={projectDescription}
                        onValueChange={(val: string) => setProjectDescription(val)} />
                </FormGroup>

                {dialogError ? <p className="error">ERROR: {dialogError}</p> : null}
            </DialogBody>
            <DialogFooter actions={
                <>
                    <Button onClick={(e) => onClose()}>Cancel</Button>
                    <Button onClick={(e) => submit()} intent="primary" loading={isSubmitting} disabled={projectName == "" || projectDescription == ""}>Clone Project</Button>
                </>
            } />
        </Dialog>
    )
}



export const EditProjectDialog: React.FC<{ isOpen: boolean, project: ProjectInfo, onClose: () => void, onSubmit: (updatedProject: ProjectInfo) => void }> = ({ isOpen, project, onClose, onSubmit }) => {
    const [projectName, setProjectName] = useState('');
    const [projectDescription, setProjectDescription] = useState('');

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [dialogError, setDialogError] = useState('');


    useEffect(() => {
        if (!isOpen) {
            return;
        }
        setProjectName(project.name);
        setProjectDescription(project.description);
    }, [isOpen])

    const submit = () => {
        let data = { "name": projectName, "description": projectDescription }
        setIsSubmitting(true);
        let clonedName = "NewBlankProjectClone"
        Fetch.post<ProjectInfo>(`/ws/projects/${clonedName}/`, { body: JSON.stringify(data) })
            .then((clonedProject) => {
                projectTransformTimeIntoDates(clonedProject);
                onSubmit(clonedProject);
            }).catch((e) => {
                let err = e as JsonErrorMsg;
                let msg = `Failed to update project ${project.name} data: ${err.error}`;
                setDialogError(msg);
            }).finally(() => {
                setIsSubmitting(false);
            })
    }

    return (
        <Dialog isOpen={isOpen} onClose={onClose} title={`Edit Project (${project.name})`} autoFocus={true}>
            <DialogBody useOverflowScrollContainer>
                <FormGroup label="Project Name:" labelInfo="(required)">
                    <InputGroup id="project-name"
                        placeholder=""
                        value={projectName}
                        autoFocus={true}
                        onValueChange={(val: string) => setProjectName(val)}
                    />
                </FormGroup>

                <FormGroup label="Project Description:" labelInfo="(required)">
                    <InputGroup id="project-description"
                        placeholder=""
                        value={projectDescription}
                        onValueChange={(val: string) => setProjectDescription(val)} />
                </FormGroup>

                {dialogError ? <p className="error">ERROR: {dialogError}</p> : null}
            </DialogBody>
            <DialogFooter actions={
                <>
                    <Button onClick={(e) => onClose()}>Cancel</Button>
                    <Button onClick={(e) => submit()} intent="primary" loading={isSubmitting} disabled={projectName == "" || projectDescription == ""}>Update Project</Button>
                </>
            } />
        </Dialog>
    )
}

export const HistoryOfProjectApprovalsDialog: React.FC<{ isOpen: boolean, onClose: () => void }> = ({ isOpen, onClose }) => {
    const [isLoading, setIsLoading] = useState(false);
    const [dialogError, setDialogError] = useState('');
    const [projectHistory, setProjectHistory] = useState<ProjectApprovalHistory[]>([]);


    useEffect(() => {
        if (!isOpen) {
            return;
        }

        setIsLoading(true);
        Fetch.get<ProjectApprovalHistory[]>(`/ws/history/project_approvals`)
            .then((data) => {
                data.forEach(d => d.switch_time = new Date(d.switch_time));
                setProjectHistory(data);
                setDialogError('');
            }).catch((e) => {
                console.error("Failed to fetch project approvals", e);
                let err = e as JsonErrorMsg;
                setDialogError(`Failed to fetch history of project approvals: ${err.error}`);
            }).finally(() => {
                setIsLoading(false);
            })
    }, [isOpen])

    const projectHistoryTable = useMemo(() => {
        if (isLoading) {
            return <NonIdealState icon={<Spinner />} title="Loading" description={"Fetching data..."} />
        }

        if (dialogError) {
            return <NonIdealState icon="error" title="Error" description={dialogError} />
        }

        if (projectHistory.length == 0) {
            return <NonIdealState icon="search" title="No Project Approvals Found" description={"There are no project approvals at this moment"}></NonIdealState>
        }

        return (
            <table className="table table-sm table-bordered table-striped">
                <thead>
                    <tr>
                        <th>Project Name</th>
                        <th>Switched at</th>
                        <th>Switched by</th>
                        <th>Project description</th>
                        <th>Project owner</th>
                    </tr>
                </thead>
                <tbody>
                    {projectHistory.map(history => {
                        return (
                            <tr key={history._id}>
                                <td className="text-nowrap">{history.prj}</td>
                                <td className="text-nowrap">{formatToLiccoDateTime(history.switch_time)}</td>
                                <td className="text-nowrap">{history.requestor_uid}</td>
                                <td>{history.description}</td>
                                <td className="text-nowrap">{history.owner}</td>
                            </tr>
                        )
                    })}
                </tbody>
            </table>
        )

    }, [projectHistory])

    return (
        <Dialog isOpen={isOpen} onClose={onClose} title={`History of Project Approvals`} style={{ width: "60rem", maxWidth: "90%" }}>
            <DialogBody useOverflowScrollContainer>
                {projectHistoryTable}
            </DialogBody>
            <DialogFooter actions={
                <>
                    <Button onClick={(e) => onClose()}>Close</Button>
                </>
            } />
        </Dialog>
    )
}


// dialog for chosing with with other project we want to compare our project with
export const ProjectComparisonDialog: React.FC<{ isOpen: boolean, project: ProjectInfo, availableProjects: ProjectInfo[], onClose: () => void, onSubmit?: (updatedProject: ProjectInfo) => void }> = ({ isOpen, project, availableProjects, onClose, onSubmit }) => {
    const DEFAULT_PROJECT = "Please select a project";
    const [selectedProjectName, setSelectedProjectName] = useState<string>(DEFAULT_PROJECT);

    const projects = useMemo(() => {
        let p = availableProjects.filter(p => p.name != project.name).map(p => p.name);
        p.sort((a, b) => sortString(a, b, false));
        return [DEFAULT_PROJECT, ...p];
    }, [availableProjects]);

    const selectedProject = useMemo(() => {
        if (selectedProjectName == DEFAULT_PROJECT) {
            // we just return the same project we are comparing with to get around typesystem
            // the button is disabled in case of a default project, so this should never be a problem
            return project;
        }

        for (let p of availableProjects) {
            if (p.name == selectedProjectName) {
                return p;
            }
        }
        return project;
    }, [selectedProjectName])

    return (
        <Dialog isOpen={isOpen} onClose={onClose} title={`Compare Projects`} autoFocus={true}>
            <DialogBody useOverflowScrollContainer>
                <FormGroup label="Selected Project:" inline={true}>
                    <Label>{project.name}</Label>
                </FormGroup>

                <FormGroup label="Compare With:" inline={true}>
                    <HTMLSelect
                        value={selectedProjectName}
                        options={projects}
                        onChange={e => setSelectedProjectName(e.target.value)}
                        iconName="caret-down"
                        autoFocus={true}
                    />
                </FormGroup>
            </DialogBody>
            <DialogFooter actions={
                <>
                    <Button onClick={(e) => onClose()}>Close</Button>
                    <AnchorButton
                        href={`/projects/${project._id}/diff?with=${selectedProject._id}`}
                        intent="primary"
                        disabled={selectedProjectName == DEFAULT_PROJECT || selectedProjectName == project.name}
                    >Compare Projects</AnchorButton>
                </>
            } />
        </Dialog>
    )
}