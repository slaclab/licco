import { Button, ButtonGroup, Dialog, DialogBody, DialogFooter, FormGroup, HTMLSelect, InputGroup, NonIdealState, Tooltip } from "@blueprintjs/core";
import Link from "next/link";
import React, { useEffect, useState } from "react";
import { formatToLiccoDateTime } from "../utils/date_utils";
import { Fetch, JsonErrorMsg } from "../utils/fetching";
import { ProjectApprovalDialog } from "./project_approval_dialog";
import { ProjectInfo, fetchAllProjects, isProjectSubmitted, projectTransformTimeIntoDates } from "./project_model";


export const ProjectsOverview: React.FC = ({ }) => {
    const [projectData, setProjectData] = useState<ProjectInfo[]>([]);
    const [projectDataLoading, setProjectDataLoading] = useState(false);
    const [err, setError] = useState("");

    const [isAddProjectDialogOpen, setIsAddProjectDialogOpen] = useState(false);
    const [isApprovalDialogOpen, setIsApprovalDialogOpen] = useState(false);
    const [selectedProject, setSelectedProject] = useState<ProjectInfo>();

    const fetchProjectData = () => {
        setProjectDataLoading(true);
        fetchAllProjects()
            .then((projects) => {
                setProjectData(projects);
            }).catch((e) => {
                console.error(e);
                let err = e as JsonErrorMsg;
                setError("Failed to load projects data: " + err.error);
            }).finally(() => {
                setProjectDataLoading(false);
            });
    }

    useEffect(() => {
        fetchProjectData();
    }, []);


    if (err) {
        return <p>{err}</p>
    }

    const showAddProjectDialog = () => {
        setIsAddProjectDialogOpen(true);
    }

    return (
        <>
        <div className="table-responsive">
            <table className="table table-striped table-bordered table-sm">
                <thead>
                    <tr>
                            <th scope="col">
                                <Tooltip content="Add new Project" position="bottom">
                                    <Button icon="add" onClick={(e) => showAddProjectDialog()} minimal={true} small={true} />
                                </Tooltip>
                                <Tooltip content="Show the history of project approvals" position="bottom">
                                    <Button icon="history" minimal={true} small={true} />
                                </Tooltip>
                                {projectDataLoading ?
                                    <Button minimal={true} small={true} disabled={true} loading={projectDataLoading} />
                                    : null
                                }
                            </th>
                        <th>Name</th>
                        <th>Owner</th>
                        <th>Created</th>
                        <th>Last Edit</th>
                        <th>Description</th>
                        <th>Notes</th>
                    </tr>
                </thead>
                <tbody>
                    {projectData.map((project) => {
                        return (
                            <tr key={project._id}>
                                <td>
                                    <ButtonGroup minimal={true}>
                                        <Tooltip content="Compare (diff) with another project" position="bottom">
                                            <Button icon="comparison" small={true} />
                                        </Tooltip>

                                        <Tooltip content="Clone this project" position="bottom">
                                            <Button icon="duplicate" small={true} />
                                        </Tooltip>

                                        {!isProjectSubmitted(project) ?
                                            <>
                                                <Tooltip content="Edit this project" position="bottom">
                                                    <Button icon="edit" minimal={true} small={true} />
                                                </Tooltip>

                                                <Tooltip content="Submit this project for approval" position="bottom">
                                                    <Button icon="user"
                                                        minimal={true} small={true}
                                                        onClick={(e) => {
                                                            setSelectedProject(project);
                                                            setIsApprovalDialogOpen(true);
                                                        }}
                                                    />
                                                </Tooltip>

                                                <Tooltip content="Upload data to this project" position="bottom">
                                                    <Button icon="export" minimal={true} small={true} />
                                                </Tooltip>
                                            </>
                                            : null
                                        }

                                        <Tooltip content="Download this project" position="bottom">
                                            <Button icon="import" minimal={true} small={true} />
                                        </Tooltip>

                                    </ButtonGroup>
                                </td>
                                <td><Link href={`/projects/${project._id}`}>{project.name}</Link></td>
                                <td>{project.owner}</td>
                                <td>{formatToLiccoDateTime(project.creation_time)}</td>
                                <td>{formatToLiccoDateTime(project.edit_time)}</td>
                                <td>{project.description}</td>
                                <td></td>
                            </tr>
                        )
                    })
                    }
                </tbody>
            </table>
            </div>

            {!projectDataLoading && err != "" && projectData.length == 0 ?
                <NonIdealState icon="search" title="No Projects Found" description="There are no projects to display. Try adding a new project by clicking on the button below">
                    <Button icon="plus" onClick={(e) => showAddProjectDialog()}>Add Project</Button>
                </NonIdealState>
                : null
            }

            <AddProjectDialog
                isOpen={isAddProjectDialogOpen}
                onClose={() => setIsAddProjectDialogOpen(false)}
                onSubmit={(newProject) => {
                    projectTransformTimeIntoDates(newProject);
                    let newData = [...projectData, newProject];
                    setProjectData(newData);
                    setIsAddProjectDialogOpen(false)
                }}
            />

            <ProjectApprovalDialog
                isOpen={isApprovalDialogOpen}
                projectTitle={selectedProject?.name ?? ''}
                projectId={selectedProject?._id ?? ''}
                onClose={() => setIsApprovalDialogOpen(false)}
                onSubmit={(approvedProject) => {
                    // replace an existing project with a new one
                    projectTransformTimeIntoDates(approvedProject);
                    let updatedProjects = [];
                    for (let p of projectData) {
                        if (p._id !== approvedProject._id) {
                            updatedProjects.push(p);
                            continue;
                        }
                        updatedProjects.push(approvedProject);
                    }
                    setProjectData(updatedProjects);
                    setIsApprovalDialogOpen(false);
                }}
            />
        </>
    )
}

// dialog for adding new projects
const AddProjectDialog: React.FC<{ isOpen: boolean, onClose: () => void, onSubmit: (projectInfo: ProjectInfo) => void }> = ({ isOpen, onClose, onSubmit }) => {
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

    return (
        <Dialog isOpen={isOpen} onClose={onClose} title="Create a New Project" autoFocus={true}>
            <DialogBody useOverflowScrollContainer>
                <FormGroup label="Select a Project Template:">
                    <HTMLSelect
                        value={selectedTemplate}
                        options={projectTemplates}
                        onChange={(e) => setSelectedTemplate(e.currentTarget.value)}
                        fill={true} iconName="caret-down" />
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
                    <Button onClick={(e) => submit()} intent="primary" loading={isSubmitting}>Create</Button>
                </>
            } />
        </Dialog>
    )
}