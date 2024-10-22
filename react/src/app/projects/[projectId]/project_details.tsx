import { HtmlPage } from "@/app/components/html_page";
import { JsonErrorMsg } from "@/app/utils/fetching";
import { createGlobMatchRegex } from "@/app/utils/glob_matcher";
import { Alert, Button, ButtonGroup, Colors, Divider, HTMLSelect, Icon, InputGroup, NonIdealState, NumericInput } from "@blueprintjs/core";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import React, { Dispatch, ReactNode, SetStateAction, useEffect, useMemo, useState } from "react";
import { DeviceState, ProjectDeviceDetails, ProjectDeviceDetailsNumericKeys, ProjectFFT, ProjectInfo, addFftsToProject, fetchProjectFfts, fetchProjectInfo, isProjectSubmitted, syncDeviceUserChanges } from "../project_model";
import { ProjectApprovalDialog } from "../projects_overview_dialogs";
import { CopyFFTToProjectDialog, FilterFFTDialog, ProjectHistoryDialog } from "./project_dialogs";

import { AddFftDialog, FFTInfo } from "@/app/ffts/ffts_overview";
import { SortState, sortNumber, sortString } from "@/app/utils/sort_utils";
import styles from './project_details.module.css';

type deviceDetailsColumn = (keyof Omit<ProjectDeviceDetails, "id" | "comments">);

/**
 * Helper function for sorting device details based on the clicked table column header
 */
export function sortDeviceDataByColumn(data: ProjectDeviceDetails[], col: deviceDetailsColumn, desc: boolean) {
    if (data.length == 0) {
        return; // nothing to sort
    }

    switch (col) {
        case "fc":
            data.sort((a, b) => {
                let diff = sortString(a.fc, b.fc, desc);
                if (diff != 0) {
                    return diff;
                }
                return sortString(a.fg, b.fg, false); // asc 
            });
            break;
        case "fg":
            data.sort((a, b) => {
                let diff = sortString(a.fg, b.fg, desc);
                if (diff != 0) {
                    return diff;
                }
                return sortString(a.fc, b.fc, false); // asc
            });
            break;
        default:
            let isNumericField = ProjectDeviceDetailsNumericKeys.indexOf(col) >= 0;
            if (isNumericField) {
                data.sort((a, b) => {
                    let diff = sortNumber(a[col] as any, b[col] as any, desc);
                    if (diff != 0) {
                        return diff;
                    }
                    return sortString(a.fc, b.fc, false); // asc
                })
            } else {
                data.sort((a, b) => {
                    let diff = sortString(a[col] as any ?? '', b[col] as any ?? '', desc);
                    if (diff != 0) {
                        return diff
                    }
                    return sortString(a.fc, b.fc, false); // asc
                });
            }

            break;
    }
}


