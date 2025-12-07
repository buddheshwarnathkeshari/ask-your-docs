// src/components/RightPanel.jsx
import React, { useEffect, useRef, useState } from "react";
import { listDocuments, uploadDocument } from "../api";

export default function RightPanel({ project, projectId: projectIdProp, onDocumentSelect }) {
  const projectId = project?.id || projectIdProp || null;

  const [documents, setDocuments] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(null);
  const fileInputRef = useRef(null);
  const listRef = useRef(null);

  const fetchDocs = async () => {
    setLoadingDocs(true);
    try {
      const docs = await listDocuments(projectId);
      setDocuments(Array.isArray(docs) ? docs : []);
    } catch (err) {
      console.error("Failed to load documents", err);
      setDocuments([]);
    } finally {
      setLoadingDocs(false);
    }
  };

  useEffect(() => {
    fetchDocs();
  }, [projectId]);

  // listen for external scrollTo events (clicking chip)
  useEffect(() => {
    const handler = (ev) => {
      const { documentId } = ev.detail || {};
      if (!documentId) return;
      // find element
      const el = listRef.current && listRef.current.querySelector(`[data-docid="${documentId}"]`);
      if (el) {
        // smooth scroll into view within listRef
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        // add blink class (CSS animation 3 iterations)
        el.classList.remove("blink"); // reset
        // force reflow to restart animation
        // eslint-disable-next-line no-unused-expressions
        el.offsetWidth;
        el.classList.add("blink");
        // cleanup after animationend
        const onEnd = () => {
          el.classList.remove("blink");
          el.removeEventListener("animationend", onEnd);
        };
        el.addEventListener("animationend", onEnd);
      }
    };
    window.addEventListener("documents:scrollTo", handler);
    return () => window.removeEventListener("documents:scrollTo", handler);
  }, []);

  const onFileChange = (e) => {
    setSelectedFile(e.target.files?.[0] || null);
  };

  const doUpload = async () => {
    if (!selectedFile) return;
    setUploading(true);
    try {
      await uploadDocument(selectedFile, projectId);
      await fetchDocs();
      // notify others
      window.dispatchEvent(new CustomEvent("documents:updated", { detail: { projectId } }));
    } catch (err) {
      console.error("Upload failed", err);
      alert(err.message || "Upload failed");
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
      setSelectedFile(null);
      setUploading(false);
    }
  };

  // delete flow (call prop or fallback to API delete endpoint)
  async function doDeleteDocument() {
    if (!confirmDelete) return;
    const doc = confirmDelete;
    setConfirmDelete(null);
    try {
      // attempt to call API delete endpoint (assumes /api/documents/<id>/delete/ exists)
      const res = await fetch(`/api/documents/${doc.id}/delete/`, { method: "DELETE" });
      if (!res.ok) {
        const data = await res.json().catch(()=>({}));
        throw new Error(data.detail || "Delete failed");
      }
      await fetchDocs();
      window.dispatchEvent(new CustomEvent("documents:updated", { detail: { projectId } }));
    } catch (err) {
      console.error("delete document failed", err);
      alert(err.message || "Delete failed");
    }
  }

  return (
    <aside className="right-panel" style={{ padding: 20, width: 320 }}>
      <h3 style={{ marginBottom: 12 }}>Documents ({documents.length})</h3>

      <div className="uploader" style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.txt,.docx"
          onChange={onFileChange}
          disabled={uploading}
          style={{ flex: 1 }}
        />
        <button
          onClick={doUpload}
          disabled={!selectedFile || uploading}
          style={{
            background: "#16a085",
            color: "white",
            border: "none",
            padding: "8px 12px",
            borderRadius: 8,
            cursor: (!selectedFile || uploading) ? "not-allowed" : "pointer",
          }}
        >
          {uploading ? "Uploading…" : "Upload"}
        </button>
      </div>

      <div style={{ marginBottom: 8, color: "#aaa", fontSize: 13 }}>
        {project ? <div>Project: <strong>{project.name}</strong></div> : <div>All documents</div>}
      </div>

      <div ref={listRef} className="documents-list" style={{
        display: "flex",
        flexDirection: "column",
        gap: 8,
        maxHeight: "calc(100vh - 260px)",
        overflowY: "auto",
        paddingRight: 6
      }}>
        {loadingDocs && <div style={{ color: "#999" }}>Loading documents…</div>}

        {documents.length === 0 && !loadingDocs && (
          <div style={{ color: "#999" }}>No documents uploaded yet.</div>
        )}

        {documents.map((d) => {
          // determine download URL: use server-provided download_url if available
          const downloadUrl = d.download_url || `/api/documents/${d.id}/download/`;
          return (
            <div
              key={d.id}
              data-docid={d.id}
              style={{
                padding: "12px 14px",
                borderRadius: 10,
                background: "#121212",
                cursor: onDocumentSelect ? "pointer" : "default",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                border: (String(projectId) && String(d.project_id) === String(projectId)) ? "1px solid rgba(16,163,127,0.06)" : undefined
              }}
            >
              <div style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
                <div style={{ fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 160 }}>{d.filename}</div>
                <div style={{ fontSize: 12, color: "#999" }}>{(d.status || "unknown")} · {d.size ? `${d.size} bytes` : ""}</div>
              </div>

              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <a title="Download" href={downloadUrl} style={{ color: "#9aa", textDecoration: "none" }}>
                  ⬇
                </a>

                <button
                  title="Delete"
                  onClick={(e) => { e.stopPropagation(); setConfirmDelete(d); }}
                  style={{ background: "transparent", border: "none", color: "rgba(255,255,255,0.6)", cursor: "pointer", padding: 6 }}
                >
                  🗑
                </button>

                { (d.status || "").toLowerCase() === "done" && (
                  <span style={{ fontSize: 12, color: "#8fd99e" }}>✓</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {confirmDelete && (
        <div style={{
          position: "fixed",
          left: 0, top: 0, right: 0, bottom: 0,
          display: "flex", alignItems: "center", justifyContent: "center",
          background: "rgba(0,0,0,0.6)", zIndex: 1200
        }}>
          <div style={{ width: 420, background: "var(--panel)", padding: 16, borderRadius: 8 }}>
            <h4 style={{ marginTop: 0 }}>Delete document</h4>
            <p>Are you sure you want to delete <strong>{confirmDelete.filename}</strong>?</p>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 12 }}>
              <button className="btn ghost" onClick={() => setConfirmDelete(null)}>Cancel</button>
              <button className="btn" onClick={doDeleteDocument}>Delete</button>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
