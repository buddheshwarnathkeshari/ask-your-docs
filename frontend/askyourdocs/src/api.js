const API_ROOT = "/api";

// --- Projects ---
export async function listProjects() {
  const res = await fetch(`${API_ROOT}/projects/`);
  if (!res.ok) throw new Error("Failed to list projects");
  return res.json();
}

export async function createProject(name, description = "") {
  const res = await fetch(`${API_ROOT}/projects/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description }),
  });
  if (!res.ok) {
    let msg = "Failed to create project";
    try {
      const data = await res.json();
      msg = data.detail || JSON.stringify(data);
    } catch (e) {}
    throw new Error(msg);
  }
  // backend returns created project object (including conversations)
  return res.json();
}

// Updated: delete at RESTful /projects/{id}/ with DELETE
export async function deleteProject(projectId) {
  if (!projectId) throw new Error("projectId required");
  const res = await fetch(`${API_ROOT}/projects/${projectId}/`, {
    method: "DELETE",
  });

  if (!res.ok) {
    let msg = `Failed to delete project (${res.status})`;
    try {
      const data = await res.json();
      msg = data.detail || JSON.stringify(data);
    } catch (e) {}
    throw new Error(msg);
  }

  // backend may return 204 No Content or a small JSON; normalize to true
  return true;
}

// --- Documents ---
export async function uploadDocument(file, projectId) {
  const fd = new FormData();
  fd.append("file", file);
  if (projectId) fd.append("project_id", projectId);

  const res = await fetch(`${API_ROOT}/documents/`, {
    method: "POST",
    body: fd,
  });

  // Consider both 200 (duplicate) and 201 (created) as OK results
  if (!res.ok) {
    let err = "Upload failed";
    try {
      const data = await res.json();
      err = data.detail || (data.file ? data.file.join(" ") : JSON.stringify(data));
    } catch (e) {}
    throw new Error(err);
  }
  return res.json();
}

export async function listDocuments(projectId) {
  const url = new URL(`${API_ROOT}/documents/`, window.location.origin);
  if (projectId) url.searchParams.set("project_id", projectId);
  const res = await fetch(url.pathname + url.search);
  if (!res.ok) throw new Error("Failed to list documents");
  return res.json();
}

export async function deleteDocument(docId) {
  const res = await fetch(`${API_ROOT}/documents/${docId}/`, {
    method: "DELETE",
  });
  if (res.status === 204 || res.status === 200) return true;
  let msg = "Failed to delete document";
  try { msg = (await res.json()).detail || JSON.stringify(await res.json()); } catch {}
  throw new Error(msg);
}

// --- Conversations ---
export async function createConversation(projectId) {
  const res = await fetch(`${API_ROOT}/conversations/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_id: projectId }),
  });
  if (!res.ok) {
    let msg = "Failed to create conversation";
    try {
      const data = await res.json();
      msg = data.detail || JSON.stringify(data);
    } catch (e) {}
    throw new Error(msg);
  }
  return res.json();
}

export async function postMessage(convId, text) {
  const res = await fetch(`${API_ROOT}/conversations/${convId}/message/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) {
    let msg = "Failed to post message";
    try {
      const data = await res.json();
      msg = data.detail || JSON.stringify(data);
    } catch (e) {}
    throw new Error(msg);
  }
  return res.json();
}

export async function listMessages(convId) {
  const res = await fetch(`${API_ROOT}/conversations/${convId}/messages/`);
  if (!res.ok) throw new Error("Failed to list messages");
  return res.json();
}

export async function updateProject(projectId, data = {}) {
  const res = await fetch(`${API_ROOT}/projects/${projectId}/`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    let msg = "Failed to update project";
    try { msg = (await res.json()).detail || JSON.stringify(await res.json()); } catch (e) {}
    throw new Error(msg);
  }
  return res.json();
}

export function downloadDocument(docId) {
  return `/api/documents/${docId}/download/`;
}
