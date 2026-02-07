import { useEffect, useMemo, useRef, useState } from "react";
import Editor from "@monaco-editor/react";
import ReactFlow, { Background, Controls, MiniMap } from "reactflow";
import { Terminal } from "xterm";
import { FitAddon } from "xterm-addon-fit";
import "reactflow/dist/style.css";
import "xterm/css/xterm.css";

const DEFAULT_PERSONAS = [
  { id: "Coder", label: "Coder Agent" },
  { id: "Researcher", label: "Research Agent" },
  { id: "VLA", label: "VLA Agent" },
  { id: "Reviewer", label: "Reviewer Agent" },
  { id: "Legal", label: "Legal Agent" },
];

const NAV_TABS = [
  { key: "mission", label: "Mission Control" },
  { key: "coder", label: "Coder" },
  { key: "research", label: "Research" },
  { key: "vla", label: "VLA" },
  { key: "brain", label: "Brain" },
  { key: "governance", label: "Governance" },
  { key: "health", label: "Health" },
];

const REFRESH_INTERVAL_MS = 2000;

function useInterval(callback, delay) {
  useEffect(() => {
    if (delay === null) return undefined;
    const id = setInterval(callback, delay);
    return () => clearInterval(id);
  }, [callback, delay]);
}

function extractArtifacts(events) {
  for (const e of events) {
    if (!e || !e.payload) continue;
    const payload = e.payload.payload || e.payload;
    const text = typeof payload === "string" ? payload : JSON.stringify(payload);
    const match = text.match(/```(html|svg)([\s\S]*?)```/i);
    if (match) {
      return { type: match[1].toLowerCase(), content: match[2].trim() };
    }
  }
  return null;
}

function extractUIBlocks(events) {
  const blocks = [];
  events.forEach((e, idx) => {
    if (!e || e.event_type !== "ui_block") return;
    const payload = e.payload?.payload || e.payload || {};
    const ui = payload.ui;
    if (ui && typeof ui === "object") {
      blocks.push({ id: `${e.event_type}-${idx}`, ui, timestamp: e.timestamp || 0 });
    }
  });
  return blocks;
}

