import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Footer } from "./footer";
import { Navigation } from "./navbar";

interface Props {
    children: React.ReactNode
}

const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            gcTime: 0,  // Disable caching globally
            staleTime: 0,  // Always refetch data globally
            refetchOnWindowFocus: false,
            refetchOnReconnect: false,
        },
    },
}
);

export const HtmlPage: React.FC<Props> = ({ children }) => {
    return (
        <>
            <QueryClientProvider client={queryClient}>
                <Navigation />
                <div className="main-content">
                    {children}
                </div>
                <Footer />
            </QueryClientProvider>
        </>
    );
}