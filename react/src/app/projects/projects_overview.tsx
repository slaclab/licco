import { createLink } from "@/app/utils/path_utils";
import { AnchorButton, Button, ButtonGroup, Collapse, Icon, NonIdealState } from "@blueprintjs/core";
import Link from "next/link";
import React, { useEffect, useMemo, useState } from "react";
import { Container } from "react-bootstrap";
import { MultiLineText } from "../components/multiline_text";
import { formatToLiccoDateTime } from "../utils/date_utils";
import { JsonErrorMsg } from "../utils/fetching";
import { SortState, sortDate, sortString } from "../utils/sort_utils";
import { ProjectInfo, fetchAllProjectsInfo, isProjectApproved, isProjectSubmitted, isUserAProjectApprover, isUserAProjectEditor, transformProjectForFrontendUse, whoAmI } from "./project_model";
import { AddProjectDialog, CloneProjectDialog, EditProjectDialog, HistoryOfProjectApprovalsDialog, ProjectComparisonDialog, ProjectExportDialog, ProjectImportDialog } from "./projects_overview_dialogs";

import styles from './projects_overview.module.css';

export const ProjectsOverview: React.FC = ({ }) => {
    const [projectData, setProjectData] = useState<ProjectInfo[]>([]);
    const [projectDataLoading, setProjectDataLoading] = useState(true);
    const [err, setError] = useState("");
    const [currentlyLoggedInUser, setCurrentlyLoggedInUser] = useState<string>('');

    // dialogs
    const [isAddProjectDialogOpen, setIsAddProjectDialogOpen] = useState(false);
    const [isProjectHistoryDialogOpen, setIsProjectHistoryDialogOpen] = useState(false);
    const [isComparisonDialogOpen, setIsComparisonDialogOpen] = useState(false);
    const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
    const [isCloneDialogOpen, setIsCloneDialogOpen] = useState(false);
    const [isImportDialogOpen, setIsImportDialogOpen] = useState(false);
    const [isExportDialogOpen, setIsExportDialogOpen] = useState(false);
    const [selectedProject, setSelectedProject] = useState<ProjectInfo>();

    // sorting
    type sortColumnField = 'name' | 'created' | 'edit' | 'owner';
    const [sortByColumn, setSortByColumn] = useState<SortState<sortColumnField>>(new SortState('created'));

    const fetchProjectData = async () => {
        const [projects, whoami] = await Promise.all([
            fetchAllProjectsInfo(),
            whoAmI(),
        ]);
        return { projects, whoami };
    }

    useEffect(() => {
        setProjectDataLoading(true);
        fetchProjectData()
            .then(d => {
                setProjectData(d.projects);
                setCurrentlyLoggedInUser(d.whoami);
            }).catch((e: JsonErrorMsg) => {
                let msg = "Failed to load projects data: " + e.error;
                setError(msg);
                console.error(msg, e);
            }).finally(() => {
                setProjectDataLoading(false);
            });
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
        let approvedProjects: ProjectInfo[] = [];
        let projectsToApprove: ProjectInfo[] = [];
        let displayedData: ProjectInfo[] = [];

        for (let p of projectData) {
            if (isProjectApproved(p)) {
                approvedProjects.push(p);
                continue;
            }

            if (isUserAProjectApprover(p, currentlyLoggedInUser) || (p.status == "submitted" && isUserAProjectEditor(p, currentlyLoggedInUser))) {
                projectsToApprove.push(p);
                continue;
            }

            displayedData.push(p);
        }

        // sort data according to selected filter
        switch (sortByColumn.column) {
            case 'created':
                approvedProjects.sort((a, b) => sortDate(a.creation_time, b.creation_time, sortByColumn.sortDesc));
                projectsToApprove.sort((a, b) => sortDate(a.creation_time, b.creation_time, sortByColumn.sortDesc));
                displayedData.sort((a, b) => sortDate(a.creation_time, b.creation_time, sortByColumn.sortDesc));
                break;
            case 'edit':
                approvedProjects.sort((a, b) => sortDate(a.edit_time, b.edit_time, sortByColumn.sortDesc));
                projectsToApprove.sort((a, b) => sortDate(a.edit_time, b.edit_time, sortByColumn.sortDesc));
                displayedData.sort((a, b) => sortDate(a.edit_time, b.edit_time, sortByColumn.sortDesc));
                break;
            case 'name':
                approvedProjects.sort((a, b) => sortString(a.name, b.name, sortByColumn.sortDesc));
                projectsToApprove.sort((a, b) => sortString(a.name, b.name, sortByColumn.sortDesc));
                displayedData.sort((a, b) => sortString(a.name, b.name, sortByColumn.sortDesc));
                break;
            case 'owner':
                approvedProjects.sort((a, b) => sortString(a.owner, b.owner, sortByColumn.sortDesc));
                projectsToApprove.sort((a, b) => sortString(a.owner, b.owner, sortByColumn.sortDesc));
                displayedData.sort((a, b) => sortString(a.owner, b.owner, sortByColumn.sortDesc));
                break;
            default:
                approvedProjects.sort((a, b) => sortDate(a.creation_time, b.creation_time, sortByColumn.sortDesc));
                projectsToApprove.sort((a, b) => sortDate(a.creation_time, b.creation_time, sortByColumn.sortDesc));
                displayedData.sort((a, b) => sortDate(a.creation_time, b.creation_time, sortByColumn.sortDesc));
        }

        let projects: ProjectInfo[] = [...approvedProjects, ...projectsToApprove, ...displayedData];
        return projects;
    }, [projectData, currentlyLoggedInUser, sortByColumn]);


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
                            <th>Editors</th>
                            <th onClick={(e) => sortOrderChanged('created')}>Created {renderTableSortButtonIfAny('created')}</th>
                            <th onClick={(e) => sortOrderChanged('edit')}>Last Edit {renderTableSortButtonIfAny('edit')}</th>
                            <th>Description</th>
                            <th>Notes</th>
                        </tr>
                    </thead>
                    <tbody>
                        {projectDataDisplayed.map((project) => {
                            const allowProjectEdits = isUserAProjectEditor(project, currentlyLoggedInUser);
                            return (
                                <tr key={project._id} className={isProjectApproved(project) ? 'approved-table-row' : ''}>
                                    <td>
                                        <ButtonGroup minimal={true}>
                                            {isUserAProjectApprover(project, currentlyLoggedInUser) || (isUserAProjectEditor(project, currentlyLoggedInUser) && project.status === "submitted") ?
                                                <AnchorButton icon="confirm" title="Approve submitted project" intent={"danger"} style={{ zIndex: 1 }} minimal={true} small={true}
                                                    href={createLink(`/projects/${project._id}/approval`)}
                                                />
                                                : null
                                            }
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
                                                        disabled={!allowProjectEdits}
                                                        onClick={(e) => {
                                                            setSelectedProject(project);
                                                            setIsEditDialogOpen(true);
                                                        }}
                                                    />

                                                    <AnchorButton icon="user" title="Submit this project for approval"
                                                        disabled={!allowProjectEdits}
                                                        href={createLink(`/projects/${project._id}/submit-for-approval`)}
                                                        minimal={true} small={true}
                                                    />

                                                    <Button icon="export" title="Upload data to this project"
                                                        minimal={true} small={true}
                                                        disabled={!allowProjectEdits}
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
                                    <td>{project.editors.join(", ")}</td>
                                    <td>{formatToLiccoDateTime(project.creation_time)}</td>
                                    <td>{formatToLiccoDateTime(project.edit_time)}</td>
                                    <td>{project.description}</td>
                                    <td><CollapsibleProjectNotes notes={project.notes} /></td>
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
                user={currentlyLoggedInUser}
                isOpen={isAddProjectDialogOpen}
                onClose={() => setIsAddProjectDialogOpen(false)}
                onSubmit={(newProject) => {
                    transformProjectForFrontendUse(newProject);
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
                    user={currentlyLoggedInUser}
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


export const CollapsibleProjectNotes: React.FC<{ notes: string[], defaultNoNoteMsg?: React.ReactNode, defaultOpen?: boolean }> = ({ notes, defaultNoNoteMsg = <>/</>, defaultOpen = false }) => {
    const [showingNotes, setShowingNotes] = useState(defaultOpen);

    if (notes.length == 0) {
        return <>{defaultNoNoteMsg}</>
    }

    return (
        <>
            <Button small={true} onClick={e => setShowingNotes((c) => !c)}>{showingNotes ? "Hide Notes" : "Show Notes"} ({notes.length})</Button>
            <Collapse isOpen={showingNotes} keepChildrenMounted={true}>
                {notes.map((note, i) => {
                    return (
                        <div key={i} className={styles.userNote}>
                            <MultiLineText text={note} />
                        </div>
                    )
                })}
            </Collapse>
        </>
    )
}