import { Alert, Button, ButtonGroup, Colors, Dialog, DialogBody, DialogFooter, FormGroup, Icon, InputGroup, NonIdealState, Spinner } from "@blueprintjs/core";
import React, { useEffect, useState } from "react";
import { FFTInfo, deleteFft, fetchFfts } from "../projects/project_model";
import { JsonErrorMsg } from "../utils/fetching";
import { sortString } from "../utils/sort_utils";
import { StringSuggest } from "../components/suggestion_field";

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



export const AddFftDialog: React.FC<{ isOpen: boolean, ffts?: FFTInfo[], currentProject: string, dialogType: 'addToProject' | 'create', onClose: () => void, onSubmit: (fft: FFTInfo) => void }> = ({ isOpen, ffts, currentProject, dialogType, onClose, onSubmit }) => {
    const [fcName, setFcName] = useState('');
    const [fgName, setFgName] = useState('');
    const [allFfts, setAllFfts] = useState<FFTInfo[]>([]);

    const [dialogError, setDialogError] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const [fcNames, setFcNames] = useState(new Set<string>([
        'AT1L0', 'AT2L0',   'BS1L0', 'BS1L1', 'BS2L1',  'BS3L0',   'BS4L0',  'BT1L0',  'BT1L1', 'BT2L0', 
        'BT2L1', 'BT3L0',   'BT3L1', 'BT4L0', 'BT5L0',  'BTM2',    'BTM3',   'EM1L0',  'EM2L0', 'EM3L0', 
        'IM1L0', 'IM1L1',   'IM2L0', 'IM3L0', 'IM4L0',  'MBTMSFT', 'MBXPM1', 'MBXPM2', 'MR1L0', 'MR1L1', 
        'MR2L0', 'MSFTDMP', 'ND1H',  'PA1L0', 'PC1L0',  'PC1L1',   'PC2L0',  'PC2L1',  'PC3L0', 'PC3L1', 
        'PC4L0', 'PCPM2',   'PCPM3', 'PF1L0', 'RTDSL0', 'SL1L0',   'SL2L0',  'SL3L0',  'SP1L0', 'ST1L0', 
        'ST1L1', 'TP',      'TV1L0', 'TV1L1', 'TV2L0',  'TV3L0'
    ]))

    const createFgFcNames = (ffts: FFTInfo[]) => {
        let fcSet = new Set<string>();

        for (let fft of ffts) {
            let fcName = fft.fc.name;
            if (fcName != "") {
                fcSet.add(fcName);
            }
        }

        // setFcNames(fcSet);
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
                if (fft.fc.name == fc) {
                    // the chosen combination already exists, so there is nothing 
                    // to create. Simply return
                    onSubmit(fft)
                    return;
                }
            }

            // chosen fc-fg name combination was not found, therefore we have to create
            // a new one.
        }

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
                        <StringSuggest value={fcName} setValue={setFcName} items={Array.from(fcNames.values()).sort((a, b) => sortString(a, b, false))} 
                            inputProps={{ 
                                id: "fc-name", 
                                autoFocus: true,
                                rightElement: <Icon className="ps-2 pe-2" icon="caret-down" color={Colors.GRAY1} /> 
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