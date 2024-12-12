import { createLink } from "@/app/utils/path_utils";
import { AnchorButton, Button, Dialog, DialogBody, DialogFooter, Divider, FileInput, FormGroup, HTMLSelect, InputGroup, Label, NonIdealState, Spinner, Text } from "@blueprintjs/core";
import { useEffect, useMemo, useState } from "react";
import { formatToLiccoDateTime } from "../utils/date_utils";
import { Fetch, JsonErrorMsg } from "../utils/fetching";
import { sortString } from "../utils/sort_utils";
import { ImportResult, ProjectApprovalHistory, ProjectInfo, transformProjectForFrontendUse } from "./project_model";


// dialog for adding new projects
export const AddProjectDialog: React.FC<{ isOpen: boolean, approvedProjects: ProjectInfo[], onClose: () => void, onSubmit: (projectInfo: ProjectInfo) => void }> = ({ isOpen, approvedProjects, onClose, onSubmit }) => {
    const DEFAULT_TEMPLATE = "Blank Project";

    const [selectedTemplate, setSelectedTemplate] = useState<string>(DEFAULT_TEMPLATE);
    const [projectName, setProjectName] = useState('');
    const [description, setDescription] = useState('');

    const [dialogError, setDialogError] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);

    const projectTemplates = useMemo(() => {
        return [DEFAULT_TEMPLATE, ...approvedProjects.map(p => p.name)];
    }, [approvedProjects])


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
            let selectedProject = approvedProjects.filter(p => p.name === selectedTemplate)[0];
            let projectId = selectedProject._id;
            projectUrl = `/ws/projects/${projectId}/clone/`;
        }

        setIsSubmitting(true);
        let body = { "name": projectName, "description": description }
        Fetch.post<ProjectInfo>(projectUrl, { body: JSON.stringify(body) })
            .then(newProjectInfo => {
                onSubmit(newProjectInfo);
            }).catch((e: JsonErrorMsg) => {
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
                transformProjectForFrontendUse(clonedProject);
                onSubmit(clonedProject);
            }).catch((e: JsonErrorMsg) => {
                let msg = `Failed to clone project '${project.name}': ${e.error}`;
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
                transformProjectForFrontendUse(clonedProject);
                onSubmit(clonedProject);
            }).catch((e: JsonErrorMsg) => {
                let msg = `Failed to update project ${project.name} data: ${e.error}`;
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
            }).catch((e: JsonErrorMsg) => {
                let msg = `Failed to fetch history of project approvals: ${e.error}`;
                setDialogError(msg);
                console.error(msg, e);
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

export const ProjectImportDialog: React.FC<{
    isOpen: boolean,
    project: ProjectInfo,
    onClose: (dataImported: boolean) => void,
}> = ({ isOpen, project, onClose }) => {
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [dialogError, setDialogError] = useState('');
    const [selectedFile, setSelectedFile] = useState<File>();
    const [importResult, setImportResult] = useState(String);
    const [robustReport, setRobustReport] = useState(String);
    const [downloadButtonState, setDownloadButtonState] = useState(false)
    const [fileButtonState, setFileButtonState] = useState(true)



    useEffect(() => {
        if (!isOpen) {
            return;
        }
    }, [isOpen])

    const submit = () => {
        if (!selectedFile) {
            return;
        }

        setIsSubmitting(true);
        const data = new FormData();
        data.append("file", selectedFile);
        data.append("name", selectedFile.name)


        Fetch.post<ImportResult>(`/ws/projects/${project._id}/import/`, { body: data, headers: { "Content-Type": "MULTIPART" } })
            .then((resp) => {
                setImportResult(resp.status_str.replaceAll("_", ""));
                setRobustReport(resp.log_name);
                setDialogError('');
                setDownloadButtonState(false);
                setFileButtonState(false);
            })
            .catch((e: JsonErrorMsg) => {
                let msg = `Failed to upload file '${selectedFile.name}' to project '${project.name}'`;
                setDialogError(msg);
                console.error(msg, e);
            })
            .finally(() => {
                setIsSubmitting(false);
            })
    }

    const importFileChosen = (e: any) => {
        if (!e || !e.target.files) {
            return;
        }
        let file = e.target.files[0] as File;
        setSelectedFile(file);
        setDownloadButtonState(true);
    }

    const downloadReport = () => {
        if (robustReport === '') {
            // For whatever reason, no report url            
            setDialogError("No robust report found.")
            return;
        }
        Fetch.get<Blob>(`/ws/projects/${robustReport}/download/`, { headers: { "Content-Type": "MULTIPART", "Accept": "text/plain" } })
            .then((resp) => {
                let url = window.URL.createObjectURL(resp);
                let a = document.createElement('a');
                a.href = url;
                a.download = `${robustReport}.txt`;
                a.click();
            });
        return;
    }

    const renderImportResult = () => {
        // Before file is selected
        if (!selectedFile) {
            return <NonIdealState icon={"search"} title="Please Upload a File" description={"Please select and upload a file"} />
        }
        // Before file is uploaded
        if (importResult === '') {
            return <NonIdealState title="Click Submit to upload file." />
        }

        return (
            <>
                <h5>Upload Successful!</h5>
                <h6>Project: {project.name}</h6>
                <h6>Filename: {selectedFile.name}</h6>
                <Text>
                    <div style={{ whiteSpace: 'pre-line' }}>
                        {importResult}
                    </div>
                </Text>
                <Divider></Divider>
                <h5>(Optional) Robust Changelog</h5>
                <Button onClick={(e) => downloadReport()} intent="primary">Download</Button>
            </>
        )
    }

    const clearImportForm = () => {
        setImportResult('');
        setRobustReport('');
        setDialogError('');
        setSelectedFile(undefined);
        setDownloadButtonState(true);
        setFileButtonState(true);
    }

    const closeDialog = () => {
        const successfulImport = importResult != '';
        clearImportForm();
        onClose(successfulImport);
    }

    return (
        <Dialog isOpen={isOpen} onClose={closeDialog} title={`Upload a Data File to Project: (${project.name})`} autoFocus={true}>
            <DialogBody useOverflowScrollContainer>
                <Text> Upload a .csv to import the data into this project.</Text>
                <FormGroup label="Select a file:">
                    <FileInput id="upload-file" inputProps={{ accept: ".csv" }}
                        disabled={!fileButtonState}
                        text={selectedFile?.name || "Choose file to upload"}
                        onInputChange={e => importFileChosen(e)}
                    />
                    {"  "}
                    <Button onClick={(e) => submit()} intent="primary" loading={isSubmitting} disabled={!downloadButtonState}>Submit File</Button>
                </FormGroup>
                <Divider></Divider>
                {dialogError ? <p className="error">ERROR: {dialogError}</p> : null}
                {renderImportResult()}
            </DialogBody>
            <DialogFooter actions={
                <>
                    <Button onClick={(e) => closeDialog()} >Close</Button>
                </>
            } />
        </Dialog>
    )
}

export const ProjectExportDialog: React.FC<{
    isOpen: boolean,
    project: ProjectInfo,
    onClose: () => void,
    onSubmit: () => void;
}> = ({ isOpen, project, onClose, onSubmit }) => {
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [dialogError, setDialogError] = useState('');

    useEffect(() => {
        if (!isOpen) {
            return;
        }

    }, [isOpen])

    const submit = () => {
        setIsSubmitting(true);
        if (!project._id) {
            // in general this should never happen, if it does we have a bug
            setDialogError(`Invalid project id for project '${project}'`);
            return;
        }

        Fetch.get<Blob>(`/ws/projects/${project._id}/export/`, { headers: { "Content-Type": "MULTIPART", "Accept": "text/csv" } })
            .then(blob => {
                let url = window.URL.createObjectURL(blob);
                let a = document.createElement('a');
                a.href = url;
                const now = new Date().toISOString();
                a.download = `${project.name}_${now}.csv`;
                a.click();

                onSubmit();
                setDialogError("");
            })
            .catch((e) => {
                let msg = `Failed to download the project.`;
                setDialogError(msg);
                console.error(msg, e);
            }).finally(() => {
                setIsSubmitting(false);
            })
    }
    return (
        <Dialog isOpen={isOpen} onClose={onClose} title={`Download Project (${project.name})`} autoFocus={true}>
            <DialogBody useOverflowScrollContainer>
                <p>Download a copy of this project as a .csv?</p>
                {dialogError ? <p className="error">ERROR: {dialogError}</p> : null}
            </DialogBody>
            <DialogFooter actions={
                <>
                    <Button onClick={(e) => onClose()}>Cancel</Button>
                    <Button onClick={(e) => submit()} intent="primary" loading={isSubmitting}>Download</Button>
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
                        href={createLink(`/projects/${project._id}/diff?with=${selectedProject._id}`)}
                        intent="primary"
                        disabled={selectedProjectName == DEFAULT_PROJECT || selectedProjectName == project.name}
                    >Compare Projects</AnchorButton>
                </>
            } />
        </Dialog>
    )
}