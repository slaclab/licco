import { constructTimeBoundaries, formatToLiccoDateTime, setTimeBoundary, toIsoDate } from "@/app/utils/date_utils";
import { Fetch, JsonErrorMsg } from "@/app/utils/fetching";
import { Button, ButtonGroup, Dialog, DialogBody, DialogFooter, FormGroup, InputGroup, NonIdealState, Spinner } from "@blueprintjs/core";
import { useEffect, useMemo, useState } from "react";
import { Row } from "react-bootstrap";
import { fetchHistoryOfChanges, fetchLatestSnapshot, ProjectInfo, ProjectSnapshot } from "../project_model";
import { renderTableField } from "../project_utils";

export interface ProjectHistoryDialogState {
    selectedProjectDate?: Date;
    startTime?: Date;
    endTime?: Date;
    snapshotHistory: ProjectSnapshot[];
}

export const ProjectHistoryDialog: React.FC<{
    isOpen: boolean, project: ProjectInfo,
    state: ProjectHistoryDialogState, onStateChange: (state: ProjectHistoryDialogState) => void,
    selectedTimestamp?: Date, onClose: () => void, displayProjectSince: (time?: Date) => void
}> = ({ isOpen, project, state, onStateChange, selectedTimestamp, onClose, displayProjectSince }) => {
    const [isLoading, setIsLoading] = useState(false);
    const [dialogErr, setDialogErr] = useState('');
    const [editedSnapshot, setEditedSnapshot] = useState<ProjectSnapshot>();
    const [latestSnapshot, setLatestSnapshot] = useState<ProjectSnapshot>();

    // Implementation Note: history state is passed from the parent component, as otherwise the state is not retained 
    // when selecting a snapshot from the past (user selected date boundaries would be lost without this workaround)

    useEffect(() => {
        if (!isOpen) {
            return;
        }

        // always fetch latest snapshot since it's the only way to mark the latest snapshot in the history table
        fetchLatestSnapshot(project._id).then(snap => setLatestSnapshot(snap));

        // fetch history on dialog open, but only the first time when the dialog is opened.
        // if there are no snapshots we can still make a request, since it's a quick check.
        //
        // We should also refetch if the end time is set to the current date or later, since any
        // user device change will add a new change into the history of snapshots.
        const noSnapshots = state.snapshotHistory.length === 0;
        const endTimeIsTodayOrAfter = state.endTime && state.endTime.getTime() > new Date().getTime();
        if (noSnapshots || endTimeIsTodayOrAfter) {
            fetchHistory(state.startTime, state.endTime);
        }

        // NOTE: don't put 'state' in this use effect array as otherwise you will end up in infinite loop
        // of request making. This effect should only track open/close dialog state and nothing else 
        // no matter what the linter may tell you.
    }, [isOpen]);


    // fetch history and update the table
    const fetchHistory = (start?: Date, end?: Date, limit: number = 0) => {
        setIsLoading(true);
        fetchHistoryOfChanges(project._id, start, end, limit)
            .then((data) => {
                let newState = Object.assign({}, state);
                newState.startTime = start;
                newState.endTime = end;
                newState.snapshotHistory = data;
                onStateChange(newState);
                setDialogErr('');
            }).catch((e: JsonErrorMsg) => {
                console.error(e);
                let msg = "Failed to fetch project diff history: " + e.error;
                setDialogErr(msg);
            }).finally(() => {
                setIsLoading(false);
            })
    }

    const projectHistoryTable = useMemo(() => {
        if (isLoading) {
            return <NonIdealState icon={<Spinner />} title="Loading Project History" description="Please wait..." />
        }

        if (dialogErr) {
            return <NonIdealState icon="error" title="Error" description={dialogErr} />
        }

        if (state.snapshotHistory.length == 0) {
            return <NonIdealState icon="clean" title="No Project History Exists" description={`Project ${project.name} does not have any changes since creation`} />
        }

        const changedDeviceColStyle = {
            "width": "100%",
            "maxWidth": "20%",
        };

        const isSelectedHistory = (snapshotDate: Date, selectedSnapshotDate?: Date): boolean => {
            if (selectedSnapshotDate === undefined) {
                return false;
            }

            // selected date exists, compare it to snapshot date
            if (snapshotDate.getTime() === selectedSnapshotDate.getTime()) {
                return true
            }
            return false
        }

        return (
            <>
                <table className="table table-sm table-bordered table-striped">
                    <thead>
                        <tr>
                            <th></th>
                            <th>Name</th>
                            <th>Updated</th>
                            <th>Created</th>
                            <th>Deleted</th>
                            <th className="text-nowrap">Changed By</th>
                            <th className="text-nowrap">At time</th>
                        </tr>
                    </thead>
                    <tbody>
                        {state.snapshotHistory.map((snapshot, i) => {
                            const isSnapshotSelected = isSelectedHistory(snapshot.created, selectedTimestamp || latestSnapshot?.created);
                            return (
                                <tr key={snapshot._id}>
                                    <td>
                                        <ButtonGroup>
                                            <Button icon="history"
                                                className="me-1"
                                                intent={isSnapshotSelected ? "danger" : "none"}
                                                disabled={isSnapshotSelected}
                                                title="View the project as of this point in time"
                                                onClick={(e) => {
                                                    console.log("Latest snapshot:", latestSnapshot?.created)
                                                    if (snapshot.created.getTime() === latestSnapshot?.created.getTime()) {
                                                    // remove filter if latest snapshot was clicked
                                                        displayProjectSince(undefined);
                                                    } else {
                                                        displayProjectSince(snapshot.created)
                                                    }
                                                }
                                                }
                                            />

                                            <Button icon="edit"
                                                title="Edit Snapshot Name"
                                                onClick={(e) => setEditedSnapshot(snapshot)}
                                            />
                                        </ButtonGroup>
                                    </td>
                                    <td>{snapshot.name}</td>
                                    <td style={changedDeviceColStyle}>{renderTableField(snapshot.changelog?.updated ?? [])}</td>
                                    <td style={changedDeviceColStyle}>{renderTableField(snapshot.changelog?.created ?? [])}</td>
                                    <td style={changedDeviceColStyle}>{renderTableField(snapshot.changelog?.deleted ?? [])}</td>
                                    <td className="text-nowrap">{snapshot.author}</td>
                                    <td>{formatToLiccoDateTime(snapshot.created)}</td>
                                </tr>
                            )
                        })}
                    </tbody>
                </table>
            </>
        )
    }, [state.snapshotHistory, selectedTimestamp, latestSnapshot, dialogErr, isLoading, project.name, displayProjectSince])


    return (
        <>
            <Dialog isOpen={isOpen} onClose={onClose} title={`Project History (${project.name})`} autoFocus={true} style={{ width: "100%", maxWidth: "95%", height: "90vh" }}>
                <DialogBody useOverflowScrollContainer style={{ maxHeight: "100%" }}>
                    <Row className="mb-2">
                        <ButtonGroup>
                            <Button
                                text="Last Week"
                                disabled={isLoading}
                                onClick={() => {
                                    const { start, end } = constructTimeBoundaries(new Date(), "lastWeek")
                                    fetchHistory(start, end);
                                }} />
                            <Button text="Last Month"
                                disabled={isLoading}
                                onClick={() => {
                                    const { start, end } = constructTimeBoundaries(new Date(), "lastMonth")
                                    fetchHistory(start, end);
                                }}
                            />
                            <Button text="Last Year"
                                disabled={isLoading}
                                onClick={() => {
                                    const { start, end } = constructTimeBoundaries(new Date(), "lastYear");
                                    fetchHistory(start, end);
                                }}
                            />
                            <Button text="Last 100"
                                disabled={isLoading}
                                onClick={() => {
                                    fetchHistory(undefined, undefined, 100)
                                }} />

                            <span className="me-5"></span>

                            <label className="me-1 d-flex align-items-center" htmlFor="from-input">From:</label>
                            <input className="me-2" id="from-input" type="date" onChange={(e) => {
                                // Implementation Note: we didn't want to trigger a search query on every change 
                                // since when looking between date boundaries the user will generally want to change
                                // both boundaries before searching. If search is slow, we don't want an insta query.
                                const date = e.target.valueAsDate;
                                let newState = Object.assign({}, state);
                                newState.startTime = date ? setTimeBoundary(date, "startDay") : undefined;
                                onStateChange(newState);
                            }} value={state.startTime ? toIsoDate(state.startTime) : ''}></input>

                            <label className="me-1 d-flex align-items-center" htmlFor="to-input">To:</label>
                            <input id="to-input" type="date" className="me-1"
                                onChange={(e) => {
                                    const date = e.target.valueAsDate;
                                    let newState = Object.assign({}, state);
                                    newState.endTime = date ? setTimeBoundary(date, "endDay") : undefined;
                                    onStateChange(newState);
                                }}
                                value={state.endTime ? toIsoDate(state.endTime) : ''}></input>

                            <Button icon="search"
                                disabled={isLoading}
                                onClick={(e) => {
                                    let start = state.startTime;
                                    let end = state.endTime;
                                    if (start && end && (start.getTime() > end.getTime())) {
                                        // start > end, swap the times around and search
                                        let temp = start;
                                        start = setTimeBoundary(end, "startDay");
                                        end = setTimeBoundary(temp, "endDay");
                                    }
                                    fetchHistory(state.startTime, state.endTime);
                                }}>Search</Button>
                        </ButtonGroup>
                    </Row>

                    {projectHistoryTable}
                </DialogBody>
                <DialogFooter actions={
                    <>
                        <Button autoFocus={true} onClick={onClose}>Close</Button>
                    </>
                }>
                </DialogFooter>
            </Dialog >

            {editedSnapshot ?
                <EditSnapshotNameDialog
                    project={project}
                    snapshot={editedSnapshot}
                    isOpen={editedSnapshot !== undefined}
                    onClose={() => setEditedSnapshot(undefined)}
                    onSubmit={(updatedSnapshot) => {
                        // replace the snapshot with an updated snapshot
                        const oldSnapshot = editedSnapshot;
                        let updatedHistory = [];
                        for (const snap of state.snapshotHistory) {
                            if (snap._id !== oldSnapshot._id) {
                                updatedHistory.push(snap);
                                continue;
                            }
                            updatedHistory.push(updatedSnapshot);
                        }

                        // close the dialog
                        let updatedState = Object.assign({}, state)
                        updatedState.snapshotHistory = updatedHistory;
                        onStateChange(updatedState);
                        setEditedSnapshot(undefined);
                    }
                    }
                />
                : null}
        </>
    )
}

