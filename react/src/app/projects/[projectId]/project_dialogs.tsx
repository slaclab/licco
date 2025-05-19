import { formatToLiccoDateTime } from "@/app/utils/date_utils";
import { Fetch, JsonErrorMsg } from "@/app/utils/fetching";
import { sortString } from "@/app/utils/sort_utils";
import { Button, Checkbox, Colors, Dialog, DialogBody, DialogFooter, FormGroup, HTMLSelect, Icon, InputGroup, Label, NonIdealState, Spinner, Text, TextArea } from "@blueprintjs/core";
import { useEffect, useMemo, useState } from "react";
import { ButtonGroup } from "react-bootstrap";
import { DeviceState, ProjectDeviceDetails, ProjectInfo, ProjectSnapshot, Tag, addDeviceComment, deviceDetailsBackendToFrontend, fetchAllProjectsInfo, fetchDeviceDataByName, fetchHistoryOfChanges, isProjectApproved, isProjectInDevelopment, isProjectSubmitted, isUserAProjectApprover, isUserAProjectEditor, syncDeviceUserChanges } from "../project_model";
import { renderTableField } from "../project_utils";
import { CollapsibleProjectNotes } from "../projects_overview";
import { DeviceValueDiff, diffDeviceFields } from "./diff/project_diff_model";


// this dialog is used for filtering the table (fc, fg, and based on state)
export const FilterDeviceDialog: React.FC<{
  isOpen: boolean;
  possibleStates: DeviceState[];
  onClose: () => void;
  onSubmit: (
    newFcFilter: string,
    newFgFilter: string,
    newStateFilter: string
  ) => void;
}> = ({ isOpen, possibleStates, onClose, onSubmit }) => {
  const [fcFilter, setFcFilter] = useState("");
  const [fgFilter, setFgFilter] = useState("");
  const [stateFilter, setStateFilter] = useState("");

  const submitSearchForm = () => {
    onSubmit(fcFilter, fgFilter, stateFilter);
  };

  const submitOnEnter = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      submitSearchForm();
    }
  };

  const availableStates = useMemo(() => {
    return ["---- Any ----", ...possibleStates.map((s) => s.name)];
  }, [possibleStates]);

  return (
    <Dialog
      isOpen={isOpen}
      onClose={onClose}
      title="Apply Filter to Table"
      autoFocus={true}
    >
      <DialogBody useOverflowScrollContainer>
        <Text>Note: You can filter on a partial match with the wildcard character * {"\n"}For example, you can filter FCs with AT*, or *L0</Text>
        <FormGroup label="FC:" labelFor="fc-filter">
          <InputGroup
            id="fc-filter"
            placeholder="Use GLOB pattern to filter on FC name"
            value={fcFilter}
            onKeyUp={submitOnEnter}
            autoFocus={true}
            onValueChange={(val: string) => setFcFilter(val)}
          />
        </FormGroup>

        <FormGroup label="FG:" labelFor="fg-filter">
          <InputGroup
            id="fg-filter"
            placeholder="Use GLOB pattern to filter on FG name"
            value={fgFilter}
            onKeyUp={submitOnEnter}
            onValueChange={(val: string) => setFgFilter(val)}
          />
        </FormGroup>

        <FormGroup label="State:" labelFor="state-filter">
          <HTMLSelect
            id="state-filter"
            value={stateFilter}
            options={availableStates}
            onChange={(e) => setStateFilter(e.currentTarget.value)}
            fill={true}
            iconName="caret-down"
          />
        </FormGroup>
      </DialogBody>
      <DialogFooter
        actions={
          <>
            <Button onClick={onClose}>Cancel</Button>
            <Button onClick={(e) => submitSearchForm()} intent="primary">
              Search
            </Button>
          </>
        }
      ></DialogFooter>
    </Dialog>
  );
};


