// src/components/RightPanel.jsx
import React, { useEffect, useRef, useState } from "react";
import { listDocuments, uploadDocument, deleteDocument } from "../api";

/**
 * RightPanel
 * props:
 *  - project
 *  - projectId (optional)
 *  - onDocumentSelect(doc)
 */
export default function RightPanel({ project, projectId: projectIdProp, onDocumentSelect }) {
  const projectId = project?.id || projectIdProp || null;

  const [documents, setDocuments] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(null); // document to delete
  const fileInputRef = useRef(null);

  const fetchDocs = async () => {
    setLoadingDocs(true);
    try {
      const docs = await listDocuments(projectId);
      // filter out soft-deleted items if backend returns is_deleted flag
      setDocuments(Array.isArray(docs) ? docs.filter(d => !d.is_deleted) : []);
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

  useEffect(() => {
    const handler = (ev) => {
      const pid = ev.detail && ev.detail.projectId;
      if (!pid || String(pid) === String(projectId)) fetchDocs();
    };
    window.addEventListener("documents:updated", handler);
    return () => window.removeEventListener("documents:updated", handler);
  }, [projectId]);

  const onFileChange = (e) => {
    setSelectedFile(e.target.files?.[0] || null);
  };

  const doUpload = async () => {
    if (!selectedFile) return;
    setUploading(true);
    try {
      await uploadDocument(selectedFile, projectId);
      await fetchDocs();
      // notify other components (ChatPanel) to create conversation if needed
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

  function askDeleteDocument(doc, e) {
    if (e) e.stopPropagation();
    setConfirmDelete(doc);
  }

  async function doDeleteDocument() {
    if (!confirmDelete) return;
    const doc = confirmDelete;
    setConfirmDelete(null);
    try {
      await deleteDocument(doc.id);
      await fetchDocs();
      window.dispatchEvent(new CustomEvent("documents:updated", { detail: { projectId } }));
    } catch (err) {
      console.error("delete document failed", err);
      alert(err.message || "Delete failed");
    }
  }

  const docCount = documents.length;

  return (
    <aside className="right-panel" style={{ padding: 20, width: 320 }}>
      <h3 style={{ margin: 0 }}>Documents {`(${docCount})`}</h3>

      <div className="uploader" style={{ display: "flex", gap: 8, marginTop: 12, marginBottom: 12 }}>
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
        {project ? <div>Project: <strong className="truncate">{project.name}</strong></div> : <div>All documents</div>}
      </div>

      <div className="documents-list" style={{
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

        {documents.map((d) => (
          <div
            key={d.id}
            className="doc-item"
            onClick={() => onDocumentSelect && onDocumentSelect(d)}
            style={{
              padding: "12px 14px",
              borderRadius: 10,
              background: "#121212",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: 8,
              minWidth: 0
            }}
          >
            <div style={{ display: "flex", flexDirection: "column", flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="doc-title truncate" title={d.filename} style={{ fontWeight: 600 }}>{d.filename}</div>
                </div>

                {/* status + delete */}
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ color: (d.status || "").toLowerCase() === "done" ? "#8fd99e" : "#f0c36d", fontSize: 12 }}>
                    {(d.status || "done") === "done" ? "✓" : d.status || "queued"}
                  </span>

                  <button
                    title="Delete document"
                    onClick={(e) => askDeleteDocument(d, e)}
                    style={{ background: "transparent", border: "none", color: "rgba(255,255,255,0.6)", cursor: "pointer", padding: 6 }}
                    aria-label={`Delete document ${d.filename}`}
                  >
                    🗑
                  </button>
                </div>
              </div>

              <div style={{ fontSize: 12, color: "#999", marginTop: 6 }}>{(d.status || "done")} · {d.size ? `${d.size} bytes` : ""}</div>
            </div>
          </div>
        ))}
      </div>

      {confirmDelete && (
        <div style={{
          position: "fixed", left: 0, top: 0, right: 0, bottom: 0,
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