function extractUI(payload) {
  const raw = typeof payload === "string" ? payload : JSON.stringify(payload);
  const fenced = raw.match(/```ui([\s\S]*?)```/i);
  if (fenced) {
    try {
      return JSON.parse(fenced[1]);
    } catch {
      return null;
    }
  }
  const inline = raw.match(/\"ui\"\s*:\s*(\{[\s\S]*\})/i);
  if (inline) {
    try {
      return JSON.parse(inline[1]);
    } catch {
      return null;
    }
  }
  return null;
}

function eventSummary(event) {
  if (!event) return "";
  const payload = event.payload?.payload || event.payload || {};
  if (typeof payload === "string") return payload;
  if (payload.message) return payload.message;
  if (payload.intent) return payload.intent;
  if (payload.ui && payload.ui.title) return payload.ui.title;
  return "";
}

function formatTimestamp(ts) {
  if (!ts) return "";
  const date = new Date(ts * 1000);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString();
}

function renderUICard(ui) {
  if (!ui || typeof ui !== "object") return null;
  if (ui.type === "table") {
    const columns = Array.isArray(ui.columns) ? ui.columns : [];
    const rows = Array.isArray(ui.rows) ? ui.rows : [];
    return (
      <div className="tool" style={{ background: "#eef2ff" }}>
        <div><strong>{ui.title || "Table"}</strong></div>
        <div className="genui-table">
          <div className="genui-row genui-head">
            {columns.map((c, idx) => (
              <div key={`col-${idx}`} className="genui-cell">{c}</div>
            ))}
          </div>
          {rows.map((row, idx) => (
            <div key={`row-${idx}`} className="genui-row">
              {row.map((cell, cidx) => (
                <div key={`cell-${idx}-${cidx}`} className="genui-cell">{cell}</div>
              ))}
            </div>
          ))}
        </div>
      </div>
    );
  }
  if (ui.type === "approval") {
    return (
      <div className="tool" style={{ background: "#fff7ed" }}>
        <div><strong>{ui.title || "Approval"}</strong></div>
        <div className="muted" style={{ marginTop: 6 }}>{ui.summary || "Action requires approval."}</div>
      </div>
    );
  }
  if (ui.type === "flight_card") {
    return (
      <div className="tool" style={{ background: "#eef2ff" }}>
        <div><strong>Flight</strong></div>
        <div>{ui.from} → {ui.to}</div>
        <div>Date: {ui.date || "TBD"}</div>
        <div>Price: {ui.price || "—"}</div>
        <button className="secondary" style={{ marginTop: 6 }}>Select</button>
      </div>
    );
  }
  if (ui.type === "date_picker") {
    return (
      <div className="tool" style={{ background: "#eef2ff" }}>
        <div><strong>Date Picker</strong></div>
        <div style={{ marginTop: 6, display: "flex", gap: 6 }}>
          <input type="date" />
          <button className="secondary">Apply</button>
        </div>
      </div>
    );
  }
  return (
    <div className="tool">
      <pre className="mono">{JSON.stringify(ui, null, 2)}</pre>
    </div>
  );
}

function renderUIActions(actions = [], onAction) {
  if (!Array.isArray(actions) || !actions.length) return null;
  return (
    <div className="ui-actions">
      {actions.map((action, idx) => (
        <button
          key={`action-${idx}`}
          className={action.primary ? "primary" : "secondary"}
          onClick={() => onAction(action)}
        >
          {action.label || action.type || `Action ${idx + 1}`}
        </button>
      ))}
    </div>
  );
}

function TerminalPanel({ lines }) {
  const containerRef = useRef(null);
  const terminalRef = useRef(null);
  const fitRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current) return undefined;
    if (!terminalRef.current) {
      const term = new Terminal({
        fontFamily: "JetBrains Mono, monospace",
        fontSize: 12,
        theme: { background: "#0f172a", foreground: "#e2e8f0" },
        convertEol: true,
      });
      const fit = new FitAddon();
      term.loadAddon(fit);
      term.open(containerRef.current);
      fit.fit();
      terminalRef.current = term;
      fitRef.current = fit;
    }
    const resize = () => fitRef.current?.fit();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);

  useEffect(() => {
    if (!terminalRef.current) return;
    terminalRef.current.reset();
    (lines || []).forEach((line) => terminalRef.current.writeln(line));
  }, [lines]);

  return <div className="terminal-panel" ref={containerRef} />;
}

function eventBadge(eventType) {
  if (!eventType) return "default";
  if (eventType.includes("error") || eventType.includes("fail")) return "danger";
  if (eventType.includes("plan") || eventType.includes("intent")) return "warn";
  if (eventType.includes("tool") || eventType.includes("action")) return "success";
  return "default";
}

