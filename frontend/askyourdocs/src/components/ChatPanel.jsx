// src/components/ChatPanel.jsx
import React, { useEffect, useRef, useState } from "react";
import { createConversation, postMessage } from "../api";
import { updateProject } from "../api"; // optional direct import (or use parent callback)

/**
 * ChatPanel
 *
 * - Loads (and rehydrates) conversation messages from GET /api/conversations/:id/messages/
 * - When sending a message: shows user message immediately, shows assistant "typing" bubble,
 *   then replaces typing bubble with the assistant response when the API returns.
 * - Auto-scrolls when at bottom; if user scrolls up, shows Go to bottom button.
 */
export default function ChatPanel({ project, onProjectRename }) {
  const [conv, setConv] = useState(null);
  const [messages, setMessages] = useState([]); // { role, text, citations?, loading? }
  const [input, setInput] = useState("");
  const [docsPresent, setDocsPresent] = useState(false);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [awaitingResponse, setAwaitingResponse] = useState(false);

  // edit modal states
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");

  const messagesRef = useRef(null);

  // --- helper: fetch messages from the messages API and set state (preserves citations) ---
  async function fetchConversationMessages(convId) {
    if (!convId) return;
    try {
      const res = await fetch(`/api/conversations/${convId}/messages/`);
      if (!res.ok) {
        console.warn("Failed to fetch conversation messages", await res.text());
        return;
      }
      const data = await res.json();
      // normalize messages: backend returns { role, text, created_at, citations: [] }
      setMessages((data || []).map(m => ({
        role: m.role,
        text: m.text,
        citations: Array.isArray(m.citations) ? m.citations : [],
        created_at: m.created_at || null
      })));
      setDocsPresent(true);
    } catch (err) {
      console.error("fetchConversationMessages error", err);
    }
  }

  // --- ensureConversation: create OR reuse conversation and then fetch messages ---
  async function ensureConversation() {
    if (!project) return;
    try {
      // createConversation returns { id, messages? } in some implementations but be defensive
      const resp = await createConversation(project.id);
      if (!resp || !resp.id) {
        console.error("createConversation did not return id", resp);
        return;
      }
      setConv({ id: resp.id });

      // attempt to populate messages:
      // 1) if createConversation returned messages array use that
      if (Array.isArray(resp.messages) && resp.messages.length > 0) {
        setMessages(resp.messages.map(m => ({
          role: m.role,
          text: m.text,
          citations: m.citations || [],
          created_at: m.created_at || null
        })));
        setDocsPresent(true);
      } else {
        // 2) otherwise fetch via messages endpoint (this ensures citations and persistence)
        await fetchConversationMessages(resp.id);
      }
    } catch (err) {
      console.error("ensureConversation failed", err);
    }
  }

  // --- react to RightPanel dispatches (documents:updated) to create conversation if docs added ---
  useEffect(() => {
    const handler = async (ev) => {
      if (!project) return;
      const pid = ev.detail?.projectId;
      if (String(pid) !== String(project.id)) return;
      await ensureConversation();
    };
    window.addEventListener("documents:updated", handler);
    return () => window.removeEventListener("documents:updated", handler);
  }, [project]);

  // --- when project changes: reset UI and ensure conversation (which will fetch messages) ---
  useEffect(() => {
    setMessages([]);
    setConv(null);
    setInput("");
    setDocsPresent(false);
    setEditing(false);
    setEditName("");
    setAwaitingResponse(false);
    if (!project) return;
    ensureConversation();
  }, [project?.id]);

  // --- scroll handling: auto-scroll only if user at bottom; track user's scroll to show go-to-bottom button ---
  useEffect(() => {
    const node = messagesRef.current;
    if (!node) return;
    // auto-scroll when messages change if user is at bottom
    if (isAtBottom) {
      // small timeout to allow DOM to render new message nodes
      setTimeout(() => { node.scrollTop = node.scrollHeight; }, 30);
    }
  }, [messages, isAtBottom]);

  useEffect(() => {
    const node = messagesRef.current;
    if (!node) return;
    const onScroll = () => {
      const tolerance = 20;
      const atBottom = (node.scrollHeight - node.scrollTop - node.clientHeight) <= tolerance;
      setIsAtBottom(atBottom);
    };
    node.addEventListener("scroll", onScroll, { passive: true });
    // initial check
    onScroll();
    return () => node.removeEventListener("scroll", onScroll);
  }, []);

  // --- sending a message ---
  async function send() {
    if (!input.trim()) return;
    if (!conv || !conv.id) { alert("No conversation created"); return; }

    const text = input.trim();
    // 1) optimistic add user message
    setMessages(prev => [...prev, { role: "user", text }]);
    setInput("");
    setIsAtBottom(true);

    // 2) add an assistant "typing" placeholder (so UI shows typing)
    const placeholder = { role: "assistant", text: "…", loading: true };
    setMessages(prev => [...prev, placeholder]);
    setAwaitingResponse(true);

    try {
      const res = await postMessage(conv.id, text);
      // remove the last placeholder and push actual assistant response
      setMessages(prev => {
        // remove the last placeholder (find last with loading: true)
        const clone = [...prev];
        const li = clone.map((m,i)=>({m,i})).reverse().find(x => x.m.loading);
        if (li) clone.splice(li.m ? li.i : clone.length-1, 1); // remove placeholder
        // append actual assistant message
        const assistantMsg = {
          role: "assistant",
          text: (res && res.answer) ? res.answer : "No answer (error)",
          citations: (res && res.citations) ? res.citations : []
        };
        return [...clone, assistantMsg];
      });
    } catch (err) {
      console.error("send message error", err);
      // replace/remove placeholder with an error message
      setMessages(prev => {
        const clone = [...prev];
        // remove last loading placeholder
        const idx = clone.map(m=>m.loading ? 1 : 0).lastIndexOf(1);
        if (idx >= 0) clone.splice(idx, 1);
        clone.push({ role: "assistant", text: "Send failed" });
        return clone;
      });
    } finally {
      setAwaitingResponse(false);
    }
  }

  function goToBottom() {
    const node = messagesRef.current;
    if (!node) return;
    node.scrollTop = node.scrollHeight;
    setIsAtBottom(true);
  }

  // --- edit modal handlers (unchanged) ---
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

  // --- simple render helpers for citations ---
  function renderCitations(citations = []) {
    if (!citations || citations.length === 0) return null;
    return (
      <div style={{ marginTop: 8, fontSize: 12, color: "var(--muted)" }}>
        <strong>Sources:</strong>
        <ul>
          {citations.map((c, i) => {
            const title = c.document_title || c.document_id || "unknown";
            const short = String(title).length > 60 ? String(title).slice(0, 56).trim() + "..." : title;
            return (
              <li key={i} style={{ marginTop: 6 }}>
                <strong>{short}</strong>{c.page ? ` · page ${c.page}` : "" }
                {c.snippet ? <div style={{ color: "var(--muted)", marginTop: 4 }}>{String(c.snippet).slice(0,140)}{String(c.snippet).length>140?"...":""}</div> : null}
              </li>
            );
          })}
        </ul>
      </div>
    );
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
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 20h9" />
            <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z"/>
          </svg>
        </button>
      </div>

      <div ref={messagesRef} className="chat-window" style={{ padding: 16 }}>
        {messages.map((m, idx) => (
          <div key={idx} className={`message ${m.role === 'user' ? 'user' : 'assistant'}`} style={{ opacity: m.loading ? 0.85 : 1 }}>
            <div dangerouslySetInnerHTML={{ __html: (m.text || "").replace(/\n/g, "<br/>") }} />
            {m.citations && m.citations.length > 0 && (
  <div style={{ marginTop: 8, fontSize: 12, color: "var(--muted)" }}>
    <strong>Sources:</strong>
    <ul style={{ listStyle: "disc", paddingLeft: 20 }}>
      {m.citations.map((c, i) => {
        const title = c.document_title || c.document_id || "unknown";
        const shortTitle = title.length > 60 ? title.slice(0, 56) + "..." : title;

        // Make snippet single-line, trimmed
        const snippet = (c.snippet || "")
          .replace(/\s+/g, " ")      // make snippet one line
          .trim()
          .slice(0, 80);            // truncate
        const finalSnippet = snippet.length === 80 ? snippet + "..." : snippet;

        return (
          <li key={i} style={{ marginBottom: 4 }}>
            <span style={{ fontWeight: 600 }}>{shortTitle}</span>
            <br/>
            {/* {c.page ? ` · page ${c.page}` : ""} */}
            {finalSnippet ? ` · ${finalSnippet}` : ""}
          </li>
        );
      })}
    </ul>
  </div>
)}
            {m.loading && <div style={{ marginTop:6, color:"var(--muted)", fontSize:12 }}>Thinking…</div>}
          </div>
        ))}
      </div>

      {!isAtBottom && (
        <button
          onClick={goToBottom}
          style={{
            position: "absolute",
            bottom: 90,
            left: "50%",
            transform: "translateX(-50%)",
            padding: "6px 12px",
            background: "#10a37f",
            borderRadius: 6,
            border: "none",
            cursor: "pointer",
            color: "white",
            fontSize: 12,
            zIndex: 30
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
        <button className="btn" onClick={send} disabled={!input.trim() || awaitingResponse}>Send</button>
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
