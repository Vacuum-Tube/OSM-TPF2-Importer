/* global pywebview */
const byId = (id) => document.getElementById(id);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function waitForApi() {
  if (window.pywebview && window.pywebview.api) return;
  await new Promise((resolve) => window.addEventListener("pywebviewready", resolve, { once: true }));
}

async function choosePath(method, ...args) {
  await waitForApi();
  const result = await window.pywebview.api[method](...args);
  if (result && result.ok && result.path) return result.path;
  if (result && !result.cancelled) showError(result.error || "Could not select that path.");
  return "";
}

function showError(message) {
  byId("jobLabel").textContent = "Could not start";
  byId("jobMeta").textContent = "Error";
  byId("jobStage").textContent = message;
  byId("result").textContent = "";
  byId("jobBar").style.width = "0";
}

async function runConversion() {
  const source = byId("source").value.trim();
  const destination = byId("destination").value.trim();
  if (!source || !destination) {
    showError("Choose both a source mod and an output folder.");
    return;
  }

  const button = byId("btnConvert");
  button.disabled = true;
  byId("jobLabel").textContent = "Converting";
  byId("jobMeta").textContent = "Starting";
  byId("jobStage").textContent = "Inspecting metadata…";
  byId("jobBar").style.width = "2%";
  byId("result").textContent = "";

  try {
    await waitForApi();
    const started = await window.pywebview.api.convert_tf3_mod(
      source,
      destination,
      byId("name").value,
      byId("author").value,
    );
    if (!started || !started.job_id) {
      showError((started && started.error) || "The converter did not start.");
      return;
    }

    let state;
    do {
      await sleep(400);
      state = await window.pywebview.api.job_status(started.job_id);
      byId("jobLabel").textContent = state.status === "running" ? "Converting" : (state.ok ? "Complete" : "Failed");
      byId("jobMeta").textContent = state.status === "running" ? "Working" : "";
      byId("jobStage").textContent = state.stage || state.error || "";
      const percent = Number(state.percent);
      byId("jobBar").style.width = `${Math.max(0, Math.min(100, Number.isFinite(percent) ? percent : 0))}%`;
    } while (state.status === "running");

    if (!state.ok) {
      showError(state.error || state.stage || "Conversion failed.");
      return;
    }
    byId("jobMeta").textContent = "Done";
    byId("jobBar").style.width = "100%";
    byId("result").textContent = [
      `Name: ${state.name}`,
      `Mod ID: ${state.modId}`,
      `Revision: ${state.revision}`,
      `Output: ${state.destination}`,
      "Generated mod.json and _metadata/modinfo.json.",
      "Folder contents were copied unchanged; TF3 compatibility still needs manual verification.",
      ...(state.warnings || []).map((warning) => `Warning: ${warning}`),
    ].join("\n");
  } catch (error) {
    showError(String(error));
  } finally {
    button.disabled = false;
  }
}

byId("btnTools").addEventListener("click", async () => {
  await waitForApi();
  const result = await window.pywebview.api.open_mode("osm");
  if (!result || !result.ok) showError((result && result.error) || "Could not switch to TPF2 Studio.");
  else window.location.href = result.url;
});
byId("btnSourceFolder").addEventListener("click", async () => {
  const path = await choosePath("pick_tf3_source", true);
  if (path) byId("source").value = path;
});
byId("btnSourceFile").addEventListener("click", async () => {
  const path = await choosePath("pick_tf3_source", false);
  if (path) byId("source").value = path;
});
byId("btnDestination").addEventListener("click", async () => {
  const path = await choosePath("pick_tf3_destination");
  if (path) byId("destination").value = path;
});
byId("btnConvert").addEventListener("click", runConversion);
