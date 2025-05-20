import { Button, Dialog, DialogBody, DialogFooter, FormGroup, HTMLSelect, NonIdealState, Spinner } from "@blueprintjs/core";
import React, { useEffect, useMemo, useState } from "react";
import { StringSuggest } from "../components/suggestion_field";
import { FFTInfo, fetchFcs, fetchProjectDevices } from "../projects/project_model";
import { calculateValidFcs } from "../utils/fc_utils";
import { JsonErrorMsg } from "../utils/fetching";
import { DeviceType, deviceTypes } from "../projects/device_model";


export const AddFftDialog: React.FC<{ isOpen: boolean, fcs?: string[], currentProject: string, dialogType: 'addToProject' | 'create', onClose: () => void, onSubmit: (fft: FFTInfo) => void }> = ({ isOpen, fcs, currentProject, dialogType, onClose, onSubmit }) => {
    const [fcName, setFcName] = useState('');
    const [fgName, setFgName] = useState('');
    const [deviceType, setDeviceType] = useState(DeviceType.MCD);
    const [allFcs, setAllFcs] = useState<string[]>([]);
    const [usedFcs, setUsedFcs] = useState<string[]>([]);

    const [dialogError, setDialogError] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);

    useEffect(() => {
        if (!isOpen) {
            setFcName('');
            setDeviceType(DeviceType.MCD);
            return;
        }

        // fcs were provided, nothing to do
        if (fcs != undefined) {
            return;
        }

        // fcs were not provided, download them on our own
        setIsLoading(true);

        const p1 = fetchProjectDevices(currentProject)
            .then(devices =>
                setUsedFcs(devices.map(device => device.fc))
            );
        const p2 = fetchFcs()
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
    }, [isOpen, currentProject, fcs])


    const disableSubmit = fcName.trim() == "" || deviceType == 0;

    const submit = () => {
        const fc = fcName.trim();
        const fg = fgName.trim();

        // TODO: refactor this, we are no longer using this
        let data: FFTInfo = {
            fc: { _id: '', name: fc, description: '' },
            fg: { _id: '', name: fg, description: '' },
            device_type: deviceType,
            is_being_used: false,
            _id: currentProject
        }

        setIsSubmitting(true);
        onSubmit(data);
        setIsSubmitting(false);
    }

    const fcList = useMemo(() => {
        if (fcs != undefined) {
            return fcs;
        }
        return calculateValidFcs(allFcs, usedFcs)
    }, [fcs, allFcs, usedFcs])

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
                        <FormGroup label="Functional Component:" labelFor="fc-name">
                            <StringSuggest value={fcName} setValue={setFcName} items={fcList} 
                                inputProps={{ 
                                    id: "fc-name", 
                                    autoFocus: true,
                                }} 
                            />
                        </FormGroup>
                    
                        <FormGroup label="Device Type:" labelFor="device-type">
                            <HTMLSelect id="device-type" options={deviceTypes} value={deviceType} onChange={e => setDeviceType(parseInt(e.currentTarget.value))}
                                disabled={true} 
                                />
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