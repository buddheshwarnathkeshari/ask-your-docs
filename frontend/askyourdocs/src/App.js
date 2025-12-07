// src/App.jsx
import React, { useEffect, useState } from "react";
import LeftPanel from "./components/LeftPanel";
import ChatPanel from "./components/ChatPanel";
import RightPanel from "./components/RightPanel";
import "./index.css";
import { listProjects, createProject, deleteProject } from "./api";

export default function App() {
  const [projects, setProjects] = useState([]);
  const [activeProject, setActiveProject] = useState(null);

  const [confirmDeleteProject, setConfirmDeleteProject] = useState(null);
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


  async function handleCreateProject(name, description) {
    try {
      const p = await createProject(name, description || "");
      if (p && p.id) {
        // put new project on top and activate
        setProjects((prev) => [p, ...prev]);
        setActiveProject(p);

        // update URL
        const url = new URL(window.location.href);
        url.searchParams.set("project_id", p.id);
        window.history.replaceState({}, "", url.toString());
      }
    } catch (err) {
      console.error("create project failed", err);
      alert("Project creation failed: " + (err.message || err));
    }
  }

  // When LeftPanel's delete button is pressed, it should call this to open confirm modal
  function handleRequestDeleteProject(project) {
    setConfirmDeleteProject(project);
  }

  // Confirmed delete action
  async function doDeleteProject() {
    if (!confirmDeleteProject) return;
    const project = confirmDeleteProject;
    try {
      await deleteProject(project.id);
      // remove from local list
      setProjects((prev) => prev.filter((p) => p.id !== project.id));

      // if the deleted project is active, pick next or clear
      if (activeProject && activeProject.id === project.id) {
        const remaining = projects.filter((p) => p.id !== project.id);
        const newActive = remaining.length ? remaining[0] : null;
        setActiveProject(newActive);
        const url = new URL(window.location.href);
        if (newActive && newActive.id) url.searchParams.set("project_id", newActive.id);
        else url.searchParams.delete("project_id");
        window.history.replaceState({}, "", url.toString());
      }
    } catch (err) {
      console.error("Delete project failed:", err);
      alert("Delete project failed: " + (err.message || JSON.stringify(err)));
    } finally {
      setConfirmDeleteProject(null);
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
          onDelete={async (project) => {
    // LeftPanel.doDelete() calls await onDelete(confirmDelete)
    try {
      await deleteProject(project.id);
      // remove from local list
      setProjects((prev) => prev.filter((x) => x.id !== project.id));
      // if deleted project was active -> choose next project or clear
      if (activeProject && activeProject.id === project.id) {
        const remaining = projects.filter((p) => p.id !== project.id);
        const newActive = remaining.length ? remaining[0] : null;
        setActiveProject(newActive);
        const url = new URL(window.location.href);
        if (newActive && newActive.id) url.searchParams.set("project_id", newActive.id);
        else url.searchParams.delete("project_id");
        window.history.replaceState({}, "", url.toString());
      }
    } catch (err) {
      console.error("deleteProject failed", err);
      throw err; // LeftPanel.doDelete will catch and alert if it wants
    }
  }}
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

      {/* Project delete confirm modal (same style as your document modal) */}
      {confirmDeleteProject && (
        <div
          style={{
            position: "fixed",
            left: 0,
            top: 0,
            right: 0,
            bottom: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "rgba(0,0,0,0.6)",
            zIndex: 1200,
          }}
        >
          <div style={{ width: 420, background: "var(--panel)", padding: 16, borderRadius: 8 }}>
            <h4 style={{ marginTop: 0 }}>Delete project</h4>
            <p>
              Are you sure you want to delete <strong>{confirmDeleteProject.name}</strong>?
            </p>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 12 }}>
              <button className="btn ghost" onClick={() => setConfirmDeleteProject(null)}>
                Cancel
              </button>
              <button
                className="btn"
                onClick={doDeleteProject}
                style={{ background: "crimson", borderColor: "transparent" }}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
