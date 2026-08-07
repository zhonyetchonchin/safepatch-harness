const statusNode = document.querySelector("#status");

async function loadHealth() {
  try {
    const response = await fetch("/health");
    const payload = await response.json();
    statusNode.textContent = `API status: ${payload.status}`;
  } catch {
    statusNode.textContent = "API status: unavailable";
  }
}

void loadHealth();
