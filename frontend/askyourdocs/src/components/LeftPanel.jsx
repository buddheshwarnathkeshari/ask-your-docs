// src/components/LeftPanel.jsx
import React, { useState } from "react";
import { createProject } from "../api";

/**
 * LeftPanel
 * props:
 *  - projects: []
 *  - onCreate(project)
 *  - onSelect(project)
 *  - activeProject
 *  - onDelete(project)
 */
export default function LeftPanel({ projects = [], onCreate, onSelect, activeProject, onDelete }) {
  const [name, setName] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(null); // project to delete

  async function handleCreate(e) {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      const p = await createProject(name.trim(), "");
      onCreate && onCreate(p);
      setName("");
    } catch (err) {
      console.error("create project failed", err);
      alert(err.message || "Project creation failed");
    }
  }

  function askDelete(project, e) {
    // e may be undefined if called programmatically
    if (e) e.stopPropagation();
    setConfirmDelete(project);
  }

  async function doDelete() {
    if (!confirmDelete) return;
    setConfirmDelete(null);
    try {
      await onDelete(confirmDelete);
    } catch (err) {
      // onDelete should handle errors; just in case:
      console.error("delete failed", err);
      alert(err.message || "Delete failed");
    }
  }

  return (
    <>
      <form onSubmit={handleCreate} style={{ display: "flex", gap: 8 }}>
        <input
          className="input"
          placeholder="New project name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          aria-label="New project name"
        />
        <button className="btn" type="submit" disabled={!name.trim()}>
          Create
        </button>
      </form>

      <div style={{ marginTop: 8, fontSize: 13, color: "var(--muted)" }}>Projects</div>
      <div className="projects" style={{ marginTop: 8 }}>
        {projects.length === 0 && <div style={{ color: "var(--muted)", padding: 8 }}>No projects yet</div>}
        {projects.map((p) => (
          <div
            key={p.id}
            className={`project-item ${activeProject && activeProject.id === p.id ? "active" : ""}`}
            onClick={() => onSelect && onSelect(p)}
            style={{ alignItems: "center" }}
          >
            <div style={{ display: "flex", flexDirection: "column", flex: 1, minWidth: 0 }}>
              <strong className="truncate" style={{ fontSize: 13 }}>{p.name}</strong>
              <small style={{ color: "var(--muted)" }} className="truncate">{p.description}</small>
            </div>

            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <button
                title="Delete project"
                onClick={(e) => { e.stopPropagation(); askDelete(p, e); }}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "rgba(255,255,255,0.6)",
                  cursor: "pointer",
                  padding: 6,
                }}
                aria-label={`Delete project ${p.name}`}
              >
                🗑
              </button>
            </div>
          </div>
        ))}
      </div>

      {confirmDelete && (
        <div style={{
          position: "fixed",
          left: 0, top: 0, right: 0, bottom: 0,
          display: "flex", alignItems: "center", justifyContent: "center",
          background: "rgba(0,0,0,0.6)", zIndex: 1200
        }}>
          <div style={{ width: 420, background: "var(--panel)", padding: 16, borderRadius: 8 }}>
            <h4 style={{ marginTop: 0 }}>Delete project</h4>
            <p>Are you sure you want to delete <strong>{confirmDelete.name}</strong>? This will hide it from the list.</p>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 12 }}>
              <button className="btn ghost" onClick={() => setConfirmDelete(null)}>Cancel</button>
              <button className="btn" onClick={doDelete}>Delete</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
