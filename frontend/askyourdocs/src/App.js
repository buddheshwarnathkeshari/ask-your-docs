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
  }, []);

  async function loadProjects(){
    const res = await listProjects();
    setProjects(res || []);
    if(res && res.length && !activeProject){
      setActiveProject(res[0]);
    }
  }

  return (
    <div className="app">
      <div className="left">
        <h3 className="h1">ASKYOURDOCS</h3>
        <LeftPanel
          projects={projects}
          onCreate={(p)=> { setProjects(prev => [p, ...prev]); setActiveProject(p); }}
          onSelect={(p)=> setActiveProject(p)}
          activeProject={activeProject}
        />
      </div>

      <div className="center">
        <ChatPanel project={activeProject} />
      </div>

      <div className="right">
        <RightPanel
          project={activeProject}
          onUploadComplete={() => {
            // Child will refresh docs via its internal fetch. If you want to update projects, add callbacks.
          }}
        />
      </div>
    </div>
  );
}
