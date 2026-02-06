import { useEffect, useMemo, useState } from "react";
import Editor from "@monaco-editor/react";

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

function renderUICard(ui) {
  if (!ui || typeof ui !== "object") return null;
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
  const [tab, setTab] = useState("a2a");
  const [artifactMode, setArtifactMode] = useState("preview");
  const [showSheet, setShowSheet] = useState(false);
  const [showBrain, setShowBrain] = useState(false);
  const [pendingRuns, setPendingRuns] = useState([]);
  const [commandHistory, setCommandHistory] = useState([]);
  const [files, setFiles] = useState([]);
  const [memoryQuery, setMemoryQuery] = useState("");
  const [memoryResults, setMemoryResults] = useState([]);

  const artifact = useMemo(() => extractArtifacts(events), [events]);
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

  const sessionItems = useMemo(() => events.slice(0, 6), [events]);

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
              <div>
                <h3>Live Canvas</h3>
                <div className="stream">
                  {events.map((e, idx) => {
                    const ui = extractUI(e.payload || {});
                    const badge = eventBadge(e.event_type || "");
                    return (
                      <details key={`${e.event_type}-${idx}`} className="event">
                        <summary>
                          <span className={`badge ${badge}`}>{e.event_type}</span>
                          <span className="mono" style={{ marginLeft: 8 }}>{new Date((e.timestamp || 0) * 1000).toLocaleTimeString()}</span>
                        </summary>
                        <div className="mono">{JSON.stringify(e.payload || {}, null, 2)}</div>
                        {ui ? renderUICard(ui) : null}
                      </details>
                    );
                  })}
                </div>
              </div>

              <div>
                <div className="tabs" id="detail-tabs">
                  {[
                    { key: "a2a", label: "A2A" },
                    { key: "terminal", label: "Terminal" },
                    { key: "sources", label: "Sources" },
                    { key: "tools", label: "Tools" },
                  ].map((item) => (
                    <button
                      key={item.key}
                      className={`tab ${tab === item.key ? "active" : ""}`}
                      onClick={() => setTab(item.key)}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
                <div className="stack">
                  {tab === "a2a" && (
                    <div>
                      <h3>A2A Feed</h3>
                      <div className="stream">
                        {a2a.map((m, idx) => (
                          <div key={`${m.sender}-${idx}`} className="event">
                            <strong>{m.sender}</strong> → {m.receiver}
                            <div className="mono">{m.message}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {tab === "terminal" && (
                    <div>
                      <h3>Terminal Output</h3>
                      <pre className="mono">{terminal.join("\n") || "No output yet."}</pre>
                    </div>
                  )}
                  {tab === "sources" && (
                    <div>
                      <h3>Sources</h3>
                      {sources.length ? sources.map((s, idx) => {
                        const name = (s.source || "").split(/[\\/]/).slice(-1)[0] || s.source;
                        return (
                          <div key={`${name}-${idx}`} className="source-card">
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
                  )}
                  {tab === "tools" && (
                    <div>
                      <h3>Tools</h3>
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
                  )}
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

function BrainView({ graph }) {
  const nodes = graph.nodes || [];
  const edges = graph.edges || [];
  const width = 800;
  const height = 420;
  const radius = Math.min(width, height) / 3;
  const positions = {};

  nodes.forEach((n, i) => {
    const angle = (i / Math.max(1, nodes.length)) * Math.PI * 2;
    positions[n.id] = {
      x: Math.cos(angle) * radius,
      y: Math.sin(angle) * radius,
    };
  });

  return (
    <svg width="100%" height="420" viewBox={`${-width / 2} ${-height / 2} ${width} ${height}`}>
      <g>
        {edges.map((e, idx) => {
          const s = positions[e.source];
          const t = positions[e.target];
          if (!s || !t) return null;
          return (
            <line
              key={`edge-${idx}`}
              x1={s.x}
              y1={s.y}
              x2={t.x}
              y2={t.y}
              stroke="#2563eb"
              strokeWidth={Math.max(1, e.count / 2)}
            />
          );
        })}
        {nodes.map((n) => {
          const pos = positions[n.id] || { x: 0, y: 0 };
          return (
            <g key={n.id}>
              <circle cx={pos.x} cy={pos.y} r="18" fill={n.type === "local" ? "#0ea5e9" : "#2563eb"} />
              <text x={pos.x} y={pos.y + 4} textAnchor="middle" fill="#fff" fontSize="12">
                {n.label}
              </text>
            </g>
          );
        })}
      </g>
    </svg>
  );
}
