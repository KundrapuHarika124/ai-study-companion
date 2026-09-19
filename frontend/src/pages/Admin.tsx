import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { api, post } from "../lib/api";
import { Button, Card, ErrorBox, Loading, PageTitle, Stat, Badge, statusTone, eventLabel, fmtDate, inputCls } from "../components/ui";

const TABS = ["Overview", "Users", "Activity", "AI runs", "Jobs", "Evaluations", "Health"] as const;

export default function Admin() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Overview");
  return (
    <>
      <PageTitle title="Admin" sub="Platform-level visibility. Access is enforced by the API for admin accounts only." />
      <div className="flex flex-wrap gap-1 border-b border-line mb-5">{TABS.map((t) => <button key={t} onClick={() => setTab(t)} className={`px-3 py-2 text-sm -mb-px border-b-2 ${tab === t ? "border-teal text-teal font-medium" : "border-transparent text-mute hover:text-ink"}`}>{t}</button>)}</div>
      {tab === "Overview" && <Overview />}{tab === "Users" && <Users />}{tab === "Activity" && <ActivityTab />}{tab === "AI runs" && <AIRuns />}{tab === "Jobs" && <Jobs />}{tab === "Evaluations" && <Evals />}{tab === "Health" && <Health />}
    </>
  );
}

function useAdmin(key: string, path: string) { return useQuery({ queryKey: ["admin", key, path], queryFn: () => api(path) }); }

function Overview() {
  const q = useAdmin("overview", "/admin/overview");
  if (q.isLoading) return <Loading />; if (q.error) return <ErrorBox error={q.error} />;
  const d = q.data;
  return (
    <>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Users" value={d.users} hint={`${d.active_users} active in 30d`} /><Stat label="Projects" value={d.projects} hint={`${d.spaces} spaces`} /><Stat label="Materials" value={d.materials} hint={`${d.materials_failed} failed`} /><Stat label="Quiz answers (30d)" value={d.quiz_answers} hint={`${d.tutor_messages} tutor replies`} />
        <Stat label="AI runs (30d)" value={d.ai.total_runs} hint={`$${d.ai.total_cost_usd.toFixed(4)} · ${d.ai.failures} failed`} /><Stat label="Avg mastery" value={d.mastery.avg == null ? "—" : `${Math.round(d.mastery.avg * 100)}%`} hint={`${d.mastery.concepts} concept rows`} /><Stat label="Jobs failed" value={d.jobs.failed} hint={`${d.jobs.queued + d.jobs.processing + d.jobs.retrying} in flight`} />
      </div>
      <div className="grid gap-4 md:grid-cols-2 mt-4">
        <Card title="Platform activity (30d)"><div className="h-48"><ResponsiveContainer><BarChart data={d.activity_by_day.map((x: any) => ({ day: x.day.slice(5), count: x.count }))}><XAxis dataKey="day" tick={{ fontSize: 11 }} /><YAxis allowDecimals={false} tick={{ fontSize: 11 }} /><Tooltip /><Bar dataKey="count" fill="#2F5D62" /></BarChart></ResponsiveContainer></div></Card>
        <Card title="Events by type"><ul className="text-sm divide-y divide-line">{d.events_by_type.map((e: any) => <li key={e.type} className="flex justify-between py-1.5"><span>{eventLabel(e.type)}</span><span className="text-mute tabular-nums">{e.count}</span></li>)}</ul></Card>
        <Card title="AI by feature" className="md:col-span-2"><Table rows={d.ai.by_feature} cols={[["feature", "Feature"], ["runs", "Runs"], ["avg_latency_ms", "Avg ms"], ["failures", "Failures"], ["input_tokens", "In tokens"], ["output_tokens", "Out tokens"], ["cost_usd", "Cost $"]]} /></Card>
      </div>
    </>
  );
}

