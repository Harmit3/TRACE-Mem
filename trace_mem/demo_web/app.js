"use strict";
const get = id => document.getElementById(id);
const percent = n => (100 * n).toFixed(1) + "%";
const number = n => n.toLocaleString("en");
const cell = (tag, value) => {
  const element = document.createElement(tag);
  element.textContent = value;
  return element;
};
const list = (id, rows) => get(id).replaceChildren(...rows.map(x => cell("li", x)));
async function json(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error("Request failed (" + response.status + ")");
  return response.json();
}
let newestReplay = 0;
async function replay() {
  const request = ++newestReplay;
  const step = Number(get("step").value);
  const selected = get("query").value;
  const options = [new Option("Current replay day", "current")];
  for (let i = 1; i < step; i++) options.push(new Option("Day " + i, i));
  get("query").replaceChildren(...options);
  get("query").value = Number(selected) < step && selected !== "current" ? selected : "current";
  const controls = new URLSearchParams({
    policy: get("policy").value, cap: get("cap").value, step,
    query: get("query").value === "current" ? step : get("query").value,
  });
  try {
    const data = await json("/api/replay?" + controls);
    if (request !== newestReplay) return;
    get("usage").textContent = data.policy + " used " + data.stats.calls + " of " + data.stats.allowance
      + " allowed calls through day " + data.step + ". Showing memory as of day " + data.query + ".";
    list("facts", data.facts.length ? data.facts.map(f => f.slot + " · " + f.value + " | Source "
      + f.source + " | From " + f.valid_from + (f.valid_to ? " until " + f.valid_to : "")) : ["No visible facts"]);
    list("events", data.timeline.map(e => "Day " + e.day + " · " + e.label + " [" + e.operations.join(", ") + "]"));
  } catch (error) {
    if (request !== newestReplay) return;
    get("usage").textContent = error.message;
    list("facts", []);
    list("events", []);
  }
}
async function dashboard() {
  try {
    const a = await json("/api/archive");
    get("cohort").textContent = a.cohort.histories + " fictional histories in " + a.cohort.families
      + " design families. Step 31 reuses these histories.";
    function render() {
      const mode = get("mode").value;
      const budget = Number(get("budget").value);
      get("performance").replaceChildren(...a.performance.filter(r => r.mode === mode && r.budget === budget).map(r => {
        const row = document.createElement("tr");
        const method = cell("th", r.method);
        method.scope = "row";
        row.append(method, ...[percent(r.current_accuracy), percent(r.historical_accuracy), r.harmful_adoptions,
          r.verification_attempts + " / " + r.budget_cap].map(x => cell("td", x)));
        return row;
      }));
      const pair = a.contrasts.find(r => r.mode === mode && r.budget === budget && r.left === "T2" && r.right === "H-paced");
      get("contrast").textContent = pair ? "T2 minus H-paced on current accuracy: " + percent(pair.difference)
        + " (95% paired interval " + percent(pair.lower) + " to " + percent(pair.upper) + ")." : "";
    }
    render();
    get("research-controls").addEventListener("change", render);
    list("external", Object.entries(a.external).map(([k, v]) => k + " · " + v.correct + "/" + v.completed
      + " correct completed; evidence turns " + v.turn_recall.hits + "/" + v.turn_recall.targets));
    list("validation", Object.entries(a.validation).map(([k, v]) => k + " · Extraction F1 " + percent(v.extraction.f1)
      + "; reader accuracy " + percent(v.reader.accuracy)));
    const v = a.resources.verifier;
    get("compute").textContent = number(v.attempts + v.cache_hits) + " logical verifier calls, "
      + number(v.attempts) + " fresh requests and " + number(v.cache_hits) + " cache hits. Fresh requests consumed "
      + number(v.input_tokens + v.output_tokens) + " reported tokens. Run wall time " + Math.round(a.resources.wall_seconds) + " s.";
  } catch (error) {
    get("archive-error").textContent = error.message;
  }
}
get("replay-controls").addEventListener("change", replay);
replay();
dashboard();
