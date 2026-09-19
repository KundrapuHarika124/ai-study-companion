import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { api } from "../lib/api";
import { Card, Empty, ErrorBox, Loading, LinkButton, MasteryBar, Stat, PageTitle, fmtRel } from "../components/ui";
import { useAuth } from "../lib/auth";

export default function Home() {
  const { user } = useAuth();
  const q = useQuery({ queryKey: ["home"], queryFn: () => api("/home") });
  if (q.isLoading) return <Loading label="Loading your workspace" />;
  if (q.error) return <ErrorBox error={q.error} retry={q.refetch} />;
  const d = q.data;
  const cl = d.continue_learning;
  const rec = d.recommendation;
  const recLink = (r: any) => !r ? "" : r.action_type === "quiz" ? `/projects/${r.project_id}/quiz?concept=${encodeURIComponent(r.concept || "")}` : r.action_type === "tutor" ? `/projects/${r.project_id}/tutor?ask=${encodeURIComponent("Explain " + (r.concept || ""))}` : r.action_type === "material" ? `/projects/${r.project_id}/materials${r.material_id ? `?open=${r.material_id}&page=${r.page || 1}` : ""}` : `/projects/${r.project_id}/mastery`;

  if (!d.space_count) {
    return (<><PageTitle title={`Welcome, ${user?.name || "learner"}`} sub="Start by creating a space for what you want to learn." />
      <Empty title="No spaces yet" body="A space groups related projects: a course, a certification, a skill. Create one, add a project inside it, and upload a PDF to begin." action={<LinkButton to="/spaces">Create your first space</LinkButton>} /></>);
  }

  return (
    <>
      <PageTitle title={`Welcome back, ${user?.name || "learner"}`} sub="Where you were, how you are doing, and what to do next." />
      <div className="grid gap-4 md:grid-cols-[1.4fr_1fr]">
        <Card title="Continue learning">
          {cl ? (
            <div>
              <p className="text-xs text-mute">{cl.space_name}</p>
              <Link to={`/projects/${cl.id}`} className="text-lg font-medium text-ink hover:text-teal">{cl.name}</Link>
              <p className="text-sm text-mute mt-1">Last activity {fmtRel(cl.last_activity_at)}{cl.last_activity_type ? ` · ${cl.last_activity_type.replace(/_/g, " ")}` : ""}</p>
              <div className="mt-4 flex flex-wrap gap-2">
                <LinkButton to={`/projects/${cl.id}/tutor${d.last_conversation ? `?c=${d.last_conversation.id}` : ""}`}>{d.last_conversation ? "Resume conversation" : "Open Tutor"}</LinkButton>
                <LinkButton variant="secondary" to={`/projects/${cl.id}/quiz`}>Take a quiz</LinkButton>
              </div>
            </div>
          ) : <Empty title="No project yet" body="Create a project inside a space to start learning." action={<LinkButton to="/spaces">Go to spaces</LinkButton>} />}
        </Card>
        <Card title="Recommended next step">
          {rec ? (
            <div>
              <p className="font-medium text-ink">{rec.title}</p>
              <p className="text-sm text-mute mt-1">{rec.body}</p>
              <Link to={recLink(rec)} className="mt-3 inline-flex items-center gap-1 text-sm text-teal font-medium">Do this now <ArrowRight size={14} /></Link>
            </div>
          ) : <p className="text-sm text-mute">Recommendations appear after your first quiz. Upload material and take a quiz to get a personalised next step.</p>}
        </Card>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
        <Stat label="Concepts tracked" value={d.overall.concepts} />
        <Stat label="Average mastery" value={d.overall.avg == null ? "—" : `${Math.round(d.overall.avg * 100)}%`} hint="across assessed concepts" />
        <Stat label="Need attention" value={d.overall.attention} hint="below 60%" />
        <Stat label="Questions answered" value={d.quiz.answers} hint={d.quiz.avg_score == null ? undefined : `avg score ${Math.round(d.quiz.avg_score * 100)}%`} />
      </div>
      <div className="grid gap-4 md:grid-cols-2 mt-4">
        <Card title="Areas requiring attention">
          {d.attention.length ? d.attention.map((a: any) => <MasteryBar key={a.project_id + a.concept} value={a.mastery} label={a.concept} sub={a.project} />)
            : <p className="text-sm text-mute">Nothing flagged. Weak concepts show up here once you have quiz evidence.</p>}
        </Card>
        <Card title="Recent projects">
          <ul className="divide-y divide-line">
            {d.recent_projects.map((p: any) => (
              <li key={p.id} className="py-2.5 flex items-center justify-between gap-3">
                <div className="min-w-0"><Link to={`/projects/${p.id}`} className="font-medium text-ink hover:text-teal truncate block">{p.name}</Link><p className="text-xs text-mute">{p.space_name} · {fmtRel(p.last_activity_at)}</p></div>
                <span className="text-sm text-mute tabular-nums shrink-0">{p.mastery.avg == null ? "no evidence" : `${Math.round(p.mastery.avg * 100)}%`}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </>
  );
}
