
import '@blueprintjs/core/lib/css/blueprint.css';
import '@blueprintjs/icons/lib/css/blueprint-icons.css';
import 'bootstrap/dist/css/bootstrap.min.css';
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
      <meta charSet='UTF-8'></meta>
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <body>
        {children}
      </body>
    </html>
  );
}