function Users() {
  const [qs, setQs] = useState(""); const [sel, setSel] = useState<string | null>(null);
  const q = useAdmin("users", `/admin/users${qs ? `?q=${encodeURIComponent(qs)}` : ""}`);
  const detail = useQuery({ queryKey: ["admin", "user", sel], queryFn: () => api(`/admin/users/${sel}`), enabled: !!sel });
  return (
    <div className="grid gap-4 md:grid-cols-[1fr_1.3fr]">
      <Card title="Users" action={<input className={inputCls} placeholder="Search email" value={qs} onChange={(e) => setQs(e.target.value)} style={{ width: 160 }} />}>
        {q.isLoading ? <Loading /> : q.error ? <ErrorBox error={q.error} /> : <ul className="divide-y divide-line text-sm">{q.data.map((u: any) => <li key={u.id}><button onClick={() => setSel(u.id)} className={`w-full text-left py-2 ${sel === u.id ? "text-teal" : ""}`}><span className="font-medium">{u.email}</span>{u.is_admin && <Badge tone="teal">admin</Badge>}<p className="text-xs text-mute">{u.projects} projects · {u.events} events · seen {fmtDate(u.last_seen_at)}</p></button></li>)}</ul>}
      </Card>
      <Card title="Learning journey">
        {!sel ? <p className="text-sm text-mute">Select a user.</p> : detail.isLoading ? <Loading /> : detail.error ? <ErrorBox error={detail.error} /> : (
          <div className="space-y-4 text-sm">
            <div><p className="font-medium">{detail.data.user?.email}</p><p className="text-xs text-mute">{detail.data.spaces.length} spaces · AI cost 90d ${detail.data.ai.total_cost_usd.toFixed(4)}</p></div>
            <div><p className="font-medium mb-1">Projects</p>{detail.data.projects.map((p: any) => <p key={p.id} className="text-xs py-1 border-b border-line">{p.name} · {p.materials} materials · {p.quiz.answers} answers · mastery {p.mastery.avg == null ? "—" : Math.round(p.mastery.avg * 100) + "%"}</p>)}</div>
            <div><p className="font-medium mb-1">Recent recommendations</p>{detail.data.recommendations.map((r: any) => <p key={r.id} className="text-xs py-1 border-b border-line">{r.title} <span className="text-mute">({r.trigger})</span></p>)}</div>
            <div><p className="font-medium mb-1">Recent activity</p>{detail.data.activity.slice(0, 20).map((e: any) => <p key={e.id} className="text-xs py-1 border-b border-line flex justify-between"><span>{eventLabel(e.type)}</span><span className="text-mute">{fmtDate(e.created_at)}</span></p>)}</div>
          </div>
        )}
      </Card>
    </div>
  );
}

function ActivityTab() {
  const [f, setF] = useState({ user_id: "", project_id: "", type: "", days: 30 });
  const qs = Object.entries(f).filter(([, v]) => v).map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join("&");
  const q = useAdmin("activity", `/admin/activity?${qs}`);
  return (
    <Card title="Activity" action={<div className="flex gap-2 flex-wrap"><input className={inputCls} placeholder="user id" value={f.user_id} onChange={(e) => setF({ ...f, user_id: e.target.value })} style={{ width: 130 }} /><input className={inputCls} placeholder="project id" value={f.project_id} onChange={(e) => setF({ ...f, project_id: e.target.value })} style={{ width: 130 }} /><input className={inputCls} placeholder="type" value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })} style={{ width: 130 }} /><select className={inputCls} value={f.days} onChange={(e) => setF({ ...f, days: Number(e.target.value) })}>{[1, 7, 30, 90].map((d) => <option key={d} value={d}>{d}d</option>)}</select></div>}>
      {q.isLoading ? <Loading /> : q.error ? <ErrorBox error={q.error} /> : <Table rows={q.data.map((e: any) => ({ ...e, when: fmtDate(e.created_at), what: eventLabel(e.type), detail: JSON.stringify(e.payload).slice(0, 80) }))} cols={[["when", "When"], ["user_id", "User"], ["project_id", "Project"], ["what", "Event"], ["detail", "Payload"]]} />}
    </Card>
  );
}

function AIRuns() {
  const [failed, setFailed] = useState(false);
  const q = useAdmin("ai", `/admin/ai-runs?failed=${failed}`);
  if (q.isLoading) return <Loading />; if (q.error) return <ErrorBox error={q.error} />;
  const d = q.data;
  return (
    <div className="space-y-4">
      <Card title="Recent AI runs" action={<label className="text-sm flex items-center gap-2"><input type="checkbox" checked={failed} onChange={(e) => setFailed(e.target.checked)} /> failed only</label>}>
        <Table rows={d.runs.map((r: any) => ({ ...r, when: fmtDate(r.created_at), ok: r.success ? "ok" : r.error }))} cols={[["when", "When"], ["feature", "Feature"], ["model", "Model"], ["latency_ms", "ms"], ["input_tokens", "In"], ["output_tokens", "Out"], ["estimated_cost_usd", "$"], ["retrieval_count", "Chunks"], ["attempts", "Tries"], ["ok", "Result"]]} />
      </Card>
      <Card title="Slowest successful runs"><Table rows={d.slowest.map((r: any) => ({ ...r, when: fmtDate(r.created_at) }))} cols={[["when", "When"], ["feature", "Feature"], ["latency_ms", "ms"], ["user_id", "User"]]} /></Card>
    </div>
  );
}

