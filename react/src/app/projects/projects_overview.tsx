import { Button, ButtonGroup, NonIdealState } from "@blueprintjs/core";
import Link from "next/link";
import React, { useEffect, useMemo, useState } from "react";
import { Container } from "react-bootstrap";
import { formatToLiccoDateTime, toUnixSeconds } from "../utils/date_utils";
import { JsonErrorMsg } from "../utils/fetching";
import { ProjectInfo, fetchAllProjects, isProjectSubmitted, projectTransformTimeIntoDates } from "./project_model";
import { AddProjectDialog, CloneProjectDialog, EditProjectDialog, ProjectApprovalDialog } from "./projects_overview_dialogs";

function sortByCreationDateDesc(a: ProjectInfo, b: ProjectInfo) {
    return toUnixSeconds(b.creation_time) - toUnixSeconds(a.creation_time);
}

function sortByLastEditTimeDesc(a: ProjectInfo, b: ProjectInfo) {
    let timeA = a.edit_time ? toUnixSeconds(a.edit_time) : 0;
    let timeB = b.edit_time ? toUnixSeconds(b.edit_time) : 0;

    let diff = timeB - timeA;
    if (diff == 0) { // same edit time
        return sortByCreationDateDesc(a, b)
    }
    return diff;
}


export const ProjectsOverview: React.FC = ({ }) => {
    const [projectData, setProjectData] = useState<ProjectInfo[]>([]);
    const [projectDataLoading, setProjectDataLoading] = useState(true);
    const [err, setError] = useState("");

    const [isAddProjectDialogOpen, setIsAddProjectDialogOpen] = useState(false);
    const [isApprovalDialogOpen, setIsApprovalDialogOpen] = useState(false);
    const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
    const [isCloneDialogOpen, setIsCloneDialogOpen] = useState(false);
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

    const projectDataDisplayed = useMemo(() => {
        let displayedData = [...projectData];
        displayedData.sort((a, b) => {
            // TODO: apply any other filters 
            return sortByCreationDateDesc(a, b);
        });
        return displayedData;
    }, [projectData]);

    if (err) {
        return (
            <Container className="mt-4">
                <NonIdealState icon="error" title="Error" description={err} />
            </Container>
        )
    }

    const showAddProjectDialog = () => {
        setIsAddProjectDialogOpen(true);
    }

    return (
        <>
            <div>
                <table className="table table-striped table-bordered table-sm table-sticky">
                    <thead>
                        <tr>
                            <th scope="col">
                                <Button icon="add" title="Add new Project" onClick={(e) => showAddProjectDialog()} minimal={true} small={true} />
                                <Button icon="history" title="Show the history of project approvals" minimal={true} small={true} />
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
                        {projectDataDisplayed.map((project) => {
                            return (
                                <tr key={project._id}>
                                    <td>
                                        <ButtonGroup minimal={true}>
                                            <Button icon="comparison" title="Compare (diff) with another project" minimal={true} small={true} />
                                            <Button icon="duplicate" title="Clone this project" minimal={true} small={true}
                                                onClick={(e) => {
                                                    setSelectedProject(project);
                                                    setIsCloneDialogOpen(true);
                                                }}
                                            />

                                            {!isProjectSubmitted(project) ?
                                                <>
                                                    <Button icon="edit" title="Edit this project" minimal={true} small={true}
                                                        onClick={(e) => {
                                                            setSelectedProject(project);
                                                            setIsEditDialogOpen(true);
                                                        }}
                                                    />

                                                    <Button icon="user" title="Submit this project for approval"
                                                        minimal={true} small={true}
                                                        onClick={(e) => {
                                                            setSelectedProject(project);
                                                            setIsApprovalDialogOpen(true);
                                                        }}
                                                    />

                                                    <Button icon="export" title="Upload data to this project" minimal={true} small={true} />
                                                </>
                                                : null
                                            }

                                            <Button icon="import" title="Download this project" minimal={true} small={true} />

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

            {!projectDataLoading && projectData.length == 0 ?
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

            {selectedProject && isApprovalDialogOpen ?
                <ProjectApprovalDialog
                    isOpen={isApprovalDialogOpen}
                    projectTitle={selectedProject.name}
                    projectId={selectedProject._id}
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
                : null
            }

            {selectedProject && isCloneDialogOpen ?
                <CloneProjectDialog
                    isOpen={isCloneDialogOpen}
                    project={selectedProject}
                    onClose={() => {
                        setIsCloneDialogOpen(false);
                    }}
                    onSubmit={(clonedProject) => {
                        let data = [...projectData];
                        data.push(clonedProject);
                        setProjectData(data);
                        setIsCloneDialogOpen(false);
                    }}
                />
                : null
            }

            {selectedProject && isEditDialogOpen ?
                <EditProjectDialog
                    isOpen={isEditDialogOpen}
                    project={selectedProject}
                    onClose={() => {
                        setIsEditDialogOpen(false);
                    }}
                    onSubmit={(updatedProject) => {
                        let updatedData = [];
                        for (let p of projectData) {
                            if (p._id != updatedProject._id) {
                                updatedData.push(p);
                                continue;
                            }

                            updatedData.push(updatedProject);
                        }
                        // update project info 
                        setIsEditDialogOpen(false);
                        setProjectData(updatedData);
                    }}
                />
                : null
            }

        </>
    )
}
