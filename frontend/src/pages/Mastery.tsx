import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Card, Empty, ErrorBox, Loading, PageTitle, MasteryBar, Badge, LinkButton, fmtRel } from "../components/ui";

export default function Mastery() {
  const { projectId } = useParams();
  const q = useQuery({ queryKey: ["mastery", projectId], queryFn: () => api(`/projects/${projectId}/mastery`) });
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} retry={q.refetch} />;
  const { assessed, unassessed } = q.data;
  return (
    <>
      <PageTitle title="Concept mastery" sub="Estimated from your quiz answers: harder and open-ended evidence counts for more, and each new answer moves the estimate less as evidence accumulates." action={<LinkButton to={`/projects/${projectId}/quiz`}>Take a quiz</LinkButton>} />
      {!assessed.length && !unassessed.length && <Empty title="No concepts yet" body="Concepts appear after a material is processed." />}
      {assessed.length > 0 && (
        <div className="space-y-3">
          {assessed.map((c: any) => (
            <Card key={c.concept}>
              <MasteryBar value={c.mastery} label={c.concept} />
              <div className="flex flex-wrap items-center gap-2 text-xs text-mute">
                <Badge tone={c.trend === "improving" ? "moss" : c.trend === "declining" ? "amber" : "neutral"}>{c.trend}</Badge>
                <span>{c.evidence_count} answer{c.evidence_count === 1 ? "" : "s"}</span><span>· last assessed {fmtRel(c.last_assessed_at)}</span>
                <Link to={`/projects/${projectId}/quiz?concept=${encodeURIComponent(c.concept)}`} className="text-teal">Quiz this</Link>
                <Link to={`/projects/${projectId}/tutor?ask=${encodeURIComponent("Explain " + c.concept)}`} className="text-teal">Ask Tutor</Link>
              </div>
              {c.recent_mistakes.length > 0 && <details className="mt-2 text-xs"><summary className="cursor-pointer text-mute">Recent mistakes ({c.recent_mistakes.length})</summary><ul className="mt-1 list-disc pl-4 text-mute">{c.recent_mistakes.map((m: any, i: number) => <li key={i}>{m.question}</li>)}</ul></details>}
            </Card>
          ))}
        </div>
      )}
      {unassessed.length > 0 && <Card title="Not yet assessed" className="mt-4"><p className="text-sm text-mute mb-2">No evidence yet for these concepts. Mastery is never guessed: take a quiz to measure them.</p><div className="flex flex-wrap gap-2">{unassessed.map((c: string) => <Link key={c} to={`/projects/${projectId}/quiz?concept=${encodeURIComponent(c)}`} className="rounded-full border border-line px-3 py-1 text-sm hover:border-teal">{c}</Link>)}</div></Card>}
    </>
  );
}
