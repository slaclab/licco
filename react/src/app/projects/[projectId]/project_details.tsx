import { HtmlPage } from "@/app/components/html_page";
import { Fetch, JsonErrorMsg } from "@/app/utils/fetching";
import { createGlobMatchRegex } from "@/app/utils/glob_matcher";
import { Button, ButtonGroup, Colors, Dialog, DialogBody, DialogFooter, Divider, FormGroup, HTMLSelect, Icon, InputGroup, Label, Tooltip } from "@blueprintjs/core";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ProjectApprovalDialog } from "../project_approval_dialog";
import { FFT, ProjectDeviceDetails, ProjectInfo, fetchAllProjects, fetchProjectDiff, isProjectSubmitted } from "../project_model";

// a project specific page displays all properties of a specific project 
export const ProjectSpecificPage: React.FC<{ projectId: string }> = ({ projectId }) => {
    const queryParams = useSearchParams();
    const [isLoading, setIsLoading] = useState(false);

    const [projectData, setProjectData] = useState<ProjectInfo>();
    const [fftData, setFftData] = useState<ProjectDeviceDetails[]>([]);
    const [fftDataDisplay, setFftDataDisplay] = useState<ProjectDeviceDetails[]>([]);

    // dialogs open state
    const [isFilterDialogOpen, setIsFilterDialogOpen] = useState(false);
    const [isApprovalDialogOpen, setIsApprovalDialogOpen] = useState(false);
    const [isCopyFFTDialogOpen, setIsCopyFFTDialogOpen] = useState(false);
    const [currentFFT, setCurrentFFT] = useState<FFT>({ _id: "", fc: "", fg: "" });

    // filters to apply
    const [fftStates, setFftStates] = useState<string[]>([]);
    const [fcFilter, setFcFilter] = useState("");
    const [fgFilter, setFgFilter] = useState("");
    const [stateFilter, setStateFilter] = useState("");

    // load project data
    useEffect(() => {
        console.log(queryParams);
        setIsLoading(true);

        Fetch.get<ProjectInfo>(`/ws/projects/${projectId}/`)
            .then(data => {
                setProjectData(data);
            }).catch((e) => {
                console.error("Failed to make a project request");
            });

        Fetch.get<Record<string, ProjectDeviceDetails>>(`/ws/projects/${projectId}/ffts/?showallentries=true`)
            .then((data) => {
                let devices = Object.values(data);
                // TODO: missing device number field is set to "" (empty string):
                // we should turn it into an null to avoid having problems when formatting it later
                setFftData(devices);
            }).catch((e) => {
                console.error(e);
                console.error("Error while fetching data: ", e);
            }).finally(() => {
                setIsLoading(false);
            });
    }, []);

    // get unique fft states for filter dialog
    useEffect(() => {
        let uniqueStates = Array.from(new Set(fftData.map((e) => e.state).filter(state => state)));
        setFftStates(["---- Any ----", ...uniqueStates]);
    }, [fftData])

    // apply table filters, when any filter or original data changes
    useEffect(() => {
        let fcGlobMatcher = createGlobMatchRegex(fcFilter)
        let fgGlobMatcher = createGlobMatchRegex(fgFilter);
        let filteredFftData = fftData.filter(d => {
            if (fcFilter) {
                return fcGlobMatcher.test(d.fft.fc);
            }
            return true;
        }).filter(d => {
            if (fgFilter) {
                return fgGlobMatcher.test(d.fft.fg);
            }
            return true;
        }).filter(d => {
            if (stateFilter) {
                return d.state === stateFilter;
            }
            return true;
        })
        setFftDataDisplay(filteredFftData);
    }, [fftData, fcFilter, fgFilter, stateFilter]);

    const formatDevicePositionNumber = (value?: number | string): string => {
        if (value === undefined) {
            return '';
        }
        if (typeof value === "string") {
            return value;
        }
        return value.toFixed(7);
    }

    const displayFilterIconInColumn = (filterValue: string) => {
        if (!filterValue) {
            return null
        }
        return <Icon icon="filter" color={Colors.RED2} className="ms-1" />
    }


    const isProjectSubmitted = projectData?.status === "submitted";
    const isFilterApplied = fcFilter != "" || fgFilter != "" || stateFilter != "";

    return (
        <HtmlPage>
            <table className="table table-bordered table-sm table-sticky table-striped table-sticky">
                <thead>
                    <tr>
                        <th colSpan={6}>
                            {!projectData ? <></> :
                                <ButtonGroup vertical={false}>

                                    <span className="me-3">{projectData?.name}</span>

                                    <Tooltip content="Download data to this project" position="bottom">
                                        <Button icon="import" minimal={true} small={true}></Button>
                                    </Tooltip>

                                    <Tooltip content="Upload data to this project" position="bottom">
                                        <Button icon="export" minimal={true} small={true}></Button>
                                    </Tooltip>

                                    <Divider />

                                    <Tooltip content="Filter FFTs" position="bottom">
                                        <Button icon="filter" minimal={true} small={true} intent={isFilterApplied ? "warning" : "none"} onClick={(e) => setIsFilterDialogOpen(true)}></Button>
                                    </Tooltip>

                                    <Tooltip content={"Clear filters to show all FFTs"} position="bottom" disabled={!isFilterApplied}>
                                        <Button icon="filter-remove" minimal={true} small={true} disabled={!isFilterApplied}
                                            onClick={(e) => {
                                                setFcFilter('')
                                                setFgFilter('');
                                                setStateFilter('');
                                            }}
                                        />
                                    </Tooltip>

                                    <Tooltip content="Show only FCs with changes after the project was created" position="bottom">
                                        <Button icon="filter-open" minimal={true} small={true}></Button>
                                    </Tooltip>

                                    <Divider />

                                    <Tooltip content="Create a tag" position="bottom">
                                        <Button icon="tag-add" minimal={true} small={true}></Button>
                                    </Tooltip>

                                    <Tooltip content="Show assigned tags" position="bottom">
                                        <Button icon="tags" minimal={true} small={true}></Button>
                                    </Tooltip>

                                    <Divider />

                                    <Tooltip content="Show the history of changes" position="bottom">
                                        <Button icon="history" minimal={true} small={true}></Button>
                                    </Tooltip>

                                    <Tooltip content={"Submit this project for approval"} position="bottom" disabled={isProjectSubmitted}>
                                        <Button icon="user" minimal={true} small={true}
                                            disabled={isProjectSubmitted}
                                            onClick={(e) => setIsApprovalDialogOpen(true)}
                                        />
                                    </Tooltip>
                                </ButtonGroup>
                            }
                        </th>

                        <th colSpan={3}>Nominal Location (meters in LCLS coordinates)</th>
                        <th colSpan={3}>Nominal Dimension (meters)</th>
                        <th colSpan={3}>Nominal Angle (radians)</th>
                        <th></th>
                    </tr>
                    <tr>
                        <th></th>
                        <th>FC  {displayFilterIconInColumn(fcFilter)}</th>
                        <th>Fungible {displayFilterIconInColumn(fgFilter)}</th>
                        <th>TC Part No.</th>
                        <th>State {displayFilterIconInColumn(stateFilter)}</th>
                        <th>Comments</th>

                        <th className="text-number">Z</th>
                        <th className="text-number">X</th>
                        <th className="text-number">Y</th>

                        <th className="text-number">Z</th>
                        <th className="text-number">X</th>
                        <th className="text-number">Y</th>

                        <th className="text-number">Z</th>
                        <th className="text-number">X</th>
                        <th className="text-number">Y</th>
                        <th>Must Ray Trace</th>
                    </tr>
                </thead>
                <tbody>
                    {fftDataDisplay.map(device => {
                        return (
                            <tr key={device.fft._id}>
                                <td className="text-nowrap">
                                    <Tooltip content={"Edit this FFT"} position="bottom">
                                        <Button minimal={true} small={true} icon={"edit"} />
                                    </Tooltip>
                                    <Tooltip content={"Copy over the value from the currently approved project"} position="bottom">
                                        <Button minimal={true} small={true} icon={"refresh"}
                                            onClick={(e) => {
                                                setCurrentFFT(device.fft);
                                                setIsCopyFFTDialogOpen(true);
                                            }
                                            }
                                        />
                                    </Tooltip>
                                </td>
                                <td>{device.fft.fc}</td>
                                <td>{device.fft.fg}</td>
                                <td>{device.tc_part_no}</td>
                                <td>{device.state}</td>
                                <td>{device.comments}</td>

                                <td className="text-number">{formatDevicePositionNumber(device.nom_loc_z)}</td>
                                <td className="text-number">{formatDevicePositionNumber(device.nom_loc_x)}</td>
                                <td className="text-number">{formatDevicePositionNumber(device.nom_loc_y)}</td>

                                <td className="text-number">{formatDevicePositionNumber(device.nom_dim_z)}</td>
                                <td className="text-number">{formatDevicePositionNumber(device.nom_dim_x)}</td>
                                <td className="text-number">{formatDevicePositionNumber(device.nom_dim_y)}</td>

                                <td className="text-number">{formatDevicePositionNumber(device.nom_ang_z)}</td>
                                <td className="text-number">{formatDevicePositionNumber(device.nom_ang_x)}</td>
                                <td className="text-number">{formatDevicePositionNumber(device.nom_ang_y)}</td>

                                <td>{device.ray_trace ?? null}</td>
                            </tr>
                        )
                    })
                    }
                </tbody>
            </table>

            <FilterFFTDialog
                isOpen={isFilterDialogOpen}
                possibleStates={fftStates}
                onClose={() => setIsFilterDialogOpen(false)}
                onSubmit={(newFcFilter, newFgFilter, newStateFilter) => {
                    setFcFilter(newFcFilter);
                    setFgFilter(newFgFilter);
                    newStateFilter = newStateFilter.startsWith("---") ? "" : newStateFilter;
                    setStateFilter(newStateFilter);
                    setIsFilterDialogOpen(false);
                }}
            />

            <ProjectApprovalDialog
                isOpen={isApprovalDialogOpen}
                projectTitle={projectData?.name || ''}
                projectId={projectData?._id || ''}
                onClose={() => setIsApprovalDialogOpen(false)}
                onSubmit={(projectInfo) => {
                    setProjectData(projectInfo);
                    setIsApprovalDialogOpen(false);
                }}
            />

            {/* <CopyFFTToProject
                isOpen={isCopyFFTDialogOpen && projectData !== undefined}
                FFT={currentFFT}
                currentProject={projectData!}
                // currentProjectName={projectData?.name || ''}
                onClose={() => setIsCopyFFTDialogOpen(false)}
                onSubmit={() => { }}
            /> */}
        </HtmlPage >
    )
}


