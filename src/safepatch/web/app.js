const state = {
  runs: [],
  selectedRunId: null,
  events: [],
};

const nodes = {
  status: document.querySelector("#status"),
  runForm: document.querySelector("#run-form"),
  taskInput: document.querySelector("#task-input"),
  refreshRuns: document.querySelector("#refresh-runs"),
  cancelRun: document.querySelector("#cancel-run"),
  runList: document.querySelector("#run-list"),
  selectedRunLabel: document.querySelector("#selected-run-label"),
  timeline: document.querySelector("#timeline"),
  approvalForm: document.querySelector("#approval-form"),
  approvalActionId: document.querySelector("#approval-action-id"),
  rejectionReason: document.querySelector("#rejection-reason"),
  approveAction: document.querySelector("#approve-action"),
  rejectAction: document.querySelector("#reject-action"),
  approvalResult: document.querySelector("#approval-result"),
  credentialForm: document.querySelector("#credential-form"),
  apiKey: document.querySelector("#api-key"),
  vaultPassword: document.querySelector("#vault-password"),
  deleteCredential: document.querySelector("#delete-credential"),
  credentialStatus: document.querySelector("#credential-status"),
  checkResults: document.querySelector("#check-results"),
  diffView: document.querySelector("#diff-view"),
};

function pretty(value) {
  return JSON.stringify(value, null, 2);
}

async function parseJsonResponse(response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `request failed: ${response.status}`);
  }
  return payload;
}

async function loadHealth() {
  try {
    const response = await fetch("/health");
    const payload = await parseJsonResponse(response);
    nodes.status.textContent = `API: ${payload.status}`;
  } catch (error) {
    nodes.status.textContent = error.message;
  }
}

async function loadRuns() {
  const response = await fetch("/runs");
  const payload = await parseJsonResponse(response);
  state.runs = payload.runs;
  renderRuns();
}

async function createRun(task) {
  const response = await fetch("/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task }),
  });
  const run = await parseJsonResponse(response);
  state.selectedRunId = run.run_id;
  await loadRuns();
  await loadEvents();
}

async function cancelSelectedRun() {
  if (!state.selectedRunId) return;
  const response = await fetch(`/runs/${state.selectedRunId}/cancel`, { method: "POST" });
  await parseJsonResponse(response);
  await loadRuns();
  await loadEvents();
}

async function loadEvents() {
  if (!state.selectedRunId) {
    renderEvents();
    return;
  }
  const response = await fetch(`/runs/${state.selectedRunId}/events`);
  const payload = await parseJsonResponse(response);
  state.events = payload.events;
  renderEvents();
}

async function approveAction() {
  const actionId = nodes.approvalActionId.value.trim();
  if (!actionId) return;
  const response = await fetch(`/approvals/${actionId}/approve`, { method: "POST" });
  const payload = await parseJsonResponse(response);
  nodes.approvalResult.textContent = pretty(payload);
}

async function rejectAction() {
  const actionId = nodes.approvalActionId.value.trim();
  if (!actionId) return;
  const reason = nodes.rejectionReason.value.trim() || "Rejected from WebUI";
  const response = await fetch(`/approvals/${actionId}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
  });
  const payload = await parseJsonResponse(response);
  nodes.approvalResult.textContent = pretty(payload);
}

async function loadCredentialStatus() {
  try {
    const response = await fetch("/credentials/openai/status");
    const payload = await parseJsonResponse(response);
    nodes.credentialStatus.textContent = pretty(payload);
  } catch (error) {
    nodes.credentialStatus.textContent = error.message;
  }
}

async function setCredential(event) {
  event.preventDefault();
  const response = await fetch("/credentials/openai", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      api_key: nodes.apiKey.value,
      password: nodes.vaultPassword.value,
    }),
  });
  const payload = await parseJsonResponse(response);
  nodes.credentialStatus.textContent = pretty(payload);
  nodes.apiKey.value = "";
}

async function deleteCredential() {
  const response = await fetch("/credentials/openai", { method: "DELETE" });
  const payload = await parseJsonResponse(response);
  nodes.credentialStatus.textContent = pretty(payload);
}

function statusBadgeClass(status) {
  const map = {
    running: "badge-running",
    completed: "badge-completed",
    failed: "badge-failed",
    paused_for_approval: "badge-paused",
    canceled: "badge-failed",
    budget_exhausted: "badge-failed",
  };
  return map[status] || "";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderRuns() {
  if (state.runs.length === 0) {
    nodes.runList.innerHTML = '<li class="empty">No runs yet. Create one above.</li>';
    return;
  }
  nodes.runList.innerHTML = state.runs
    .map(
      (run) => `
        <li>
          <button
            type="button"
            class="run-card ${run.run_id === state.selectedRunId ? "active" : ""}"
            data-run-id="${run.run_id}"
          >
            <span>${escapeHtml(run.task)}</span>
            <small><span class="badge ${statusBadgeClass(run.status)}">${escapeHtml(run.status)}</span></small>
          </button>
        </li>
      `,
    )
    .join("");
}

function renderEvents() {
  const selectedRun = state.runs.find((r) => r.run_id === state.selectedRunId);
  nodes.selectedRunLabel.textContent = selectedRun
    ? `${selectedRun.status} · ${selectedRun.run_id}`
    : "No run selected";

  if (!state.selectedRunId) {
    nodes.timeline.innerHTML = '<li class="empty">Select or create a run.</li>';
    nodes.checkResults.textContent = "No check results yet.";
    nodes.diffView.textContent = "No patch captured yet.";
    return;
  }

  if (state.events.length === 0) {
    nodes.timeline.innerHTML = '<li class="empty">No events recorded yet.</li>';
  } else {
    nodes.timeline.innerHTML = state.events
      .map(
        (event) => `
          <li>
            <span class="event-type">${escapeHtml(event.type)}</span>
            <pre>${escapeHtml(pretty(event.payload))}</pre>
          </li>
        `,
      )
      .join("");
  }

  const checkEvents = state.events.filter((e) =>
    ["tool_finished", "feedback_built", "run_finished"].includes(e.type),
  );
  nodes.checkResults.textContent =
    checkEvents.length === 0 ? "No check results yet." : pretty(checkEvents);

  const patchEvent = state.events.find((e) => {
    const p = JSON.stringify(e.payload || {});
    return p.includes("--- a/") || p.includes("diff --git");
  });
  nodes.diffView.textContent = patchEvent
    ? pretty(patchEvent.payload)
    : "No patch captured yet.";
}

nodes.runForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await createRun(nodes.taskInput.value.trim());
  nodes.taskInput.value = "";
});

nodes.runList.addEventListener("click", async (event) => {
  const card = event.target.closest("[data-run-id]");
  if (!card) return;
  state.selectedRunId = card.dataset.runId;
  renderRuns();
  await loadEvents();
});

nodes.refreshRuns.addEventListener("click", loadRuns);
nodes.cancelRun.addEventListener("click", cancelSelectedRun);
nodes.approveAction.addEventListener("click", () => {
  approveAction().catch((e) => { nodes.approvalResult.textContent = e.message; });
});
nodes.rejectAction.addEventListener("click", () => {
  rejectAction().catch((e) => { nodes.approvalResult.textContent = e.message; });
});
nodes.credentialForm.addEventListener("submit", (event) => {
  setCredential(event).catch((e) => { nodes.credentialStatus.textContent = e.message; });
});
nodes.deleteCredential.addEventListener("click", () => {
  deleteCredential().catch((e) => { nodes.credentialStatus.textContent = e.message; });
});

void loadHealth();
void loadRuns();
void loadCredentialStatus();