export const EditSnapshotNameDialog: React.FC<{
    isOpen: boolean;
    project: ProjectInfo,
    snapshot: ProjectSnapshot,
    onClose: () => void;
    onSubmit: (updatedSnapshot: ProjectSnapshot) => void;
}> = ({ isOpen, project, snapshot, onClose, onSubmit }) => {
    const [submittingForm, setSubmittingForm] = useState(false);
    const [snapshotName, setSnapshotName] = useState("");
    const [dialogErr, setDialogErr] = useState("");

    useEffect(() => {
        if (isOpen) {
            setSnapshotName(snapshot.name);
        }
    }, [isOpen])

    const editSnapshotName = () => {
        if (!project) {
            // in general this should never happen, if it does we have a bug
            setDialogErr(`Project was not found: this is a programming bug`);
            return;
        }

        setSubmittingForm(true);
        let params = new URLSearchParams();
        params.append("name", snapshotName)
        Fetch.post<ProjectSnapshot>(`/ws/projects/${project._id}/snapshots/${snapshot._id}/?${params.toString()}`)
            .then((updatedSnapshot) => {
                updatedSnapshot.created = new Date(updatedSnapshot.created);
                onSubmit(updatedSnapshot);
                setSnapshotName("");
                setDialogErr("");
            }).catch((e) => {
                let err = e as JsonErrorMsg;
                let msg = `Failed to create the a snapshot name: ${err.error}`;
                setDialogErr(msg);
                console.error(msg, e);
            }).finally(() => {
                setSubmittingForm(false);
            });
    };

    return (
        <Dialog onClose={onClose} isOpen={isOpen} title={`Set a Snapshot Name (${snapshot._id})`} autoFocus={true}>
            <DialogBody>
                <FormGroup label="Enter a new Snapshot Name:" labelFor="snapshot-name">
                    <InputGroup id="snapshot-name"
                        placeholder=""
                        value={snapshotName}
                        autoFocus={true}
                        onValueChange={(val: string) => setSnapshotName(val)}
                    />
                </FormGroup>

                {dialogErr ? <p className="error">ERROR: {dialogErr}</p> : null}
            </DialogBody>
            <DialogFooter
                actions={
                    <>
                        <Button onClick={(e) => {
                            setSnapshotName("");
                            onClose();
                        }
                        }>Cancel</Button>
                        <Button intent="primary" loading={submittingForm}
                            onClick={(e) => editSnapshotName()}>
                            Edit Snapshot Name
                        </Button>
                    </>
                }
            />
        </Dialog>
    );
};
