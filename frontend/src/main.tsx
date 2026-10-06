import { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { createPortal } from "react-dom";
import { Activity, Archive, CheckCircle2, ChevronRight, CircleDot, FileCode2, Github, GitPullRequest, LayoutDashboard, MessageSquare, RadioTower, RefreshCw, Search, ShieldAlert, Trash2, XCircle } from "lucide-react";
import "./styles.css";

type IncidentStatus = "acknowledged" | "pending" | "processing" | "failed" | "blocked" | "pr_created" | "ignored" | "resolved";
type Panel = "Overview" | "Incidents" | "Activity";
type ManualAction = { title: string; command: string; reason: string; validation: string };
type DiagnosisSnapshot = { incident?: string; hypothesis?: string; status?: string; confidence?: "low" | "medium" | "high"; risk?: "low" | "medium" | "high" | "critical"; manual_actions?: ManualAction[] };
type TimelineEvent = { at: string; event: string; prompt?: string; diagnosis?: DiagnosisSnapshot };
type AgentActivity = { at: string; status: "active" | "idle" | "down" };
type DiagnosisHistory = { at: string; diagnosis: { incident?: string; hypothesis?: string; status?: string; confidence?: Incident["confidence"]; risk?: Incident["risk"]; manual_actions?: ManualAction[] } };
type Incident = { id: string; title: string; summary: string; source: string; alertname: string; alertStatus: string; startsAt: string; pullRequestUrl: string; status: IncidentStatus; severity: string; namespace: string; pod: string; confidence: "low" | "medium" | "high"; risk: "low" | "medium" | "high" | "critical"; updated: string; replayedAt: string; replayPrompts: string[]; manualActions: ManualAction[]; manualActionHistory: Array<Record<string, unknown>>; diagnosisHistory: DiagnosisHistory[]; timeline: TimelineEvent[]; evidence: string[]; files: string[]; actions: string[] };

type ApiIncident = { id: string; status: IncidentStatus; alert: { source?: string; status?: string; startsAt?: string; endsAt?: string; generatorURL?: string; labels?: Record<string, string>; annotations?: Record<string, string> }; diagnosis: { incident?: string; confidence?: Incident["confidence"]; risk?: Incident["risk"]; evidence?: string[]; proposed_files?: string[]; manual_actions?: ManualAction[] }; pull_request_url?: string | null; updated_at?: string; replayed_at?: string | null; replay_prompts?: string[]; manual_actions?: Array<Record<string, unknown>>; diagnosis_history?: DiagnosisHistory[]; timeline?: TimelineEvent[] };

function toIncident(item: ApiIncident): Incident {
  const annotations = item.alert.annotations ?? {};
  return {
    id: item.id,
    title: annotations.summary ?? item.diagnosis.incident ?? item.id,
    summary: annotations.description ?? "No incident description recorded.",
    source: item.alert.source ?? item.alert.labels?.source ?? "unknown",
    alertname: item.alert.labels?.alertname ?? "unknown",
    alertStatus: item.alert.status ?? "unknown",
    startsAt: item.alert.startsAt ?? "unknown",
    pullRequestUrl: item.pull_request_url ?? "",
    status: item.status,
    severity: item.alert.labels?.severity ?? "unknown",
    namespace: item.alert.labels?.namespace ?? "",
    pod: item.alert.labels?.pod ?? "",
    confidence: item.diagnosis.confidence ?? "low",
    risk: item.diagnosis.risk ?? "low",
    updated: item.updated_at ? new Date(item.updated_at).toLocaleString() : "unknown",
    replayedAt: item.replayed_at ? new Date(item.replayed_at).toLocaleString() : "—",
    replayPrompts: item.replay_prompts ?? [],
    manualActions: item.diagnosis.manual_actions ?? [],
    manualActionHistory: item.manual_actions ?? [],
    diagnosisHistory: item.diagnosis_history ?? [],
    timeline: item.timeline ?? [],
    evidence: item.diagnosis.evidence ?? [],
    files: item.diagnosis.proposed_files ?? [],
    actions: [
      ...(item.pull_request_url ? ["open-pr"] : []),
      ...(["acknowledged", "failed", "blocked"].includes(item.status) ? ["replay"] : []),
      ...(["resolved", "ignored"].includes(item.status) ? [] : ["ignore"]),
      "delete",
    ],
  };
}

const panels: { label: Panel; icon: typeof LayoutDashboard }[] = [
  { label: "Overview", icon: LayoutDashboard }, { label: "Incidents", icon: ShieldAlert }, { label: "Activity", icon: Activity },
];

const statusFilters: IncidentStatus[] = ["acknowledged", "pending", "processing", "failed", "blocked", "pr_created", "ignored", "resolved"];

function controlToken(): string | null {
  const existing = localStorage.getItem("anton.alertToken");
  const token = existing || window.prompt("Anton alert token");
  if (token) localStorage.setItem("anton.alertToken", token);
  return token;
}

function usePortalTarget(selector: string, dependency: string): HTMLElement | null {
  const [target, setTarget] = useState<HTMLElement | null>(null);
  useEffect(() => {
    setTarget(document.querySelector<HTMLElement>(selector));
  }, [selector, dependency]);
  return target;
}

function StatusIcon({ status }: { status: IncidentStatus }) {
  if (status === "resolved") return <CheckCircle2 size={15} />;
  if (status === "blocked" || status === "failed") return <XCircle size={15} />;
  if (status === "pr_created") return <GitPullRequest size={15} />;
  if (status === "ignored") return <Archive size={15} />;
  return <CircleDot size={15} />;
}

function ManualActions({ incident, apiBase, onUpdated }: { incident: Incident; apiBase: string; onUpdated: (incident: Incident) => void }) {
  const [running, setRunning] = useState<number | null>(null);
  const target = usePortalTarget(".detail-panel", incident.id);
  const canApprove = incident.status === "blocked" && incident.manualActions.length > 0;
  const hasRuns = incident.manualActionHistory.length > 0;
  if (!canApprove && !hasRuns) return null;
  async function execute(index: number) {
    const token = controlToken();
    if (!token) return;
    if (!window.confirm(`Approve and run this command?\n\n$ ${incident.manualActions[index].command}`)) return;
    setRunning(index);
    try {
      const response = await fetch(`${apiBase}/incidents/${incident.id}/manual-actions/execute`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ action_index: index }),
      });
      if (!response.ok) throw new Error(`Manual action rejected (${response.status})`);
      onUpdated(toIncident(await response.json() as ApiIncident));
    } finally {
      setRunning(null);
    }
  }
  const content = <section className="manual-actions" aria-label="Manual actions and runs">
    {canApprove && <>
      <div className="detail-section-title"><ShieldAlert size={15} /> Manual action approval</div>
      <small className="incident-updated">Incident updated: {incident.updated}</small>
      {incident.manualActions.map((action, index) => <div className="manual-action" key={`${action.command}-${index}`}>
        <strong>{action.title}</strong><pre className="manual-command"><code>$ {action.command}</code></pre><p>{action.reason}</p><small>Validation: {action.validation}</small>
        {incident.manualActionHistory.filter((run) => run.action_index === index).slice(-1).map((run) => <small key={`${String(run.at)}-${index}`} className="manual-action-result">Last run: {String(run.status)}{run.exit_code !== undefined ? ` (exit ${String(run.exit_code)})` : ""}{run.error ? ` — ${String(run.error)}` : ""}</small>)}
        <button className="action-button" onClick={() => void execute(index)} disabled={running !== null}>{running === index ? "Running…" : "Approve & run"}</button>
      </div>)}
    </>}
    {hasRuns && <div className="manual-runs" aria-label="Manual action runs">
      {incident.manualActionHistory.slice().reverse().map((run, index) => <div className="manual-run" key={`${String(run.at)}-${index}`}>
        <div><strong>{String(run.status)}{run.exit_code !== undefined ? ` · exit ${String(run.exit_code)}` : ""}</strong><small>{String(run.at ?? "")}</small></div>
        <code>{String(run.command ?? "manual action")}</code>
        {typeof run.error === "string" && <small className="manual-run-error">{run.error}</small>}
      </div>)}
    </div>}
  </section>;
  return target ? createPortal(content, target) : null;
}

