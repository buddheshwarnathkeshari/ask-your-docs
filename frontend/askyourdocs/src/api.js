
// src/api.js
const API_ROOT = "/api";

export async function listProjects() {
  const res = await fetch(`${API_ROOT}/projects/`);
  return res.json();
}

export async function createProject(name, description = "") {
  const res = await fetch(`${API_ROOT}/projects/`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ name, description }),
  });
  return res.json();
}

export async function uploadDocument(file, projectId) {
  const fd = new FormData();
  fd.append("file", file);
  if (projectId) fd.append("project_id", projectId);
  const res = await fetch(`${API_ROOT}/documents/upload/`, {
    method: "POST",
    body: fd,
  });
  return res.json();
}

export async function listDocuments(projectId) {
  const url = new URL(`${API_ROOT}/documents/`, window.location.origin);
  if (projectId) url.searchParams.set("project_id", projectId);
  const res = await fetch(url.pathname + url.search);
  return res.json();
}

export async function createConversation(projectId) {
  const res = await fetch(`${API_ROOT}/conversations/`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ project_id: projectId }),
  });
  return res.json();
}

export async function postMessage(convId, text) {
  const res = await fetch(`${API_ROOT}/conversations/${convId}/message/`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ text }),
  });
  return res.json();
}
