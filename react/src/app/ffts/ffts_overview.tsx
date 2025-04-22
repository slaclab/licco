import { Alert, Button, ButtonGroup, Colors, Dialog, DialogBody, DialogFooter, FormGroup, Icon, InputGroup, NonIdealState, Spinner } from "@blueprintjs/core";
import React, { useEffect, useState } from "react";
import { FFTInfo, deleteFft, fetchFfts } from "../projects/project_model";
import { Fetch, JsonErrorMsg } from "../utils/fetching";
import { sortString } from "../utils/sort_utils";

export const FFTOverviewTable: React.FC = () => {
    const [data, setData] = useState<FFTInfo[]>([]);
    const [isFftDialogOpen, setIsFftDialogOpen] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [loadingError, setLoadingError] = useState('');

    const [fftToDelete, setFftToDelete] = useState<FFTInfo>();
    const [deleteError, setDeleteError] = useState('');

    const deleteSelectedFft = (fftToDelete: FFTInfo) => {
        deleteFft(fftToDelete._id)
            .then(() => {
                setDeleteError('');
                setFftToDelete(undefined);

                // remove this fft from the list of ffts
                let updatedData = data.filter(data => data._id != fftToDelete._id);
                setData(updatedData);
            }).catch((e: JsonErrorMsg) => {
                setDeleteError("Failed to delete FFT: " + e.error);
            })
    }

    useEffect(() => {
        setIsLoading(true);
        fetchFfts()
            .then(data => setData(data))
            .catch((e: JsonErrorMsg) => {
                let msg = "Failed to fetch ffts data: " + e.error;
                setLoadingError(msg);
                console.error(msg, e);
            })
            .finally(() => {
                setIsLoading(false);
            })
    }, [])

    if (loadingError && !isLoading) {
        return <NonIdealState icon="error" title="Error" description={loadingError} />
    }

    return (
        <>
            <table className="table table-striped table-bordered table-sm table-sticky">
                <thead>
                    <tr>
                        <th scope="col" className="text-nowrap">
                            <ButtonGroup>
                                <Button icon="add" title="Add a new FC" size="small" variant="minimal"
                                    onClick={e => setIsFftDialogOpen(true)}
                                />
                                {isLoading ? <Button loading={isLoading} variant="minimal" /> : null}
                            </ButtonGroup>
                        </th>
                        <th scope="col" className="">Functional component name</th>
                        <th scope="col" className="">Fungible token</th>
                    </tr>
                </thead>
                <tbody>
                    {data ?
                        data.map((fft) => {
                            return (
                                <tr key={fft._id}>
                                    <td>{fft.is_being_used ? null :
                                        <Button icon="trash" title="Delete this FFT from the system" size="small" variant="minimal"
                                            onClick={e => setFftToDelete(fft)} />
                                    }
                                    </td>
                                    <td>{fft.fc.name}</td>
                                    <td>{fft.fg.name}</td>
                                </tr>
                            )
                        })
                        :
                        <tr><td></td><td colSpan={2}> No data available</td></tr>
                    }
                </tbody>
            </table>

            <AddFftDialog isOpen={isFftDialogOpen}
                dialogType="create"
                ffts={data}
                onClose={() => setIsFftDialogOpen(false)}
                onSubmit={(fft) => {
                    let updatedFfts = [...data, fft];
                    setData(updatedFfts);
                    setIsFftDialogOpen(false)
                }}
            />

            {fftToDelete ?
                <Alert
                    canEscapeKeyCancel={true}
                    icon={"trash"}
                    cancelButtonText="Cancel"
                    confirmButtonText="Delete"
                    onConfirm={(e) => deleteSelectedFft(fftToDelete)}
                    onCancel={e => setFftToDelete(undefined)}
                    intent="danger"
                    isOpen={fftToDelete != undefined}
                >
                    <h5 className="alert-title">Delete FFT?</h5>
                    <p>Do you want to delete <b>{fftToDelete.fc.name}-{fftToDelete.fg.name}</b>?</p>

                    {deleteError ?
                        <NonIdealState icon="error" title="ERROR" description={deleteError} />
                        : null
                    }
                </Alert>
                : null
            }
        </>
    )
}