function IncidentUpdated({ incident }: { incident: Incident }) {
  const target = usePortalTarget(".incident-list-panel", incident.id);
  return target ? createPortal(<small className="incident-menu-updated">Updated {incident.updated}</small>, target) : null;
}

function ActivityFeed({ incidents, agentEvents, agentName }: { incidents: Incident[]; agentEvents: AgentActivity[]; agentName: string }) {
  const actionIcons: Record<string, typeof Activity> = {
    acknowledged: CheckCircle2,
    created: Activity,
    reopened: RefreshCw,
    replayed: RefreshCw,
    processing: Activity,
    pending: CircleDot,
    failed: XCircle,
    blocked: ShieldAlert,
    pr_created: GitPullRequest,
    resolved: CheckCircle2,
    ignored: Archive,
    manual_action_executed: ShieldAlert,
  };
  const labels: Record<string, string> = {
    acknowledged: "acknowledged alert",
    created: "received alert",
    reopened: "reopened incident",
    replayed: "replayed investigation",
    processing: "started investigation",
    pending: "waiting for recovery",
    failed: "failed investigation",
    blocked: "blocked for manual action",
    pr_created: "created pull request",
    resolved: "resolved incident",
    ignored: "ignored incident",
    manual_action_executed: "executed manual action",
  };
  const incidentEvents = incidents.flatMap((incident) => {
    const timeline = incident.timeline.length > 0
      ? incident.timeline.map((entry) => ({ at: entry.at, icon: actionIcons[entry.event] ?? CircleDot, event: labels[entry.event] ?? entry.event.replaceAll("_", " "), title: incident.title, source: incident.source, id: incident.id }))
      : [{ at: incident.updated, icon: actionIcons[incident.status] ?? CircleDot, event: labels[incident.status] ?? incident.status, title: incident.title, source: incident.source, id: incident.id }];
    const manualRuns = incident.manualActionHistory.map((run) => ({
      at: String(run.at ?? incident.updated),
      icon: ShieldAlert,
      event: `manual action ${String(run.status ?? "run")}`,
      title: incident.title,
      source: incident.source,
      id: incident.id,
    }));
    return [...timeline, ...manualRuns];
  });
  const lifecycleEvents = agentEvents.map((entry) => ({
    at: entry.at,
    icon: entry.status === "active" ? CheckCircle2 : entry.status === "idle" ? CircleDot : XCircle,
    event: `agent ${entry.status}`,
    title: `${agentName} is ${entry.status}`,
    source: "agent",
    id: agentName,
  }));
  const events = [...incidentEvents, ...lifecycleEvents]
    .sort((left, right) => right.at.localeCompare(left.at));
  return <section className="activity-panel console-panel" aria-label="Agent activity feed">
    {events.length === 0 ? <div className="panel-placeholder"><Activity size={25} /><h2>No activity yet</h2><p>Anton’s actions will appear here as alerts are processed.</p></div> : <div className="activity-feed">
      {events.map((entry, index) => {
        const Icon = entry.icon;
        return <article className="activity-item" key={`${entry.id}-${entry.at}-${index}`}>
          <span className="activity-icon"><Icon size={14} /></span>
          <div className="activity-item-body"><div><strong>{entry.event}</strong><time dateTime={entry.at}>{new Date(entry.at).toLocaleString()}</time></div><p>{entry.title}</p><small>{entry.source} · {entry.id}</small></div>
        </article>;
      })}
    </div>}
  </section>;
}

