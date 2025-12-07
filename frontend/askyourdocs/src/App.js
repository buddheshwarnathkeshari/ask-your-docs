// src/App.jsx
import React, { useEffect, useState } from "react";
import LeftPanel from "./components/LeftPanel";
import ChatPanel from "./components/ChatPanel";
import RightPanel from "./components/RightPanel";
import "./index.css";
import { listProjects } from "./api";

export default function App(){
  const [projects, setProjects] = useState([]);
  const [activeProject, setActiveProject] = useState(null);

  useEffect(()=> {
    loadProjects();
    // if URL contains project_id, will be selected after projects load
  }, []);

  async function loadProjects(){
    try {
      const res = await listProjects();
      setProjects(res || []);
      // check URL param
      const url = new URL(window.location.href);
      const pid = url.searchParams.get("project_id");
      if (pid) {
        const found = (res || []).find(p => String(p.id) === String(pid));
        if (found) {
          setActiveProject(found);
          return;
        }
      }
      if(res && res.length && !activeProject){
        setActiveProject(res[0]);
      }
    } catch (e) {
      console.error("Failed loading projects", e);
    }
  }

  function onCreateProject(p){
    setProjects(prev => [p, ...prev]);
    selectProject(p);
  }

  function selectProject(p){
    setActiveProject(p);
    // update URL so refresh keeps selection
    try {
      const url = new URL(window.location.href);
      if (p && p.id) url.searchParams.set("project_id", p.id);
      else url.searchParams.delete("project_id");
      window.history.replaceState({}, "", url);
    } catch (e) {
      // ignore
    }
  }

  function onRenameProject(updatedProject){
    // update projects list and activeProject
    setProjects(prev => {
      return prev.map(p => (String(p.id) === String(updatedProject.id) ? updatedProject : p));
    });
    if (activeProject && String(activeProject.id) === String(updatedProject.id)) {
      setActiveProject(updatedProject);
    }
  }

  return (
    <div className="app">
      <div className="left">
        <h3 className="h1">AskYourDocs</h3>
        <LeftPanel
          projects={projects}
          onCreate={onCreateProject}
          onSelect={(p) => selectProject(p)}
          activeProject={activeProject}
        />
      </div>

      <div className="center">
        <ChatPanel project={activeProject} onProjectRename={onRenameProject} />
      </div>

      <div className="right">
        <RightPanel
          project={activeProject}
        />
      </div>
    </div>
  );
}