// this dialog is used for filtering the table (fc, fg, and based on state)
const FilterFFTDialog: React.FC<{ isOpen: boolean, possibleStates: string[], onClose: () => void, onSubmit: (newFcFilter: string, newFgFilter: string, newStateFilter: string) => void }> = ({ isOpen, possibleStates, onClose, onSubmit }) => {
    const [fcFilter, setFcFilter] = useState('');
    const [fgFilter, setFgFilter] = useState('');
    const [stateFilter, setStateFilter] = useState('');

    const submitSearchForm = () => {
        onSubmit(fcFilter, fgFilter, stateFilter);
    }

    const submitOnEnter = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === "Enter") {
            submitSearchForm();
        }
    }

    return (
        <Dialog isOpen={isOpen} onClose={onClose} title="Apply Filter to Table" autoFocus={true}>
            <DialogBody useOverflowScrollContainer>
                <FormGroup label="FC:" labelFor="fc-filter">
                    <InputGroup id="fc-filter"
                        placeholder="Use GLOB pattern to filter on FC name"
                        value={fcFilter}
                        onKeyUp={submitOnEnter}
                        onValueChange={(val: string) => setFcFilter(val)} />
                </FormGroup>

                <FormGroup label="FG:" labelFor="fg-filter">
                    <InputGroup id="fg-filter"
                        placeholder="Use GLOB pattern to filter on FG name"
                        value={fgFilter}
                        onKeyUp={submitOnEnter}
                        onValueChange={(val: string) => setFgFilter(val)} />
                </FormGroup>

                <FormGroup label="State:" labelFor="state-filter">
                    <HTMLSelect id="state-filter"
                        value={stateFilter} options={possibleStates}
                        onChange={(e) => setStateFilter(e.currentTarget.value)}
                        fill={true} iconName="caret-down" />
                </FormGroup>
            </DialogBody>
            <DialogFooter actions={
                <>
                    <Button onClick={onClose}>Cancel</Button>
                    <Button onClick={(e) => submitSearchForm()} intent="primary">Search</Button>
                </>
            }>
            </DialogFooter>
        </Dialog>
    )
}

