import { Alert, Button, ButtonGroup, Dialog, DialogBody, DialogFooter, FormGroup, NonIdealState, Spinner } from "@blueprintjs/core";
import React, { useEffect, useMemo, useState } from "react";
import { FFTInfo, deleteFft, fetchFcs, fetchProjectFfts } from "../projects/project_model";
import { JsonErrorMsg } from "../utils/fetching";
import { StringSuggest } from "../components/suggestion_field";
import { calculateValidFcs } from "../utils/fc_utils";

export const FFTOverviewTable: React.FC = () => {
    const [fcs, setFcs] = useState<string[]>([]);
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
        fetchFcs()
            .then(fcs => setFcs(fcs))
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
                fcs={fcs}
                currentProject=""
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



export const AddFftDialog: React.FC<{ isOpen: boolean, fcs?: string[], currentProject: string, dialogType: 'addToProject' | 'create', onClose: () => void, onSubmit: (fft: FFTInfo) => void }> = ({ isOpen, fcs, currentProject, dialogType, onClose, onSubmit }) => {
    const [fcName, setFcName] = useState('');
    const [fgName, setFgName] = useState('');
    const [allFcs, setAllFcs] = useState<string[]>([]);
    const [usedFcs, setUsedFcs] = useState<string[]>([]);

    const [dialogError, setDialogError] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);

    useEffect(() => {
        if (!isOpen) {
            setFcName('');
            return;
        }

        // fcs were provided, nothing to do
        if (fcs != undefined) {
            setAllFcs(fcs);
            return;
        }

        // fcs were not provided, download them on our own
        setIsLoading(true);

        var p1 = fetchProjectFfts(currentProject)
            .then(ffts => 
                setUsedFcs(ffts.map(fft => fft.fc))
            );
        var p2 = fetchFcs()
            .then(fcs => {
                setAllFcs(fcs);
                setDialogError('');
            });
        Promise.all([p1, p2])
            .catch((e: JsonErrorMsg) => {
                let msg = "Failed to fetch FFTs: " + e.error;
                setDialogError(msg);
            }).finally(() => {
                setIsLoading(false)
            });
    }, [isOpen])


    const disableSubmit = fcName.trim() == "";

    const submit = () => {
        const fc = fcName.trim();
        const fg = fgName.trim();

        // TODO: refactor this, we are no longer using this
        let data: FFTInfo = {
            fc: { _id: '', name: fc, description: '' },
            fg: { _id: '', name: fg, description: '' },
            is_being_used: false,
            _id: currentProject
        }

        setIsSubmitting(true);
        onSubmit(data);
        setIsSubmitting(false);
    }

    const fcList = useMemo(() => {
        return calculateValidFcs(allFcs, usedFcs)
    }, [allFcs, usedFcs])

    return (
        <Dialog isOpen={isOpen} onClose={onClose} title="Add a New FC" autoFocus={true} style={{ width: "70ch" }}>
            <DialogBody useOverflowScrollContainer>
                <p>Please choose/enter a functional component name.
                    You can choose one of the existing entities or you can type in a brand new functional component name.
                </p>

                {isLoading ?
                    <NonIdealState icon={<Spinner />} title="Loading" description="Please Wait..." />
                    :
                    <FormGroup label="Functional Component:" labelFor="fc-name">
                        <StringSuggest value={fcName} setValue={setFcName} items={fcList} 
                            inputProps={{ 
                                id: "fc-name", 
                                autoFocus: true,
                            }} 
                        />
                    </FormGroup>
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