// this dialog is used to copy the device values from a different project
export const CopyDeviceValuesDialog: React.FC<{ isOpen: boolean, currentProject: ProjectInfo, selectedDevice: ProjectDeviceDetails, onClose: () => void, onSubmit: (updatedDeviceData: ProjectDeviceDetails) => void }> = ({ isOpen, currentProject, selectedDevice, onClose, onSubmit }) => {
  const DEFAULT_PROJECT = "Please select a project"
  const [availableProjects, setAvailableProjects] = useState<ProjectInfo[]>([]);
  const [projectNames, setProjectNames] = useState<string[]>([DEFAULT_PROJECT]);
  const [selectedProject, setSelectedProject] = useState<string>(DEFAULT_PROJECT);

  const [dialogErr, setDialogErr] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [fetchingProjectDiff, setFetchingProjectDiff] = useState(false);
  const [missingFFTOnOtherProject, setMissingFFTOnOtherProject] = useState(false);

  const [changedFields, setChangedFields] = useState<DeviceValueDiff[]>([]);
  const [fieldsToCopy, setFieldsToCopy] = useState<boolean[]>([]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    fetchAllProjectsInfo()
      .then((projects) => {
        let allProjects = projects.filter(p => {
          return isProjectSubmitted(p) || isProjectApproved(p) || isProjectInDevelopment(p);
        }).filter(p => p.name !== currentProject.name);
        allProjects.sort((a, b) => sortString(a.name, b.name, false));
        setAvailableProjects(allProjects);
        setProjectNames([DEFAULT_PROJECT, ...allProjects.map(p => p.name)]);
        setDialogErr("");
      }).catch((e: JsonErrorMsg) => {
        console.error("failed to fetch project data:", e);
        let msg = `Failed to fetch project data: ${e.error}`;
        setDialogErr(msg);
      })
  }, [isOpen, currentProject.name]);


  // query for fft changes between chosen from/to projects
  useEffect(() => {
    if (!isOpen) {
      return;
    }

    if (selectedProject === DEFAULT_PROJECT) {
      setChangedFields([]);
      return;
    }

    let projectToCopyFrom = availableProjects.filter(p => p.name === selectedProject)[0];
    // query if there is any change between fft of selected project 
    // and fft of a new project 
    // 
    // We should be able to abort the query if necessary 
    setFetchingProjectDiff(true);
    fetchDeviceDataByName(projectToCopyFrom._id, selectedDevice.fc)
      .then((deviceFromOtherProject) => {
        // TODO: if device is of a different type, we should show the warning before the table
        // (device is of a different type: Mirror -> Aperture)
        // * Fields that will be automatically copied: [field_names]
        // * Fields that will be automatically removed: [field_names]
        const differentDevice = selectedDevice.device_type != deviceFromOtherProject.device_type;

        const diff = diffDeviceFields(selectedDevice, deviceFromOtherProject);
        setChangedFields(diff);
        setMissingFFTOnOtherProject(false);
        setDialogErr("");
      }).catch((e: JsonErrorMsg) => {
        if (e.code == 404) {
          // this device does not exist in the other project, show the missing fft icon
          setMissingFFTOnOtherProject(true);
          setDialogErr("");
          return;
        }

        let msg = "Failed to fetch project diff: " + e.error;
        setDialogErr(msg);
        console.error(msg, e);
      }).finally(() => {
        setFetchingProjectDiff(false);
      })
  }, [selectedProject, selectedDevice, isOpen, availableProjects, currentProject._id])

  // clear the checkboxes whenever fft diff changes
  useEffect(() => {
    let changed = changedFields.map(f => false);
    setFieldsToCopy(changed);
  }, [changedFields])

  const numOfFFTChanges = useMemo(() => {
    let count = 0;
    for (let selected of fieldsToCopy) {
      if (selected) {
        count++;
      }
    }
    return count
  }, [fieldsToCopy]);


  // button submit action
  const submit = () => {
    if (selectedProject === DEFAULT_PROJECT) {
      setDialogErr("Invalid project selected");
      return;
    }

    if (changedFields.length == 0) {
      // this should never happen
      setDialogErr("Can't copy from unknown changed ffts: this is a programming bug");
      return;
    }

    setSubmitting(true);

    const project = availableProjects.filter(p => p.name == selectedProject)[0];
    const projectIdToCopyFrom = project._id;

    const attributeNamesToCopy = changedFields.filter((_, i) => {
      if (fieldsToCopy[i]) { // this field/value was selected for copying by the end user via a checkbox
        return true;
      }
      return false;
    }).map(diff => diff.fieldName);

    const projectIdToCopyTo = currentProject._id;
    const data = {
      'src_project': projectIdToCopyFrom,
      'dest_project': projectIdToCopyTo,
      'fc': selectedDevice.fc,
      'attrnames': attributeNamesToCopy
    }

    Fetch.post<ProjectDeviceDetails>(`/ws/projects/copy_from_project`,
      { body: JSON.stringify(data) }
    ).then(updatedDeviceData => {
      onSubmit(deviceDetailsBackendToFrontend(updatedDeviceData));
    }).catch((e: JsonErrorMsg) => {
      let msg = `Failed to copy fft changes of ${selectedDevice.fc}-${selectedDevice.fg}: ${e.error}`;
      setDialogErr(msg);
      console.error(msg, e);
    }).finally(() => {
      setSubmitting(false);
    })
  }

  const allChangesAreSelected = numOfFFTChanges == fieldsToCopy.length;

  // render fft diff table
  const renderDiffTable = () => {
    if (selectedProject === DEFAULT_PROJECT) {
      return <NonIdealState icon={"search"} title="No Project Selected" description={"Please select a project"} />
    }

    if (fetchingProjectDiff) {
      return <NonIdealState icon={<Spinner />} title="Loading" description={'Please Wait'} />
    }

    if (missingFFTOnOtherProject) {
      return <NonIdealState icon={'warning-sign'} title="Missing FFT" description={`${selectedDevice.fc}-${selectedDevice.fg} does not exist on selected project ${selectedProject}`} />
    }

    if (changedFields.length == 0) {
      // there is no fft difference between projects
      return <NonIdealState icon={"clean"} title="No Changes" description={"All FFT values are equal between compared projects"} />
    }

    return (
      <>
        <h6>FFT Value Changes:</h6>
        <table className="table table-bordered table-striped table-sm">
          <thead>
            <tr>
              <th>Name</th>
              <th>Current Value</th>
              <th></th>
              <th>New Value</th>
              <th>
                <Checkbox className="table-checkbox"
                  checked={allChangesAreSelected}
                  onChange={(e) => {
                    if (allChangesAreSelected) {
                      let unselectAll = fieldsToCopy.map(_ => false);
                      setFieldsToCopy(unselectAll);
                    } else {
                      let selectAll = fieldsToCopy.map(_ => true);
                      setFieldsToCopy(selectAll);
                    }
                  }
                  } />
              </th>
            </tr>
          </thead>
          <tbody>
            {changedFields.map((change, i) => {
              return (<tr key={`${change.fieldName}`}>
                <td>{change.fieldName}</td>
                <td>{renderTableField(change.oldVal)}</td>
                <td className="text-center"><Icon icon="arrow-right" color={Colors.GRAY1}></Icon></td>
                <td>{renderTableField(change.newVal)}</td>
                <td>
                  {/* note: leave the comparison === true, otherwise the React will complain about controlled
                      and uncontrolled components. I think this is a bug in the library and not the issue with our code,
                      since our usage of controlled component is correct here
                    */}
                  <Checkbox className="table-checkbox"
                    checked={fieldsToCopy[i] === true} value={''}
                    onChange={(e) => {
                      let newSelection = [...fieldsToCopy];
                      newSelection[i] = !fieldsToCopy[i];
                      setFieldsToCopy(newSelection);
                    }
                    } />
                </td>
              </tr>)
            })
            }
          </tbody>
        </table>
      </>
    )
  }

  return (
    <Dialog isOpen={isOpen} onClose={onClose} title={`Copy Device Changes to "${currentProject.name}"`} autoFocus={true} style={{ width: "45rem" }}>
      <DialogBody useOverflowScrollContainer>
        <table className="table table-sm table-borderless table-nohead table-nobg m-0 mb-2">
          <thead>
            <tr>
              <th></th>
              <th className="w-100"></th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><Label className="text-end mb-1">FFT:</Label></td>
              <td>{selectedDevice.fc}-{selectedDevice.fg}</td>
            </tr>
            <tr>
              <td><Label className="text-nowrap text-end mb-1" htmlFor="project-select">Copy From Project:</Label></td>
              <td>
                <HTMLSelect id="project-select"
                  value={selectedProject}
                  options={projectNames}
                  onChange={(e) => setSelectedProject(e.currentTarget.value)}
                  disabled={fetchingProjectDiff}
                  fill={false} iconName="caret-down" />
              </td>
            </tr>
            <tr>
              <td><Label className="text-end mb-1">Copy To Project:</Label></td>
              <td>{currentProject.name}</td>
            </tr>
          </tbody>
        </table>

        <hr />

        {renderDiffTable()}

      </DialogBody>
      <DialogFooter actions={
        <>
          <Button onClick={onClose}>Close</Button>
          <Button onClick={(e) => submit()} intent="primary" loading={submitting} disabled={selectedProject === DEFAULT_PROJECT || numOfFFTChanges === 0}>Copy {numOfFFTChanges} {numOfFFTChanges == 1 ? "Change" : "Changes"} to {currentProject.name}</Button>
        </>
      }>
        {dialogErr ? <span className="error">ERROR: {dialogErr}</span> : null}
      </DialogFooter>
    </Dialog >
  )
};

