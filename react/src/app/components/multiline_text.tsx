import { useMemo } from "react";

// React component that turns a text into paragraphs (in html \n symbols are ommited)
const MultiLineText: React.FC<{ text: string }> = ({ text }) => {
    let data = useMemo(() => {
        return text.split("\n").map((t, key) => {
            if (t) {
                return <p key={key}>{t}</p>
            }
            return '';
        })
    }, [text])
    return data
}

export { MultiLineText };

