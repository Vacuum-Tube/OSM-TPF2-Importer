/* global pywebview */
async function waitForApi() {
  if (window.pywebview && window.pywebview.api) return;
  await new Promise((resolve) => window.addEventListener("pywebviewready", resolve, { once: true }));
}

async function openMode(mode) {
  const status = document.getElementById("status");
  status.textContent = "";
  try {
    await waitForApi();
    const result = await window.pywebview.api.open_mode(mode);
    if (!result || !result.ok) {
      status.textContent = (result && result.error) || "Could not open that workspace.";
      return;
    }
    window.location.href = result.url;
  } catch (error) {
    status.textContent = String(error);
  }
}

document.querySelectorAll("[data-mode]").forEach((button) => {
  button.addEventListener("click", () => openMode(button.dataset.mode));
});
