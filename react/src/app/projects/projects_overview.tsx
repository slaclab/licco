import { Button, ButtonGroup, Icon, NonIdealState } from "@blueprintjs/core";
import Link from "next/link";
import React, { useEffect, useMemo, useState } from "react";
import { Container } from "react-bootstrap";
import { formatToLiccoDateTime, toUnixSeconds } from "../utils/date_utils";
import { JsonErrorMsg } from "../utils/fetching";
import { ProjectInfo, fetchAllProjects, isProjectSubmitted, projectTransformTimeIntoDates } from "./project_model";
import { AddProjectDialog, CloneProjectDialog, EditProjectDialog, ProjectApprovalDialog } from "./projects_overview_dialogs";


function sortString(a: string, b: string, desc: boolean = true) {
    let diff = a.localeCompare(b);
    return desc ? -diff : diff;
}

function sortByCreationDate(a: ProjectInfo, b: ProjectInfo, desc: boolean = true) {
    let diff = toUnixSeconds(b.creation_time) - toUnixSeconds(a.creation_time);
    return desc ? diff : -diff;
}

function sortByLastEditTime(a: ProjectInfo, b: ProjectInfo, desc: boolean = true) {
    let timeA = a.edit_time ? toUnixSeconds(a.edit_time) : 0;
    let timeB = b.edit_time ? toUnixSeconds(b.edit_time) : 0;

    let diff = timeB - timeA;
    return desc ? diff : -diff;
}

export const ProjectsOverview: React.FC = ({ }) => {
    const [projectData, setProjectData] = useState<ProjectInfo[]>([]);
    const [projectDataLoading, setProjectDataLoading] = useState(true);
    const [err, setError] = useState("");

    // dialogs
    const [isAddProjectDialogOpen, setIsAddProjectDialogOpen] = useState(false);
    const [isApprovalDialogOpen, setIsApprovalDialogOpen] = useState(false);
    const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
    const [isCloneDialogOpen, setIsCloneDialogOpen] = useState(false);
    const [selectedProject, setSelectedProject] = useState<ProjectInfo>();

    // sorting
    type sortColumnField = 'name' | 'created' | 'edit' | 'owner'
    const [sortedField, setSortedField] = useState<sortColumnField>('created');
    const [sortInDescOrder, setSortInDescOrder] = useState<boolean>(true);

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


    const showAddProjectDialog = () => {
        setIsAddProjectDialogOpen(true);
    }

    const sortOrderChanged = (field: sortColumnField) => {
        let desc = true; // by default we always order in desc order first
        if (field == sortedField) {
            // same field was clicked, change sort order based on the previous state
            desc = !sortInDescOrder;
        }
        setSortedField(field);
        setSortInDescOrder(desc);
    }

    const renderSortButtonIfAny = (field: sortColumnField) => {
        if (field != sortedField) {
            // if we don't show the icon (null node) the column would change width 
            // when we display the icon for the first time. To avoid this jump 
            // we instead render a blank icon. 
            return <Icon className="ms-1" icon="blank" />
        }

        return <Icon className="ms-1" icon={sortInDescOrder ? "arrow-down" : "arrow-up"} />
    }

    const projectDataDisplayed = useMemo(() => {
        let displayedData = [...projectData];

        // sort data according to selected filter
        switch (sortedField) {
            case 'created':
                displayedData.sort((a, b) => sortByCreationDate(a, b, sortInDescOrder));
                break;
            case 'edit':
                displayedData.sort((a, b) => sortByLastEditTime(a, b, sortInDescOrder));
                break;
            case 'name':
                displayedData.sort((a, b) => sortString(a.name, b.name, sortInDescOrder));
                break;
            case 'owner':
                displayedData.sort((a, b) => sortString(a.owner, b.owner, sortInDescOrder));
                break;
            default:
                displayedData.sort((a, b) => sortByCreationDate(a, b, sortInDescOrder));
        }
        return displayedData;
    }, [projectData, sortedField, sortInDescOrder]);


    if (err) {
        return (
            <Container className="mt-4">
                <NonIdealState icon="error" title="Error" description={err} />
            </Container>
        )
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
                            <th onClick={(e) => sortOrderChanged('name')}>Name {renderSortButtonIfAny('name')}</th>
                            <th onClick={(e) => sortOrderChanged('owner')}>Owner {renderSortButtonIfAny('owner')}</th>
                            <th onClick={(e) => sortOrderChanged('created')}>Created {renderSortButtonIfAny('created')}</th>
                            <th onClick={(e) => sortOrderChanged('edit')}>Last Edit {renderSortButtonIfAny('edit')}</th>
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
                    projectOwner={selectedProject.owner}
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