export default function App() {
  const [nav, setNav] = useState("mission");
  const [command, setCommand] = useState("");
  const [plan, setPlan] = useState("");
  const [events, setEvents] = useState([]);
  const [a2a, setA2a] = useState([]);
  const [tools, setTools] = useState([]);
  const [sources, setSources] = useState([]);
  const [metrics, setMetrics] = useState({});
  const [terminal, setTerminal] = useState([]);
  const [graph, setGraph] = useState({ nodes: [], edges: [] });
  const [personas, setPersonas] = useState(DEFAULT_PERSONAS);
  const [persona, setPersona] = useState("");
  const [configText, setConfigText] = useState("{}");
  const [hudImage, setHudImage] = useState("");
  const [artifactMode, setArtifactMode] = useState("preview");
  const [showSheet, setShowSheet] = useState(false);
  const [showBrain, setShowBrain] = useState(false);
  const [pendingRuns, setPendingRuns] = useState([]);
  const [commandHistory, setCommandHistory] = useState([]);
  const [files, setFiles] = useState([]);
  const [memoryQuery, setMemoryQuery] = useState("");
  const [memoryResults, setMemoryResults] = useState([]);
  const [runHistory, setRunHistory] = useState([]);
  const [runDiff, setRunDiff] = useState("");
  const [runDiffError, setRunDiffError] = useState("");
  const [runDiffLoading, setRunDiffLoading] = useState(false);
  const [runA, setRunA] = useState("");
  const [runB, setRunB] = useState("");
  const [clarificationInputs, setClarificationInputs] = useState({});

  const artifact = useMemo(() => extractArtifacts(events), [events]);
  const uiBlocks = useMemo(() => extractUIBlocks(events), [events]);
  const suggestions = useMemo(() => commandHistory.slice(0, 5), [commandHistory]);

  async function refresh() {
    try {
      const cockpit = await fetch("/api/cockpit").then((r) => r.json());
      setEvents(cockpit.events || []);
      setA2a(cockpit.a2a || []);
      setMetrics(cockpit.metrics || {});
    } catch {}

    try {
      const toolsData = await fetch("/api/tools").then((r) => r.json());
      setTools(toolsData || []);
    } catch {}

    try {
      const sourcesData = await fetch("/api/rag_sources").then((r) => r.json());
      setSources(sourcesData || []);
    } catch {}

    try {
      const cfg = await fetch("/api/config").then((r) => r.json());
      setConfigText(JSON.stringify(cfg || {}, null, 2));
    } catch {}

    try {
      const log = await fetch("/api/log_tail").then((r) => r.json());
      setTerminal(log.lines || []);
    } catch {}

    try {
      const hud = await fetch("/api/vla_latest").then((r) => r.json());
      setHudImage(hud.image || "");
    } catch {}

    try {
      const graphData = await fetch("/api/graph").then((r) => r.json());
      setGraph(graphData || { nodes: [], edges: [] });
    } catch {}

    try {
      const roles = await fetch("/api/roles").then((r) => r.json());
      if (roles && roles.length) {
        setPersonas(roles);
      }
    } catch {}

    try {
      const pending = await fetch("/api/pending_runs").then((r) => r.json());
      setPendingRuns(pending || []);
    } catch {}

    try {
      const runs = await fetch("/api/runs").then((r) => r.json());
      setRunHistory(runs || []);
      if (!runA && runs && runs.length) setRunA(runs[0].run_id);
      if (!runB && runs && runs.length > 1) setRunB(runs[1].run_id || runs[0].run_id);
    } catch {}
  }

  useInterval(refresh, REFRESH_INTERVAL_MS);
  useEffect(() => {
    refresh();
  }, []);

  async function sendCommand() {
    const cmd = command.trim();
    if (!cmd) return;
    const fileInfo = files.length ? `\nFiles: ${files.map((f) => f.name).join(", ")}` : "";
    const res = await fetch("/api/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command: cmd + fileInfo }),
    });
    const data = await res.json();
    setPlan(data.plan || JSON.stringify(data, null, 2));
    setCommandHistory((prev) => [cmd, ...prev.filter((c) => c !== cmd)].slice(0, 10));
    setCommand("");
    setFiles([]);
  }

  async function sendQuickCommand(cmd) {
    if (!cmd) return;
    await fetch("/api/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command: cmd }),
    });
  }

  async function handleUIAction(action) {
    if (!action) return;
    await fetch("/api/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command: `ui_action ${JSON.stringify(action)}` }),
    });
  }

  async function approve(runId) {
    if (!runId) return;
    await fetch("/api/approve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_id: runId }),
    });
  }

  async function approveStep() {
    await fetch("/api/approve_step", { method: "POST", headers: { "Content-Type": "application/json" } });
  }

  async function applyPersona(value) {
    if (!value) return;
    await fetch("/api/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command: `profile ${value}` }),
    });
  }

  async function handlePersonaChange(value) {
    setPersona(value);
    await applyPersona(value);
  }

  async function saveConfig() {
    try {
      const parsed = JSON.parse(configText || "{}");
      await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ updates: parsed }),
      });
    } catch {
      alert("Invalid JSON");
    }
  }

  async function searchMemory() {
    if (!memoryQuery.trim()) return;
    try {
      const res = await fetch("/api/memory_search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: memoryQuery.trim() }),
      });
      const data = await res.json();
      setMemoryResults(data || []);
    } catch {}
  }

  async function fetchRunDiff() {
    if (!runA || !runB) return;
    setRunDiffLoading(true);
    setRunDiffError("");
    try {
      const res = await fetch(`/api/run_diff?run_a=${encodeURIComponent(runA)}&run_b=${encodeURIComponent(runB)}`);
      if (!res.ok) {
        setRunDiffError(`Diff failed: ${res.status}`);
        setRunDiff("");
      } else {
        const data = await res.json();
        setRunDiff(data.diff || "");
      }
    } catch (err) {
      setRunDiffError(`Diff error: ${err}`);
      setRunDiff("");
    } finally {
      setRunDiffLoading(false);
    }
  }

  function updateClarification(blockId, key, value) {
    setClarificationInputs((prev) => ({
      ...prev,
      [blockId]: {
        ...(prev[blockId] || {}),
        [key]: value,
      },
    }));
  }

  async function submitClarification(blockId) {
    const values = clarificationInputs[blockId] || {};
    await fetch("/api/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command: `submit_form ${JSON.stringify(values)}` }),
    });
  }

  const sessionItems = useMemo(() => events.slice(0, 6), [events]);
  const activeRun = pendingRuns[0];
  const planSteps = Array.isArray(activeRun?.plan_steps) ? activeRun.plan_steps : [];

  const omniBar = (
    <div className="omni-bar">
      <div className="omni-inner">
        <div>
          <div className="omni-input" onDrop={(e) => {
            e.preventDefault();
            const dropped = Array.from(e.dataTransfer.files || []);
            if (dropped.length) setFiles(dropped);
          }} onDragOver={(e) => e.preventDefault()}>
            <input
              value={command}
              onChange={(event) => setCommand(event.target.value)}
              placeholder="Ask anything, drop files, or issue a command"
            />
            <div className="badge">{files.length ? `${files.length} file(s)` : "No files"}</div>
          </div>
          <div className="suggestions">
            {suggestions.map((s) => (
              <div key={s} className="suggestion" onClick={() => setCommand(s)}>{s}</div>
            ))}
          </div>
        </div>
        <div className="omni-actions">
          <button className="secondary" onClick={approveStep}>Approve Step</button>
          <button className="primary" onClick={sendCommand}>Send</button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="app">
      <header>
        <div className="brand">
          <div className="dot" />
          Agentic Control Plane
        </div>
        <div className="nav">
          {NAV_TABS.map((item) => (
            <button
              key={item.key}
              className={`ghost ${nav === item.key ? "active" : ""}`}
              onClick={() => setNav(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="status">
          <div className="pill">Metrics: {Object.keys(metrics).length}</div>
          <div className="pill">Events: {events.length}</div>
          <select
            className="persona"
            value={persona}
            onChange={(event) => handlePersonaChange(event.target.value)}
          >
            <option value="">Persona: Default</option>
            {personas.map((p) => (
              <option key={p.id} value={p.id}>{p.label || p.id}</option>
            ))}
          </select>
          <button className="secondary" onClick={() => setShowSheet(true)}>Config</button>
          <button className="secondary" onClick={() => setShowBrain(true)}>Graph</button>
        </div>
      </header>

      <main>
        {nav === "mission" && (
          <section className="shell">
            <aside className="sidebar">
              <div>
                <h4>Agent Market</h4>
                <div className="persona-list">
                  {personas.map((p) => (
                    <button
                      key={p.id}
                      className={`secondary ${persona === p.id ? "active" : ""}`}
                      onClick={() => handlePersonaChange(p.id)}
                    >
                      {p.label || p.id}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <h4>Sessions</h4>
                {sessionItems.map((item, idx) => (
                  <div key={`${item.event_type}-${idx}`} className="session">
                    <strong>{item.event_type || "event"}</strong>
                  </div>
                ))}
              </div>
              <div>
                <h4>Pending Approvals</h4>
                {pendingRuns.length ? pendingRuns.map((run) => (
                  <div key={run.run_id} className="session">
                    <div>{run.intent || "Pending"}</div>
                    <button className="primary" style={{ marginTop: 6 }} onClick={() => approve(run.run_id)}>Approve</button>
                  </div>
                )) : <div className="session">None</div>}
              </div>
            </aside>

            <section className="panel">
              <div className="panel-grid">
                <div className="card unified">
                  <div className="split-head">
                    <h3>Unified Flow</h3>
                    <div className="mono">Run: {activeRun?.run_id || "—"}</div>
                  </div>
                  <div className="split">
                    <div className="split-col">
                      <h4>Plan</h4>
                      {planSteps.length ? (
                        <ol className="plan-list">
                          {planSteps.map((s, idx) => (
                            <li key={`${s.step || idx}`}>
                              <span className="plan-step">{s.step || idx + 1}</span>
                              <div>
                                <strong>{s.action || "step"}</strong>
                                <div className="mono">{s.target || s.command || "—"}</div>
                                <div className="muted">{s.reason || "No rationale yet."}</div>
                              </div>
                            </li>
                          ))}
                        </ol>
                      ) : (
                        <pre className="mono">{plan || "No active plan yet."}</pre>
                      )}
                    </div>
                    <div className="split-col">
                      <h4>Execution</h4>
                      <div className="stream compact">
                        {events.slice(0, 8).map((e, idx) => {
                          const ui = extractUI(e.payload || {});
                          const badge = eventBadge(e.event_type || "");
                          const uiPayload = e.payload?.payload || e.payload || {};
                          const actions = uiPayload.ui?.actions || [];
                          return (
                            <div key={`${e.event_type}-${idx}`} className="event-line">
                              <span className={`badge ${badge}`}>{e.event_type}</span>
                              <span className="mono">{eventSummary(e) || "event"}</span>
                              <span className="meta">{new Date((e.timestamp || 0) * 1000).toLocaleTimeString()}</span>
                              {ui ? (
                                <div className="genui-block">
                                  {renderUICard(ui)}
                                  {renderUIActions(actions, handleUIAction)}
                                </div>
                              ) : null}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="card">
                  <h3>Approvals & Clarifications</h3>
                  <div className="approval-grid">
                    {pendingRuns.map((run) => {
                      const intent = typeof run.intent === "string"
                        ? run.intent
                        : (run.intent?.command || run.intent?.goal || "Pending run");
                      return (
                        <div key={run.run_id} className="approval-card">
                          <div className="approval-title">
                            <strong>{intent}</strong>
                            <span className="mono">{run.run_id.slice(0, 8)}</span>
                          </div>
                          <div className="approval-steps">
                            {(run.plan_steps || []).slice(0, 5).map((s, idx) => (
                              <div key={`${run.run_id}-${idx}`} className="approval-step">
                                {s.step || idx + 1}. {s.action || "step"} → {s.target || s.command || "—"}
                              </div>
                            ))}
                          </div>
                          <div className="actions">
                            <button className="primary" onClick={() => approve(run.run_id)}>Approve</button>
                          </div>
                        </div>
                      );
                    })}
                    {uiBlocks.filter((b) => b.ui.type === "form").map((block) => {
                      const fields = Array.isArray(block.ui.fields) ? block.ui.fields : [];
                      return (
                        <div key={block.id} className="approval-card">
                          <div className="approval-title">
                            <strong>{block.ui.title || "Clarification needed"}</strong>
                            <span className="mono">{new Date(block.timestamp * 1000).toLocaleTimeString()}</span>
                          </div>
                          <div className="form-grid">
                            {fields.map((f, idx) => {
                              const key = typeof f === "string"
                                ? f
                                : (f.key || f.name || f.label || `field_${idx + 1}`);
                              const label = typeof f === "string"
                                ? f
                                : (f.label || f.name || f.key || `Field ${idx + 1}`);
                              return (
                                <label key={`${block.id}-${key}`} className="form-field">
                                  <span>{label}</span>
                                  <input
                                    value={clarificationInputs[block.id]?.[key] || ""}
                                    onChange={(event) => updateClarification(block.id, key, event.target.value)}
                                  />
                                </label>
                              );
                            })}
                          </div>
                          <div className="actions">
                            <button className="secondary" onClick={() => submitClarification(block.id)}>Submit</button>
                          </div>
                        </div>
                      );
                    })}
                    {uiBlocks.filter((b) => b.ui.type === "approval").map((block) => (
                      <div key={block.id} className="approval-card">
                        <div className="approval-title">
                          <strong>{block.ui.title || "Approval requested"}</strong>
                          <span className="mono">{new Date(block.timestamp * 1000).toLocaleTimeString()}</span>
                        </div>
                        <div className="actions">
                          <button className="primary" onClick={() => sendQuickCommand("approve_once")}>Approve Once</button>
                          <button className="secondary" onClick={() => sendQuickCommand("approve_always")}>Always Allow</button>
                          <button className="secondary" onClick={() => sendQuickCommand("approve_never")}>Never Allow</button>
                        </div>
                      </div>
                    ))}
                    {!pendingRuns.length && !uiBlocks.length && (
                      <div className="event">No approvals or clarifications right now.</div>
                    )}
                  </div>
                </div>

                <div className="card">
                  <h3>Live Terminal Stream</h3>
                  <TerminalPanel lines={terminal} />
                </div>

                <div className="card">
                  <h3>Agents, Tools & Graph</h3>
                  <div className="agent-badges">
                    {personas.map((p) => (
                      <span key={p.id} className={`badge ${persona === p.id ? "success" : ""}`}>
                        {p.label || p.id}
                      </span>
                    ))}
                  </div>
                  <div className="tool-grid compact">
                    {tools.slice(0, 8).map((t) => (
                      <div key={t.name} className="tool">
                        <div><strong>{t.name}</strong></div>
                        <div className="mono">{t.arg_hint || ""}</div>
                        <div style={{ color: "var(--muted)" }}>risk: {t.risk || "n/a"}</div>
                      </div>
                    ))}
                  </div>
                  <div className="graph-mini">
                    <BrainView graph={graph} width={520} height={260} />
                  </div>
                </div>
              </div>
            </section>

            <aside className="canvas">
              <div className="canvas-header">
                <div>
                  <h3>Artifacts</h3>
                  <div className="mono" style={{ fontSize: 11, color: "var(--muted)" }}>
                    Canvas auto-opens when artifacts arrive.
                  </div>
                </div>
                <div className="tabs">
                  <button
                    className={`tab ${artifactMode === "preview" ? "active" : ""}`}
                    onClick={() => setArtifactMode("preview")}
                  >
                    Preview
                  </button>
                  <button
                    className={`tab ${artifactMode === "raw" ? "active" : ""}`}
                    onClick={() => setArtifactMode("raw")}
                  >
                    Raw
                  </button>
                </div>
              </div>
              {artifact ? (
                artifactMode === "preview" ? (
                  <div className="artifact-view">
                    <iframe title="artifact preview" srcDoc={artifact.content} />
                  </div>
                ) : (
                  <pre>{artifact.content}</pre>
                )
              ) : (
                <pre>No artifacts yet.</pre>
              )}

              <div className="run-history">
                <h4>Run History</h4>
                <div className="run-list">
                  {runHistory.length ? runHistory.map((run) => (
                    <div key={run.run_id} className="run-item">
                      <div>
                        <strong>{run.goal || "Untitled run"}</strong>
                        <div className="mono">{run.run_id}</div>
                        <div className="muted">{run.status || "unknown"} • {formatTimestamp(run.updated_at) || "—"}</div>
                      </div>
                      <div className="run-actions">
                        <button className="ghost" onClick={() => setRunA(run.run_id)}>Use A</button>
                        <button className="ghost" onClick={() => setRunB(run.run_id)}>Use B</button>
                      </div>
                    </div>
                  )) : <div className="event">No runs yet.</div>}
                </div>
              </div>

              <div className="diff-panel">
                <h4>Run Diff</h4>
                <div className="diff-controls">
                  <select value={runA} onChange={(e) => setRunA(e.target.value)}>
                    <option value="">Select Run A</option>
                    {runHistory.map((run) => (
                      <option key={`a-${run.run_id}`} value={run.run_id}>{run.run_id}</option>
                    ))}
                  </select>
                  <select value={runB} onChange={(e) => setRunB(e.target.value)}>
                    <option value="">Select Run B</option>
                    {runHistory.map((run) => (
                      <option key={`b-${run.run_id}`} value={run.run_id}>{run.run_id}</option>
                    ))}
                  </select>
                  <button className="secondary" onClick={fetchRunDiff} disabled={runDiffLoading}>
                    {runDiffLoading ? "Diffing..." : "Diff Runs"}
                  </button>
                </div>
                {runDiffError ? (
                  <div className="event">{runDiffError}</div>
                ) : (
                  <pre className="mono">{runDiff || "Select two runs to compare."}</pre>
                )}
              </div>
            </aside>
          </section>
        )}

        {nav === "coder" && (
          <section className="workspace">
            <div className="workspace-grid">
              <div className="card">
                <h4>Active Plan</h4>
                <pre>{plan || "No active plan yet."}</pre>
                <div className="actions" style={{ marginTop: 10 }}>
                  {pendingRuns.map((run) => (
                    <button key={run.run_id} className="primary" onClick={() => approve(run.run_id)}>
                      Approve {run.run_id.slice(0, 6)}
                    </button>
                  ))}
                </div>
              </div>
              <div className="card">
                <h4>Coder Workspace</h4>
                <Editor
                  height="360px"
                  defaultLanguage="python"
                  theme="vs-light"
                  value={artifact ? artifact.content : "// Code output will appear here"}
                  options={{ readOnly: true, minimap: { enabled: false } }}
                />
              </div>
            </div>
            <div className="card">
              <h4>Recent Tool Calls</h4>
              <div className="stream">
                {events.slice(0, 8).map((e, idx) => (
                  <div key={`code-${idx}`} className="event">
                    <strong>{e.event_type}</strong>
                    <div className="mono">{JSON.stringify(e.payload || {}, null, 2)}</div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}

        {nav === "research" && (
          <section className="workspace">
            <div className="workspace-grid">
              <div className="card">
                <h4>Research Stream</h4>
                <div className="stream">
                  {events.slice(0, 10).map((e, idx) => (
                    <div key={`research-${idx}`} className="event">
                      <strong>{e.event_type}</strong>
                      <div className="mono">{JSON.stringify(e.payload || {}, null, 2)}</div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="card">
                <h4>Sources Tray</h4>
                {sources.length ? sources.map((s, idx) => {
                  const name = (s.source || "").split(/[\\/]/).slice(-1)[0] || s.source;
                  return (
                    <div key={`${name}-${idx}`} className="source-card" style={{ marginBottom: 10 }}>
                      <div className="source-icon">{name.slice(0, 1).toUpperCase()}</div>
                      <div>
                        <strong>{name}</strong>
                        <div style={{ fontSize: 12, color: "var(--muted)" }}>{s.source}</div>
                        <div style={{ fontSize: 12, color: "var(--muted)" }}>
                          chunks={s.chunks} rank={(s.avg_rank || 0).toFixed(2)}
                        </div>
                      </div>
                    </div>
                  );
                }) : <div className="event">No sources indexed.</div>}
              </div>
            </div>
          </section>
        )}

        {nav === "vla" && (
          <section className="workspace">
            <div className="workspace-grid">
              <div className="card">
                <h4>Vision Feed</h4>
                {hudImage ? (
                  <div className="artifact-view">
                    <img src={hudImage} alt="VLA HUD" style={{ width: "100%" }} />
                  </div>
                ) : (
                  <div className="event">No HUD image yet.</div>
                )}
              </div>
              <div className="card">
                <h4>Action History</h4>
                <div className="stream">
                  {events.slice(0, 8).map((e, idx) => (
                    <div key={`vla-${idx}`} className="event">
                      <strong>{e.event_type}</strong>
                      <div className="mono">{JSON.stringify(e.payload || {}, null, 2)}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </section>
        )}

        {nav === "brain" && (
          <section className="workspace">
            <div className="card">
              <h4>Memory Search</h4>
              <div className="composer">
                <input
                  value={memoryQuery}
                  onChange={(e) => setMemoryQuery(e.target.value)}
                  placeholder="Ask memory (e.g., A2A secret)"
                />
                <button className="primary" onClick={searchMemory}>Search</button>
              </div>
              <div className="stream" style={{ marginTop: 12 }}>
                {memoryResults.length ? memoryResults.map((m, idx) => (
                  <div key={`mem-${idx}`} className="event">
                    <span className="badge">{m.kind}</span>
                    <div className="mono" style={{ marginTop: 6 }}>{m.content}</div>
                    <div className="mono" style={{ fontSize: 11, color: "var(--muted)" }}>score {(m.score || 0).toFixed(2)}</div>
                  </div>
                )) : <div className="event">No results yet.</div>}
              </div>
            </div>
          </section>
        )}

        {nav === "governance" && (
          <section className="workspace">
            <div className="workspace-grid">
              <div className="card">
                <h4>Pending Approvals</h4>
                {pendingRuns.length ? pendingRuns.map((run) => (
                  <div key={run.run_id} className="event">
                    <div><strong>{run.intent}</strong></div>
                    <pre>{(run.plan_steps || []).join("\n")}</pre>
                    <button className="primary" onClick={() => approve(run.run_id)}>Approve</button>
                  </div>
                )) : <div className="event">No pending runs.</div>}
              </div>
              <div className="card">
                <h4>Recent Decisions</h4>
                <div className="stream">
                  {events.slice(0, 8).map((e, idx) => (
                    <div key={`gov-${idx}`} className="event">
                      <strong>{e.event_type}</strong>
                      <div className="mono">{JSON.stringify(e.payload || {}, null, 2)}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </section>
        )}

        {nav === "health" && (
          <section className="workspace">
            <div className="workspace-grid">
              <div className="card">
                <h4>System Metrics</h4>
                <pre>{JSON.stringify(metrics, null, 2)}</pre>
              </div>
              <div className="card">
                <h4>Tool Inventory</h4>
                <div className="tool-grid">
                  {tools.map((t) => (
                    <div key={t.name} className="tool">
                      <div><strong>{t.name}</strong></div>
                      <div className="mono">{t.arg_hint || ""}</div>
                      <div style={{ color: "var(--muted)" }}>risk: {t.risk || "n/a"}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </section>
        )}
      </main>

      {showSheet && (
        <>
          <div className="overlay show" onClick={() => setShowSheet(false)} />
          <div className="sheet open">
            <h3>Configuration</h3>
            <textarea
              className="mono"
              style={{ width: "100%", height: 300 }}
              value={configText}
              onChange={(event) => setConfigText(event.target.value)}
            />
            <div className="actions" style={{ marginTop: 10 }}>
              <button className="primary" onClick={saveConfig}>Save</button>
              <button className="secondary" onClick={() => setShowSheet(false)}>Close</button>
            </div>
          </div>
        </>
      )}

      {showBrain && (
        <div className="brain-view show" onClick={() => setShowBrain(false)}>
          <div className="brain-canvas" onClick={(e) => e.stopPropagation()}>
            <h3>Agent Mesh</h3>
            <BrainView graph={graph} />
            <button className="secondary" onClick={() => setShowBrain(false)}>Close</button>
          </div>
        </div>
      )}

      {hudImage ? (
        <div className="hud">
          <img src={hudImage} alt="VLA HUD" />
        </div>
      ) : null}

      {omniBar}
    </div>
  );
}

function BrainView({ graph, width = 800, height = 420 }) {
  const nodes = graph.nodes || [];
  const edges = graph.edges || [];
  const flowNodes = nodes.map((n, idx) => ({
    id: n.id,
    data: { label: n.label || n.id },
    position: { x: 120 * (idx % 4), y: 100 * Math.floor(idx / 4) },
    style: {
      borderRadius: 12,
      padding: 10,
      border: "1px solid #c7d2fe",
      background: n.type === "local" ? "#dbeafe" : "#eff6ff",
      fontSize: 12,
    },
  }));
  const flowEdges = edges.map((e, idx) => ({
    id: `e-${idx}`,
    source: e.source,
    target: e.target,
    label: e.count ? `${e.count}` : undefined,
    animated: true,
    style: { stroke: "#2563eb" },
  }));
  return (
    <div className="reactflow-wrapper" style={{ width, height }}>
      <ReactFlow nodes={flowNodes} edges={flowEdges} fitView>
        <MiniMap />
        <Controls />
        <Background gap={16} color="#e2e8f0" />
      </ReactFlow>
    </div>
  );
}