export const AddFftDialog: React.FC<{ isOpen: boolean, ffts?: FFTInfo[], dialogType: 'addToProject' | 'create', onClose: () => void, onSubmit: (fft: FFTInfo) => void }> = ({ isOpen, ffts, dialogType, onClose, onSubmit }) => {
    const [fcName, setFcName] = useState('');
    const [fgName, setFgName] = useState('');
    const [allFfts, setAllFfts] = useState<FFTInfo[]>([]);

    const [dialogError, setDialogError] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const [fcNames, setFcNames] = useState<Set<string>>(new Set());

    const createFgFcNames = (ffts: FFTInfo[]) => {
        let fcSet = new Set<string>();

        for (let fft of ffts) {
            let fcName = fft.fc.name;
            if (fcName != "") {
                fcSet.add(fcName);
            }
        }

        setFcNames(fcSet);
        setFgName('');
    }

    useEffect(() => {
        if (!isOpen) {
            return;
        }

        // ffts were provided, nothing to do
        if (ffts != undefined) {
            createFgFcNames(ffts);
            setAllFfts(ffts);
            return;
        }

        // ffts were not provided, download them on our own
        setIsLoading(true);
        fetchFfts()
            .then(data => {
                createFgFcNames(data);
                setAllFfts(data);
                setDialogError('');
            }).catch((e: JsonErrorMsg) => {
                let msg = "Failed to fetch FFTs: " + e.error;
                setDialogError(msg);
            }).finally(() => {
                setIsLoading(false)
            });
    }, [ffts, isOpen])


    const disableSubmit = fcName.trim() == "";

    const submit = () => {
        const fc = fcName.trim();
        const fg = fgName.trim();

        if (dialogType === 'addToProject') {
            // check if the chosen combination of fc-fg name already exists in provided data
            // if it does, we simply return an existing fft. This is a special behavior
            // when we are adding an fft to a project that doesn't already have such fft 
            // assigned.
            for (let fft of allFfts) {
                if (fft.fc.name == fc && fft.fg.name == fg) {
                    // the chosen combination already exists, so there is nothing 
                    // to create. Simply return
                    onSubmit(fft)
                    return;
                }
            }

            // chosen fc-fg name combination was not found, therefore we have to create
            // a new one.
        }

        let data: any = {
            fc: fc,
            fg: fg,
        }

        setIsSubmitting(true);
        Fetch.post<FFTInfo>("/ws/ffts/", { body: JSON.stringify(data) })
            .then((resp) => {
                onSubmit(resp);
            }).catch((e: JsonErrorMsg) => {
                let msg = "Failed to create new fft: " + e.error;
                setDialogError(msg)
                console.error(msg, e);
            }).finally(() => {
                setIsSubmitting(false);
            })
    }

    return (
        <Dialog isOpen={isOpen} onClose={onClose} title="Add a New FC" autoFocus={true} style={{ width: "70ch" }}>
            <DialogBody useOverflowScrollContainer>
                <p>Please choose/enter a functional component name.
                    You can choose one of the existing entities or you can type in a brand new functional component name.
                </p>

                {isLoading ?
                    <NonIdealState icon={<Spinner />} title="Loading" description="Please Wait..." />
                    :
                    <>
                        <datalist id="fc-names-list">
                            {Array.from(fcNames.values()).sort((a, b) => sortString(a, b, false)).map(name => {
                                return <option key={name} value={name} />
                            })
                            }
                        </datalist>

                        <FormGroup label="Functional Component:" labelFor="fc-name">
                            <InputGroup id="fc-name"
                                autoFocus={true}
                                list="fc-names-list"
                                placeholder=""
                                value={fcName}
                                rightElement={<Icon className="ps-2 pe-2" icon="caret-down" color={Colors.GRAY1} />}
                                onValueChange={(val: string) => setFcName(val)} />
                        </FormGroup>

                    </>
                }

            </DialogBody>
            <DialogFooter actions={
                <>
                    <Button onClick={(e) => onClose()}>Cancel</Button>
                    <Button onClick={(e) => submit()} intent="primary" loading={isSubmitting} disabled={disableSubmit}>Create FC</Button>
                </>
            }>
                {dialogError ? <p className="error">ERROR: {dialogError}</p> : null}
            </DialogFooter>
        </Dialog>
    )
}