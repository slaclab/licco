import { Colors } from "@blueprintjs/core";
import React from "react";
import { Col, Row } from "react-bootstrap";


export const DividerWithText: React.FC<{ text: React.ReactElement | string, className?: string }> = ({ text, className }) => {
    const renderText = () => {
        if (typeof (text) == 'string') {
            return <div style={{ color: Colors.GRAY1 }}>{text}</div>
        }
        return text
    }

    return (
        <Row className={`align-items-center ${className || ''}`}>
            <Col><hr /></Col>
            <Col className="col-auto m-0 p-0"> {renderText()} </Col>
            <Col><hr /></Col>
        </Row>
    )
}