// src/components/ChatPanel.jsx
import React, { useEffect, useRef, useState } from "react";
import { createConversation, postMessage } from "../api";
import { updateProject } from "../api"; // optional

export default function ChatPanel({ project, onProjectRename }) {
  const [conv, setConv] = useState(null);
  const [messages, setMessages] = useState([]); // messages from server or optimistic
  const [input, setInput] = useState("");
  const [docsPresent, setDocsPresent] = useState(false);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [sending, setSending] = useState(false); // used to show typing placeholder

  const messagesRef = useRef(null);

  // Create or reuse conversation for project
  async function ensureConversation() {
    if (!project) return;
    try {
      const resp = await createConversation(project.id);
      if (resp && resp.id) {
        setConv({ id: resp.id });
        // server returns messages with citations (ConversationCreateView)
        if (Array.isArray(resp.messages) && resp.messages.length > 0) {
          setMessages(resp.messages);
          setDocsPresent(true);
        } else {
          // no messages yet, but documents exist on server (we consider docsPresent true because createConversation succeeded for project)
          setMessages([]);
          setDocsPresent(true);
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
    setSending(false);
    if (!project) return;
    ensureConversation();
  }, [project?.id]);

  // listen to docs updated events from RightPanel (upload / delete)
  useEffect(() => {
    const handler = async (ev) => {
      if (!project) return;
      const pid = ev.detail?.projectId;
      if (String(pid) !== String(project.id)) return;
      // re-create / reuse conversation to make sure messages/citations restored
      await ensureConversation();
    };
    window.addEventListener("documents:updated", handler);
    return () => window.removeEventListener("documents:updated", handler);
  }, [project]);

  // auto-scroll when messages change but only if user is at bottom
  useEffect(() => {
    const node = messagesRef.current;
    if (!node) return;
    if (isAtBottom) node.scrollTop = node.scrollHeight;
  }, [messages, isAtBottom]);

  // track scroll to show "go to bottom"
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

  // helper to dispatch scroll event to RightPanel
  function scrollToDocument(docId) {
    window.dispatchEvent(new CustomEvent("documents:scrollTo", { detail: { documentId: docId } }));
  }

  // render message text + inline chips
  function renderMessageHTML(text, citations = []) {
    // We want inline chips for referenced documents. The backend's pretty_replace_sources might have
    // inserted readable titles in square brackets. But to be robust, we'll insert chips by scanning
    // for each citation.document_title and replacing the first occurrence with a chip.
    let html = text || "";
    if (!citations || citations.length === 0) return { __html: html.replace(/\n/g, "<br/>") };

    for (const c of citations) {
      const title = c.document_title || c.document_id || "source";
      const short = title.length > 60 ? title.slice(0, 56).trim() + "..." : title;
      // escape for regexp
      const esc = short.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const patt = new RegExp(esc);
      // only replace first occurrence
      if (patt.test(html)) {
        // insert a clickable span with data-docid for mapping
        const span = `<span class="source-chip" data-docid="${c.document_id}">${short}</span>`;
        html = html.replace(patt, span);
      } else {
        // fallback: try to replace the document_title if it's longer than short (non-truncated)
        const fullEsc = (c.document_title || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        if (fullEsc && new RegExp(fullEsc).test(html)) {
          html = html.replace(new RegExp(fullEsc), `<span class="source-chip" data-docid="${c.document_id}">${short}</span>`);
        }
      }
    }

    // convert newlines to <br/>
    html = html.replace(/\n/g, "<br/>");

    return { __html: html };
  }

  // attach click handler for inline chips (delegation)
  useEffect(() => {
    const node = messagesRef.current;
    if (!node) return;
    const onClick = (e) => {
      const chip = e.target.closest && e.target.closest(".source-chip");
      if (chip) {
        const docId = chip.getAttribute("data-docid");
        if (docId) {
          scrollToDocument(docId);
        }
      }
    };
    node.addEventListener("click", onClick);
    return () => node.removeEventListener("click", onClick);
  }, []);

  // optimistic send: add user msg, show local typing bubble, then append assistant
  async function send() {
    if (!input.trim()) return;
    if (!conv) { alert("No conversation created"); return; }

    const text = input.trim();
    // add user message
    setMessages(prev => [...prev, { role: "user", text, created_at: new Date().toISOString() }]);
    setInput("");
    setIsAtBottom(true);
    setSending(true); // show typing

    try {
      const res = await postMessage(conv.id, text);
      // remove typing indicator (we show server assistant next)
      setSending(false);
      if (res && res.answer) {
        setMessages(prev => [...prev, { role: "assistant", text: res.answer, citations: res.citations || [], created_at: new Date().toISOString() }]);
      } else if (res && res.detail) {
        setMessages(prev => [...prev, { role: "assistant", text: `Error: ${res.detail}`, created_at: new Date().toISOString() }]);
      } else {
        setMessages(prev => [...prev, { role: "assistant", text: "No answer (error)", created_at: new Date().toISOString() }]);
      }
    } catch (err) {
      console.error("send message error", err);
      setSending(false);
      setMessages(prev => [...prev, { role: "assistant", text: "Send failed", created_at: new Date().toISOString() }]);
    }
  }

  // go to bottom helper
  function goToBottom() {
    const node = messagesRef.current;
    if (!node) return;
    node.scrollTop = node.scrollHeight;
    setIsAtBottom(true);
  }

  // edit project name (modal)
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
      const updated = await updateProject(project.id, { name: editName.trim() });
      if (typeof onProjectRename === "function") onProjectRename(updated);
      setEditing(false);
    } catch (err) {
      console.error("Failed to update project", err);
      alert("Failed to rename project: " + (err.message || err));
    }
  }

  // final UI
  if (!project) return <div className="chat-empty">Pick a project to start.</div>;
  if (!docsPresent) return <div className="chat-empty">No documents uploaded yet. Upload docs in the right panel to start chat.</div>;

  return (
    <div className="chat-panel" style={{ height: "100%", position: "relative", display: "flex", flexDirection: "column" }}>
      <div className="chat-header" style={{ padding: 16, display: "flex", alignItems: "center", gap: 12 }}>
        <h3 className="h1" style={{ margin: 0 }}>{project.name}</h3>
        <button title="Edit project name" onClick={openEdit} style={{
          background: "transparent", border: "none", color: "var(--muted)", cursor: "pointer", padding: 6
        }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 20h9" />
            <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z"/>
          </svg>
        </button>
      </div>

      <div ref={messagesRef} className="chat-window" style={{ padding: 16, flex: 1 }}>
        {messages.map((m, idx) => (
          <div key={idx} className={`message ${m.role === 'user' ? 'user' : 'assistant'}`} style={{ marginBottom: 14 }}>
            <div dangerouslySetInnerHTML={renderMessageHTML(m.text, m.citations || [])} />
            {m.citations && m.citations.length > 0 && (
              <div style={{ marginTop: 8, fontSize: 12, color: "var(--muted)" }}>
                <strong>Sources:</strong>
                <ul style={{ marginTop: 8 }}>
                  {m.citations.map((c, i) => {
                    const title = c.document_title || c.document_id || "source";
                    const short = title.length > 60 ? title.slice(0, 56).trim() + "..." : title;
                    return (
                      <li key={i} style={{ marginBottom: 6 }}>
                        <button
                          className="chip-link"
                          onClick={() => scrollToDocument(c.document_id)}
                          style={{ background: "transparent", border: "none", padding: 0, color: "var(--text)", cursor: "pointer" }}
                        >
                          <strong>{short}</strong>
                        </button>
                        {c.snippet ? <div style={{ color: "var(--muted)", marginTop: 4 }}>{c.snippet.slice(0, 140)}{c.snippet.length>140?"...":""}</div> : null}
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
          </div>
        ))}

        {sending && (
          <div className="message assistant typing" style={{ opacity: 0.8 }}>
            <div>...</div>
          </div>
        )}
      </div>

      {(
        <button
          onClick={goToBottom}
          style={{
            position: "absolute",
            right: 24,
            bottom: 84,
            padding: "8px 12px",
            background: "#10a37f",
            borderRadius: 999,
            border: "none",
            cursor: "pointer",
            color: "white",
            fontSize: 12,
            zIndex: 600
          }}
        >
          ↓
        </button>
      )}

      <div className="chat-input-bar" style={{ padding: 12, display: "flex", gap: 8 }}>
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
