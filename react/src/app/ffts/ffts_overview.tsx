import { Alert, Button, ButtonGroup, Colors, Dialog, DialogBody, DialogFooter, FormGroup, Icon, InputGroup, NonIdealState } from "@blueprintjs/core";
import React, { useEffect, useState } from "react";
import { Fetch, JsonErrorMsg } from "../utils/fetching";
import { sortString } from "../utils/sort_utils";

interface FFT {
    _id: string;
    is_being_used: boolean;
    fc: FC;
    fg: FG;
}

interface FC {
    _id: string;
    name: string;
    description: string;
}

interface FG {
    _id: string;
    name: string;
    description: string;
}

function deleteFft(fftId: string): Promise<void> {
    return Fetch.delete<void>(`/ws/ffts/${fftId}`);
}

export const FFTOverviewTable: React.FC = () => {
    const [data, setData] = useState<FFT[]>([]);
    const [isFftDialogOpen, setIsFftDialogOpen] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [loadingError, setLoadingError] = useState('');

    const [fftToDelete, setFftToDelete] = useState<FFT>();
    const [deleteError, setDeleteError] = useState('');

    const deleteSelectedFft = (fftToDelete: FFT) => {
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
        Fetch.get<FFT[]>("/ws/ffts/")
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
                                <Button icon="add" title="Add a new FFT" small={true} minimal={true}
                                    onClick={e => setIsFftDialogOpen(true)}
                                />
                            </ButtonGroup>
                        </th>
                        <th scope="col" className="">Functional component name {isLoading ? <Button loading={isLoading} minimal={true} /> : null}</th>
                        <th scope="col" className="">Fungible token</th>
                    </tr>
                </thead>
                <tbody>
                    {data ?
                        data.map((fft) => {
                            return (
                                <tr key={fft._id}>
                                    <td>{fft.is_being_used ? null :
                                        <Button icon="trash" title="Delete this FFT from the system" small={true} minimal={true}
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

            <AddFfftDialog isOpen={isFftDialogOpen}
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



export const AddFfftDialog: React.FC<{ isOpen: boolean, ffts: FFT[], onClose: () => void, onSubmit: (fft: FFT) => void }> = ({ isOpen, ffts, onClose, onSubmit }) => {
    const [fcName, setFcName] = useState('');
    const [fgName, setFgName] = useState('');

    const [dialogError, setDialogError] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);


    const [fcNames, setFcNames] = useState<Set<string>>(new Set());
    const [fcDescription, setFcDescription] = useState('');

    const [fgNames, setFgNames] = useState<Set<string>>(new Set());
    const [fgDescription, setFgDescription] = useState('');

    useEffect(() => {
        let fcSet = new Set<string>();
        let fgSet = new Set<string>();

        for (let fft of ffts) {
            let fcName = fft.fc.name;
            if (fcName != "") {
                fcSet.add(fcName);
            }

            let fgName = fft.fg.name;
            if (fgName != "") {
                fgSet.add(fgName);
            }
        }

        setFcNames(fcSet);
        setFgNames(fgSet);
    }, [ffts])


    const renderFcDescription = fcName != "" && !fcNames.has(fcName);
    const renderFgDescription = fgName != "" && !fgNames.has(fgName);
    const disableSubmit = fcName.trim() == "" || fgName.trim() == "" || (renderFcDescription && fcDescription.trim() == "" || renderFgDescription && fgDescription.trim() == "");

    const submit = () => {
        let data: any = {
            fc: fcName,
            fg: fgName,
        }
        if (renderFcDescription) {
            data["fc_description"] = fcDescription;
        }
        if (renderFgDescription) {
            data["fg_description"] = fgDescription;
        }

        setIsSubmitting(true);
        Fetch.post<FFT>("/ws/ffts/", { body: JSON.stringify(data) })
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
        <Dialog isOpen={isOpen} onClose={onClose} title="Add a new FFT" autoFocus={true} style={{ width: "70ch" }}>
            <DialogBody useOverflowScrollContainer>
                <p>Please choose/enter a functional component name and fungible token.
                    You can choose one of the existing entities or you can type in a brand new functional component name or fungible token.
                </p>
                <p>If either entity does not exist in the system, description inputs will be enabled. Please enter a valid description; and these will be automatically created in the system for you as part of creating the new FFT.</p>

                <datalist id="fc-names-list">
                    {Array.from(fcNames.values()).sort((a, b) => sortString(a, b, false)).map(name => {
                        return <option key={name} value={name} />
                    })
                    }
                </datalist>

                <datalist id="fg-names-list">
                    {Array.from(fgNames.values()).sort((a, b) => sortString(a, b, false)).map(name => {
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

                <FormGroup label="FC Description:" labelInfo="(required)" labelFor="fc-description"
                    disabled={!renderFcDescription}>
                    <InputGroup id="fc-description"
                        disabled={!renderFcDescription}
                        value={fcDescription}
                        onValueChange={(val: string) => setFcDescription(val)}
                    />
                </FormGroup>

                <FormGroup label="Fungible Token:" labelFor="fg-name" className="mt-4">
                    <InputGroup id="fg-name"
                        list="fg-names-list"
                        rightElement={<Icon className="ps-2 pe-2" icon="caret-down" color={Colors.GRAY1} />}
                        value={fgName}
                        onValueChange={(val: string) => setFgName(val)} />
                </FormGroup>

                <FormGroup label="FG Description:" labelInfo="(required)" labelFor="fg-description"
                    disabled={!renderFgDescription}>
                    <InputGroup id="fg-description"
                        disabled={!renderFgDescription}
                        value={fgDescription}
                        onValueChange={(val: string) => setFgDescription(val)}
                    />
                </FormGroup>

            </DialogBody>
            <DialogFooter actions={
                <>
                    <Button onClick={(e) => onClose()}>Cancel</Button>
                    <Button onClick={(e) => submit()} intent="primary" loading={isSubmitting} disabled={disableSubmit}>Create FFT</Button>
                </>
            }>
                {dialogError ? <p className="error">ERROR: {dialogError}</p> : null}
            </DialogFooter>
        </Dialog>
    )
}