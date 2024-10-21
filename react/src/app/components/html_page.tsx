import { Footer } from "./footer";
import { Navigation } from "./navbar";

interface Props {
    children: React.ReactNode
}

export const HtmlPage: React.FC<Props> = ({ children }) => {
    return (
        <>
            <Navigation />
            <div className="main-content">
                {children}
            </div>
            <Footer />
        </>
    );
}