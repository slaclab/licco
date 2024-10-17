'use client';

import { HtmlPage } from "./components/html_page";
import { ProjectsOverview } from "./projects/projects_overview";

export default function Home() {
  return (
    <HtmlPage>
      <ProjectsOverview />
    </HtmlPage>
  );
}
