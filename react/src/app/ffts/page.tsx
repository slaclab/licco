'use client';

import { Button } from "@blueprintjs/core";
import { useQuery } from "@tanstack/react-query";
import React from "react";
import { HtmlPage } from "../components/html_page";
import { Fetch, LiccoRequest } from "../utils/fetching";

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

export const FFTOverviewTable: React.FC = () => {
    const { data, error, isLoading } = useQuery({
        queryKey: ["ffts"],
        queryFn: async (): Promise<FFT[]> => {
            let d = await Fetch.get<LiccoRequest<FFT[]>>("/ws/ffts/")
            return d.value;
        }
    })

    if (error) {
        return <p>Error: {error.message}</p>
    }

    return (
        <table className="table table-striped table-bordered table-sm table-sticky">
            <thead>
                <tr>
                    <th scope="col" className="text-nowrap">&emsp;</th>
                    <th scope="col" className="">Functional component name {isLoading ? <Button loading={isLoading} minimal={true} /> : null}</th>
                    <th scope="col" className="">Fungible token</th>
                </tr>
            </thead>
            <tbody>
                {data ?
                    data.map((fft) => {
                        return (
                            <tr key={fft._id}>
                                <td></td>
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
    )
}


export default function FFTs() {
    return (
        <HtmlPage>
            <FFTOverviewTable />
        </HtmlPage>
    )
}