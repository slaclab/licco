import { Button, Collapse, Colors, NonIdealState, Spinner } from "@blueprintjs/core";
import Link from "next/link";
import React, { ReactNode, useMemo, useState } from "react";
import { ProjectDeviceDetails, ProjectDevicePositionKeys, ProjectInfo, useWhoAmIHook } from "../../project_model";
import { formatDevicePositionNumber } from "../project_details";
import { ProjectFftDiff, useFetchProjectDiffDataHook } from "./project_diff_model";

import { capitalizeFirstLetter } from "@/app/utils/string_utils";
import { Col, Row } from "react-bootstrap";
import { renderTableField } from "../../project_utils";
import { FFTCommentViewerDialog } from "../project_dialogs";
import styles from './project_diff.module.css';

// displays the diff tables between two projects
export const ProjectDiffPage: React.FC<{ projectIdA: string, projectIdB: string }> = ({ projectIdA, projectIdB }) => {
    const { isLoading, loadError, diff } = useFetchProjectDiffDataHook(projectIdA, projectIdB)
    const { user, isUserDataLoading, userLoadingError } = useWhoAmIHook();
    return <ProjectDiffTables isLoading={isLoading || isUserDataLoading} loadError={loadError || userLoadingError} user={user} diff={diff} />
}


export const ProjectDiffTables: React.FC<{ isLoading: boolean, loadError: string, user: string, diff?: ProjectFftDiff }> = ({ isLoading, loadError, user, diff }) => {
    if (isLoading) {
        return <NonIdealState icon={<Spinner />} title="Loading Diff" description="Loading project data..." className="mt-5" />
    }

    if (loadError) {
        return <NonIdealState icon="error" title="Error" description={loadError} className="mt-5" />
    }

    if (!diff) {
        return <NonIdealState icon="blank" title="No Diff to Display" description="There is no diff to display" className="mt-5" />
    }

    if (diff.a._id == diff.b._id) {
        // user compared project 'a' to the same project
        // this can happen when we approve the project and the compared and approved projects are the same
        // in this case we just show the entire list of devices
        return <ProjectDiffTable user={user} diff={diff} type="listOfIdenticalDevices" />
    }

    return (
        <>
            <ProjectDiffTable user={user} diff={diff} type="new" />
            <ProjectDiffTable user={user} diff={diff} type="updated" />
            <ProjectDiffTable user={user} diff={diff} type="identical" defaultOpen={false} />
        </>
    )
}


const DiffTableHeading: React.FC<{ title?: ReactNode }> = ({ title }) => {
    return (
        <thead>
            {title ? <tr><th colSpan={17}><h5>{title}</h5></th></tr> : null}
            <tr>
                <th colSpan={7}></th>

                <th colSpan={3} className="text-center">Nominal Location (meters in LCLS coordinates)</th>
                <th colSpan={3} className="text-center">Nominal Angle (radians)</th>
                <th></th>
                <th></th>
                <th></th>
            </tr>
            <tr>
                <th>FC</th>
                <th>Fungible</th>
                <th>TC Part No.</th>
                <th>Stand/Nearest Stand</th>
                <th>Area</th>
                <th>Beamline</th>
                <th>State</th>

                <th className="text-center">Z</th>
                <th className="text-center">X</th>
                <th className="text-center">Y</th>

                <th className="text-center">Rz</th>
                <th className="text-center">Rx</th>
                <th className="text-center">Ry</th>
                <th>Must Ray Trace</th>
                <th>Comments</th>
                <th>Communications</th>
            </tr>
        </thead>
    )
}

