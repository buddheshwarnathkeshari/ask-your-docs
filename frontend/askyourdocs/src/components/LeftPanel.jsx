// src/components/LeftPanel.jsx
import React, { useState } from "react";
import { createProject } from "../api";

export default function LeftPanel({ projects = [], onCreate, onSelect, activeProject }){
  const [name, setName] = useState("");

  async function handleCreate(e){
    e.preventDefault();
    if(!name.trim()) return;
    const p = await createProject(name, "");
    if(p && p.id){
      onCreate(p);
      setName("");
    } else {
      alert("Project creation failed");
    }
  }

  return (
    <>
      <form onSubmit={handleCreate} style={{display:"flex", gap:8}}>
        <input className="input" placeholder="New project name" value={name} onChange={e=>setName(e.target.value)} />
        <button className="btn" type="submit">Create</button>
      </form>

      <div style={{marginTop:8, fontSize:13, color:"var(--muted)"}}>Projects</div>
      <div className="projects" style={{marginTop:8}}>
        {projects.length === 0 && <div style={{color:"var(--muted)", padding:8}}>No projects yet</div>}
        {projects.map(p => (
          <div key={p.id} className={`project-item ${activeProject && activeProject.id===p.id ? "active" : ""}`} onClick={()=>onSelect(p)}>
            <div style={{display:"flex",flexDirection:"column"}}>
              <strong style={{fontSize:13}}>{p.name}</strong>
              <small style={{color:"var(--muted)"}}>{p.description}</small>
            </div>
            <div style={{opacity:0.6, fontSize:12}}>{/* created */}</div>
          </div>
        ))}
      </div>
    </>
  );
}
