import { NonIdealState, Spinner } from "@blueprintjs/core"
import React from "react"


export const LoadingSpinner: React.FC<{ isLoading: boolean, title?: string, description?: React.ReactElement | string }> = ({ isLoading, title = "Loading", description }) => {
    if (isLoading) {
        return <NonIdealState icon={<Spinner />} title={title} description={description} />
    }
    return null
}


export const ErrorDisplay: React.FC<{ title?: string, description?: React.ReactElement | string }> = ({ title = "Error", description }) => {
    return <NonIdealState icon={"error"} title={title} description={description} />
}