// just for displaying data
export const ProjectDiffTable: React.FC<{ diff: ProjectFftDiff, user: string, type: 'new' | 'updated' | 'missing' | 'identical' | 'listOfIdenticalDevices', defaultOpen?: boolean }> = ({ diff, user, type, defaultOpen = true }) => {
    const [collapsed, setCollapsed] = useState(!defaultOpen);
    const [commentDevice, setCommentDevice] = useState<ProjectDeviceDetails>();

    const createProjectLink = (project: ProjectInfo, type: 'a' | 'b') => {
        const color = type == 'a' ? Colors.RED2 : Colors.BLUE2;
        return <Link style={{ color: color }} href={`/projects/${project._id}/`}>{project.name}</Link>
    }

    const titleDescription: ReactNode = useMemo(() => {
        switch (type) {
            case "new": return <>{diff.new.length} New devices in {createProjectLink(diff.a, 'a')} compared to {createProjectLink(diff.b, 'b')}</>
            case "updated": return <>{diff.updated.length} Updated devices in {createProjectLink(diff.a, 'a')} compared to {createProjectLink(diff.b, 'b')}</>
            case "missing": return <>{diff.missing.length} Missing devices from {createProjectLink(diff.a, 'a')} (they are present in {createProjectLink(diff.b, 'b')})</>
            case "identical": return <>{diff.identical.length} Identical devices in {createProjectLink(diff.a, 'a')} and {createProjectLink(diff.b, 'b')}</>
            case "listOfIdenticalDevices": return <>{diff.identical.length} devices in {createProjectLink(diff.a, 'a')}</>
        }
    }, [diff, type])

    const renderDiscussionButton = (device: ProjectDeviceDetails) => {
        return <Button icon="chat" variant="minimal" onClick={e => setCommentDevice(device)}>({device.discussion.length})</Button>
    }

    const renderDiffRows = (data: { a: ProjectDeviceDetails, b: ProjectDeviceDetails }[]) => {
        const formatValueIfNumber = (val: any, field: keyof ProjectDeviceDetails) => {
            if (field == "id" || field == "fc" || field == "fg") {
                return val;
            }
            const isPositionField = ProjectDevicePositionKeys.indexOf(field) >= 0;
            if (isPositionField) {
                return formatDevicePositionNumber(val);
            }
            return val;
        }

        const formatField = (val: any, field: keyof ProjectDeviceDetails) => {
            if (val === undefined) {
                // undefined fields are not displayed at all
                return <></>;
            }

            if (val === "") {
                // empty strings are made more obvious this way
                return "<empty>";
            }

            if (Array.isArray(val)) {
                return val.join(", ");
            }

            if (typeof val == "string" && val.trim() == "") {
                // html by default collapses multiple spaces into 1; since we would like to preserve
                // the exact number of spaces, an extra span is needed.
                return <span style={{ whiteSpace: 'pre' }}>{val}</span>;
            }

            return formatValueIfNumber(val, field)
        }

        const renderField = (a: ProjectDeviceDetails, b: ProjectDeviceDetails, field: keyof ProjectDeviceDetails) => {
            let isChanged = a[field] != b[field];
            if (!isChanged) {
                // if the value is empty, we just render empty tag
                return <span style={{ color: Colors.GRAY1 }}>{formatValueIfNumber(a[field], field)}</span>
            }

            // there is a change in fields (display both one under the other)
            let aData = formatField(a[field], field);
            let bData = formatField(b[field], field);
            return (
                <>
                    <span style={{ backgroundColor: Colors.RED5 }}>{aData}</span>
                    <br />
                    <span style={{ backgroundColor: Colors.BLUE5 }}>{bData}</span>
                </>
            )
        }

        return data.map(devices => {
            return (<tr key={devices.a.id}>
                <td>{renderField(devices.a, devices.b, 'fc')}</td>
                <td>{renderField(devices.a, devices.b, 'fg_desc')}</td>
                <td>{renderField(devices.a, devices.b, 'tc_part_no')}</td>
                <td>{renderField(devices.a, devices.b, 'stand')}</td>
                <td>{renderField(devices.a, devices.b, 'area')}</td>
                <td>{renderField(devices.a, devices.b, 'beamline')}</td>
                <td>{renderField(devices.a, devices.b, 'state')}</td>

                <td>{renderField(devices.a, devices.b, 'nom_loc_z')}</td>
                <td>{renderField(devices.a, devices.b, 'nom_loc_x')}</td>
                <td>{renderField(devices.a, devices.b, 'nom_loc_y')}</td>

                <td>{renderField(devices.a, devices.b, 'nom_ang_z')}</td>
                <td>{renderField(devices.a, devices.b, 'nom_ang_x')}</td>
                <td>{renderField(devices.a, devices.b, 'nom_ang_y')}</td>

                <td>{renderField(devices.a, devices.b, 'ray_trace')}</td>

                <td>{renderField(devices.a, devices.b, 'comments')}</td>

                <td>{renderDiscussionButton(devices.a)}</td>
            </tr>
            )
        })
    }

    const renderDataRows = (data: ProjectDeviceDetails[], renderDiscussion: boolean = true) => {
        return data.map(d => {
            return (
                <tr key={d.id}>
                    <td>{d.fc}</td>
                    <td>{d.fg_desc}</td>
                    <td>{d.tc_part_no}</td>
                    <td>{d.stand}</td>
                    <td>{d.area}</td>
                    <td>{renderTableField(d.beamline)}</td>
                    <td>{d.state}</td>

                    <td>{formatDevicePositionNumber(d.nom_loc_z)}</td>
                    <td>{formatDevicePositionNumber(d.nom_loc_x)}</td>
                    <td>{formatDevicePositionNumber(d.nom_loc_y)}</td>

                    <td>{formatDevicePositionNumber(d.nom_ang_z)}</td>
                    <td>{formatDevicePositionNumber(d.nom_ang_x)}</td>
                    <td>{formatDevicePositionNumber(d.nom_ang_y)}</td>

                    <td>{d.ray_trace}</td>
                    <td>{d.comments}</td>

                    <td>{renderDiscussion ? renderDiscussionButton(d) : null}</td>
                </tr>
            )
        })
    }

    const renderTableBody = () => {
        switch (type) {
            case 'new': return renderDataRows(diff.new);
            case 'missing': return renderDataRows(diff.missing, false);
            case 'updated': return renderDiffRows(diff.updated);
            case 'identical': return renderDataRows(diff.identical);
            case 'listOfIdenticalDevices': return renderDataRows(diff.identical);
        }
    }

    const noDevices: boolean = useMemo(() => {
        switch (type) {
            case 'new': return diff.new.length == 0;
            case 'missing': return diff.missing.length == 0;
            case 'updated': return diff.updated.length == 0;
            case 'identical': return diff.identical.length == 0;
            case 'listOfIdenticalDevices': return diff.identical.length == 0
        }
    }, [diff, type]);

    const replaceDeviceDiscussion = (newDevice: ProjectDeviceDetails, devices: ProjectDeviceDetails[]) => {
        for (let device of devices) {
            if (device.id == newDevice.id) {
                device.discussion = newDevice.discussion;
                return
            }
        }
    }

    const noDevicesDisplay = () => {
        if (type == 'listOfIdenticalDevices') {
            return <NonIdealState icon="clean" title={`No Devices`} description={`There are no devices`} />
        }
        return <NonIdealState icon="clean" title={`No ${capitalizeFirstLetter(type)} Devices`} description={`There are no ${type} devices`} />
    }


    if (type == "missing" && diff.missing.length == 0) {
        // no need to display the missing table if nothing is missing
        return null;
    }

    return (
        <div className="mb-5">
            <Row className="align-items-center m-0">
                <Col className="col-auto ps-0 pe-0">
                    <Button icon={collapsed ? "chevron-right" : "chevron-down"} variant="minimal"
                        onClick={(e) => setCollapsed((collapsed) => !collapsed)}
                    />
                </Col>
                <Col className="ps-0">
                    <h5 className="m-0">{titleDescription}</h5>
                </Col>
            </Row>

            <Collapse isOpen={!collapsed} keepChildrenMounted={true}>
                {noDevices ? <>{noDevicesDisplay()}</>
                    :
                    <div className="table-responsive" style={{ maxHeight: "75vh" }}>
                        <table className={`table table-sm table-bordered table-striped table-sticky ${styles.diffTable}`}>
                            <DiffTableHeading />
                            <tbody>{renderTableBody()}</tbody>
                        </table>
                    </div>
                }
            </Collapse>

            {commentDevice ?
                <FFTCommentViewerDialog
                    project={diff.a}
                    isOpen={commentDevice != undefined}
                    device={commentDevice}
                    user={user}
                    onClose={() => setCommentDevice(undefined)}
                    onCommentAdd={newDevice => {
                        setCommentDevice(commentDevice);

                        // replace the discussion field of the right device
                        replaceDeviceDiscussion(newDevice, diff.identical);
                        replaceDeviceDiscussion(newDevice, diff.missing);
                        replaceDeviceDiscussion(newDevice, diff.new);
                        for (let devices of diff.updated) {
                            if (devices.a.id == newDevice.id) {
                                devices.a.discussion = newDevice.discussion
                                break
                            }
                        }
                    }}
                />
                : null
            }
        </div>
    )
}