// src/components/ChatPanel.jsx
import React, { useEffect, useRef, useState } from "react";
import { createConversation, postMessage } from "../api";
import { updateProject } from "../api"; // optional direct import (or use parent callback)

export default function ChatPanel({ project, onProjectRename }) {
  const [conv, setConv] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [docsPresent, setDocsPresent] = useState(false);
  const [isAtBottom, setIsAtBottom] = useState(true);

  // edit modal states
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");

  const messagesRef = useRef(null);

  // helper: check documents using event-driven approach (RightPanel dispatches)
  useEffect(() => {
    // we only need to react to documents:updated to check docsPresence and create conversation
    const handler = async (ev) => {
      if (!project) return;
      const pid = ev.detail?.projectId;
      if (String(pid) !== String(project.id)) return;
      // create or reuse conversation
      await ensureConversation(); // will check docs presence internally
    };
    window.addEventListener("documents:updated", handler);
    return () => window.removeEventListener("documents:updated", handler);
  }, [project]);

  // create or reuse conversation for project (server returns messages when exists)
  async function ensureConversation() {
    if (!project) return;
    try {
      const resp = await createConversation(project.id);
      if (resp && resp.id) {
        setConv({ id: resp.id });
        if (Array.isArray(resp.messages) && resp.messages.length > 0) {
          setMessages(resp.messages.map(m => ({ role: m.role, text: m.text, created_at: m.created_at })));
          setDocsPresent(true);
        } else {
          // if the server returned existing conv but no messages, still consider docs present
          setDocsPresent(true);
          setMessages([]);
        }
      }
    } catch (err) {
      console.error("ensureConversation failed", err);
    }
  }

  // initial whenever project changes
  useEffect(() => {
    setMessages([]);
    setConv(null);
    setInput("");
    setDocsPresent(false);
    setEditing(false);
    setEditName("");
    if (!project) return;
    // attempt to reuse conversation on load (server will return messages if present)
    ensureConversation();
  }, [project?.id]);

  // scroll behavior
  useEffect(() => {
    const node = messagesRef.current;
    if (!node) return;
    if (isAtBottom) node.scrollTop = node.scrollHeight;
  }, [messages, isAtBottom]);

  useEffect(() => {
    const node = messagesRef.current;
    if (!node) return;
    const onScroll = () => {
      const tolerance = 20;
      const atBottom = (node.scrollHeight - node.scrollTop - node.clientHeight) <= tolerance;
      setIsAtBottom(atBottom);
    };
    node.addEventListener("scroll", onScroll);
    onScroll();
    return () => node.removeEventListener("scroll", onScroll);
  }, []);

  async function send() {
    if (!input.trim()) return;
    if (!conv) { alert("No conversation created"); return; }

    setMessages(prev => [...prev, { role: "user", text: input }]);
    setInput("");
    setIsAtBottom(true);

    try {
      const res = await postMessage(conv.id, input);
      if (res && res.answer) {
        setMessages(prev => [...prev, { role: "assistant", text: res.answer, citations: res.citations || [] }]);
      } else {
        setMessages(prev => [...prev, { role: "assistant", text: "No answer (error)" }]);
      }
    } catch (err) {
      console.error("send message error", err);
      setMessages(prev => [...prev, { role: "assistant", text: "Send failed" }]);
    }
  }

  function goToBottom() {
    const node = messagesRef.current;
    if (!node) return;
    node.scrollTop = node.scrollHeight;
    setIsAtBottom(true);
  }

  // Edit modal handlers
  function openEdit() {
    setEditName(project?.name || "");
    setEditing(true);
    setTimeout(() => {
      const el = document.getElementById("project-name-input");
      if (el) el.focus();
    }, 50);
  }

  async function saveEdit() {
    if (!editName.trim() || !project) { setEditing(false); return; }
    try {
      // use API directly or parent callback
      const updated = await updateProject(project.id, { name: editName.trim() });
      // notify parent (App) to update list & activeProject
      if (typeof onProjectRename === "function") onProjectRename(updated);
      setEditing(false);
    } catch (err) {
      console.error("Failed to update project", err);
      alert("Failed to rename project: " + (err.message || err));
    }
  }

  if (!project) return <div className="chat-empty">Pick a project to start.</div>;
  if (!docsPresent) return <div className="chat-empty">No documents uploaded yet. Upload docs in the right panel to start chat.</div>;

  return (
    <div className="chat-panel" style={{ height: "100%", position: "relative" }}>
      <div className="chat-header" style={{ padding: 16, display: "flex", alignItems: "center", gap: 12 }}>
        <h3 className="h1" style={{ margin: 0 }}>{project.name}</h3>
        <button title="Edit project name" onClick={openEdit} style={{
          background: "transparent", border: "none", color: "var(--muted)", cursor: "pointer", padding: 6
        }}>
          {/* simple pencil svg */}
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 20h9" />
            <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z"/>
          </svg>
        </button>
      </div>

      <div ref={messagesRef} className="chat-window" style={{ padding: 16 }}>
        {messages.map((m, idx) => (
          <div key={idx} className={`message ${m.role === 'user' ? 'user' : 'assistant'}`}>
            <div dangerouslySetInnerHTML={{ __html: (m.text || "").replace(/\n/g, "<br/>") }} />
            {m.citations && m.citations.length > 0 && (
              <div style={{ marginTop: 8, fontSize: 12, color: "var(--muted)" }}>
                <strong>Sources:</strong>
                <ul>
                  {m.citations.map((c, i) => <li key={i}>Doc: {c.document_id} Page:{c.page} — {c.snippet ? `${c.snippet.slice(0,120)}...` : 'no snippet'}</li>)}
                </ul>
              </div>
            )}
          </div>
        ))}
      </div>

      {!isAtBottom && (
        <button
          onClick={goToBottom}
          style={{
            position: "absolute",
            bottom: 100,
            left: "50%",
            transform: "translateX(-50%)",
            padding: "6px 12px",
            background: "#10a37f",
            borderRadius: 6,
            border: "none",
            cursor: "pointer",
            color: "white",
            fontSize: 12
          }}
        >
          ↓ Go to bottom
        </button>
      )}

      <div className="chat-input-bar" style={{ padding: 12 }}>
        <input
          className="input"
          placeholder="Ask something..."
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          aria-label="Chat input"
        />
        <button className="btn" onClick={send}>Send</button>
      </div>

      {editing && (
        <div style={{
          position: "fixed", left: 0, top: 0, right: 0, bottom: 0, display:"flex", alignItems:"center", justifyContent:"center",
          background: "rgba(0,0,0,0.6)", zIndex: 1000
        }}>
          <div style={{ width: 420, background: "var(--panel)", padding: 16, borderRadius: 8 }}>
            <h4 style={{ marginTop: 0 }}>Rename project</h4>
            <input id="project-name-input" className="input" value={editName} onChange={e=>setEditName(e.target.value)} />
            <div style={{ display:"flex", justifyContent:"flex-end", gap:8, marginTop:12 }}>
              <button className="btn ghost" onClick={()=>setEditing(false)}>Cancel</button>
              <button className="btn" onClick={saveEdit}>Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