// a project specific page displays all properties of a specific project 
export const ProjectDetails: React.FC<{ projectId: string }> = ({ projectId }) => {
    // page and url info
    const router = useRouter();
    const pathName = usePathname();
    const queryParams = useSearchParams();

    // data and loading
    const [isLoading, setIsLoading] = useState(false);
    const [fftDataLoadingError, setFftDataLoadingError] = useState('');
    const [projectData, setProjectData] = useState<ProjectInfo>();
    const [fftData, setFftData] = useState<ProjectDeviceDetails[]>([]);
    const [fftDataDisplay, setFftDataDisplay] = useState<ProjectDeviceDetails[]>([]);

    // dialogs open state
    const [isAddNewFftDialogOpen, setIsAddNewFftDialogOpen] = useState(false);
    const [isFilterDialogOpen, setIsFilterDialogOpen] = useState(false);
    const [isApprovalDialogOpen, setIsApprovalDialogOpen] = useState(false);
    const [isCopyFFTDialogOpen, setIsCopyFFTDialogOpen] = useState(false);
    const [isProjectHistoryDialogOpen, setIsProjectHistoryDialogOpen] = useState(false);
    const [currentFFT, setCurrentFFT] = useState<ProjectFFT>({ _id: "", fc: "", fg: "" });
    const [errorAlertMsg, setErrorAlertMsg] = useState<ReactNode>('');

    // filters to apply
    const [fcFilter, setFcFilter] = useState("");
    const [fgFilter, setFgFilter] = useState("");
    const [availableFftStates, setAvailableFftStates] = useState<DeviceState[]>(DeviceState.allStates);
    const [stateFilter, setStateFilter] = useState("");
    const [showFftSinceCreationFilter, setShowFftSinceCreationFilter] = useState(false);
    const [asOfTimestampFilter, setAsOfTimestampFilter] = useState("");

    // state suitable for row updates
    const [editedDevice, setEditedDevice] = useState<ProjectDeviceDetails>();

    const [sortedByColumn, setSortedByColumn] = useState<SortState<deviceDetailsColumn>>(new SortState('fc', false));


    const changeSortOrder = (columnClicked: deviceDetailsColumn) => {
        let newSortOrder = sortedByColumn.changed(columnClicked);
        setSortedByColumn(newSortOrder);
    }

    const loadFFTData = (projectId: string, showAllEntries: boolean = true, sinceTime?: Date): Promise<void | ProjectDeviceDetails[]> => {
        setIsLoading(true);
        setFftDataLoadingError('');
        return fetchProjectFfts(projectId, showAllEntries, sinceTime)
            .then(devices => {
                setFftData(devices);
                return devices;
            }).catch((e: JsonErrorMsg) => {
                let msg = `Failed to load device data: ${e.error}`;
                setFftData([]);
                setFftDataLoadingError(msg);
                console.error(msg, e);
            }).finally(() => {
                setIsLoading(false);
            });
    }

    // load project data on load
    useEffect(() => {
        setIsLoading(true);
        {
            // set filters based on query params
            setFcFilter(queryParams.get("fc") ?? "");
            setFgFilter(queryParams.get("fg") ?? "");
            setStateFilter(queryParams.get("state") ?? "");
            setAsOfTimestampFilter(queryParams.get("asoftimestamp") ?? "");
        }

        fetchProjectInfo(projectId)
            .then(data => setProjectData(data))
            .catch((e: JsonErrorMsg) => {
                console.error("Failed to load required project data", e);
                setErrorAlertMsg("Failed to load project info: most actions will be disabled.\nError: " + e.error);
            });

        let showAllEntries = true;
        let timestampFilter = queryParams.get("asoftimestamp") ?? '';
        let asOfTimestamp = timestampFilter ? new Date(timestampFilter) : undefined;
        loadFFTData(projectId, showAllEntries, asOfTimestamp);
    }, []);


    // apply table filters, when any filter or original data changes
    useEffect(() => {
        let fcGlobMatcher = createGlobMatchRegex(fcFilter)
        let fgGlobMatcher = createGlobMatchRegex(fgFilter);
        let filteredFftData = fftData.filter(d => {
            if (fcFilter) {
                return fcGlobMatcher.test(d.fc);
            }
            return true;
        }).filter(d => {
            if (fgFilter) {
                return fgGlobMatcher.test(d.fg);
            }
            return true;
        }).filter(d => {
            if (stateFilter) {
                return d.state === stateFilter;
            }
            return true;
        })

        sortDeviceDataByColumn(filteredFftData, sortedByColumn.column, sortedByColumn.sortDesc);
        setFftDataDisplay(filteredFftData);
    }, [fftData, fcFilter, fgFilter, stateFilter, sortedByColumn]);


    const displayFilterIconInColumn = (filterValue: string) => {
        if (!filterValue) {
            return null;
        }
        return <Icon icon="filter" color={Colors.RED2} className="ms-1" />
    }

    const displaySortOrderIconInColumn = (col: deviceDetailsColumn) => {
        if (col != sortedByColumn.column) {
            return null;
        }
        return <Icon icon={sortedByColumn.sortDesc ? "arrow-down" : "arrow-up"} className="ms-1" />
    }

    const updateQueryParams = (fcFilter: string, fgFilter: string, stateFilter: string, asOfTimestampFilter: string) => {
        const params = new URLSearchParams();
        if (fcFilter) {
            params.set("fc", fcFilter);
        }
        if (fgFilter) {
            params.set("fg", fgFilter);
        }
        if (stateFilter) {
            params.set("state", stateFilter);
        }
        if (asOfTimestampFilter) {
            params.set("asoftimestamp", asOfTimestampFilter)
        }
        router.replace(`${pathName}?${params.toString()}`)
    }

    const addNewFft = (newFft: FFTInfo) => {
        if (!projectData) {
            // this should never happen
            setErrorAlertMsg("Can't add a new fft to a project without knowing the projec details; this is a programming bug");
            return;
        }

        // check if desired fft combination already exist within the project 
        // if it does, simply show an error message to the user
        for (let fft of fftData) {
            if (fft.fc === newFft.fc.name && fft.fg === newFft.fg.name) {
                setErrorAlertMsg(<>FFT <b>{fft.fc}-{fft.fg}</b> is already a part of the project: "{projectData.name}".</>);
                return
            }
        }

        let fft: ProjectFFT = {
            _id: newFft._id,
            fc: newFft.fc._id,
            fg: newFft.fg._id,
        }
        return addFftsToProject(projectData._id, [fft])
            .then(data => {
                // TODO: when we try to add an fft that is already there, the backend doesn't complain
                // it just returns success: true, erromsg: no changes detected.
                // TODO: we only need the fft that was updated, not all ffts of the project
                setFftData(data)
                setIsAddNewFftDialogOpen(false);
            }).catch((e: JsonErrorMsg) => {
                let msg = "Failed to add an fft to a project: " + e.error;
                console.error(msg, e);
                setErrorAlertMsg(msg);
            });
    }

    const isProjectSubmitted = projectData?.status === "submitted";
    const isFilterApplied = fcFilter != "" || fgFilter != "" || stateFilter != "" 
    const isRemoveFilterEnabled = isFilterApplied || showFftSinceCreationFilter || asOfTimestampFilter
    const isEditedTable = editedDevice != undefined;

    return (
        <HtmlPage>
            {fftDataLoadingError ? <NonIdealState className="mb-4 mt-4" icon="error" title="Error" description={fftDataLoadingError} /> : null}

            {/* NOTE: horizontally scrollable table with sticky header only works if it's max height is capped */}
            <div className="table-responsive" style={{ maxHeight: 'calc(100vh - 130px)' }}>
                <table className={`table table-bordered table-sm table-sticky table-striped ${styles.detailsTable}`}>
                    <thead>
                        <tr>
                            <th colSpan={6}>
                                {!projectData ? <></> :
                                    <ButtonGroup vertical={false} className={isEditedTable ? "table-disabled" : ''}>

                                        <h5 className="m-0 me-3" style={{ color: Colors.RED2 }}>{projectData?.name}</h5>

                                        <Button icon="import" title="Download data to this project" minimal={true} small={true} />
                                        <Button icon="export" title="Upload data to this project" minimal={true} small={true} />

                                        <Divider />

                                        <Button icon="add" title="Add a new FFT to Project" minimal={true} small={true}
                                            onClick={e => setIsAddNewFftDialogOpen(true)}
                                        />

                                        <Divider />

                                        <Button icon="filter" title="Filter FFTs" minimal={true} small={true} intent={isFilterApplied ? "warning" : "none"} onClick={(e) => setIsFilterDialogOpen(true)} />

                                        <Button icon="filter-remove" title="Clear filters to show all FFTs" minimal={true} small={true} disabled={!isRemoveFilterEnabled}
                                            onClick={(e) => {
                                                setFcFilter('')
                                                setFgFilter('');
                                                setStateFilter('');
                                                let timestampFilter = asOfTimestampFilter;
                                                setAsOfTimestampFilter('');

                                                if (showFftSinceCreationFilter) {
                                                    setShowFftSinceCreationFilter(false);
                                                    loadFFTData(projectData._id, true);
                                                } else if (timestampFilter) {
                                                    // timestamp filter was applied and now we have to load original data
                                                    loadFFTData(projectData._id, true);
                                                }
                                                updateQueryParams('', '', '', '');
                                            }}
                                        />

                                        <Button icon="filter-open" minimal={true} small={true} intent={showFftSinceCreationFilter ? "warning" : "none"}
                                            title="Show only FCs with changes after the project was created"
                                            onClick={(e) => {
                                                if (showFftSinceCreationFilter) {
                                                    // filter is applied, therefore we have to toggle it off and show all entries
                                                    loadFFTData(projectId, true);
                                                } else {
                                                    // filter is not applied, therefore we have to display changes after project was created
                                                    loadFFTData(projectId, false);
                                                }

                                                // toggle the filter flag 
                                                setShowFftSinceCreationFilter(show => !show);
                                            }}
                                        />

                                        <Divider />

                                        <Button icon="tag-add" title="Create a tag" minimal={true} small={true} />
                                        <Button icon="tags" title="Show assigned tags" minimal={true} small={true} />

                                        <Divider />

                                        <Button icon="history" title="Show the history of changes" minimal={true} small={true}
                                            intent={asOfTimestampFilter ? "danger" : "none"}
                                            onClick={(e) => setIsProjectHistoryDialogOpen(true)}
                                        />
                                        <Button icon="user" title="Submit this project for approval" minimal={true} small={true}
                                            disabled={isProjectSubmitted}
                                            onClick={(e) => setIsApprovalDialogOpen(true)}
                                        />
                                    </ButtonGroup>
                                }
                            </th>

                            <th colSpan={3} className="text-center">Nominal Location (meters in LCLS coordinates)</th>
                            <th colSpan={3} className="text-center">Nominal Dimension (meters)</th>
                            <th colSpan={3} className="text-center">Nominal Angle (radians)</th>
                            <th></th>
                        </tr>
                        <tr>
                            {isProjectSubmitted ? null : <th></th>}
                            <th onClick={e => changeSortOrder('fc')}>FC {displayFilterIconInColumn(fcFilter)}{displaySortOrderIconInColumn('fc')}</th>
                            <th onClick={e => changeSortOrder('fg')}>Fungible {displayFilterIconInColumn(fgFilter)}{displaySortOrderIconInColumn('fg')}</th>
                            <th onClick={e => changeSortOrder('tc_part_no')}>TC Part No. {displaySortOrderIconInColumn('tc_part_no')}</th>
                            <th onClick={e => changeSortOrder('state')}>State {displayFilterIconInColumn(stateFilter)} {displaySortOrderIconInColumn('state')}</th>
                            <th>Comments</th>

                            <th onClick={e => changeSortOrder('nom_loc_z')} className="text-center">Z {displaySortOrderIconInColumn('nom_loc_z')}</th>
                            <th onClick={e => changeSortOrder('nom_loc_x')} className="text-center">X {displaySortOrderIconInColumn('nom_loc_x')}</th>
                            <th onClick={e => changeSortOrder('nom_loc_y')} className="text-center">Y {displaySortOrderIconInColumn('nom_loc_y')}</th>

                            <th onClick={e => changeSortOrder('nom_dim_z')} className="text-center">Z {displaySortOrderIconInColumn('nom_dim_z')}</th>
                            <th onClick={e => changeSortOrder('nom_dim_x')} className="text-center">X {displaySortOrderIconInColumn('nom_dim_x')}</th>
                            <th onClick={e => changeSortOrder('nom_dim_y')} className="text-center">Y {displaySortOrderIconInColumn('nom_dim_y')}</th>

                            <th onClick={e => changeSortOrder('nom_ang_z')} className="text-center">Z {displaySortOrderIconInColumn('nom_ang_z')}</th>
                            <th onClick={e => changeSortOrder('nom_ang_x')} className="text-center">X {displaySortOrderIconInColumn('nom_ang_x')}</th>
                            <th onClick={e => changeSortOrder('nom_ang_y')} className="text-center">Y {displaySortOrderIconInColumn('nom_ang_y')}</th>
                            <th onClick={e => changeSortOrder('ray_trace')}>Must Ray Trace {displaySortOrderIconInColumn('ray_trace')}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {fftDataDisplay.map(device => {
                            const isEditedDevice = editedDevice == device;
                            const disableRow = isEditedTable && !isEditedDevice;
                            if (!isEditedDevice) {
                                return <DeviceDataTableRow key={device.id} project={projectData} device={device} disabled={disableRow}
                                    onEdit={(device) => setEditedDevice(device)}
                                    onCopyFft={(device) => {
                                        setCurrentFFT({ _id: device.id, fc: device.fc, fg: device.fg });
                                        setIsCopyFFTDialogOpen(true);
                                    }
                                    }
                                />
                            }

                            return <DeviceDataEditTableRow key={device.id} project={projectData} device={device} availableFftStates={availableFftStates}
                                onEditDone={(updatedDeviceData, action) => {
                                    if (action == "cancel") {
                                        setEditedDevice(undefined);
                                        return;
                                    }

                                    // update existing fft data
                                    let newDeviceData = [];
                                    for (let d of fftData) {
                                        if (d.id != updatedDeviceData.id) {
                                            newDeviceData.push(d);
                                            continue
                                        }
                                        newDeviceData.push(updatedDeviceData);
                                    }
                                    setFftData(newDeviceData);
                                    setEditedDevice(undefined);
                                }}
                            />
                        })
                        }
                    </tbody>
                </table>
            </div>

            {!isLoading && !fftDataLoadingError && !isFilterApplied && fftDataDisplay.length == 0 ?
                <NonIdealState icon="search" title="No FFTs Found" description={<>Project {projectData?.name} does not have any FFTs</>} />
                : null}

            {!isLoading && isFilterApplied && fftDataDisplay.length == 0 ?
                <NonIdealState icon="filter" title="No FFTs Found" description="Try changing your filters"></NonIdealState>
                : null
            }

            {projectData ?
                <AddFftDialog
                    dialogType="addToProject"
                    isOpen={isAddNewFftDialogOpen}
                    onClose={() => setIsAddNewFftDialogOpen(false)}
                    onSubmit={(newFft) => addNewFft(newFft)}
                />
                : null
            }

            <FilterFFTDialog
                isOpen={isFilterDialogOpen}
                possibleStates={availableFftStates}
                onClose={() => setIsFilterDialogOpen(false)}
                onSubmit={(newFcFilter, newFgFilter, newStateFilter) => {
                    setFcFilter(newFcFilter);
                    setFgFilter(newFgFilter);
                    newStateFilter = newStateFilter.startsWith("---") ? "" : newStateFilter;
                    setStateFilter(newStateFilter);
                    updateQueryParams(newFcFilter, newFgFilter, newStateFilter, asOfTimestampFilter);
                    setIsFilterDialogOpen(false);
                }}
            />

            {projectData ?
                <ProjectApprovalDialog
                    isOpen={isApprovalDialogOpen}
                    projectTitle={projectData.name}
                    projectId={projectData._id}
                    projectOwner={projectData.owner}
                    onClose={() => setIsApprovalDialogOpen(false)}
                    onSubmit={(projectInfo) => {
                        setProjectData(projectInfo);
                        setIsApprovalDialogOpen(false);
                    }}
                />
                : null}

            {projectData ?
                <CopyFFTToProjectDialog
                    isOpen={isCopyFFTDialogOpen}
                    FFT={currentFFT}
                    currentProject={projectData}
                    onClose={() => setIsCopyFFTDialogOpen(false)}
                    onSubmit={(newDeviceDetails) => {
                        // find current fft and update device details
                        let updatedData = [];
                        for (let d of fftData) {
                            if (d.id != newDeviceDetails.id) {
                                updatedData.push(d);
                                continue;
                            }
                            updatedData.push(newDeviceDetails);
                        }
                        setFftData(updatedData);
                        setIsCopyFFTDialogOpen(false);
                    }}
                /> : null}

            {projectData ?
                <ProjectHistoryDialog
                    currentProject={projectData}
                    isOpen={isProjectHistoryDialogOpen}
                    onClose={() => setIsProjectHistoryDialogOpen(false)}
                    displayProjectSince={(time) => {
                        loadFFTData(projectData._id, true, time);
                        setIsProjectHistoryDialogOpen(false);

                        let timestampFilter = time.toISOString();
                        updateQueryParams(fcFilter, fgFilter, stateFilter, timestampFilter);
                        setAsOfTimestampFilter(timestampFilter);
                    }}
                />
                : null}


            {/* Alert for displaying error messages that may happen in other dialogs */}
            <Alert
                className="alert-default"
                confirmButtonText="Ok"
                onConfirm={(e) => setErrorAlertMsg('')}
                intent="danger"
                isOpen={errorAlertMsg != ""}>
                <h5 className="alert-title"><Icon icon="error" />Error</h5>
                <p>{errorAlertMsg}</p>
            </Alert>
        </HtmlPage >
    )
}


