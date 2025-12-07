// src/components/RightPanel.jsx
import React, { useEffect, useRef, useState } from "react";
import { listDocuments, uploadDocument } from "../api";

export default function RightPanel({ project, projectId: projectIdProp, onDocumentSelect }) {
  const projectId = project?.id || projectIdProp || null;

  const [documents, setDocuments] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const fileInputRef = useRef(null);

  const fetchDocs = async () => {
    setLoadingDocs(true);
    try {
      const docs = await listDocuments(projectId);
      setDocuments(Array.isArray(docs) ? docs : []);
      window.dispatchEvent(new CustomEvent("documents:updated", { detail: { projectId } }));
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

  const onFileChange = (e) => {
    setSelectedFile(e.target.files?.[0] || null);
  };

  const doUpload = async () => {
    if (!selectedFile) return;
    setUploading(true);
    try {
      await uploadDocument(selectedFile, projectId);
      await fetchDocs();
    } catch (err) {
      console.error("Upload failed", err);
      alert("Upload failed: " + (err.message || err));
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
      setSelectedFile(null);
      setUploading(false);
    }
  };

  const docCount = documents.length;

  return (
    <aside className="right" style={{ padding: 20 }}>
      <h3 style={{ marginBottom: 12 }}>Documents {typeof docCount === "number" ? `(${docCount})` : ""}</h3>

      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
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
            opacity: (!selectedFile || uploading) ? 0.6 : 1
          }}
        >
          {uploading ? "Uploading…" : "Upload"}
        </button>
      </div>

      <div style={{ marginBottom: 8, color: "#aaa", fontSize: 13 }}>
        {/* removed project name display per request */}
      </div>

      <div className="documents-list" style={{
        display: "flex",
        flexDirection: "column",
        gap: 8,
        maxHeight: "calc(100vh - 300px)",
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
            onClick={() => onDocumentSelect && onDocumentSelect(d)}
            style={{
              padding: "12px 14px",
              borderRadius: 10,
              background: "#121212",
              cursor: onDocumentSelect ? "pointer" : "default",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center"
            }}
          >
            <div style={{ display: "flex", flexDirection: "column" }}>
              <div style={{ fontWeight: 600 }}>{d.filename}</div>
              <div style={{ fontSize: 12, color: "#999" }}>
                {d.size ? `${d.size} bytes` : ""} {d.status ? ` · ${d.status}` : ""}
              </div>
            </div>

            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <span style={{ fontSize: 12, color: "#8fd99e" }}>✓</span>
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}
