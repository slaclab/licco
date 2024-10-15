import { HtmlPage } from "@/app/components/html_page";
import { Fetch, JsonErrorMsg } from "@/app/utils/fetching";
import { createGlobMatchRegex } from "@/app/utils/glob_matcher";
import { Alert, Button, ButtonGroup, Colors, Divider, HTMLSelect, Icon, InputGroup, NonIdealState, NumericInput } from "@blueprintjs/core";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import React, { Dispatch, ReactNode, SetStateAction, useEffect, useMemo, useState } from "react";
import { DeviceState, FFT, ProjectDeviceDetails, ProjectInfo, isProjectSubmitted, syncDeviceUserChanges, transformProjectDeviceDetails } from "../project_model";
import { ProjectApprovalDialog } from "../projects_overview_dialogs";
import { CopyFFTToProjectDialog, FilterFFTDialog } from "./project_dialogs";


const formatDevicePositionNumber = (value?: number | string): string => {
    if (value === undefined) {
        return '';
    }
    if (typeof value === "string") {
        return value;
    }
    return value.toFixed(7);
}

// a project specific page displays all properties of a specific project 
export const ProjectSpecificPage: React.FC<{ projectId: string }> = ({ projectId }) => {
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
    const [isFilterDialogOpen, setIsFilterDialogOpen] = useState(false);
    const [isApprovalDialogOpen, setIsApprovalDialogOpen] = useState(false);
    const [isCopyFFTDialogOpen, setIsCopyFFTDialogOpen] = useState(false);
    const [currentFFT, setCurrentFFT] = useState<FFT>({ _id: "", fc: "", fg: "" });

    // filters to apply
    const [fcFilter, setFcFilter] = useState("");
    const [fgFilter, setFgFilter] = useState("");
    const [availableFftStates, setAvailableFftStates] = useState<DeviceState[]>(DeviceState.allStates);
    const [stateFilter, setStateFilter] = useState("");
    const [showFftSinceCreationFilter, setShowFftSinceCreationFilter] = useState(false);

    // state suitable for row updates
    const [editedDevice, setEditedDevice] = useState<ProjectDeviceDetails>();



    const loadFFTData = (projectId: string, showAllEntries: boolean = true): Promise<void | ProjectDeviceDetails[]> => {
        setIsLoading(true);
        setFftDataLoadingError('');
        return Fetch.get<Record<string, ProjectDeviceDetails>>(`/ws/projects/${projectId}/ffts/?showallentries=${showAllEntries}`)
            .then((data) => {
                // TODO: missing device number field is set to "" (empty string):
                // we should turn it into an null to avoid having problems when formatting it later
                let devices = Object.values(data);
                devices.forEach(d => transformProjectDeviceDetails(d));
                setFftData(devices);
                return devices;
            }).catch((e) => {
                console.error("Failed to load device data:", e);
                let err = e as JsonErrorMsg;
                let msg = `Failed to load device data: ${err.error}`;
                setFftData([]);
                setFftDataLoadingError(msg);
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
        }

        Fetch.get<ProjectInfo>(`/ws/projects/${projectId}/`)
            .then(data => {
                setProjectData(data);
            }).catch((e) => {
                console.error("Failed to make a project request");
            });

        let showAllEntries = true;
        loadFFTData(projectId, showAllEntries);
    }, []);


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


    const displayFilterIconInColumn = (filterValue: string) => {
        if (!filterValue) {
            return null
        }
        return <Icon icon="filter" color={Colors.RED2} className="ms-1" />
    }

    const updateQueryParams = (fcFilter: string, fgFilter: string, stateFilter: string) => {
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
        router.replace(`${pathName}?${params.toString()}`)
    }

    const isProjectSubmitted = projectData?.status === "submitted";
    const isFilterApplied = fcFilter != "" || fgFilter != "" || stateFilter != ""
    const isRemoveFilterEnabled = isFilterApplied || showFftSinceCreationFilter
    const isEditedTable = editedDevice != undefined;

    return (
        <HtmlPage>
            {fftDataLoadingError ? <NonIdealState className="mb-4 mt-4" icon="error" title="Error" description={fftDataLoadingError} /> : null}

            {/* NOTE: horizontally scrollable table with sticky header only works if it's max height is capped */}
            <div className="table-responsive" style={{ maxHeight: 'calc(100vh - 130px)' }}>
                <table className="table table-bordered table-sm table-sticky table-striped">
                    <thead>
                        <tr>
                            <th colSpan={6}>
                                {!projectData ? <></> :
                                    <ButtonGroup vertical={false} className={isEditedTable ? "table-disabled" : ''}>

                                        <span className="me-3">{projectData?.name}</span>

                                        <Button icon="import" title="Download data to this project" minimal={true} small={true} />
                                        <Button icon="export" title="Upload data to this project" minimal={true} small={true} />

                                        <Divider />

                                        <Button icon="filter" title="Filter FFTs" minimal={true} small={true} intent={isFilterApplied ? "warning" : "none"} onClick={(e) => setIsFilterDialogOpen(true)} />

                                        <Button icon="filter-remove" title="Clear filters to show all FFTs" minimal={true} small={true} disabled={!isRemoveFilterEnabled}
                                            onClick={(e) => {
                                                setFcFilter('')
                                                setFgFilter('');
                                                setStateFilter('');
                                                if (showFftSinceCreationFilter) {
                                                    setShowFftSinceCreationFilter(false);
                                                    loadFFTData(projectData._id);
                                                }
                                                updateQueryParams('', '', '');
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

                                        <Button icon="history" title="Show the history of changes" minimal={true} small={true} />
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
                            <th>FC  {displayFilterIconInColumn(fcFilter)}</th>
                            <th>Fungible {displayFilterIconInColumn(fgFilter)}</th>
                            <th>TC Part No.</th>
                            <th>State {displayFilterIconInColumn(stateFilter)}</th>
                            <th>Comments</th>

                            <th className="text-center">Z</th>
                            <th className="text-center">X</th>
                            <th className="text-center">Y</th>

                            <th className="text-center">Z</th>
                            <th className="text-center">X</th>
                            <th className="text-center">Y</th>

                            <th className="text-center">Z</th>
                            <th className="text-center">X</th>
                            <th className="text-center">Y</th>
                            <th>Must Ray Trace</th>
                        </tr>
                    </thead>
                    <tbody>
                        {fftDataDisplay.map(device => {
                            const isEditedDevice = editedDevice == device;
                            const disableRow = isEditedTable && !isEditedDevice;
                            if (!isEditedDevice) {
                                return <DeviceDataTableRow key={device.fft._id} project={projectData} device={device} disabled={disableRow}
                                    onEdit={(device) => setEditedDevice(device)}
                                    onCopyFft={(device) => {
                                        setCurrentFFT(device.fft);
                                        setIsCopyFFTDialogOpen(true);
                                    }
                                    }
                                />
                            }

                            return <DeviceDataEditTableRow key={device.fft._id} project={projectData} device={device} availableFftStates={availableFftStates}
                                onEditDone={(updatedDeviceData, action) => {
                                    if (action == "cancel") {
                                        setEditedDevice(undefined);
                                        return;
                                    }

                                    // update existing fft data
                                    let newDeviceData = [];
                                    for (let d of fftData) {
                                        if (d.fft._id != updatedDeviceData.fft._id) {
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

            <FilterFFTDialog
                isOpen={isFilterDialogOpen}
                possibleStates={availableFftStates}
                onClose={() => setIsFilterDialogOpen(false)}
                onSubmit={(newFcFilter, newFgFilter, newStateFilter) => {
                    setFcFilter(newFcFilter);
                    setFgFilter(newFgFilter);
                    newStateFilter = newStateFilter.startsWith("---") ? "" : newStateFilter;
                    setStateFilter(newStateFilter);
                    updateQueryParams(newFcFilter, newFgFilter, newStateFilter);
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
                            if (d.fft._id != newDeviceDetails.fft._id) {
                                updatedData.push(d);
                                continue;
                            }
                            updatedData.push(newDeviceDetails);
                        }
                        setFftData(updatedData);
                        setIsCopyFFTDialogOpen(false);
                    }}
                /> : null}
        </HtmlPage >
    )
}


const DeviceDataTableRow: React.FC<{ project?: ProjectInfo, device: ProjectDeviceDetails, disabled: boolean, onEdit: (device: ProjectDeviceDetails) => void, onCopyFft: (device: ProjectDeviceDetails) => void }> = ({ project, device, disabled, onEdit, onCopyFft }) => {
    // we have to cache each table row, as once we have lots of rows in a table editing text fields within
    // becomes very slow due to constant rerendering of rows and their tooltips on every keystroke. 
    const row = useMemo(() => {
        return (
            <tr className={disabled ? 'table-disabled' : ''}>
                {isProjectSubmitted(project) ? null :
                    <td className="text-nowrap">
                        <Button icon="edit" minimal={true} small={true} title="Edit this FFT"
                            onClick={(e) => onEdit(device)}
                        />
                        <Button icon="refresh" minimal={true} small={true} title={"Copy over the value from the currently approved project"}
                            onClick={(e) => onCopyFft(device)}
                        />
                    </td>
                }

                <td>{device.fft.fc}</td>
                <td>{device.fft.fg}</td>
                <td className="text-nowrap"> {device.tc_part_no}</td>
                <td className="text-nowrap">{device.state}</td>
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

        { key: 'ray_trace', type: "number", value: useState<string>(), err: useState(false), max: 1, min: 0 }
    ]

    useEffect(() => {
        for (let field of editableDeviceFields) {
            if (field.key == 'fft') { // fft field is not editable
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
        fieldNames = fieldNames.filter(field => field != "fft");
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
        syncDeviceUserChanges(project._id, deviceWithChanges.fft._id, changes)
            .then((response) => {
                // TODO: for some reason server returns data for all devices again
                // when we don't really need it. We just update our changed device
                onEditDone(deviceWithChanges, "ok");
            }).catch((e) => {
                let err = e as JsonErrorMsg;
                let msg = `Failed to sync user device changes: ${err.error}`;
                console.error(msg, e);
                setEditError(msg);
            }).finally(() => {
                setSubmitting(false);
            })
    }

    return (
        <tr>
            {isProjectSubmitted(project) ? null :
                <td className="text-nowrap">
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

            <td>{device.fft.fc}</td>
            <td>{device.fft.fg}</td>

            {editableDeviceFields.map((field) => {
                // the reason why we use components instead of rendering edit fields directly is due to performance
                // Rerendering the entire row and all its fields on every keystroke is noticably slow, therefore
                // we cache edit fields via components.
                let inputField: ReactNode;
                if (field.type == "string") {
                    inputField = <StringEditField value={field.value[0] ?? ''} setter={field.value[1]} err={field.err[0]} errSetter={field.err[1]} />
                } else if (field.type == "number") {
                    inputField = <NumericEditField value={field.value[0]} setter={field.value[1]} min={field.min} max={field.max} err={field.err[0]} errSetter={field.err[1]} />
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
const NumericEditField: React.FC<{ value: string | number | undefined, setter: any, err: boolean, errSetter: any, min?: number, max?: number }> = ({ value, setter, err, errSetter, min, max }) => {
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