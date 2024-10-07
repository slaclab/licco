import { Button, Dialog, DialogBody, DialogFooter, FormGroup, HTMLSelect } from "@blueprintjs/core";
import { useEffect, useState } from "react";
import { Fetch } from "../utils/fetching";
import { ProjectInfo } from "./project_model";

type projectApprovers = string[];

export const ProjectApprovalDialog: React.FC<{ isOpen: boolean, projectTitle: string, projectId: string, onClose: () => void, onSubmit: (updatedProject: ProjectInfo) => void }> = ({ isOpen, projectTitle, projectId, onClose, onSubmit }) => {
    const DEFAULT_USER = "Please select an approver";
    const [selectedUser, setSelectedUser] = useState(DEFAULT_USER);
    const [approvers, setApprovers] = useState<string[]>([]);
    const [submittingForm, setSubmittingForm] = useState(false);
    const [disableSubmit, setDisableSubmit] = useState(true);

    useEffect(() => {
        Fetch.get<projectApprovers>('/ws/approvers/')
            .then(projectApprovers => {
                let approvers = [DEFAULT_USER, ...projectApprovers];
                setApprovers(approvers);
            }).catch((e) => {
                // TODO: handle error message
                console.error("ERROR:", e);
            })
    }, []);

    useEffect(() => {
        const userNotSelected = !selectedUser || selectedUser === DEFAULT_USER;
        const emptyProjectId = !projectId;
        setDisableSubmit(userNotSelected || emptyProjectId);
    }, [selectedUser, projectId]);


    const submitApprover = () => {
        if (!selectedUser || selectedUser == DEFAULT_USER) {
            // TODO: display an error message
            return;
        }

        if (!projectId) {
            // TODO: display an error message
            return;
        }

        setSubmittingForm(true);
        Fetch.post<ProjectInfo>(`/ws/projects/${projectId}/submit_for_approval?approver=${selectedUser}`)
            .then((newProject) => {
                onSubmit(newProject);
            }).catch((e) => {
                // TODO: handle error message
                console.error("Failed to submit the user for approver: ", e);
            }).finally(() => {
                setSubmittingForm(false);
            });
    }

    return (
        <Dialog onClose={onClose} isOpen={isOpen} title={`Submit for Approval (${projectTitle})`}>
            <DialogBody>
                <FormGroup>
                    <HTMLSelect
                        value={selectedUser}
                        options={approvers}
                        onChange={(e) => setSelectedUser(e.target.value)}
                    />
                </FormGroup>
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