export const ProjectHistoryDialog: React.FC<{ isOpen: boolean, currentProject: ProjectInfo, onClose: () => void, displayProjectSince: (time: Date) => void }> = ({ isOpen, currentProject, onClose, displayProjectSince }) => {
  const [isLoading, setIsLoading] = useState(false);
  const [dialogErr, setDialogErr] = useState('');
  const [data, setData] = useState<ProjectSnapshot[]>([])

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    setIsLoading(true);
    fetchHistoryOfChanges(currentProject._id)
      .then((data) => {
        setData(data);
        setDialogErr('');
      }).catch((e: JsonErrorMsg) => {
        console.error(e);
        let msg = "Failed to fetch project diff history: " + e.error;
        setDialogErr(msg);
      }).finally(() => {
        setIsLoading(false);
      })
  }, [isOpen, currentProject._id]);

  const projectHistoryTable = useMemo(() => {
    if (isLoading) {
      return <NonIdealState icon={<Spinner />} title="Loading Project History" description="Please wait..." />
    }

    if (dialogErr) {
      return <NonIdealState icon="error" title="Error" description={dialogErr} />
    }

    if (data.length == 0) {
      return <NonIdealState icon="clean" title="No Project History Exists" description={`Project ${currentProject.name} does not have any changes since creation`} />
    }

    const changedDeviceColStyle = {
      "width": "100%",
      "maxWidth": "20%",
    };

    return (
      <>
      <table className="table table-sm table-bordered table-striped">
        <thead>
          <tr>
            <th></th>
            <th>Updated</th>
            <th>Created</th>
            <th>Deleted</th>
            <th className="text-nowrap">Changed By</th>
            <th className="text-nowrap">At time</th>
          </tr>
        </thead>
        <tbody>
            {data.map((change, i) => {
            return (
              <tr key={change._id}>
                <td>
                  <Button icon="history"
                    title="View the project as of this point in time"
                    onClick={(e) => displayProjectSince(change.created)}
                  />
                </td>
                <td style={changedDeviceColStyle}>{renderTableField(change.changelog?.updated ?? [])}</td>
                <td style={changedDeviceColStyle}>{renderTableField(change.changelog?.created ?? [])}</td>
                <td style={changedDeviceColStyle}>{renderTableField(change.changelog?.deleted ?? [])}</td>
                <td className="text-nowrap">{change.author}</td>
                <td>{formatToLiccoDateTime(change.created)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>

        {/* Inform the user that they are looking at a limited number of changes (for performance reasons) */}
        {data.length < 100 ? null : <p className="comment">NOTE: only the last {data.length} user changes are displayed in this table!</p>}
      </>
    )
  }, [data, dialogErr, isLoading, currentProject.name, displayProjectSince])

  return (
    <Dialog isOpen={isOpen} onClose={onClose} title={`Project History (${currentProject.name})`} autoFocus={true} style={{ width: "100%", maxWidth: "95%" }}>
      <DialogBody useOverflowScrollContainer>
        {projectHistoryTable}
      </DialogBody>
      <DialogFooter actions={
        <>
          <Button autoFocus={true} onClick={onClose}>Close</Button>
        </>
      }>
      </DialogFooter>
    </Dialog >
  )
}

export const SnapshotCreationDialog: React.FC<{
  isOpen: boolean;
  projectId: string;
  onClose: () => void;
  onSubmit: () => void;
}> = ({ isOpen, projectId, onClose, onSubmit }) => {
  const [submittingForm, setSubmittingForm] = useState(false);
  const [tagName, setTagName] = useState("");
  const [dialogErr, setDialogErr] = useState("");

  const submitCreateTag = () => {
    if (!projectId) {
      // in general this should never happen, if it does we have a bug
      setDialogErr(`Invalid project id '${projectId}'`);
      return;
    }
    const currentDate = new Date();

    setSubmittingForm(true);
    Fetch.get<Tag[]>(`/ws/projects/${projectId}/add_tag?tag_name=${tagName}&asoftimestamp=${currentDate.toISOString()}`)
      .then(() => {
        setTagName("");
        onSubmit();
        setDialogErr("");
      })
      .catch((e) => {
        let err = e as JsonErrorMsg;
        let msg = `Failed to create the tag.`;
        setDialogErr(msg);
        console.error(msg, e);
      })
      .finally(() => {
        setSubmittingForm(false);
      });
  };

  return (
    <Dialog onClose={onClose} isOpen={isOpen} title={`Create a New Snapshot`}>
      <DialogBody>
        <FormGroup label="Enter a Name for a New Snapshot:">
          <InputGroup id="tag-name"
            placeholder=""
            value={tagName}
            autoFocus={true}
            onValueChange={(val: string) => setTagName(val)}
          />
        </FormGroup>

        {dialogErr ? <p className="error">ERROR: {dialogErr}</p> : null}
      </DialogBody>
      <DialogFooter
        actions={
          <>
            <Button onClick={(e) => onClose()}>
              Cancel
            </Button>
            <Button
              intent="primary"
              loading={submittingForm}
              onClick={(e) => submitCreateTag()}
            >
              Create Snapshot
            </Button>
          </>
        }
      />
    </Dialog>
  );
};


export const SnapshotSelectionDialog: React.FC<{
  isOpen: boolean;
  projectId: string;
  onClose: () => void;
  onSubmit: (tagDate: Date) => void;
}> = ({ isOpen, projectId, onClose, onSubmit }) => {
  const DEFAULT_SNAPSHOT = "Please select a snapshot";
  const [selectedTag, setSelectedTag] = useState(DEFAULT_SNAPSHOT);
  const [tagNames, setTagNames] = useState<string[]>([]);
  const [allTags, setAllTags] = useState<Tag[]>([]);
  const [submittingForm, setSubmittingForm] = useState(false);
  const [disableSubmit, setDisableSubmit] = useState(true);

  const [dialogErr, setDialogErr] = useState("");

  useEffect(() => {
    if (isOpen) {
      Fetch.get<Tag[]>(`/ws/projects/${projectId}/tags/`)
        .then((projectTags) => {
          projectTags.forEach(t => {
            if (t.time) {
              t.time = new Date(t.time);
            }
          })

          if (projectTags && projectTags.length) {
            setAllTags(projectTags);
            const tags = [DEFAULT_SNAPSHOT, ...projectTags.map((p) => p.name)];
            setTagNames(tags);
          } else {
            const tags = ["No Available Snapshots"]
            setTagNames(tags);
          }
        })
        .catch((e) => {
          let err = e as JsonErrorMsg;
          let msg = `Failed to fetch project tags: ${err.error}`;
          console.error(msg, e);
          setDialogErr(msg);
        });
    }
  }, [isOpen, projectId]);

  useEffect(() => {
    const tagNotSelected = !selectedTag || selectedTag === DEFAULT_SNAPSHOT;
    const emptyProjectId = !projectId;
    setDisableSubmit(tagNotSelected || emptyProjectId);
  }, [selectedTag, projectId]);

  const submitTag = () => {
    if (!selectedTag || selectedTag == DEFAULT_SNAPSHOT) {
      setDialogErr("Please select a valid tag");
      return;
    }

    if (!projectId) {
      // in general this should never happen, if it does we have a bug
      setDialogErr(`Invalid project id '${projectId}'`);
      return;
    }
    // Get the time assosciated with the tag name
    allTags.map((tag) => {
      if (tag.name === selectedTag) {
        setSubmittingForm(true);
        onSubmit(tag.time);
      }
      setDialogErr(`No valid timestamp for tag '${selectedTag}'`);
      return;
    })

    setDialogErr("");
    setSubmittingForm(false);
  };

  return (
    <Dialog onClose={onClose} isOpen={isOpen} title={`Filter the Project by a Specified Snapshot`}>
      <DialogBody>
        <FormGroup label="Snapshots:">
          <HTMLSelect
            iconName="caret-down"
            value={selectedTag}
            options={tagNames}
            autoFocus={true}
            onChange={(e) => setSelectedTag(e.target.value)}
          />
        </FormGroup>

        {dialogErr ? <p className="error">ERROR: {dialogErr}</p> : null}
      </DialogBody>
      <DialogFooter
        actions={
          <>
            <Button onClick={(e) => onClose()} disabled={submittingForm}>
              Cancel
            </Button>
            <Button
              intent="primary"
              loading={submittingForm}
              disabled={disableSubmit}
              onClick={(e) => submitTag()}
            >
              Filter Snapshot
            </Button>
          </>
        }
      />
    </Dialog>
  );
};


// sort project value changes according to the order in which device fields appear in the device table
const sortProjectValueChanges = (changes: Record<string, any>) => {
  let order: (keyof ProjectDeviceDetails)[] = ['fc', 'fg', 'tc_part_no', 'stand', 'state', 'comments', 'nom_loc_z', 'nom_loc_x', 'nom_loc_y', 'nom_ang_z', 'nom_ang_x', 'nom_ang_y', 'ray_trace'];
  let sortOrder: Record<any, number> = {};
  for (let i = 0; i < order.length; i++) {
    sortOrder[order[i]] = i;
  }

  const values = Object.entries(changes);
  values.sort((a: any, b: any) => {
    let orderA = sortOrder[a[0]] ?? 100;
    let orderB = sortOrder[b[0]] ?? 100;
    return orderA - orderB;
  });
  return values;
}

// dialog for confirming the changed values and adding comments to value change
export const ProjectEditConfirmDialog: React.FC<{ isOpen: boolean, keymap: Record<string, string>, project: ProjectInfo, device: ProjectDeviceDetails, valueChanges: Record<string, any>, onClose: () => void, onSubmit: (device: ProjectDeviceDetails) => void }> = ({ isOpen, keymap, project, device, valueChanges, onClose, onSubmit }) => {
  const [dialogErr, setDialogErr] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [comment, setComment] = useState('');

  useEffect(() => {
    // clear error from the previous time when dialog was opened 
    setDialogErr('');
  }, [])

  const renderEntry = (entry: any) => {
    if (Array.isArray(entry)) {
      return entry.join(", ");
    }
    return entry;
  }

  const projectChangeTable = useMemo(() => {
    if (valueChanges.length == 0) {
      return <NonIdealState icon="clean" title="No Value Changes" description={`There were no value changes for device ${device.fc}`} />
    }

    const values = sortProjectValueChanges(valueChanges);
    const d = device as any;
    return (
      <>
        <b>{device.fc} Changes:</b>
        <table className="table table-sm table-bordered table-striped">
          <thead>
            <tr>
              <th>Name</th>
              <th className="text-nowrap">Current Value</th>
              <th></th>
              <th className="text-nowrap">New Value</th>
            </tr>
          </thead>
          <tbody>
            {values.map((entry) => {
              return (
                <tr key={entry[0]}>
                  <td>{keymap[entry[0]]}</td>
                  <td>{renderEntry(d[entry[0]])}</td>
                  <td className="text-center"><Icon icon="arrow-right" color={Colors.GRAY1}></Icon></td>
                  <td>{renderEntry(entry[1])}</td>
                </tr>
              )
            }
            )}
          </tbody>
        </table>
      </>
    )
  }, [valueChanges, device, keymap])

  const submit = () => {
    setDialogErr('');
    setIsSubmitting(true);

    // If we store just the user comment, then when another user is reviewing the comments it's not
    // clear to them what has changed (they only see the users's comment). For this reason we should
    // append the changed values at the end of the comment 
    let fieldsThatChanged = Object.keys(valueChanges);
    let changeComment = comment.trim();
    if (changeComment && fieldsThatChanged.length > 0) {
      changeComment += "\n\n--- Changes: ---\n";
      let d = device as any;
      for (let field of fieldsThatChanged) {
        changeComment += `${field}: ${renderEntry(d[field]) ?? ''} -> ${renderEntry(valueChanges[field]) ?? ''}\n`;
      }
      valueChanges['discussion'] = changeComment;
    }

    syncDeviceUserChanges(project._id, device._id, valueChanges)
      .then((device) => {
        // There are 2 things that may happen:
        // 1) the user wanted to update a few fields of an existing device (an existing device will come back)
        // 2) the user wanted to update a few fields and change fc/fg (change a device)
        onSubmit(device);
      }).catch((e: JsonErrorMsg) => {
        let msg = `Failed to sync user device changes: ${e.error}`;
        console.error(msg, e);
        setDialogErr(msg);
      }).finally(() => {
        setIsSubmitting(false);
      });
  }

  const userNotes: string[] = useMemo(() => {
    return device.discussion.map((d) => {
      let text = `${d.author} (${formatToLiccoDateTime(d.created)}):\n\n${d.comment}`;
      return text;
    });
  }, [device.discussion]);

  return (
    <Dialog isOpen={isOpen} onClose={onClose} title={`Save Changes for ${device.fc}?`} autoFocus={true} style={{ width: "75ch", maxWidth: "95%" }}>
      <DialogBody useOverflowScrollContainer>
        {projectChangeTable}

        {dialogErr ? <p className="error">ERROR: {dialogErr}</p> : null}

        <hr className="mt-4 mb-3" />

        <FormGroup label="Reason for the update:" labelInfo={"(optional)"}>
          <TextArea autoFocus={true} value={comment} onChange={e => setComment(e.target.value)} fill={true} placeholder="Why are these changes necessary?" rows={4} />
        </FormGroup>

        <CollapsibleProjectNotes
          defaultOpen={true}
          notes={userNotes}
          defaultNoNoteMsg={<p style={{ color: Colors.GRAY1 }}>There are no user comments for this device</p>}
        />
      </DialogBody>
      <DialogFooter actions={
        <>
          <Button onClick={e => onClose()}>Close</Button>
          <Button intent="primary" onClick={e => submit()} loading={isSubmitting}>Save Changes</Button>
        </>
      }>
      </DialogFooter>
    </Dialog >
  )
}

export const CommentDialog: React.FC<{ isOpen: boolean, project: ProjectInfo, device: ProjectDeviceDetails, user: string, disableActionButton?: boolean, onClose: () => void, onCommentAdd: (device: ProjectDeviceDetails) => void }> = ({ isOpen, project, device, user, disableActionButton = false, onClose, onCommentAdd }) => {
  const [dialogErr, setDialogErr] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [comment, setComment] = useState('');

  const userNotes = useMemo(() => {

    let notes = device.discussion.map((d) => {
      let text = `${d.author} (${formatToLiccoDateTime(d.created)}):\n\n${d.comment}`;
      return text;
    });

    return <CollapsibleProjectNotes
      defaultOpen={true}
      notes={notes}
      defaultNoNoteMsg={<p style={{ color: Colors.GRAY1 }}>There are no comments</p>}
    />
  }, [device.discussion]);

  const addAComment = () => {
    setDialogErr('');

    if (comment.trim().length == 0) {
      setDialogErr("Comment field should not be empty");
      return;
    }

    setIsSubmitting(true);
    addDeviceComment(project._id, device._id, comment)
      .then(updatedDevice => {
        setComment('');
        onCommentAdd(updatedDevice);
      }).catch((e: JsonErrorMsg) => {
        setDialogErr("Error while uploading a new comment: " + e.error);
      }).finally(() => {
        setIsSubmitting(false);
      });
  }

  return (
    <Dialog isOpen={isOpen} onClose={onClose} title={`Comments for ${device.fc}-${device.fg}`} autoFocus={true} style={{ width: "75ch", maxWidth: "95%" }}>
      <DialogBody useOverflowScrollContainer>

        {isUserAProjectEditor(project, user) || isUserAProjectApprover(project, user) ?
          <FormGroup label="Add a comment:">
            <TextArea autoFocus={true} fill={true} disabled={disableActionButton} onChange={e => setComment(e.target.value)} value={comment} placeholder="Comment text..." rows={4} />

            <ButtonGroup className="d-flex justify-content-end">
              <Button className="mt-1" intent="primary" loading={isSubmitting}
                disabled={disableActionButton}
                onClick={e => addAComment()}>Add Comment</Button>
            </ButtonGroup>
            {dialogErr ? <p className="error">ERROR: {dialogErr}</p> : null}
          </FormGroup>
          :
          <NonIdealState icon="blocked-person" title="No Permissions" description={"You don't have permissions to add a comment"} />
        }

        <hr className="mt-4 mb-3" />

        {userNotes}
      </DialogBody>
      <DialogFooter actions={
        <>
          <Button onClick={e => onClose()} autoFocus={disableActionButton ? true : false}>Close</Button>
        </>
      }>
      </DialogFooter>
    </Dialog >
  )
}