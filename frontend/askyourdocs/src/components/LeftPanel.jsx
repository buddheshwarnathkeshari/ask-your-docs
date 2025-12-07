// src/components/LeftPanel.jsx
import React, { useState } from "react";
import { createProject } from "../api";

/**
 * LeftPanel
 * props:
 *  - projects: []
 *  - onCreate(project)  // optional async function
 *  - onSelect(project)
 *  - activeProject
 *  - onDelete(project)  // async
 */
export default function LeftPanel({ projects = [], onCreate, onSelect, activeProject, onDelete }) {
  const [name, setName] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(null); // project to delete
  const [creating, setCreating] = useState(false);

  async function handleCreate(e) {
    e.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    try {
      // prefer parent onCreate if provided (it may do API work and return project)
      if (typeof onCreate === "function") {
        const maybeProject = await onCreate({ name: name.trim(), description: "" });
        setName("");
        setCreating(false);
        // parent handled creation
        return;
      }
      // fallback: call API directly
      const p = await createProject(name.trim(), "");
      setName("");
      if (typeof onCreate === "function") onCreate(p);
    } catch (err) {
      console.error("create project failed", err);
      alert(err.message || "Project creation failed");
    } finally {
      setCreating(false);
    }
  }

  function askDelete(project, e) {
    if (e && typeof e.stopPropagation === "function") e.stopPropagation();
    setConfirmDelete(project);
  }

  async function doDelete() {
    if (!confirmDelete) return;
    const proj = confirmDelete;
    setConfirmDelete(null);
    try {
      if (typeof onDelete === "function") {
        await onDelete(proj);
      } else {
        console.warn("onDelete not provided; nothing deleted");
      }
    } catch (err) {
      console.error("delete failed", err);
      alert(err.message || "Delete failed");
    }
  }

  return (
    <>
      <div style={{ padding: 14, boxSizing: "border-box", display: "flex", flexDirection: "column", gap: 12 }}>
        <form onSubmit={handleCreate} style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            className="input"
            placeholder="New project name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            aria-label="New project name"
            style={{
              flex: 1,
              minWidth: 0,
              height: 36,
              padding: "8px 10px",
              borderRadius: 8,
              boxSizing: "border-box",
            }}
          />
          <button
            className="btn"
            type="submit"
            disabled={!name.trim() || creating}
            aria-disabled={!name.trim() || creating}
            style={{
              height: 36,
              padding: "0 12px",
              opacity: (!name.trim() || creating) ? 0.6 : 1,
              cursor: (!name.trim() || creating) ? "not-allowed" : "pointer",
            }}
          >
            {creating ? "Creating..." : "Create"}
          </button>
        </form>

        <div style={{ marginTop: 2, fontSize: 13, color: "var(--muted)" }}>Projects</div>

        <div
          className="projects"
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 8,
            marginTop: 8,
            overflowY: "auto",
            maxHeight: "calc(100vh - 220px)",
            paddingRight: 6,
            boxSizing: "border-box",
          }}
        >
          {projects.length === 0 && <div style={{ color: "var(--muted)", padding: 8 }}>No projects yet</div>}

          {projects.map((p) => {
            const active = activeProject && String(activeProject.id) === String(p.id);
            return (
              <div
                key={p.id}
                role="button"
                tabIndex={0}
                onClick={() => onSelect && onSelect(p)}
                onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onSelect && onSelect(p)}
                style={{
                  display: "flex",
                  gap: 8,
                  alignItems: "center",
                  width: "100%",
                  boxSizing: "border-box",
                  padding: "10px 12px",
                  borderRadius: 10,
                  cursor: "pointer",
                  background: active ? "rgba(16,163,127,0.12)" : "transparent",
                  border: active ? "1px solid rgba(16,163,127,0.12)" : "1px solid rgba(255,255,255,0.02)",
                  transition: "background 120ms ease, transform 80ms ease",
                }}
                onMouseEnter={(e) => {
                  if (!active) e.currentTarget.style.background = "rgba(255,255,255,0.02)";
                }}
                onMouseLeave={(e) => {
                  if (!active) e.currentTarget.style.background = "transparent";
                }}
              >
                <div style={{ display: "flex", flexDirection: "column", minWidth: 0, flex: 1 }}>
                  <strong
                    className="truncate"
                    style={{
                      fontSize: 14,
                      lineHeight: "18px",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                    title={p.name}
                  >
                    {p.name}
                  </strong>
                  <small
                    style={{
                      color: "var(--muted)",
                      fontSize: 12,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                    title={p.description}
                  >
                    {p.description || ""}
                  </small>
                </div>

                <div style={{ display: "flex", gap: 6, alignItems: "center", flexShrink: 0 }}>
                  <button
                    title={`Delete ${p.name}`}
                    onClick={(e) => askDelete(p, e)}
                    style={{
                      background: "transparent",
                      border: "none",
                      color: "rgba(255,255,255,0.6)",
                      cursor: "pointer",
                      padding: 6,
                      fontSize: 14,
                      lineHeight: "14px",
                    }}
                    aria-label={`Delete project ${p.name}`}
                  >
                    🗑
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {confirmDelete && (
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
              Are you sure you want to delete <strong>{confirmDelete.name}</strong>? This will hide it from the list.
            </p>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 12 }}>
              <button className="btn ghost" onClick={() => setConfirmDelete(null)}>
                Cancel
              </button>
              <button
                className="btn"
                onClick={doDelete}
                style={{ background: "crimson", borderColor: "transparent" }}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
