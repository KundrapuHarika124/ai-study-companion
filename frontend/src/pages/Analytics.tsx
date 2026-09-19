import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { api } from "../lib/api";
import { Card, ErrorBox, Loading, PageTitle, Stat, eventLabel } from "../components/ui";

export default function Analytics() {
  const { projectId } = useParams();
  const isGlobal = !projectId;
  const q = useQuery({ queryKey: ["analytics", projectId || "global"], queryFn: () => api(isGlobal ? "/analytics/global" : `/projects/${projectId}/analytics`) });
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} retry={q.refetch} />;
  const d = q.data;
  const days = d.activity_by_day.map((x: any) => ({ day: x.day.slice(5), count: x.count }));
  return (
    <>
      <PageTitle title={isGlobal ? "Your learning analytics" : "Project analytics"} sub={isGlobal ? "Everything across all spaces and projects, computed from your real activity." : "Activity, assessment and AI usage for this project."} />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {isGlobal && <Stat label="Projects" value={d.projects} hint={`${d.spaces} spaces · ${d.materials_ready} materials ready`} />}
        <Stat label="Concepts assessed" value={d.mastery.concepts} hint={d.mastery.avg == null ? "no evidence yet" : `avg ${Math.round(d.mastery.avg * 100)}%`} />
        <Stat label="Questions answered" value={d.quiz.answers} hint={`${d.quiz.sessions_completed} quizzes completed`} />
        <Stat label="Average score" value={d.quiz.avg_score == null ? "—" : `${Math.round(d.quiz.avg_score * 100)}%`} />
        <Stat label="AI requests (30d)" value={d.ai.total_runs} hint={`≈ $${d.ai.total_cost_usd.toFixed(4)} · ${d.ai.failures} failed`} />
      </div>
      <div className="grid gap-4 md:grid-cols-2 mt-4">
        <Card title="Activity, last 30 days">{days.length ? <div className="h-48"><ResponsiveContainer><BarChart data={days}><CartesianGrid stroke="#DDE1DE" strokeDasharray="3 3" /><XAxis dataKey="day" tick={{ fontSize: 11 }} /><YAxis allowDecimals={false} tick={{ fontSize: 11 }} /><Tooltip /><Bar dataKey="count" fill="#2F5D62" radius={[3, 3, 0, 0]} /></BarChart></ResponsiveContainer></div> : <p className="text-sm text-mute">No activity in the last 30 days.</p>}</Card>
        <Card title="What you did">{d.events_by_type.length ? <ul className="text-sm divide-y divide-line">{d.events_by_type.map((e: any) => <li key={e.type} className="flex justify-between py-1.5"><span>{eventLabel(e.type)}</span><span className="tabular-nums text-mute">{e.count}</span></li>)}</ul> : <p className="text-sm text-mute">Nothing recorded yet.</p>}</Card>
        <Card title="Score by difficulty">{d.quiz.by_difficulty.length ? <ul className="text-sm divide-y divide-line">{d.quiz.by_difficulty.map((x: any) => <li key={x.difficulty} className="flex justify-between py-1.5"><span className="capitalize">{x.difficulty}</span><span className="tabular-nums text-mute">{Math.round(x.avg * 100)}% · {x.n} q</span></li>)}</ul> : <p className="text-sm text-mute">Take a quiz to see this.</p>}</Card>
        <Card title="AI usage by feature">{d.ai.by_feature.length ? <ul className="text-sm divide-y divide-line">{d.ai.by_feature.map((x: any) => <li key={x.feature} className="flex justify-between py-1.5"><span>{x.feature}</span><span className="tabular-nums text-mute">{x.runs} runs · {x.avg_latency_ms} ms · ${x.cost_usd.toFixed(4)}</span></li>)}</ul> : <p className="text-sm text-mute">No AI requests yet.</p>}</Card>
      </div>
      {isGlobal && d.per_project.length > 0 && <Card title="By project" className="mt-4"><ul className="text-sm divide-y divide-line">{d.per_project.map((p: any) => <li key={p.project_id} className="flex justify-between py-2 gap-2"><Link to={`/projects/${p.project_id}`} className="hover:text-teal">{p.name}</Link><span className="text-mute tabular-nums">{p.mastery.avg == null ? "no evidence" : `${Math.round(p.mastery.avg * 100)}% mastery`} · {p.quiz.answers} answers</span></li>)}</ul></Card>}
    </>
  );
}
