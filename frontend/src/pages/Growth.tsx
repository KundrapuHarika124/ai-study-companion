import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { api } from "../lib/api";
import { Card, Empty, ErrorBox, Loading, PageTitle, Badge, Stat, statusTone, LinkButton } from "../components/ui";

export default function Growth() {
  const { projectId } = useParams();
  const q = useQuery({ queryKey: ["growth", projectId], queryFn: () => api(`/projects/${projectId}/growth?days=30`) });
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} retry={q.refetch} />;
  const d = q.data;
  if (!d.has_evidence) return (<><PageTitle title="Growth" sub="How your understanding changes over time." /><Empty title="Not enough evidence yet" body="Growth needs at least two assessments per concept. Take a quiz now and another one later to see whether you are improving." action={<LinkButton to={`/projects/${projectId}/quiz`}>Take a quiz</LinkButton>} /></>);
  const perf = d.session_performance.map((p: any, i: number) => ({ name: `Quiz ${i + 1}`, score: Math.round(p.avg * 100) }));
  return (
    <>
      <PageTitle title="Growth" sub="Last 30 days. Status is computed from the change in mastery, not from a single score." />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Improving" value={d.counts.improving} /><Stat label="Stable" value={d.counts.stable} /><Stat label="Need attention" value={d.counts.attention} /><Stat label="Insufficient evidence" value={d.counts.insufficient_evidence} />
      </div>
      {perf.length > 1 && (
        <Card title="Quiz performance over time" className="mt-4">
          <div className="h-56"><ResponsiveContainer><LineChart data={perf}><CartesianGrid stroke="#DDE1DE" strokeDasharray="3 3" /><XAxis dataKey="name" tick={{ fontSize: 12 }} /><YAxis domain={[0, 100]} tick={{ fontSize: 12 }} unit="%" /><Tooltip /><Line type="monotone" dataKey="score" stroke="#2F5D62" strokeWidth={2} dot /></LineChart></ResponsiveContainer></div>
        </Card>
      )}
      <div className="mt-4 space-y-3">
        {d.concepts.map((c: any) => (
          <Card key={c.concept}>
            <div className="flex items-center justify-between gap-3">
              <div><p className="font-medium">{c.concept}</p><p className="text-xs text-mute">{c.evidence_count} answers · now {Math.round(c.mastery * 100)}%{c.delta != null ? ` · ${c.delta >= 0 ? "+" : ""}${Math.round(c.delta * 100)} pts in window` : ""}</p></div>
              <Badge tone={statusTone(c.status)}>{c.status.replace("_", " ")}</Badge>
            </div>
            {c.series.length > 1 && <div className="h-20 mt-2"><ResponsiveContainer><LineChart data={c.series.map((s: any) => ({ v: Math.round(s.v * 100), t: new Date(s.t).toLocaleDateString() }))}><YAxis domain={[0, 100]} hide /><XAxis dataKey="t" hide /><Tooltip formatter={(v: any) => `${v}%`} /><Line type="monotone" dataKey="v" stroke={c.status === "attention" ? "#B7791F" : c.status === "improving" ? "#2E7D5B" : "#2F5D62"} strokeWidth={2} dot={false} /></LineChart></ResponsiveContainer></div>}
          </Card>
        ))}
      </div>
    </>
  );
}
