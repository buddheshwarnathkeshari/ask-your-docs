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

  useEffect(() => {
    const handler = (ev) => {
      const { documentId } = ev.detail || {};
      if (!documentId) return;
      const el = listRef.current && listRef.current.querySelector(`[data-docid="${documentId}"]`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        el.classList.remove("blink");
        // restart animation
        // eslint-disable-next-line no-unused-expressions
        el.offsetWidth;
        el.classList.add("blink");
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

  const openFilePicker = () => {
    if (fileInputRef.current) fileInputRef.current.click();
  };

  const doUpload = async () => {
    if (!selectedFile) return;
    setUploading(true);
    try {
      await uploadDocument(selectedFile, projectId);
      await fetchDocs();
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

  async function doDeleteDocument() {
    if (!confirmDelete) return;
    const doc = confirmDelete;
    setConfirmDelete(null);
    try {
      const res = await fetch(`/api/documents/${doc.id}/delete/`, { method: "DELETE" });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Delete failed");
      }
      await fetchDocs();
      window.dispatchEvent(new CustomEvent("documents:updated", { detail: { projectId } }));
    } catch (err) {
      console.error("delete document failed", err);
      alert(err.message || "Delete failed");
    }
  }

  // small helper for filename display (shorten long names)
  const shortName = (name, max = 40) => {
    if (!name) return "";
    return name.length > max ? name.slice(0, max - 3) + "..." : name;
  };

  return (
    <aside
      className="right-panel"
      style={{
        padding: 14,
        // width: 300,
        minWidth: 260,
        boxSizing: "border-box",
        display: "flex",
        flexDirection: "column",
        gap: 12,
      }}
    >
      <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>
        Documents <span style={{ color: "#9aa", fontWeight: 500, marginLeft: 8 }}>({documents.length})</span>
      </h3>

      {/* uploader row: custom picker (hidden native input) + Upload button */}
      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.txt,.docx"
          onChange={onFileChange}
          style={{
            position: "absolute",
            opacity: 0,
            pointerEvents: "none",
            width: 0,
            height: 0,
          }}
        />

        {/* styled file display / choose button */}
        <button
          type="button"
          onClick={openFilePicker}
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 10,
            padding: "9px 12px",
            borderRadius: 8,
            background: "transparent",
            border: "1px solid rgba(255,255,255,0.04)",
            color: "inherit",
            cursor: "pointer",
            textAlign: "left",
            fontSize: 13,
          }}
        >
          <span style={{ color: selectedFile ? "#fff" : "#bbb", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", display: "block", flex: 1 }}>
            {selectedFile ? shortName(selectedFile.name, 36) : "Choose file"}
          </span>
          <span style={{ marginLeft: 8, fontWeight: 700, color: "#9aa", fontSize: 13 }}>{selectedFile ? "Change" : "Browse"}</span>
        </button>

        <button
          onClick={doUpload}
          disabled={!selectedFile || uploading}
          style={{
            background: selectedFile && !uploading ? "#16a085" : "rgba(16,160,140,0.18)",
            color: "white",
            border: "none",
            padding: "9px 12px",
            borderRadius: 8,
            cursor: (!selectedFile || uploading) ? "not-allowed" : "pointer",
            minWidth: 74,
            fontWeight: 700,
            fontSize: 13,
            boxShadow: "none",
          }}
        >
          {uploading ? "Uploading…" : "Upload"}
        </button>
      </div>

      <div style={{ color: "#aaa", fontSize: 13 }}>
        {project ? <div>Project: <strong style={{ color: "inherit" }}>{project.name}</strong></div> : <div>All documents</div>}
      </div>

      <div
        ref={listRef}
        className="documents-list"
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 10,
          maxHeight: "calc(100vh - 220px)",
          overflowY: "auto",
          paddingRight: 6,
        }}
      >
        {loadingDocs && <div style={{ color: "#999", fontSize: 13 }}>Loading documents…</div>}

        {documents.length === 0 && !loadingDocs && (
          <div style={{ color: "#999", fontSize: 13 }}>No documents uploaded yet.</div>
        )}

        {documents.map((d) => {
          const downloadUrl = d.download_url || `/api/documents/${d.id}/download/`;
          return (
            <div
              key={d.id}
              data-docid={d.id}
              style={{
                padding: "10px 12px",
                borderRadius: 10,
                background: "#0f0f0f",
                cursor: typeof onDocumentSelect === "function" ? "pointer" : "default",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                border: (String(projectId) && String(d.project_id) === String(projectId)) ? "1px solid rgba(16,163,127,0.06)" : "1px solid rgba(255,255,255,0.02)",
              }}
              onClick={() => {
                if (typeof onDocumentSelect === "function") onDocumentSelect(d);
              }}
            >
              <div style={{ display: "flex", flexDirection: "column", minWidth: 0, marginRight: 8 }}>
                <div
                  style={{
                    fontWeight: 700,
                    fontSize: 14,
                    lineHeight: "18px",
                    color: "inherit",
                    whiteSpace: "normal",
                    wordBreak: "break-word",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    maxHeight: 40,
                  }}
                  title={d.filename}
                >
                  {d.filename}
                </div>
                <div style={{ fontSize: 12, color: "#999", marginTop: 6 }}>
                  {(d.status || "unknown")} · {d.size ? `${d.size} bytes` : ""}
                </div>
              </div>

              <div style={{ display: "flex", gap: 8, alignItems: "center", flexShrink: 0 }}>
                <a
                  title="Download"
                  href={downloadUrl}
                  style={{
                    color: "#bcd",
                    textDecoration: "none",
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    width: 28,
                    height: 28,
                    borderRadius: 6,
                    fontSize: 14,
                  }}
                  onClick={(e) => e.stopPropagation()}
                >
                  ⬇
                </a>

                <button
                  title="Delete"
                  onClick={(e) => { e.stopPropagation(); setConfirmDelete(d); }}
                  style={{
                    background: "transparent",
                    border: "none",
                    color: "rgba(255,255,255,0.7)",
                    cursor: "pointer",
                    padding: 6,
                    width: 28,
                    height: 28,
                    borderRadius: 6,
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 13,
                  }}
                >
                  🗑
                </button>

                { (d.status || "").toLowerCase() === "done" && (
                  <span style={{ fontSize: 13, color: "#8fd99e", minWidth: 18, textAlign: "center" }}>✓</span>
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
              <button className="btn delete-button" onClick={doDeleteDocument}>Delete</button>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