const DeviceDataTableRow: React.FC<{ project?: ProjectInfo, device: ProjectDeviceDetails, disabled: boolean, onEdit: (device: ProjectDeviceDetails) => void, onCopyFft: (device: ProjectDeviceDetails) => void }> = ({ project, device, disabled, onEdit, onCopyFft }) => {
    // we have to cache each table row, as once we have lots of rows in a table editing text fields within
    // becomes very slow due to constant rerendering of rows and their tooltips on every keystroke. 
    const formatDevicePositionNumber = (value?: number | string): string => {
        if (value === undefined) {
            return '';
        }
        if (typeof value === "string") {
            return value;
        }
        return value.toFixed(7);
    }

    const row = useMemo(() => {
        return (
            <tr className={disabled ? 'table-disabled' : ''}>
                {isProjectSubmitted(project) ? null :
                    <td>
                        <Button icon="edit" minimal={true} small={true} title="Edit this FFT"
                            onClick={(e) => onEdit(device)}
                        />
                        <Button icon="refresh" minimal={true} small={true} title={"Copy over the value from the currently approved project"}
                            onClick={(e) => onCopyFft(device)}
                        />
                    </td>
                }

                <td>{device.fc}</td>
                <td>{device.fg}</td>
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
    }, [project, device, disabled])
    return row;
}



const DeviceDataEditTableRow: React.FC<{
    project?: ProjectInfo,
    device: ProjectDeviceDetails,
    availableFftStates: DeviceState[],
    onEditDone: (newDevice: ProjectDeviceDetails, action: "ok" | "cancel") => void,
}> = ({ project, device, availableFftStates, onEditDone }) => {
    const [editError, setEditError] = useState('');
    const [isSubmitting, setSubmitting] = useState<boolean>(false);

    interface EditField {
        key: (keyof ProjectDeviceDetails);
        type: "string" | "number" | "select"
        value: [string | undefined, Dispatch<SetStateAction<string | undefined>>];
        valueOptions?: string[]; // only used when type == "select"
        err: [boolean, Dispatch<SetStateAction<boolean>>];
        min?: number;
        max?: number;
        allowNumbersOnly?: boolean;
    }

    let fftStates = useMemo(() => {
        return availableFftStates.map(s => s.name);
    }, [availableFftStates])

    const editableDeviceFields: EditField[] = [
        { key: 'tc_part_no', type: "string", value: useState<string>(), err: useState(false) },
        { key: 'state', type: "select", valueOptions: fftStates, value: useState<string>(), err: useState(false) },
        { key: 'comments', type: "string", value: useState<string>(), err: useState(false) },

        { key: 'nom_loc_z', type: "number", value: useState<string>(), err: useState(false) },
        { key: 'nom_loc_x', type: "number", value: useState<string>(), err: useState(false) },
        { key: 'nom_loc_y', type: "number", value: useState<string>(), err: useState(false) },

        { key: 'nom_dim_z', type: "number", value: useState<string>(), err: useState(false) },
        { key: 'nom_dim_x', type: "number", value: useState<string>(), err: useState(false) },
        { key: 'nom_dim_y', type: "number", value: useState<string>(), err: useState(false) },

        { key: 'nom_ang_z', type: "number", value: useState<string>(), err: useState(false) },
        { key: 'nom_ang_x', type: "number", value: useState<string>(), err: useState(false) },
        { key: 'nom_ang_y', type: "number", value: useState<string>(), err: useState(false) },

        { key: 'ray_trace', type: "number", value: useState<string>(), err: useState(false), max: 1, min: 0, allowNumbersOnly: true }
    ]

    useEffect(() => {
        for (let field of editableDeviceFields) {
            if (field.key == 'id' || field.key == 'fg' || field.key == 'fc') { // fft field is not editable
                continue;
            }
            field.value[1](device[field.key] as any);
        }
    }, [device])

    const numberOrDefault = (value: string | undefined, defaultVal: number | undefined): number | undefined => {
        if (value == "" || value == undefined) {
            return undefined;
        }

        let num = Number.parseFloat(value);
        if (isNaN(num)) {
            // this should never happen since we verify the fields before the user 
            // is able to submit them. 
            return defaultVal;
        }
        return num;
    }

    const createDeviceWithChanges = (): ProjectDeviceDetails => {
        let copyDevice = structuredClone(device);
        for (let editField of editableDeviceFields) {
            let field = editField.key;
            let device = copyDevice as any;
            if (editField.type == "number") {
                device[field] = numberOrDefault(editField.value[0], undefined);
            } else {
                device[field] = editField.value[0] || '';
            }
        }
        return copyDevice;
    }


    let errStates = editableDeviceFields.map(f => f.err[0]);
    const allFieldsAreValid = useMemo(() => {
        for (let f of editableDeviceFields) {
            if (f.err[0] === true) {
                return false;
            }
        }

        // all fields are valid, we can submit this change
        return true;
    }, [...errStates])


    const submitChanges = () => {
        let deviceWithChanges = createDeviceWithChanges();

        // find changes that have to be synced with backend
        // later on, we may have to add a user comment to each of those changes
        let fieldNames = Object.keys(deviceWithChanges) as (keyof ProjectDeviceDetails)[];
        fieldNames = fieldNames.filter(field => field != "id" && field != "fg" && field != "fc");
        let changes: Record<string, any> = {};
        for (let field of fieldNames) {
            if (deviceWithChanges[field] !== device[field]) { // this field has changed
                if (field === "state") {
                    // we have to transform the state from what's displayed into an enum that
                    // a backend understands, hence this transformation
                    changes[field] = DeviceState.fromString(deviceWithChanges[field]).backendEnumName;
                    continue;
                }
                changes[field] = deviceWithChanges[field];
            }
        }

        if (changes.length == 0) {
            // nothing to sync 
            return;
        }

        if (!project) {
            // this should never happen
            let msg = "Project that we want to sync our changes to does not exist: this is a programming bug that should never happen";
            console.error(msg);
            setEditError(msg)
            return;
        }

        setSubmitting(true);
        syncDeviceUserChanges(project._id, deviceWithChanges.id, changes)
            .then((response) => {
                // TODO: for some reason server returns data for all devices again
                // when we don't really need it. We just update our changed device
                onEditDone(deviceWithChanges, "ok");
            }).catch((e: JsonErrorMsg) => {
                let msg = `Failed to sync user device changes: ${e.error}`;
                console.error(msg, e);
                setEditError(msg);
            }).finally(() => {
                setSubmitting(false);
            })
    }

    return (
        <tr>
            {isProjectSubmitted(project) ? null :
                <td>
                    <Button icon="tick" minimal={true} small={true} loading={isSubmitting}
                        title="Submit your edits"
                        disabled={!allFieldsAreValid}
                        onClick={(e) => submitChanges()}
                    />

                    <Button icon="cross" minimal={true} small={true} title="Discard your edits"
                        onClick={(e) => onEditDone(createDeviceWithChanges(), "cancel")}
                    />
                </td>
            }

            <td>{device.fc}</td>
            <td>{device.fg}</td>

            {editableDeviceFields.map((field) => {
                // the reason why we use components instead of rendering edit fields directly is due to performance
                // Rerendering the entire row and all its fields on every keystroke is noticably slow, therefore
                // we cache edit fields via components.
                let inputField: ReactNode;
                if (field.type == "string") {
                    inputField = <StringEditField value={field.value[0] ?? ''} setter={field.value[1]} err={field.err[0]} errSetter={field.err[1]} />
                } else if (field.type == "number") {
                    inputField = <NumericEditField value={field.value[0]} setter={field.value[1]} min={field.min} max={field.max} err={field.err[0]} errSetter={field.err[1]} allowNumbersOnly={field.allowNumbersOnly} />
                } else if (field.type == "select") {
                    inputField = <SelectEditField value={field.value[0] ?? ''} setter={field.value[1]} options={field.valueOptions || []} err={field.err[0]} errSetter={field.err[1]} />
                } else {
                    throw new Error("Unhandled field type: ", field.type)
                }
                return <td key={field.key}>{inputField}</td>
            })
            }

                {editError ?
                    <Alert
                        className="alert-default"
                        confirmButtonText="Ok"
                        onConfirm={(e) => setEditError('')}
                        intent="danger"
                        isOpen={editError != ""}>
                        <h5 className="alert-title"><Icon icon="error" />Error</h5>
                        <p>{editError}</p>
                    </Alert>
                    : null
                }
            </tr>
        )
    }


const StringEditField: React.FC<{ value: string, setter: any, err: boolean, errSetter: any }> = ({ value, setter, err, errSetter }) => {
    return useMemo(() => {
        return <InputGroup value={value} onValueChange={(val) => setter(val)} style={{ width: 'auto', minWidth: "5ch" }} fill={true} />
    }, [value, err])
}

const SelectEditField: React.FC<{ value: string, setter: any, options: string[], err: boolean, errSetter: any }> = ({ value, setter, options, err, errSetter }) => {
    return useMemo(() => {
        return <HTMLSelect value={value} options={options} onChange={(e) => setter(e.target.value)} style={{ width: "auto" }} iconName="caret-down" fill={true} />
    }, [value, options, err])
} 

// performance optimization to avoid re-rendering every field in a row every time the user types one character in one of them.
const NumericEditField: React.FC<{ value: string | number | undefined, setter: any, err: boolean, errSetter: any, min?: number, max?: number, allowNumbersOnly?: boolean }> = ({ value, setter, err, errSetter, min, max, allowNumbersOnly: allowNumericCharsOnly }) => {
    const isNumeric = (v: string) => {
        return /^\d+$/.test(v);
    }
    const field = useMemo(() => {
        return (<NumericInput
            buttonPosition="none"
            allowNumericCharactersOnly={false}
            intent={err ? "danger" : "none"}
            style={{ width: "auto", maxWidth: "15ch", textAlign: "right" }}
            value={value}
            stepSize={1}
            minorStepSize={0.0000000001} /* this is necessary to avoid warnings: numeric input rounds number based on this precision */
            majorStepSize={1}
            max={undefined}
            min={undefined}
            fill={true}
            onValueChange={(num, v) => {
                setter(v);
                if (isNaN(num)) {
                    errSetter(true);
                    return;
                }

                // we have a valid number
                errSetter(false);

                // check special behavior
                if (allowNumericCharsOnly && v != "") {
                    let numeric = isNumeric(v);
                    errSetter(!numeric);
                }

                // check ranges if any 
                if (min != undefined) {
                    if (num < min) {
                        errSetter(true);
                    }
                }
                if (max != undefined) {
                    if (num > max) {
                        errSetter(true);
                    }
                }
            }
            }
        />
        )
    }, [value, err])
    return field;
}