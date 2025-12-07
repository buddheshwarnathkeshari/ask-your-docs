// src/components/ChatPanel.jsx
import React, { useEffect, useState, useRef } from "react";
import { createConversation, postMessage, listDocuments } from "../api";

export default function ChatPanel({ project }){
  const [conv, setConv] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [docsPresent, setDocsPresent] = useState(false);
  const messagesRef = useRef(null);

  useEffect(()=>{
    setMessages([]);
    setConv(null);
    setInput("");
    if(!project) return;
    (async ()=> {
      const docs = await listDocuments(project.id);
      const hasDocs = docs && docs.length>0;
      setDocsPresent(hasDocs);
      if(hasDocs){
        const c = await createConversation(project.id);
        if(c && c.id) setConv(c);
      }
    })();
  }, [project]);

  useEffect(()=> {
    // scroll to bottom
    if(messagesRef.current) messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
  }, [messages]);

  async function send(){
    if(!input.trim()) return;
    if(!conv){ alert("No conversation created"); return; }
    // push user message locally
    setMessages(prev => [...prev, {role:"user", text: input}]);
    setInput("");
    const res = await postMessage(conv.id, input);
    // response contains answer and citations
    if(res && res.answer){
      setMessages(prev => [...prev, {role:"assistant", text: res.answer, citations: res.citations || []}]);
    } else {
      setMessages(prev => [...prev, {role:"assistant", text: "No answer (error)"}]);
    }
  }

  if(!project) return <div className="chat-empty">Pick a project to start.</div>;
  if(!docsPresent) return <div className="chat-empty">No documents uploaded yet. Upload docs in the right panel to start chat.</div>;

  return (
    <>
      <div style={{display:"flex", justifyContent:"space-between", alignItems:"center"}}>
        <h3 className="h1">{project.name}</h3>
      </div>

      <div ref={messagesRef} className="chat-window" style={{flex:1}}>
        {messages.map((m, idx) => (
          <div key={idx} className={`message ${m.role === 'user' ? 'user' : 'assistant'}`}>
            <div dangerouslySetInnerHTML={{__html: m.text.replace(/\n/g,'<br/>')}} />
            {m.citations && m.citations.length > 0 && (
              <div style={{marginTop:8, fontSize:12, color:"var(--muted)"}}>
                <strong>Sources:</strong>
                <ul>
                  {m.citations.map((c,i)=> <li key={i}>Doc: {c.document_id} Page:{c.page} — {c.snippet ? `${c.snippet.slice(0,120)}...` : 'no snippet'}</li>)}
                </ul>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="chat-input-bar">
        <input className="input" placeholder="Ask something..." value={input} onChange={e=>setInput(e.target.value)} onKeyDown={(e)=>e.key==='Enter' && send()} />
        <button className="btn" onClick={send}>Send</button>
      </div>
    </>
  );
}
