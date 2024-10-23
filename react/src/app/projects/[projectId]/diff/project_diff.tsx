import { JsonErrorMsg } from "@/app/utils/fetching";
import { Button, Collapse, Colors, NonIdealState, Spinner } from "@blueprintjs/core";
import Link from "next/link";
import React, { ReactNode, useEffect, useMemo, useState } from "react";
import { ProjectDeviceDetails, ProjectInfo } from "../../project_model";
import { formatDevicePositionNumber } from "../project_details";
import { ProjectFftDiff, loadProjectDiff } from "./project_diff_model";

export const ProjectDiffPage: React.FC<{ projectIdA: string, projectIdB: string }> = ({ projectIdA, projectIdB }) => {
    const [isLoading, setIsLoading] = useState(true);
    const [loadError, setLoadError] = useState('');
    const [diff, setDiff] = useState<ProjectFftDiff>();

    useEffect(() => {
        setIsLoading(true);
        loadProjectDiff(projectIdA, projectIdB).then(diff => {
            setDiff(diff);
            setLoadError('');
            console.log("DIFF:", diff);
        }).catch((e: JsonErrorMsg) => {
            let msg = "Failed to fetch all data for project diff page: " + e.error;
            console.error(msg, e);
            setLoadError(msg);
        }).finally(() => {
            setIsLoading(false);
        })
    }, [projectIdA, projectIdB])


    // rendering part

    if (isLoading) {
        return <NonIdealState icon={<Spinner />} title="Loading Diff" description="Loading project data..." />
    }

    if (loadError) {
        return <NonIdealState icon="error" title="Error" description={loadError} />
    }

    if (!diff) {
        return <NonIdealState icon="blank" title="No Diff to Display" description="There is no diff to display" />
    }

    return (
        <>
            <ProjectDiffTable diff={diff} type="new" />
            <ProjectDiffTable diff={diff} type="missing" />
            <ProjectDiffTable diff={diff} type="changed" />
            <ProjectDiffTable diff={diff} type="unchanged" defaultOpen={false} />
        </>
    )
}


const DiffTableHeading: React.FC<{ title?: ReactNode }> = ({ title }) => {
    return (
        <thead>
            {title ? <tr><th colSpan={17}><h5>{title}</h5></th></tr> : null}
            <tr>
                <th colSpan={5}></th>

                <th colSpan={3} className="text-center">Nominal Location (meters in LCLS coordinates)</th>
                <th colSpan={3} className="text-center">Nominal Dimension (meters)</th>
                <th colSpan={3} className="text-center">Nominal Angle (radians)</th>
                <th></th>
                <th>Approval</th>
            </tr>
            <tr>
                <th>FC</th>
                <th>Fungible</th>
                <th>TC Part No.</th>
                <th>State</th>
                <th>Comments</th>

                <th className="text-center">Z</th>
                <th className="text-center">X</th>
                <th className="text-center">Y</th>

                <th className="text-center">Z</th>
                <th className="text-center">X</th>
                <th className="text-center">Y</th>

                <th className="text-center">Z</th>
                <th className="text-center">X</th>
                <th className="text-center">Y</th>
                <th>Must Ray Trace</th>
                <th>Communications</th>
            </tr>
        </thead>
    )
}

