// src/components/ChatPanel.jsx
import React, { useEffect, useRef, useState, useLayoutEffect } from "react";
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

  const [expandedMessages, setExpandedMessages] = useState(() => new Set()); // track expanded message ids/keys

  const messagesRef = useRef(null);

  // helper: check documents using event-driven approach (RightPanel dispatches)
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

  async function ensureConversation() {
    if (!project) return;
    try {
      const resp = await createConversation(project.id);
      if (resp && resp.id) {
        setConv({ id: resp.id });
        if (Array.isArray(resp.messages) && resp.messages.length > 0) {
          setMessages(resp.messages.map(m => ({ ...m })));
          setDocsPresent(true);
        } else {
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
    setExpandedMessages(new Set());
    if (!project) return;
    ensureConversation();
  }, [project?.id]);

  // helper to compute if scroll is at bottom
  function checkAtBottom(node, tolerance = 20) {
    if (!node) return true;
    const scrollTop = typeof node.scrollTop === "number" ? node.scrollTop : 0;
    const scrollHeight = typeof node.scrollHeight === "number" ? node.scrollHeight : 0;
    const clientHeight = typeof node.clientHeight === "number" ? node.clientHeight : 0;
    const atBottom = (scrollHeight - scrollTop - clientHeight) <= tolerance;
    return atBottom;
  }

  // throttle helper
  function throttle(fn, wait = 50) {
    let last = 0;
    let timeout = null;
    return (...args) => {
      const now = Date.now();
      const remaining = wait - (now - last);
      if (remaining <= 0) {
        if (timeout) { clearTimeout(timeout); timeout = null; }
        last = now;
        fn(...args);
      } else if (!timeout) {
        timeout = setTimeout(() => {
          last = Date.now();
          timeout = null;
          fn(...args);
        }, remaining);
      }
    };
  }

  // Robust single effect to attach scroll listener, resize observer, and window resize.
  useEffect(() => {
    let attached = false;
    let ro = null;
    let node = messagesRef.current;
    let intervalId = null;

    // declare cleanup early so attach can overwrite it safely
    let cleanup = () => {
      if (intervalId) {
        clearInterval(intervalId);
        intervalId = null;
      }
    };

    const attach = () => {
      if (attached) return;
      node = messagesRef.current;
      if (!node) return;
      attached = true;

      const updateAtBottom = () => {
        const atBottom = checkAtBottom(node);
        setIsAtBottom(atBottom);
        console.debug("updateAtBottom", { scrollTop: node.scrollTop, scrollHeight: node.scrollHeight, clientHeight: node.clientHeight, atBottom });
      };

      const onScroll = throttle(() => {
        updateAtBottom();
      }, 50);

      node.addEventListener("scroll", onScroll, { passive: true });
      window.addEventListener("resize", updateAtBottom);

      if (typeof ResizeObserver !== "undefined") {
        ro = new ResizeObserver(() => {
          // allow a frame for transitions/layout to settle
          requestAnimationFrame(() => updateAtBottom());
        });
        ro.observe(node);
      }

      // initial check after next paint
      requestAnimationFrame(() => updateAtBottom());

      // override cleanup to remove listeners when needed
      cleanup = () => {
        try { node.removeEventListener("scroll", onScroll); } catch (e) {}
        try { window.removeEventListener("resize", updateAtBottom); } catch (e) {}
        if (ro) {
          try { ro.disconnect(); } catch (e) {}
          ro = null;
        }
        if (intervalId) {
          clearInterval(intervalId);
          intervalId = null;
        }
      };
    };

    // If ref not ready, poll briefly until it exists (max 2s)
    if (!node) {
      const start = Date.now();
      intervalId = setInterval(() => {
        if (messagesRef.current) {
          attach();
          if (intervalId) { clearInterval(intervalId); intervalId = null; }
        } else if (Date.now() - start > 2000) {
          if (intervalId) { clearInterval(intervalId); intervalId = null; }
        }
      }, 50);
    } else {
      attach();
    }

    return () => {
      cleanup();
    };
    // reattach when project changes (new chat window size/structure)
  }, [project?.id]);

  // Auto-scroll after messages update when the user is at bottom
  // useLayoutEffect to avoid flicker (runs before paint)
  useLayoutEffect(() => {
    const node = messagesRef.current;
    if (!node) return;
    if (isAtBottom) {
      // scroll to bottom
      node.scrollTop = node.scrollHeight;
    } else {
      // re-evaluate and correct flag if needed
      const atBottom = checkAtBottom(node);
      if (atBottom) setIsAtBottom(true);
    }
  }, [messages, isAtBottom]);

  // send / UI functions
  async function send() {
    if (!input.trim()) return;
    if (!conv) { alert("No conversation created"); return; }

    // optimistic user message
    setMessages(prev => [...prev, { role: "user", text: input }]);
    setInput("");
    // we want to auto-scroll for user messages
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
      const updated = await updateProject(project.id, { name: editName.trim() });
      if (typeof onProjectRename === "function") onProjectRename(updated);
      setEditing(false);
    } catch (err) {
      console.error("Failed to update project", err);
      alert("Failed to rename project: " + (err.message || err));
    }
  }

  // Expand/collapse helpers
  function keyForMessage(m, idx) {
    // use stable key: message id if available, otherwise created_at, else index
    return m.id || m.created_at || `idx_${idx}`;
  }

  function isExpanded(m, idx) {
    const key = keyForMessage(m, idx);
    return expandedMessages.has(key);
  }

  function toggleExpand(m, idx) {
    const key = keyForMessage(m, idx);
    setExpandedMessages(prev => {
      const nxt = new Set(prev);
      if (nxt.has(key)) nxt.delete(key);
      else nxt.add(key);
      return nxt;
    });

    // force a re-check after the DOM updates/layout settles
    // small timeout gives the browser one render tick to apply layout changes
    setTimeout(() => {
      const node = messagesRef.current;
      if (!node) return;
      const atBottom = checkAtBottom(node);
      setIsAtBottom(atBottom);
      console.debug("post-toggle recheck", { atBottom, scrollTop: node.scrollTop, scrollHeight: node.scrollHeight, clientHeight: node.clientHeight });
    }, 40); // raise this to 100-200ms if you have CSS expand/collapse animations
  }

  // clicking a source should notify RightPanel to scroll & blink
  function handleClickSource(documentId) {
    if (!documentId) return;
    // dispatch event for right panel or global listener
    window.dispatchEvent(new CustomEvent("documents:scrollTo", { detail: { documentId } }));
    // also raise documents:highlight event for blinking if you use that
    window.dispatchEvent(new CustomEvent("documents:highlight", { detail: { documentId } }));
  }

  // render single-line pretty source for collapsed view
  function renderCollapsedSourceFirst(citation, idx) {
    const title = citation.document_title || citation.document_id || "unknown";
    return (
      <button
        className="chip"
        onClick={() => handleClickSource(citation.document_id)}
        style={{
          display: "inline-block",
          borderRadius: 18,
          padding: "6px 10px",
          background: "rgba(255,255,255,0.04)",
          border: "1px solid rgba(255,255,255,0.06)",
          cursor: "pointer",
          fontSize: 13,
          marginRight: 8,
          color:"rgba(255, 255, 255, 1)"
        }}
        title={title}
      >
        {title.length > 36 ? (title.slice(0, 34) + "...") : title}
      </button>
    );
  }

  // render a one-line source row used in expanded view
  function renderSourceRow(citation, i) {
    const title = citation.document_title || citation.document_id || "unknown";
    const snip = citation.snippet ? (citation.snippet.length > 120 ? citation.snippet.slice(0, 117) + "..." : citation.snippet) : "";
    return (
      <li key={i} style={{ marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
          <button onClick={() => handleClickSource(citation.document_id)} style={{ all: "unset", cursor: "pointer", fontWeight: 700 }}>
            {title}
          </button>
        </div>
        {snip ? <div style={{ marginTop: 6, color: "var(--muted)", fontSize: 13 }}>{snip}</div> : null}
      </li>
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

      <div
        ref={messagesRef}
        className="chat-window"
        style={{ padding: 16, overflowY: "auto", height: "calc(100% - 160px)" }}
      >
        {messages.map((m, idx) => (
          <div key={keyForMessage(m, idx)} className={`message ${m.role === 'user' ? 'user' : 'assistant'}`} style={{ marginBottom: 20 }}>
            <div dangerouslySetInnerHTML={{ __html: (m.text || "").replace(/\n/g, "<br/>") }} />

            {/* citations / sources */}
            {m.citations && m.citations.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <strong style={{ display: "block", color: "var(--muted)", marginBottom: 8 }}>Sources:</strong>

                {/* collapsed view */}
                {!isExpanded(m, idx) && (
                  <div>
                    {renderCollapsedSourceFirst(m.citations[0], idx)}
                    {m.citations.length > 1 && (
                      <button
                        onClick={() => toggleExpand(m, idx)}
                        style={{
                          marginLeft: 6,
                          background: "transparent",
                          border: "none",
                          color: "var(--muted)",
                          cursor: "pointer",
                          fontSize: 13
                        }}
                      >
                        +{m.citations.length - 1} more
                      </button>
                    )}
                  </div>
                )}

                {/* expanded view */}
                {isExpanded(m, idx) && (
                  <div>
                    <ul style={{ paddingLeft: 20, marginTop: 4 }}>
                      {m.citations.map((c, i) => renderSourceRow(c, i))}
                    </ul>
                    <div style={{ marginTop: 8 }}>
                      <button className="btn ghost" onClick={() => toggleExpand(m, idx)}>Collapse</button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {!isAtBottom && (
        <button
          onClick={goToBottom}
          style={{ position: "absolute", bottom: 100, left: "50%", transform: "translateX(-50%)", padding: "6px 12px", background: "#10a37f", borderRadius: 6, border: "none", cursor: "pointer", color: "white", fontSize: 12 }}
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