function OverviewPanel({ incidents }: { incidents: Incident[] }) {
  const openCount = incidents.filter((incident) => !["resolved", "ignored"].includes(incident.status)).length;
  const resolvedCount = incidents.filter((incident) => incident.status === "resolved").length;
  const sourceCounts = Array.from(new Set(incidents.map((incident) => incident.source))).sort().map((source) => ({
    label: source,
    count: incidents.filter((incident) => incident.source === source).length,
  }));
  const statusLabels: Record<IncidentStatus, string> = {
    acknowledged: "Acknowledged",
    pending: "Pending",
    processing: "Processing",
    failed: "Failed",
    blocked: "Blocked",
    pr_created: "PR created",
    ignored: "Ignored",
    resolved: "Resolved",
  };
  return <section className="overview-panel console-panel" aria-label="Incident overview">
    <div className="overview-summary">
      <div><strong>{incidents.length}</strong><span>Total</span></div>
      <div><strong>{openCount}</strong><span>Open</span></div>
      <div><strong>{resolvedCount}</strong><span>Resolved</span></div>
    </div>
    <div className="overview-sections">
      <div className="overview-section"><div className="overview-section-title">Status</div><div className="overview-count-grid">
        {statusFilters.map((status) => <div className={`overview-count ${status}`} key={status}><StatusIcon status={status} /><span>{statusLabels[status]}</span><strong>{incidents.filter((incident) => incident.status === status).length}</strong></div>)}
      </div></div>
      <div className="overview-section"><div className="overview-section-title">Sources</div><div className="overview-source-list">
        {sourceCounts.length === 0 ? <span className="overview-empty">No sources yet</span> : sourceCounts.map((source) => <div className="overview-source" key={source.label}><span>{source.label}</span><strong>{source.count}</strong><i><b style={{ width: `${Math.max(8, Math.round((source.count / Math.max(1, incidents.length)) * 100))}%` }} /></i></div>)}
      </div></div>
    </div>
  </section>;
}

