import { Button, ButtonGroup, Tooltip } from "@blueprintjs/core";
import Link from "next/link";
import { useEffect, useState } from "react";
import { formatToLiccoDateTime } from "../utils/date_utils";
import { Fetch, LiccoRequest } from "../utils/fetching";
import { ProjectInfo, isProjectSubmitted } from "./project_model";


export const ProjectsOverview: React.FC = ({ }) => {
    const [projectData, setProjectData] = useState<ProjectInfo[]>([]);
    const [projectDataLoading, setProjectDataLoading] = useState(false);
    const [err, setError] = useState("");

    const fetchProjectData = () => {
        setProjectDataLoading(true);
        Fetch.get<LiccoRequest<ProjectInfo[]>>("/ws/projects/")
            .then((projects) => {
                for (let p of projects.value) {
                    p.creation_time = new Date(p.creation_time);
                    p.edit_time = new Date(p.edit_time);
                }
                setProjectData(projects.value);
            }).catch((e) => {
                console.error(e);
                setError("Failed to load projects data: " + e.message);
            })
            .finally(() => {
                setProjectDataLoading(false);
            });
    }

    useEffect(() => {
        fetchProjectData();
    }, []);


    if (err) {
        return <p>{err}</p>
    }

    return (
        <div className="table-responsive">
            <table className="table table-striped table-bordered table-sm">
                <thead>
                    <tr>
                        <th scope="col"><Button minimal={true} small={true} disabled={true} loading={projectDataLoading} /></th>
                        <th>Name</th>
                        <th>Owner</th>
                        <th>Created</th>
                        <th>Last Edit</th>
                        <th>Description</th>
                        <th>Notes</th>
                    </tr>
                </thead>
                <tbody>
                    {projectData.map((project) => {
                        return (
                            <tr key={project._id}>
                                <td>
                                    <ButtonGroup minimal={true}>
                                        <Tooltip content="Compare (diff) with another project" position="bottom">
                                            <Button icon="comparison" small={true} />
                                        </Tooltip>

                                        <Tooltip content="Clone this project" position="bottom">
                                            <Button icon="duplicate" small={true} />
                                        </Tooltip>

                                        {!isProjectSubmitted(project) ?
                                            <>
                                                <Tooltip content="Edit this project" position="bottom">
                                                    <Button icon="edit" minimal={true} small={true} />
                                                </Tooltip>

                                                <Tooltip content="Submit this project for approval" position="bottom">
                                                    <Button icon="user" minimal={true} small={true} />
                                                </Tooltip>

                                                <Tooltip content="Upload data to this project">
                                                    <Button icon="export" minimal={true} small={true} />
                                                </Tooltip>
                                            </>
                                            : null
                                        }

                                        <Tooltip content="Download this project">
                                            <Button icon="import" minimal={true} small={true} />
                                        </Tooltip>

                                    </ButtonGroup>
                                </td>
                                <td><Link href={`/projects/${project._id}`}>{project.name}</Link></td>
                                <td>{project.owner}</td>
                                <td>{formatToLiccoDateTime(project.creation_time)}</td>
                                <td>{formatToLiccoDateTime(project.edit_time)}</td>
                                <td>{project.description}</td>
                                <td></td>
                            </tr>
                        )
                    })
                    }
                </tbody>
            </table>
        </div>
    )
}