function Jobs() {
  const qc = useQueryClient();
  const [status, setStatus] = useState("");
  const q = useAdmin("jobs", `/admin/jobs${status ? `?status=${status}` : ""}`);
  const retry = useMutation({ mutationFn: (id: string) => post(`/admin/jobs/${id}/retry`), onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "jobs"] }) });
  return (
    <Card title="Background jobs" action={<select className={inputCls} value={status} onChange={(e) => setStatus(e.target.value)}><option value="">all</option>{["queued", "processing", "retrying", "completed", "failed"].map((s) => <option key={s}>{s}</option>)}</select>}>
      {q.isLoading ? <Loading /> : q.error ? <ErrorBox error={q.error} /> : <ul className="divide-y divide-line text-sm">{q.data.map((j: any) => <li key={j.id} className="py-2 flex flex-wrap items-center justify-between gap-2"><div><span className="font-medium">{j.type}</span> <Badge tone={statusTone(j.status)}>{j.status}</Badge><p className="text-xs text-mute">{j.idempotency_key} · attempts {j.attempts}/{j.max_attempts} · {fmtDate(j.updated_at)}</p>{j.error && <p className="text-xs text-rust">{j.error}</p>}</div>{j.status === "failed" && <Button variant="secondary" onClick={() => retry.mutate(j.id)}>Retry</Button>}</li>)}</ul>}
    </Card>
  );
}

function Evals() {
  const q = useAdmin("evals", "/admin/evaluations");
  if (q.isLoading) return <Loading />; if (q.error) return <ErrorBox error={q.error} />;
  if (!q.data.length) return <Card title="Evaluations"><p className="text-sm text-mute">No evaluation runs stored yet. Run <code>python -m evals.run_evals evals/cases.json</code> in the backend to record one.</p></Card>;
  return <div className="space-y-4">{q.data.map((e: any) => <Card key={e.id} title={`${e.suite} · ${e.passed}/${e.total} passed · ${fmtDate(e.created_at)}`}><p className="text-xs text-mute mb-2">model {e.model} · embeddings {e.embedding_model} · min score {e.min_score}</p><ul className="text-sm divide-y divide-line">{e.results.map((r: any) => <li key={r.id} className="py-1.5"><Badge tone={r.passed ? "moss" : "rust"}>{r.passed ? "pass" : "fail"}</Badge> <span className="font-medium">{r.id}</span> <span className="text-mute text-xs">{r.latency_ms} ms · sufficient={String(r.sufficient)} · citations={r.citations}{r.visual ? ` · visual=${r.visual}` : ""}</span>{r.notes?.length > 0 && <p className="text-xs text-rust">{r.notes.join("; ")}</p>}<p className="text-xs text-mute">{r.answer_preview}</p></li>)}</ul></Card>)}</div>;
}

function Health() {
  const q = useAdmin("health", "/admin/health");
  if (q.isLoading) return <Loading />; if (q.error) return <ErrorBox error={q.error} />;
  const d = q.data; const ok = (v: any) => v === true ? "moss" : v === false ? "rust" : "neutral";
  return <Card title="System health"><ul className="text-sm space-y-2">{[["MongoDB", d.mongo], ["Qdrant", d.qdrant], ["Redis", d.redis == null ? "not used (inline jobs)" : d.redis], ["AI configured", d.ai_configured]].map(([k, v]: any) => <li key={k} className="flex justify-between"><span>{k}</span><Badge tone={ok(v)}>{String(v)}</Badge></li>)}<li className="flex justify-between"><span>Job backend</span><span>{d.job_backend}</span></li><li className="flex justify-between"><span>Model</span><span>{d.model}</span></li><li className="flex justify-between"><span>Auth mode</span><span>{d.auth_mode}</span></li><li className="flex justify-between"><span>Stuck jobs</span><span>{d.stuck_jobs}</span></li></ul></Card>;
}

function Table({ rows, cols }: { rows: any[]; cols: [string, string][] }) {
  if (!rows.length) return <p className="text-sm text-mute">Nothing to show.</p>;
  return <div className="overflow-x-auto"><table className="w-full text-xs"><thead><tr className="text-left text-mute border-b border-line">{cols.map(([k, l]) => <th key={k} className="py-1.5 pr-3 font-medium">{l}</th>)}</tr></thead><tbody>{rows.map((r, i) => <tr key={r.id || i} className="border-b border-line last:border-0">{cols.map(([k]) => <td key={k} className="py-1.5 pr-3 align-top max-w-[240px] truncate" title={String(r[k] ?? "")}>{fmtCell(r[k], k)}</td>)}</tr>)}</tbody></table></div>;
}

function fmtCell(v: any, k: string): string {
  if (typeof v === "number" && k.includes("cost")) return v.toFixed(5);
  return v == null ? "" : String(v);
}