function IncidentThread({ incident }: { incident: Incident }) {
  const replayEvents = incident.timeline.filter((entry) => entry.event === "replayed" && entry.prompt).map((entry) => ({
    at: entry.at,
    role: "operator" as const,
    text: entry.prompt!,
    status: undefined,
    actions: [] as string[],
  }));
  const knownPrompts = new Set(replayEvents.map((entry) => entry.text));
  const legacyPrompts = incident.replayPrompts.filter((prompt) => !knownPrompts.has(prompt)).map((prompt) => ({
    at: incident.replayedAt === "—" ? incident.updated : incident.replayedAt,
    role: "operator" as const,
    text: prompt,
    status: undefined,
    actions: [] as string[],
  }));
  const suggestions = incident.diagnosisHistory.map((entry) => ({
    at: entry.at,
    role: "agent" as const,
    status: entry.diagnosis.status,
    text: entry.diagnosis.hypothesis || entry.diagnosis.incident || "No suggestion recorded.",
    actions: entry.diagnosis.manual_actions?.map((action) => action.title) ?? [],
  }));
  const messages = [...replayEvents, ...legacyPrompts, ...suggestions].sort((left, right) => left.at.localeCompare(right.at));
  if (messages.length === 0) return null;
  return <div className="detail-section incident-thread" aria-label="Incident conversation">
    <div className="detail-section-title"><MessageSquare size={15} /> Incident thread</div>
    <div className="thread-messages">
      {messages.map((message, index) => <article className={`thread-message ${message.role}`} key={`${message.at}-${index}`}>
        <div className="thread-message-meta"><strong>{message.role === "operator" ? "You" : "Anton"}</strong><time dateTime={message.at}>{new Date(message.at).toLocaleString()}</time></div>
        <p>{message.text}</p>
        {message.role === "agent" && <>{message.status && <small className="thread-status">{message.status}</small>}{message.actions.length > 0 && <small className="thread-actions">Manual actions: {message.actions.join(" · ")}</small>}</>}
      </article>)}
    </div>
  </div>;
}

