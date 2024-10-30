import { Button, ButtonGroup, Icon, NonIdealState } from "@blueprintjs/core";
import Link from "next/link";
import React, { useEffect, useMemo, useState } from "react";
import { Container } from "react-bootstrap";
import { formatToLiccoDateTime } from "../utils/date_utils";
import { JsonErrorMsg } from "../utils/fetching";
import { SortState, sortDate, sortString } from "../utils/sort_utils";
import { ProjectInfo, fetchAllProjectsInfo, isProjectApproved, isProjectSubmitted, projectTransformTimeIntoDates } from "./project_model";
import { AddProjectDialog, CloneProjectDialog, EditProjectDialog, HistoryOfProjectApprovalsDialog, ProjectApprovalDialog, ProjectComparisonDialog, ProjectExportDialog, ProjectImportDialog } from "./projects_overview_dialogs";


export const ProjectsOverview: React.FC = ({ }) => {
    const [projectData, setProjectData] = useState<ProjectInfo[]>([]);
    const [projectDataLoading, setProjectDataLoading] = useState(true);
    const [err, setError] = useState("");

    // dialogs
    const [isAddProjectDialogOpen, setIsAddProjectDialogOpen] = useState(false);
    const [isProjectHistoryDialogOpen, setIsProjectHistoryDialogOpen] = useState(false);
    const [isComparisonDialogOpen, setIsComparisonDialogOpen] = useState(false);
    const [isApprovalDialogOpen, setIsApprovalDialogOpen] = useState(false);
    const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
    const [isCloneDialogOpen, setIsCloneDialogOpen] = useState(false);
    const [isImportDialogOpen, setIsImportDialogOpen] = useState(false);
    const [isExportDialogOpen, setIsExportDialogOpen] = useState(false);
    const [selectedProject, setSelectedProject] = useState<ProjectInfo>();

    // sorting
    type sortColumnField = 'name' | 'created' | 'edit' | 'owner';
    const [sortByColumn, setSortByColumn] = useState<SortState<sortColumnField>>(new SortState('created'));

    const fetchProjectData = () => {
        setProjectDataLoading(true);
        fetchAllProjectsInfo()
            .then((projects) => {
                setProjectData(projects);
            }).catch((e: JsonErrorMsg) => {
                let msg = "Failed to load projects data: " + e.error;
                setError(msg);
                console.error(msg, e);
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
        let newSortOrder = sortByColumn.changed(field)
        setSortByColumn(newSortOrder);
    }

    const renderTableSortButtonIfAny = (field: sortColumnField) => {
        if (field != sortByColumn.column) {
            // if we don't show the icon (null node) the column would change width 
            // when we display the icon for the first time. To avoid this jump 
            // we instead render a blank icon. 
            return <Icon className="ms-1" icon="blank" />
        }

        return <Icon className="ms-1" icon={sortByColumn.sortDesc ? "arrow-down" : "arrow-up"} />
    }

    const projectDataDisplayed = useMemo(() => {
        // approved projects should always be pinned to the top of the table 
        let approvedProjects = projectData.filter(p => isProjectApproved(p));
        let displayedData = projectData.filter(p => !isProjectApproved(p));

        // sort data according to selected filter
        switch (sortByColumn.column) {
            case 'created':
                approvedProjects.sort((a, b) => sortDate(a.creation_time, b.creation_time, sortByColumn.sortDesc));
                displayedData.sort((a, b) => sortDate(a.creation_time, b.creation_time, sortByColumn.sortDesc));
                break;
            case 'edit':
                approvedProjects.sort((a, b) => sortDate(a.edit_time, b.edit_time, sortByColumn.sortDesc));
                displayedData.sort((a, b) => sortDate(a.edit_time, b.edit_time, sortByColumn.sortDesc));
                break;
            case 'name':
                approvedProjects.sort((a, b) => sortString(a.name, b.name, sortByColumn.sortDesc));
                displayedData.sort((a, b) => sortString(a.name, b.name, sortByColumn.sortDesc));
                break;
            case 'owner':
                approvedProjects.sort((a, b) => sortString(a.owner, b.owner, sortByColumn.sortDesc));
                displayedData.sort((a, b) => sortString(a.owner, b.owner, sortByColumn.sortDesc));
                break;
            default:
                approvedProjects.sort((a, b) => sortDate(a.creation_time, b.creation_time, sortByColumn.sortDesc));
                displayedData.sort((a, b) => sortDate(a.creation_time, b.creation_time, sortByColumn.sortDesc));
        }

        let projects: ProjectInfo[] = [...approvedProjects, ...displayedData];
        return projects;
    }, [projectData, sortByColumn]);


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
                                <Button icon="history" title="Show the history of project approvals" onClick={(e) => setIsProjectHistoryDialogOpen(true)} minimal={true} small={true} />
                                {projectDataLoading ?
                                    <Button minimal={true} small={true} disabled={true} loading={projectDataLoading} />
                                    : null
                                }
                            </th>
                            <th onClick={(e) => sortOrderChanged('name')}>Name {renderTableSortButtonIfAny('name')}</th>
                            <th onClick={(e) => sortOrderChanged('owner')}>Owner {renderTableSortButtonIfAny('owner')}</th>
                            <th onClick={(e) => sortOrderChanged('created')}>Created {renderTableSortButtonIfAny('created')}</th>
                            <th onClick={(e) => sortOrderChanged('edit')}>Last Edit {renderTableSortButtonIfAny('edit')}</th>
                            <th>Description</th>
                            <th>Notes</th>
                        </tr>
                    </thead>
                    <tbody>
                        {projectDataDisplayed.map((project) => {
                            return (
                                <tr key={project._id} className={isProjectApproved(project) ? 'approved-table-row' : ''}>
                                    <td>
                                        <ButtonGroup minimal={true}>
                                            <Button icon="comparison" title="Compare (diff) with another project" minimal={true} small={true}
                                                onClick={e => {
                                                    setSelectedProject(project);
                                                    setIsComparisonDialogOpen(true);
                                                }}
                                            />
                                            <Button icon="duplicate" title="Clone this project" minimal={true} small={true}
                                                onClick={(e) => {
                                                    setSelectedProject(project);
                                                    setIsCloneDialogOpen(true);
                                                }}
                                            />

                                            {!isProjectSubmitted(project) && !isProjectApproved(project) ?
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
                                                    <Button icon="export" title="Upload data to this project"
                                                        minimal={true} small={true}
                                                        onClick={(e) => {
                                                            setSelectedProject(project);
                                                            setIsImportDialogOpen(true);
                                                        }}
                                                    />
                                                </>
                                                : null
                                            }

                                            <Button icon="import" title="Download a copy of this project"
                                                minimal={true} small={true}
                                                onClick={(e) => {
                                                    setSelectedProject(project);
                                                    setIsExportDialogOpen(true);
                                                }}
                                            />
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
                approvedProjects={projectDataDisplayed.filter(p => isProjectApproved(p))}
                isOpen={isAddProjectDialogOpen}
                onClose={() => setIsAddProjectDialogOpen(false)}
                onSubmit={(newProject) => {
                    projectTransformTimeIntoDates(newProject);
                    let newData = [...projectData, newProject];
                    setProjectData(newData);
                    setIsAddProjectDialogOpen(false)
                }}
            />

            <HistoryOfProjectApprovalsDialog
                isOpen={isProjectHistoryDialogOpen}
                onClose={() => setIsProjectHistoryDialogOpen(false)}
            />

            {selectedProject && isComparisonDialogOpen ?
                <ProjectComparisonDialog
                    isOpen={isComparisonDialogOpen}
                    project={selectedProject}
                    availableProjects={projectData}
                    onClose={() => setIsComparisonDialogOpen(false)}
                />
                : null
            }

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

            {selectedProject && isExportDialogOpen ?
                <ProjectExportDialog
                    isOpen={isExportDialogOpen}
                    project={selectedProject}
                    onClose={() => {
                        setIsExportDialogOpen(false);
                    }}
                    onSubmit={() => {
                        setIsExportDialogOpen(false);
                    }
                    }
                />
                : null
            }
            {selectedProject && isImportDialogOpen ?
                <ProjectImportDialog
                    isOpen={isImportDialogOpen}
                    project={selectedProject}
                    onClose={() => {
                        setIsImportDialogOpen(false);
                    }}
                />
                : null
            }
        </>
    )
}
