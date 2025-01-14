
import '@blueprintjs/core/lib/css/blueprint.css';
import '@blueprintjs/icons/lib/css/blueprint-icons.css';
import "@blueprintjs/select/lib/css/blueprint-select.css";
import 'bootstrap/dist/css/bootstrap.min.css';

import { createLink } from "@/app/utils/path_utils";
import type { Metadata } from "next";
import "./globals.css";


export const metadata: Metadata = {
  title: "Licco",
  description: "Line configuration management",
};


export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <link rel="icon" href={createLink("/assets/favicons/favicon.png")} type="image/png" />
      </head>
      <body>
        {children}
      </body>
    </html>
  );
}
