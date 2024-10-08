import { Button, Dialog, DialogBody, DialogFooter, FormGroup, HTMLSelect } from "@blueprintjs/core";
import { useEffect, useState } from "react";
import { Fetch, JsonErrorMsg } from "../utils/fetching";
import { ProjectInfo } from "./project_model";

type projectApprovers = string[];

export const ProjectApprovalDialog: React.FC<{ isOpen: boolean, projectTitle: string, projectId: string, onClose: () => void, onSubmit: (updatedProject: ProjectInfo) => void }> = ({ isOpen, projectTitle, projectId, onClose, onSubmit }) => {
    const DEFAULT_USER = "Please select an approver";
    const [selectedApprover, setSelectedApprover] = useState(DEFAULT_USER);
    const [approvers, setApprovers] = useState<string[]>([]);
    const [submittingForm, setSubmittingForm] = useState(false);
    const [disableSubmit, setDisableSubmit] = useState(true);

    const [dialogErr, setDialogErr] = useState("");

    useEffect(() => {
        if (isOpen) {
            Fetch.get<projectApprovers>('/ws/approvers/')
                .then(projectApprovers => {
                    let approvers = [DEFAULT_USER, ...projectApprovers];
                    setApprovers(approvers);
                }).catch((e) => {
                    let err = e as JsonErrorMsg;
                    let msg = `Failed to fetch project approvers: ${err.error}`;
                    console.error(msg, e);
                    setDialogErr(msg);
                })
        }
    }, [isOpen]);

    useEffect(() => {
        const userNotSelected = !selectedApprover || selectedApprover === DEFAULT_USER;
        const emptyProjectId = !projectId;
        setDisableSubmit(userNotSelected || emptyProjectId);
    }, [selectedApprover, projectId]);


    const submitApprover = () => {
        if (!selectedApprover || selectedApprover == DEFAULT_USER) {
            setDialogErr("Please select a valid approver");
            return;
        }

        if (!projectId) {
            // in general this should never happen, if it does we have a bug
            setDialogErr(`Invalid project id '${projectId}'`);
            return;
        }

        setSubmittingForm(true);
        Fetch.post<ProjectInfo>(`/ws/projects/${projectId}/submit_for_approval?approver=${selectedApprover}`)
            .then((newProject) => {
                onSubmit(newProject);
                setDialogErr('');
            }).catch((e) => {
                let err = e as JsonErrorMsg;
                let msg = `Failed to submit the '${selectedApprover}' for approver: ${err.error}`;
                setDialogErr(msg);
                console.error(msg, e);
            }).finally(() => {
                setSubmittingForm(false);
            });
    }

    return (
        <Dialog onClose={onClose} isOpen={isOpen} title={`Submit Project for Approval (${projectTitle})`}>
            <DialogBody>
                <FormGroup>
                    <HTMLSelect
                        value={selectedApprover}
                        options={approvers}
                        onChange={(e) => setSelectedApprover(e.target.value)}
                    />
                </FormGroup>

                {dialogErr ? <p className="error">ERROR: {dialogErr}</p> : null}
            </DialogBody>
            <DialogFooter actions={
                <>
                    <Button onClick={(e) => onClose()} disabled={submittingForm}>Cancel</Button>
                    <Button intent="primary"
                        loading={submittingForm}
                        disabled={disableSubmit}
                        onClick={(e) => submitApprover()}
                    >Submit for Approval</Button>
                </>
            } />
        </Dialog>
    )
}