function App() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [activePanel, setActivePanel] = useState<Panel>("Incidents");
  const [query, setQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [agentIdle, setAgentIdle] = useState(false);
  const [agentDown, setAgentDown] = useState(false);
  const [agentName, setAgentName] = useState("Tower");
  const [agentEvents, setAgentEvents] = useState<AgentActivity[]>([]);
  const [retryingId, setRetryingId] = useState("");
  const [statusNotification, setStatusNotification] = useState("");
  const previousAgentStatus = useRef<string | null>(null);
  const agentStatusFailures = useRef(0);
  const buildVersion = import.meta.env.VITE_ANTON_VERSION ?? "—";
  const [version, setVersion] = useState(buildVersion);
  const apiBase = import.meta.env.VITE_ANTON_API_URL ?? "";

  useEffect(() => {
    const controller = new AbortController();
    let firstLoad = true;
    let active = true;
    const loadIncidents = async () => {
      try {
        const response = await fetch(`${apiBase}/incidents?limit=200`, { signal: controller.signal, cache: "no-store" });
        if (!response.ok) throw new Error(`Anton API returned ${response.status}`);
        const data = await response.json() as { incidents: ApiIncident[] };
        if (!active) return;
        const loaded = data.incidents.map(toIncident);
        setIncidents(loaded);
        setSelectedId((current) => current && loaded.some((incident) => incident.id === current) ? current : loaded[0]?.id ?? "");
        setError("");
      } catch (reason) {
        if (reason instanceof Error && reason.name !== "AbortError") setError(reason.message === "Failed to fetch" ? `Cannot reach Anton API at ${apiBase}. Start the local API with task server:local.` : reason.message);
      } finally {
        if (active) {
          if (firstLoad) setLoading(false);
          firstLoad = false;
        }
      }
    };
    void loadIncidents();
    const interval = window.setInterval(() => void loadIncidents(), 5000);
    return () => {
      active = false;
      controller.abort();
      window.clearInterval(interval);
    };
  }, [apiBase]);

  useEffect(() => {
    fetch(`${apiBase}/version`, { cache: "no-store" })
      .then((response) => {
        if (!response.ok) throw new Error(`version endpoint returned ${response.status}`);
        return response.json() as Promise<{ version: string }>;
      })
      .then((data) => setVersion(data.version))
      .catch(() => setVersion(buildVersion));
  }, [apiBase]);

  useEffect(() => {
    let active = true;
    const loadAgentStatus = async () => {
      try {
        const response = await fetch(`${apiBase}/agent/status`, { cache: "no-store" });
        if (!response.ok) throw new Error("agent status unavailable");
        const data = await response.json() as { agent: string; status: "active" | "idle" };
        if (!active) return;
        agentStatusFailures.current = 0;
        if (data.agent) {
          setAgentName(data.agent);
          document.title = data.agent;
        }
        const nextStatus: AgentActivity["status"] = data.status;
        if (previousAgentStatus.current && previousAgentStatus.current !== nextStatus) {
          setStatusNotification(`${data.agent || agentName} is now ${nextStatus}.`);
          window.setTimeout(() => setStatusNotification(""), 4500);
        }
        if (previousAgentStatus.current !== nextStatus) {
          setAgentEvents((current) => [{ at: new Date().toISOString(), status: nextStatus }, ...current].slice(0, 100));
        }
        previousAgentStatus.current = nextStatus;
        setAgentIdle(data.status === "idle");
        setAgentDown(false);
      } catch {
        if (!active) return;
        agentStatusFailures.current += 1;
        if (agentStatusFailures.current < 3) return;
        if (previousAgentStatus.current && previousAgentStatus.current !== "down") {
          setStatusNotification(`${agentName} is unavailable.`);
          window.setTimeout(() => setStatusNotification(""), 4500);
        }
        if (previousAgentStatus.current !== "down") {
          setAgentEvents((current) => [{ at: new Date().toISOString(), status: "down" as const }, ...current].slice(0, 100));
        }
        previousAgentStatus.current = "down";
        setAgentDown(true);
      }
    };
    void loadAgentStatus();
    const interval = window.setInterval(() => void loadAgentStatus(), 5000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [apiBase]);

  const visibleIncidents = useMemo(() => incidents.filter((incident) => incident.status !== "ignored"), [incidents]);
  const sourceCount = (source: string) => visibleIncidents.filter((incident) => incident.source === source).length;
  const statusCount = (status: IncidentStatus) => incidents.filter((incident) => incident.status === status).length;
  const filtered = useMemo(() => incidents.filter((incident) => {
    const matchesDefaultStatus = statusFilter ? incident.status === statusFilter : incident.status !== "ignored";
    const matchesSource = !sourceFilter || incident.source === sourceFilter;
    const matchesQuery = `${incident.title} ${incident.summary} ${incident.source}`.toLowerCase().includes(query.toLowerCase());
    return matchesDefaultStatus && matchesSource && matchesQuery;
  }), [incidents, query, sourceFilter, statusFilter]);
  const selected = filtered.find((incident) => incident.id === selectedId) ?? filtered[0];
  const openCount = incidents.filter((incident) => !["resolved", "ignored"].includes(incident.status)).length;
  const selectedActionsDisabled = selected?.status === "processing";

  async function toggleAgentIdle() {
    const token = controlToken();
    if (!token) return;
    const nextIdle = !agentIdle;
    const response = await fetch(`${apiBase}/agent/${nextIdle ? "idle" : "active"}`, { method: "POST", headers: { Authorization: `Bearer ${token}` } });
    if (!response.ok) {
      localStorage.removeItem("anton.alertToken");
      throw new Error("Agent control request was rejected");
    }
    setAgentIdle(nextIdle);
    const nextStatus: AgentActivity["status"] = nextIdle ? "idle" : "active";
    setAgentEvents((current) => [{ at: new Date().toISOString(), status: nextStatus }, ...current].slice(0, 100));
    setStatusNotification(`${agentName} is now ${nextStatus}.`);
    window.setTimeout(() => setStatusNotification(""), 4500);
  }

  async function replayIncident(incident: Incident) {
    const token = controlToken();
    if (!token) return;
    const replayPrompt = incident.status === "blocked"
      ? window.prompt("Tell Anton what to reconsider before replaying this blocked incident") ?? ""
      : "";
    if (incident.status === "blocked" && !replayPrompt.trim()) return;
    setRetryingId(incident.id);
    try {
      const response = await fetch(`${apiBase}/incidents/replay/${incident.id}`, { method: "POST", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }, body: JSON.stringify({ prompt: incident.status === "blocked" ? replayPrompt : undefined }) });
      if (!response.ok) throw new Error(`Replay rejected (${response.status})`);
      const updated = toIncident(await response.json() as ApiIncident);
      setIncidents((current) => current.map((item) => item.id === updated.id ? updated : item));
    } finally {
      setRetryingId("");
    }
  }

  async function ignoreIncident(incident: Incident) {
    const token = controlToken();
    if (!token) return;
    const response = await fetch(`${apiBase}/incidents/${incident.id}/ignore`, { method: "POST", headers: { Authorization: `Bearer ${token}` } });
    if (!response.ok) throw new Error(`Ignore rejected (${response.status})`);
    const updated = toIncident(await response.json() as ApiIncident);
    setIncidents((current) => current.map((item) => item.id === updated.id ? updated : item));
  }

  async function deleteIncident(incident: Incident) {
    if (!window.confirm(`Delete incident “${incident.title}”? This cannot be undone.`)) return;
    const token = controlToken();
    if (!token) return;
    const response = await fetch(`${apiBase}/incidents/${incident.id}`, { method: "DELETE", headers: { Authorization: `Bearer ${token}` } });
    if (!response.ok) throw new Error(`Delete rejected (${response.status})`);
    setIncidents((current) => current.filter((item) => item.id !== incident.id));
    setSelectedId((current) => current === incident.id ? "" : current);
  }

  function updateIncident(updated: Incident) {
    setIncidents((current) => current.map((item) => item.id === updated.id ? updated : item));
  }

  return <div className="app-shell">
    {selected && <ManualActions incident={selected} apiBase={apiBase} onUpdated={updateIncident} />}
    {selected && <IncidentUpdated incident={selected} />}
    <aside className="agent-tower">
      <div className="tower-header"><span className="brand-mark" aria-label="Anton agent"><RadioTower size={19} /></span></div>
      <div className={`agent-card selected ${agentIdle ? "idle" : ""} ${agentDown ? "down" : ""}`} role="status" aria-label={`Anton is ${agentDown ? "down" : agentIdle ? "idle" : "active"}`}><img className="agent-avatar" src="/anton.png" alt="Anton" /><span className={`agent-state-dot ${agentDown ? "down" : agentIdle ? "idle" : "active"}`} /></div>
      <div className="tower-footer" />
    </aside>

    <main className="main-content">
      {statusNotification && <div className="status-toast" role="status"><CircleDot size={14} /> {statusNotification}</div>}
      <header className="console-header compact"><div className="header-readout"><button className={`agent-switch ${agentDown ? "down" : agentIdle ? "idle" : "active"}`} onClick={() => void toggleAgentIdle()} aria-label={agentDown ? "Anton unavailable" : agentIdle ? "Start Anton" : "Set Anton idle"} aria-pressed={agentIdle} disabled={agentDown} title={agentDown ? "Anton unavailable" : agentIdle ? "Start Anton" : "Set Anton idle"}><span className="agent-switch-label">{agentDown ? "DOWN" : agentIdle ? "IDLE" : "ON"}</span><span className="agent-switch-knob" /></button></div></header>
      <nav className="panel-tabs" aria-label="Agent panels">{panels.map(({ label, icon: Icon }) => <button className={activePanel === label ? "active" : ""} key={label} onClick={() => setActivePanel(label)}><Icon size={15} /> {label}{label === "Incidents" && <b>{openCount}</b>}</button>)}</nav>

      {activePanel === "Incidents" ? loading ? <div className="panel-placeholder console-panel"><RefreshCw size={25} className="spin" /><h2>Loading incidents</h2><p>Reading Anton’s operational database.</p></div> : error ? <div className="panel-placeholder console-panel"><XCircle size={25} /><h2>API unavailable</h2><p>{error}</p></div> : <div className="content-grid">
        <section className="incident-list-panel console-panel"><label className="search-box"><Search size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search incidents" /></label><button className="action-button filter-refresh" onClick={() => window.location.reload()}><RefreshCw size={14} /> Refresh</button><div className="incident-filters"><div className="filter-group"><span>Source</span><button className={!sourceFilter ? "active" : ""} onClick={() => setSourceFilter("")}>All <small className="filter-count">{visibleIncidents.length}</small></button><button className={sourceFilter === "alertmanager" ? "active" : ""} onClick={() => setSourceFilter(sourceFilter === "alertmanager" ? "" : "alertmanager")}>Alertmanager <small className="filter-count">{sourceCount("alertmanager")}</small></button><button className={sourceFilter === "gatus" ? "active" : ""} onClick={() => setSourceFilter(sourceFilter === "gatus" ? "" : "gatus")}>Gatus <small className="filter-count">{sourceCount("gatus")}</small></button></div><div className="filter-group"><span>Status</span><button className={!statusFilter ? "active" : ""} onClick={() => setStatusFilter("")}>All <small className="filter-count">{visibleIncidents.length}</small></button>{statusFilters.map((status) => <button className={statusFilter === status ? "active" : ""} key={status} onClick={() => setStatusFilter(statusFilter === status ? "" : status)}>{status.replace("_", " ")} <small className="filter-count">{statusCount(status)}</small></button>)}</div></div><div className="incident-list">{filtered.map((incident) => <button className={`incident-row ${selected && incident.id === selected.id ? "selected" : ""}`} key={incident.id} onClick={() => setSelectedId(incident.id)}><div className="incident-row-icon"><StatusIcon status={incident.status} /></div><div className="incident-row-body"><strong>{incident.title}</strong><span>{incident.source} · {incident.updated}</span></div><ChevronRight size={15} className="row-chevron" /></button>)}</div></section>
        {selected ? <section className="detail-panel console-panel"><div className="detail-heading"><div><h2>{selected.title}</h2><p>{selected.summary}</p></div></div><div className="metric-row"><div><span>STATUS</span><strong>{selected.status}</strong></div><div><span>CONFIDENCE</span><strong className={`level ${selected.confidence}`}>{selected.confidence}</strong></div><div><span>RISK LEVEL</span><strong className={`level ${selected.risk}`}>{selected.risk}</strong></div><div><span>SOURCE</span><strong>{selected.source}</strong></div></div><div className="alert-gadget"><div className="field-grid"><div><span>ALERT</span><strong>{selected.alertname}</strong></div><div><span>STATE</span><strong>{selected.alertStatus}</strong></div><div><span>SOURCE</span><strong>{selected.source}</strong></div><div><span>SEVERITY</span><strong>{selected.severity}</strong></div><div><span>NAMESPACE</span><strong>{selected.namespace || "—"}</strong></div><div><span>POD</span><strong>{selected.pod || "—"}</strong></div><div><span>STARTED</span><strong>{selected.startsAt}</strong></div><div><span>REPLAYED</span><strong>{selected.replayedAt}</strong></div></div></div><IncidentThread incident={selected} />{selected.evidence.length > 0 && <div className="detail-section"><div className="detail-section-title"><Search size={15} /> Investigation evidence</div><ul>{selected.evidence.map((item) => <li key={item}>{item}</li>)}</ul></div>}{selected.files.length > 0 && <div className="detail-section"><div className="detail-section-title"><FileCode2 size={15} /> Proposed files</div>{selected.files.map((file) => <a className="file-chip" href={selected.pullRequestUrl ? `${selected.pullRequestUrl}/files` : `https://github.com/spike442/homelab/blob/main/${file}`} target="_blank" rel="noreferrer" key={file}><FileCode2 size={13} />{file}</a>)}</div>}<div className="action-bar">{selected.actions.includes("replay") && <button className="action-button" onClick={() => void replayIncident(selected)} disabled={selectedActionsDisabled || retryingId === selected.id}><RefreshCw size={15} /> {retryingId === selected.id ? "Replaying" : "Replay"}</button>}{selected.actions.includes("ignore") && <button className="action-button" onClick={() => void ignoreIncident(selected)} disabled={selectedActionsDisabled}><Archive size={15} /> Ignore</button>}{selected.actions.includes("open-pr") && selected.pullRequestUrl && <a className={`action-button primary ${selectedActionsDisabled ? "disabled" : ""}`} href={selectedActionsDisabled ? undefined : selected.pullRequestUrl} aria-disabled={selectedActionsDisabled} onClick={(event) => { if (selectedActionsDisabled) event.preventDefault(); }} target="_blank" rel="noreferrer"><Github size={15} /> Open PR</a>}{selected.actions.includes("delete") && <button className="action-button danger" onClick={() => void deleteIncident(selected)} disabled={selectedActionsDisabled}><Trash2 size={15} /> Delete</button>}</div></section> : <section className="detail-panel console-panel"><div className="panel-placeholder"><ShieldAlert size={25} /><h2>No matching incidents</h2><p>Adjust the search or filters to see an incident.</p></div></section>}
      </div> : activePanel === "Activity" ? <ActivityFeed incidents={incidents} agentEvents={agentEvents} agentName={agentName} /> : <OverviewPanel incidents={incidents} />}
      <footer className="main-footer"><small className="app-version">v{version}</small></footer>
    </main>
  </div>;
}

export default App;

createRoot(document.getElementById("root")!).render(<App />);