// this dialog is used to copy the fft setting to a different project
const CopyFFTToProject: React.FC<{ isOpen: boolean, currentProject: ProjectInfo, FFT: FFT, onClose: () => void, onSubmit: () => void }> = ({ isOpen, currentProject, FFT, onClose, onSubmit }) => {
    const DEFAULT_PROJECT = "Please select a project"
    const [availableProjects, setAvailableProjects] = useState<ProjectInfo[]>([]);
    const [projectNames, setProjectNames] = useState<string[]>([DEFAULT_PROJECT]);
    const [selectedProject, setSelectedProject] = useState<string>(DEFAULT_PROJECT);

    const [dialogErr, setDialogErr] = useState('');
    const [submitting, setSubmitting] = useState(false);

    const [fetchingProjectDiff, setFetchingProjectDiff] = useState(false);

    useEffect(() => {
        if (!isOpen) {
            return;
        }

        fetchAllProjects()
            .then((projects) => {
                let allProjects = projects.filter(p => isProjectSubmitted(p)).filter(p => p.name !== currentProject.name);
                setAvailableProjects(allProjects);
                setProjectNames([DEFAULT_PROJECT, ...allProjects.map(p => p.name)]);
                setDialogErr("");
            }).catch((err) => {
                console.error("failed to fetch project data:", err);
                let e = err as JsonErrorMsg;
                let msg = `Failed to fetch project data: ${e.error}`;
                setDialogErr(msg);
            })
    }, [isOpen]);

    const submit = () => {
        if (selectedProject === DEFAULT_PROJECT) {
            setDialogErr("Invalid project selected");
            return;
        }

        setSubmitting(true);
        // TODO: create a request to update 1 fft value
        setSubmitting(false);
        onSubmit();
    }

    // TODO: we should provide abort signal in case of rapid changes
    const onProjectChange = (newProjectName: string) => {
        setSelectedProject(newProjectName);
        let newProject = availableProjects.filter(p => p.name === newProjectName)[0];

        // query if there is any change between fft of selected project 
        // and fft of a new project 
        // 
        // We should be able to abort the query if necessary 
        setFetchingProjectDiff(true);
        fetchProjectDiff(currentProject._id, newProject._id)
            .then(diff => {
                console.log("DIFF:", diff);
            }).catch(err => {
                console.error("Failed to fetch project diff: ", err);
            }).finally(() => {
                setFetchingProjectDiff(false);
            })
    }

    return (
        <Dialog isOpen={isOpen} onClose={onClose} title={`Copy FFT Values to "${currentProject.name}"`} autoFocus={true} >
            <DialogBody useOverflowScrollContainer>
                <table className="table table-sm table-borderless table-nohead table-nobg m-0">
                    <thead>
                        <tr>
                            <th></th>
                            <th className="w-100"></th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td><Label className="text-end mb-1">FFT:</Label></td>
                            <td>{FFT.fc}-{FFT.fg}</td>
                        </tr>
                        <tr>
                            <td><Label className="text-nowrap text-end mb-1" htmlFor="project-select">Copy From:</Label></td>
                            <td>
                                <HTMLSelect id="project-select"
                                    value={selectedProject}
                                    options={projectNames}
                                    onChange={(e) => onProjectChange(e.currentTarget.value)}
                                    fill={false} iconName="caret-down" />
                            </td>
                        </tr>
                        <tr>
                            <td><Label className="text-end mb-1">Copy To:</Label></td>
                            <td>{currentProject.name}</td>
                        </tr>
                    </tbody>
                </table>

                {dialogErr ? <p className="error">{dialogErr}</p> : null}
            </DialogBody>
            <DialogFooter actions={
                <>
                    <Button onClick={onClose}>Cancel</Button>
                    <Button onClick={(e) => submit()} intent="primary" loading={submitting} disabled={selectedProject === DEFAULT_PROJECT}>Copy FFT to {currentProject.name}</Button>
                </>
            }>
            </DialogFooter>
        </Dialog >
    )
}