'use client';

import { HtmlPage } from "@/app/components/html_page";
import { Fetch, LiccoRequest } from "@/app/utils/fetching";
import { createGlobMatchRegex } from "@/app/utils/glob_matcher";
import { Button, ButtonGroup, Colors, Dialog, DialogBody, DialogFooter, Divider, FormGroup, HTMLSelect, Icon, InputGroup, Tooltip } from "@blueprintjs/core";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ProjectDeviceDetails, ProjectInfo } from "../project_model";

// a project specific page displays all properties of a specific project 
export default function ProjectSpecificPage({ params }: { params: { projectId: string } }) {
    const queryParams = useSearchParams();
    const [isLoading, setIsLoading] = useState(false);

    const [projectData, setProjectData] = useState<ProjectInfo>();
    const [fftData, setFftData] = useState<ProjectDeviceDetails[]>([]);
    const [fftDataDisplay, setFftDataDisplay] = useState<ProjectDeviceDetails[]>([]);

    // dialogs open state
    const [isFilterDialogOpen, setIsFilterDialogOpen] = useState(false);

    // filters to apply
    const [fftStates, setFftStates] = useState<string[]>([]);
    const [fcFilter, setFcFilter] = useState("");
    const [fgFilter, setFgFilter] = useState("");
    const [stateFilter, setStateFilter] = useState("");

    // load project data
    useEffect(() => {
        setIsLoading(true);

        Fetch.get<LiccoRequest<ProjectInfo>>(`/ws/projects/${params.projectId}/`)
            .then(data => {
                setProjectData(data.value);
            }).catch((e) => {
                console.error("Failed to make a project request");
            });

        Fetch.get<LiccoRequest<Record<string, ProjectDeviceDetails>>>(`/ws/projects/${params.projectId}/ffts/?showallentries=true`)
            .then((data) => {
                let devices = Object.values(data.value);
                // TODO: missing device number field is set to "" (empty string):
                // we should turn it into an null to avoid having problems when formatting it later
                setFftData(devices);
            }).catch((e) => {
                console.error(e);
                console.error("Error while fetching data: ", e);
            }).finally(() => {
                setIsLoading(false);
            });
    }, []);

    // get unique fft states for filter dialog
    useEffect(() => {
        let uniqueStates = Array.from(new Set(fftData.map((e) => e.state).filter(state => state)));
        setFftStates(["---- Any ----", ...uniqueStates]);
    }, [fftData])

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

    const formatDevicePositionNumber = (value?: number | string): string => {
        if (value === undefined) {
            return '';
        }
        if (typeof value === "string") {
            return value;
        }
        return value.toFixed(7);
    }

    const displayFilterIconInColumn = (filterValue: string) => {
        if (!filterValue) {
            return null
        }
        return <Icon icon="filter" color={Colors.RED2} className="ms-1" />
    }


    const isProjectSubmitted = projectData?.status === "submitted";
    const isFilterApplied = fcFilter != "" || fgFilter != "" || stateFilter != "";

    return (
        <HtmlPage>
            <table className="table table-bordered table-sm table-sticky table-striped table-sticky">
                <thead>
                    <tr>
                        <th colSpan={6}>
                            <ButtonGroup vertical={false}>
                                <span className="me-3">{projectData?.name}</span>

                                <Tooltip content="Download data to this project" position="bottom">
                                    <Button icon="import" minimal={true} small={true}></Button>
                                </Tooltip>

                                <Tooltip content="Upload data to this project" position="bottom">
                                    <Button icon="export" minimal={true} small={true}></Button>
                                </Tooltip>

                                <Divider />

                                <Tooltip content="Filter FFTs" position="bottom">
                                    <Button icon="filter" minimal={true} small={true} intent={isFilterApplied ? "warning" : "none"} onClick={(e) => setIsFilterDialogOpen(true)}></Button>
                                </Tooltip>

                                <Tooltip content={"Clear filters to show all FFTs"} position="bottom" disabled={!isFilterApplied}>
                                    <Button icon="filter-remove" minimal={true} small={true} disabled={!isFilterApplied}
                                        onClick={(e) => {
                                            setFcFilter('')
                                            setFgFilter('');
                                            setStateFilter('');
                                        }}
                                    />
                                </Tooltip>

                                <Tooltip content="Show only FCs with changes after the project was created" position="bottom">
                                    <Button icon="filter-open" minimal={true} small={true}></Button>
                                </Tooltip>

                                <Divider />

                                <Tooltip content="Create a tag" position="bottom">
                                    <Button icon="tag" minimal={true} small={true}></Button>
                                </Tooltip>

                                <Tooltip content="Show assigned tags" position="bottom">
                                    <Button icon="tags" minimal={true} small={true}></Button>
                                </Tooltip>

                                <Divider />

                                <Tooltip content="Show the history of changes" position="bottom">
                                    <Button icon="history" minimal={true} small={true}></Button>
                                </Tooltip>

                                <Tooltip content={"Submit this project for approval"} position="bottom" disabled={isProjectSubmitted}>
                                    <Button icon="user" minimal={true} small={true} disabled={isProjectSubmitted}></Button>
                                </Tooltip>
                            </ButtonGroup>
                        </th>
                        <th colSpan={3}>Nominal Location (meters in LCLS coordinates)</th>
                        <th colSpan={3}>Nominal Dimension (meters)</th>
                        <th colSpan={3}>Nominal Angle (radians)</th>
                        <th></th>
                    </tr>
                    <tr>
                        <th></th>
                        <th>FC  {displayFilterIconInColumn(fcFilter)}</th>
                        <th>Fungible {displayFilterIconInColumn(fgFilter)}</th>
                        <th>TC Part No.</th>
                        <th>State {displayFilterIconInColumn(stateFilter)}</th>
                        <th>Comments</th>

                        <th className="text-number">Z</th>
                        <th className="text-number">X</th>
                        <th className="text-number">Y</th>

                        <th className="text-number">Z</th>
                        <th className="text-number">X</th>
                        <th className="text-number">Y</th>

                        <th className="text-number">Z</th>
                        <th className="text-number">X</th>
                        <th className="text-number">Y</th>
                        <th>Must Ray Trace</th>
                    </tr>
                </thead>
                <tbody>
                    {fftDataDisplay.map(device => {
                        return (
                            <tr key={device.fft._id}>
                                <td className="text-nowrap">
                                    <Tooltip content={"Edit this FFT"} position="bottom">
                                        <Button minimal={true} small={true} icon={"edit"} />
                                    </Tooltip>
                                    <Tooltip content={"Sync this FFT to another project"} position="bottom">
                                        <Button minimal={true} small={true} icon={"refresh"} />
                                    </Tooltip>
                                </td>
                                <td>{device.fft.fc}</td>
                                <td>{device.fft.fg}</td>
                                <td>{device.tc_part_no}</td>
                                <td>{device.state}</td>
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
                    })
                    }
                </tbody>
            </table>

            <FilterFFTDialog
                isOpen={isFilterDialogOpen}
                possibleStates={fftStates}
                onClose={() => setIsFilterDialogOpen(false)}
                onSubmit={(newFcFilter, newFgFilter, newStateFilter) => {
                    setFcFilter(newFcFilter);
                    setFgFilter(newFgFilter);
                    newStateFilter = newStateFilter.startsWith("---") ? "" : newStateFilter;
                    setStateFilter(newStateFilter);
                    setIsFilterDialogOpen(false);
                }}
            />
        </HtmlPage >
    )
}


// this dialog is used for filtering the table (fc, fg, and based on state)
const FilterFFTDialog: React.FC<{ isOpen: boolean, possibleStates: string[], onClose: () => void, onSubmit: (newFcFilter: string, newFgFilter: string, newStateFilter: string) => void }> = ({ isOpen, possibleStates, onClose, onSubmit }) => {
    const [fcFilter, setFcFilter] = useState('');
    const [fgFilter, setFgFilter] = useState('');
    const [stateFilter, setStateFilter] = useState('');

    const submitSearchForm = () => {
        onSubmit(fcFilter, fgFilter, stateFilter);
    }

    const submitOnEnter = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === "Enter") {
            submitSearchForm();
        }
    }

    return (
        <Dialog isOpen={isOpen} onClose={onClose} title="Apply Filter to Table" autoFocus={true}>
            <DialogBody useOverflowScrollContainer>
                <FormGroup label="FC:">
                    <InputGroup id="fc-filter"
                        placeholder="Use GLOB pattern to filter on FC name"
                        value={fcFilter}
                        onKeyUp={submitOnEnter}
                        onValueChange={(val: string) => setFcFilter(val)} />
                </FormGroup>

                <FormGroup label="FG:">
                    <InputGroup id="fg-filter"
                        placeholder="Use GLOB pattern to filter on FG name"
                        value={fgFilter}
                        onKeyUp={submitOnEnter}
                        onValueChange={(val: string) => setFgFilter(val)} />
                </FormGroup>

                <FormGroup label="State">
                    <HTMLSelect value={stateFilter} options={possibleStates}
                        onChange={(e) => setStateFilter(e.currentTarget.value)}
                        fill={true} iconName="caret-down" />
                </FormGroup>
            </DialogBody>
            <DialogFooter actions={
                <>
                    <Button onClick={onClose}>Cancel</Button>
                    <Button onClick={(e) => submitSearchForm()} intent="primary">Search</Button>
                </>
            }>
            </DialogFooter>
        </Dialog>
    )
}