// just for displaying data
export const ProjectDiffTable: React.FC<{ diff: ProjectFftDiff, type: 'new' | 'changed' | 'missing' | 'unchanged', defaultOpen?: boolean }> = ({ diff, type, defaultOpen = true }) => {
    const [collapsed, setCollapsed] = useState(!defaultOpen);

    const createProjectLink = (project: ProjectInfo, type: 'a' | 'b') => {
        const color = type == 'a' ? Colors.RED2 : Colors.BLUE2;
        return <Link style={{ color: color }} href={`/projects/${project._id}/`}>{project.name}</Link>
    }

    const titleDescription: ReactNode = useMemo(() => {
        switch (type) {
            case "new": return <>{diff.new.length} New devices in {createProjectLink(diff.a, 'a')} compared to {createProjectLink(diff.b, 'b')}</>
            case "changed": return <>{diff.changed.length} Updated devices in {createProjectLink(diff.a, 'a')} compared to {createProjectLink(diff.b, 'b')}</>
            case "missing": return <>{diff.missing.length} Missing devices from {createProjectLink(diff.a, 'a')} (they are present in {createProjectLink(diff.b, 'b')})</>
            case "unchanged": return <>{diff.unchanged.length} Identical devices in {createProjectLink(diff.a, 'a')} and {createProjectLink(diff.b, 'b')}</>
        }
    }, [diff, type])

    const renderDiffRows = (data: { a: ProjectDeviceDetails, b: ProjectDeviceDetails }[]) => {
        // const formatField = (a: any, field: keyof ProjectDeviceDetails) => {
        //     let isNumeric = ProjectDevicePositionKeys.indexOf(field as string) >= 0;
        // }

        const getColor = (type: 'a' | 'b') => {
            return type == 'a' ? Colors.RED5 : Colors.BLUE5;
        }

        const renderField = (a: ProjectDeviceDetails, b: ProjectDeviceDetails, field: keyof ProjectDeviceDetails) => {
            let isChanged = a[field] != b[field];
            if (!isChanged) {
                return <span style={{ color: Colors.GRAY1 }}>{a[field]}</span>
            }

            // there is a change in fields (display both one under the other)
            let aData = a[field] != undefined && a[field] != "" ? a[field] : '<empty>';
            let bData = b[field] != undefined && b[field] != "" ? b[field] : '<empty>';
            return (
                <>
                    <span style={{ backgroundColor: getColor('a') }}>{aData}</span>
                    <br />
                    <span style={{ backgroundColor: getColor('b') }}>{bData}</span>
                </>
            )
        }

        return Object.values(data).map(devices => {
            return (<tr key={devices.a.id}>
                <td>{renderField(devices.a, devices.b, 'fc')}</td>
                <td>{renderField(devices.a, devices.b, 'fg')}</td>
                <td>{renderField(devices.a, devices.b, 'tc_part_no')}</td>
                <td>{renderField(devices.a, devices.b, 'state')}</td>
                <td>{renderField(devices.a, devices.b, 'comments')}</td>

                <td>{renderField(devices.a, devices.b, 'nom_loc_z')}</td>
                <td>{renderField(devices.a, devices.b, 'nom_loc_x')}</td>
                <td>{renderField(devices.a, devices.b, 'nom_loc_y')}</td>

                <td>{renderField(devices.a, devices.b, 'nom_dim_z')}</td>
                <td>{renderField(devices.a, devices.b, 'nom_dim_x')}</td>
                <td>{renderField(devices.a, devices.b, 'nom_dim_y')}</td>

                <td>{renderField(devices.a, devices.b, 'nom_ang_z')}</td>
                <td>{renderField(devices.a, devices.b, 'nom_ang_x')}</td>
                <td>{renderField(devices.a, devices.b, 'nom_ang_y')}</td>

                <td>{renderField(devices.a, devices.b, 'ray_trace')}</td>
                <td></td>
            </tr>
            )
        })
    }

    const renderDataRows = (data: ProjectDeviceDetails[]) => {
        return data.map(d => {
            return (
                <tr key={d.id}>
                    <td>{d.fc}</td>
                    <td>{d.fg}</td>
                    <td>{d.tc_part_no}</td>
                    <td>{d.state}</td>
                    <td>{d.comments}</td>

                    <td>{formatDevicePositionNumber(d.nom_loc_z)}</td>
                    <td>{formatDevicePositionNumber(d.nom_loc_x)}</td>
                    <td>{formatDevicePositionNumber(d.nom_loc_y)}</td>

                    <td>{formatDevicePositionNumber(d.nom_dim_z)}</td>
                    <td>{formatDevicePositionNumber(d.nom_dim_x)}</td>
                    <td>{formatDevicePositionNumber(d.nom_dim_y)}</td>

                    <td>{formatDevicePositionNumber(d.nom_ang_z)}</td>
                    <td>{formatDevicePositionNumber(d.nom_ang_x)}</td>
                    <td>{formatDevicePositionNumber(d.nom_ang_y)}</td>

                    <td>{d.ray_trace}</td>
                    <td></td>
                </tr>
            )
        })
    }

    const renderTableBody = () => {
        switch (type) {
            case 'new': return renderDataRows(diff.new);
            case 'missing': return renderDataRows(diff.missing);
            case 'unchanged': return renderDataRows(diff.unchanged);
            case 'changed': return renderDiffRows(diff.changed);
        }
    }

    const noDevices: boolean = useMemo(() => {
        switch (type) {
            case 'new': return diff.new.length == 0;
            case 'missing': return diff.missing.length == 0;
            case 'unchanged': return diff.unchanged.length == 0;
            case 'changed': return diff.changed.length == 0;
        }
    }, [diff]);


    if (type == "missing" && diff.missing.length == 0) {
        // no need to display the entire table if it's not there
        return null;
    }

    return (
        <div className="mb-5">
            <h5 className="m-0">
                <Button icon={collapsed ? "chevron-right" : "chevron-down"} minimal={true}
                    onClick={(e) => setCollapsed((collapsed) => !collapsed)}
                />
                {titleDescription}
            </h5>

            <Collapse isOpen={!collapsed} keepChildrenMounted={true}>
                {noDevices ?
                    <NonIdealState icon="clean" title="No Such Devices" description="There are no such devices" />
                    :
                    <div className="table-responsive" style={{ maxHeight: "70vh" }}>
                        <table className="table table-sm table-bordered table-striped table-sticky">
                            <DiffTableHeading />
                            <tbody>{renderTableBody()}</tbody>
                        </table>
                    </div>
                }
            </Collapse>
        </div>
    )
}