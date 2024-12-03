import React, { useMemo } from "react";

// React component that turns a text into paragraphs (in html \n symbols are ommited)
const MultiLineText: React.FC<{ text: string }> = ({ text }) => {
    let data = useMemo(() => {
        // split on consecutive newlines -> this should be a new paragraph
        return text.split(/\r?\n{2,}/).map((t, key) => {
            if (t) {
                return <p key={key}>{textToHtml(t)}</p>
            }
            return '';
        })
    }, [text])
    return data
}

const textToHtml = (text: string) => {
    let parts = text.split("\n");
    return parts.map((t, i) => {
        return <React.Fragment key={i}>{t}{i != parts.length - 1 ? <br /> : null}</React.Fragment>
    })
}

export { MultiLineText };

