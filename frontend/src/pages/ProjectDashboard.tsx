import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { api, post, del } from "../lib/api";
import { Button, Card, ErrorBox, Loading, LinkButton, MasteryBar, PageTitle, Stat, Badge, statusTone, eventLabel, fmtRel } from "../components/ui";
import { useNavigate } from "react-router-dom";

export function recLink(projectId: string, r: any) {
  if (!r) return `/projects/${projectId}`;
  if (r.action_type === "quiz") return `/projects/${projectId}/quiz?concept=${encodeURIComponent(r.concept || "")}`;
  if (r.action_type === "tutor") return `/projects/${projectId}/tutor?ask=${encodeURIComponent("Explain " + (r.concept || ""))}`;
  if (r.action_type === "material") return `/projects/${projectId}/materials${r.material_id ? `?open=${r.material_id}&page=${r.page || 1}` : ""}`;
  return `/projects/${projectId}/mastery`;
}

export default function ProjectDashboard() {
  const { projectId } = useParams();
  const qc = useQueryClient();
  const nav = useNavigate();
  const q = useQuery({ queryKey: ["project", projectId], queryFn: () => api(`/projects/${projectId}`) });
  const refresh = useMutation({ mutationFn: () => post(`/projects/${projectId}/recommendations/refresh`), onSuccess: () => qc.invalidateQueries({ queryKey: ["project", projectId] }) });
  const remove = useMutation({ mutationFn: () => del(`/projects/${projectId}`), onSuccess: (_: any, __: any) => nav(`/spaces/${q.data?.space?.id || ""}`) });
  if (q.isLoading) return <Loading label="Loading project" />;
  if (q.error) return <ErrorBox error={q.error} retry={q.refetch} />;
  const d = q.data; const p = d.project; const rec = d.recommendation;
  const ready = d.materials.filter((m: any) => m.status === "ready").length;
  const step = !d.materials.length ? "materials" : !ready ? "processing" : !d.mastery_overview.concepts ? "quiz" : "loop";

  return (
    <>
      <PageTitle title={p.name} sub={p.learning_goal ? <span>Goal: {p.learning_goal}</span> : p.description} action={<div className="flex gap-2"><LinkButton to={`/projects/${projectId}/tutor`}>Open Tutor</LinkButton><Button variant="secondary" onClick={() => { if (confirm("Delete this project and all its data?")) remove.mutate(); }}>Delete</Button></div>} />
      {step !== "loop" && (
        <div className="mb-5 rounded-lg border border-teal/30 bg-teal-soft px-4 py-3 text-sm text-teal-deep flex items-center justify-between gap-3">
          <span>{step === "materials" ? "Start by uploading a PDF. The companion will extract concepts and build searchable knowledge." : step === "processing" ? "Your material is being processed. The Tutor and quizzes unlock once it is ready." : "Knowledge is ready. Ask the Tutor, then take a quiz to start measuring mastery."}</span>
          <Link to={`/projects/${projectId}/${step === "quiz" ? "tutor" : "materials"}`} className="font-medium whitespace-nowrap">{step === "quiz" ? "Ask the Tutor" : "Materials"} →</Link>
        </div>
      )}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Materials ready" value={`${ready}/${d.materials.length}`} />
        <Stat label="Concepts" value={d.concepts.length} hint={`${d.mastery_overview.concepts} assessed`} />
        <Stat label="Average mastery" value={d.mastery_overview.avg == null ? "—" : `${Math.round(d.mastery_overview.avg * 100)}%`} />
        <Stat label="Quiz score" value={d.quiz.avg_score == null ? "—" : `${Math.round(d.quiz.avg_score * 100)}%`} hint={`${d.quiz.answers} answers · ${d.quiz.sessions_completed} quizzes`} />
      </div>
      <div className="grid gap-4 md:grid-cols-[1.3fr_1fr] mt-4">
        <div className="space-y-4">
          <Card title="Recommended next step" action={<Button variant="ghost" onClick={() => refresh.mutate()} disabled={refresh.isPending}>{refresh.isPending ? "Thinking…" : "Refresh"}</Button>}>
            {rec ? (<div><p className="font-medium">{rec.title}</p><p className="text-sm text-mute mt-1">{rec.body}</p>{rec.rationale && <p className="text-xs text-mute mt-2">Why: {rec.rationale}</p>}<Link to={recLink(projectId!, rec)} className="mt-3 inline-flex items-center gap-1 text-sm text-teal font-medium">Do this now <ArrowRight size={14} /></Link></div>)
              : <p className="text-sm text-mute">{ready ? "Take a quiz to get an evidence-based recommendation, or press Refresh." : "Available once a material is ready."}</p>}
            {refresh.error && <p className="text-sm text-rust mt-2">{(refresh.error as any).message}</p>}
          </Card>
          <Card title="Concepts" action={<Link to={`/projects/${projectId}/mastery`} className="text-sm text-teal">All mastery</Link>}>
            {d.concepts.length ? d.concepts.slice(0, 8).map((c: any) => <MasteryBar key={c.name} value={c.mastery} label={c.name} />) : <p className="text-sm text-mute">Concepts are extracted from your materials during processing.</p>}
          </Card>
        </div>
        <div className="space-y-4">
          <Card title="Materials" action={<Link to={`/projects/${projectId}/materials`} className="text-sm text-teal">Manage</Link>}>
            {d.materials.length ? <ul className="space-y-2">{d.materials.slice(0, 5).map((m: any) => <li key={m.id} className="flex items-center justify-between gap-2 text-sm"><span className="truncate">{m.title}</span><Badge tone={statusTone(m.status)}>{m.status}</Badge></li>)}</ul> : <p className="text-sm text-mute">No materials yet.</p>}
          </Card>
          <Card title="Recent activity" action={<Link to={`/projects/${projectId}/activity`} className="text-sm text-teal">All</Link>}>
            {d.activity.length ? <ul className="space-y-2 text-sm">{d.activity.slice(0, 8).map((e: any) => <li key={e.id} className="flex justify-between gap-2"><span>{eventLabel(e.type)}{e.payload?.concept ? <span className="text-mute"> · {e.payload.concept}</span> : ""}</span><span className="text-mute shrink-0">{fmtRel(e.created_at)}</span></li>)}</ul> : <p className="text-sm text-mute">Nothing yet.</p>}
          </Card>
        </div>
      </div>
    </>
  );
}
