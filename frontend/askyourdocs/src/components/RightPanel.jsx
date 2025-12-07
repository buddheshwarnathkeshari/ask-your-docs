// src/components/RightPanel.jsx
import React, { useEffect, useState } from "react";
import { uploadDocument, listDocuments } from "../api";

export default function RightPanel({ project, onUploadComplete }){
  const [file, setFile] = useState(null);
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(()=>{
    if(project) fetchDocs();
    else setDocs([]);
  }, [project]);

  async function fetchDocs(){
    if(!project) return;
    setLoading(true);
    const res = await listDocuments(project.id);
    setDocs(res || []);
    setLoading(false);
  }

  async function handleUpload(e){
    e.preventDefault();
    if(!file || !project){ alert("Choose project and file"); return; }
    const res = await uploadDocument(file, project.id);
    console.log("upload res", res);
    setFile(null);
    fetchDocs();
    if(onUploadComplete) onUploadComplete();
  }

  return (
    <>
      <div style={{display:"flex", justifyContent:"space-between", alignItems:"center"}}>
        <h3 className="h1">Documents</h3>
      </div>

      {!project && <div style={{color:"var(--muted)"}}>Select or create a project to upload documents.</div>}

      {project && (
        <>
          <form onSubmit={handleUpload} style={{display:"flex", gap:8, marginTop:8}}>
            <input type="file" onChange={e=>setFile(e.target.files[0])} />
            <button className="btn" type="submit">Upload</button>
          </form>

          <div style={{marginTop:12}}>
            {loading ? <div style={{color:"var(--muted)"}}>Loading...</div> :
              docs.length === 0 ? <div style={{color:"var(--muted)"}}>No documents yet</div> :
              <div className="docs">
                {docs.map(d => (
                  <div className="doc-item" key={d.id}>
                    <div style={{fontSize:13, fontWeight:600}}>{d.filename}</div>
                    <div style={{fontSize:12, color:"var(--muted)"}}>{d.status} • {d.size} bytes</div>
                  </div>
                ))}
              </div>
            }
          </div>
        </>
      )}
    </>
  );
}
