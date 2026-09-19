import { useState } from "react";
import { useParams, useSearchParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, post } from "../lib/api";
import { Button, Card, ErrorBox, Loading, PageTitle, Badge, Field, inputCls, fmtRel, statusTone } from "../components/ui";
import { recLink } from "./ProjectDashboard";

export default function Quiz() {
  const { projectId } = useParams();
  const [params] = useSearchParams();
  const qc = useQueryClient();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [length, setLength] = useState(5);
  const [focus, setFocus] = useState(params.get("concept") || "");
  const [answer, setAnswer] = useState("");
  const [choice, setChoice] = useState<number | null>(null);
  const [result, setResult] = useState<any>(null);
  const project = useQuery({ queryKey: ["project", projectId], queryFn: () => api(`/projects/${projectId}`) });
  const sessions = useQuery({ queryKey: ["quiz-sessions", projectId], queryFn: () => api(`/projects/${projectId}/quiz/sessions`) });
  const session = useQuery({ queryKey: ["quiz", projectId, sessionId], queryFn: () => api(`/projects/${projectId}/quiz/sessions/${sessionId}`), enabled: !!sessionId });
  const start = useMutation({ mutationFn: () => post(`/projects/${projectId}/quiz/start`, { length, focus_concept: focus || null }), onSuccess: (r: any) => { setSessionId(r.session.id); setResult(null); qc.invalidateQueries({ queryKey: ["quiz-sessions", projectId] }); } });
  const submit = useMutation({
    mutationFn: (qid: string) => post(`/projects/${projectId}/quiz/sessions/${sessionId}/answer`, { question_id: qid, answer: session.data.question.type === "mcq" ? String(choice) : answer }),
    onSuccess: (r: any) => { setResult(r); setAnswer(""); setChoice(null); },
  });
  const next = () => { setResult(null); qc.invalidateQueries({ queryKey: ["quiz", projectId, sessionId] }); qc.invalidateQueries({ queryKey: ["project", projectId] }); };

  if (!sessionId) {
    const concepts: any[] = project.data?.concepts || [];
    return (
      <>
        <PageTitle title="Quiz" sub="Adaptive questions chosen from your weakest and least-recently-tested concepts. Open-ended answers are graded on understanding, not keywords." />
        <div className="grid gap-4 md:grid-cols-[1fr_1fr]">
          <Card title="Start a quiz">
            {!concepts.length ? <p className="text-sm text-mute">Upload and process a material first so there are concepts to test.</p> : (
              <div className="space-y-3">
                <Field label="Number of questions"><select className={inputCls} value={length} onChange={(e) => setLength(Number(e.target.value))}>{[3, 5, 8, 10].map((n) => <option key={n} value={n}>{n}</option>)}</select></Field>
                <Field label="Focus (optional)"><select className={inputCls} value={focus} onChange={(e) => setFocus(e.target.value)}><option value="">Let the companion choose</option>{concepts.map((c) => <option key={c.name} value={c.name}>{c.name}{c.mastery != null ? ` (${Math.round(c.mastery * 100)}%)` : ""}</option>)}</select></Field>
                {start.error && <p className="text-sm text-rust">{(start.error as any).message}</p>}
                <Button onClick={() => start.mutate()} disabled={start.isPending}>{start.isPending ? "Preparing first question…" : "Start quiz"}</Button>
              </div>
            )}
          </Card>
          <Card title="Past quizzes">
            {sessions.isLoading ? <Loading /> : !sessions.data?.length ? <p className="text-sm text-mute">No quizzes yet.</p> : <ul className="divide-y divide-line text-sm">{sessions.data.map((s: any) => <li key={s.id} className="py-2 flex items-center justify-between gap-2"><button onClick={() => setSessionId(s.id)} className="text-left hover:text-teal">{fmtRel(s.created_at)} · {s.answered}/{s.length} answered{s.focus_concept ? ` · ${s.focus_concept}` : ""}</button><span className="flex items-center gap-2"><Badge tone={statusTone(s.status)}>{s.status}</Badge><span className="tabular-nums text-mute">{s.answered ? `${Math.round((s.score_sum / s.answered) * 100)}%` : ""}</span></span></li>)}</ul>}
          </Card>
        </div>
      </>
    );
  }

  if (session.isLoading) return <Loading label="Loading quiz" />;
  if (session.error) return <ErrorBox error={session.error} retry={session.refetch} />;
  const d = session.data;

  if (d.status === "completed") {
    const s = d.session; const rec = d.recommendation;
    return (
      <>
        <PageTitle title="Quiz complete" sub={`${s.answered} questions · average score ${Math.round(s.avg_score * 100)}%`} action={<div className="flex gap-2"><Button variant="secondary" onClick={() => setSessionId(null)}>Back</Button><Button onClick={() => start.mutate()}>Another quiz</Button></div>} />
        <div className="grid gap-4 md:grid-cols-2">
          <Card title="By concept">{d.by_concept.map((c: any) => <div key={c.concept} className="flex justify-between py-1.5 text-sm border-b border-line last:border-0"><span>{c.concept}</span><span className="tabular-nums text-mute">{Math.round(c.avg * 100)}% · {c.count} q</span></div>)}</Card>
          <Card title="What to do next">{rec ? <><p className="font-medium">{rec.title}</p><p className="text-sm text-mute mt-1">{rec.body}</p><Link to={recLink(projectId!, rec)} className="text-sm text-teal font-medium mt-2 inline-block">Do this now →</Link></> : <p className="text-sm text-mute">Your recommendation is being generated in the background. <button className="text-teal" onClick={() => session.refetch()}>Refresh</button></p>}</Card>
        </div>
        <Card title="Review" className="mt-4">
          <ol className="space-y-4">{d.answers.map((a: any, i: number) => <li key={a.question_id} className="text-sm"><p className="text-xs text-mute">{i + 1}. {a.concept} · {a.type}</p><p className="font-medium mt-0.5">{a.question}</p>{a.answer && <p className="text-xs text-mute mt-0.5">Your answer: {a.type === "mcq" ? "option " + (Number(a.answer) + 1) : a.answer}</p>}<Feedback r={a} /></li>)}</ol>
        </Card>
      </>
    );
  }

  const q = result ? null : d.question;
  const s = result ? result.session : d.session;
  return (
    <>
      <PageTitle title={`Question ${Math.min(s.answered + 1, s.length)} of ${s.length}`} sub={<span className="flex items-center gap-2"><Badge tone="teal">{(q || result?.result)?.concept}</Badge><Badge>{(q?.difficulty) || ""}</Badge>{q?.selection_reason && <span className="text-xs">{q.selection_reason}</span>}</span>} action={<Button variant="ghost" onClick={() => setSessionId(null)}>Exit</Button>} />
      <div className="h-1 w-full rounded-full bg-line mb-5"><div className="h-full rounded-full bg-teal" style={{ width: `${(s.answered / s.length) * 100}%` }} /></div>
      {q && (
        <Card>
          <p className="text-base font-medium whitespace-pre-wrap">{q.question}</p>
          {q.type === "mcq" ? (
            <div className="mt-4 space-y-2">{q.options.map((o: string, i: number) => <label key={i} className={`flex items-start gap-3 rounded-md border p-3 text-sm cursor-pointer ${choice === i ? "border-teal bg-teal-soft" : "border-line hover:border-teal/50"}`}><input type="radio" name="opt" checked={choice === i} onChange={() => setChoice(i)} className="mt-0.5" /><span>{o}</span></label>)}</div>
          ) : (
            <textarea className={`${inputCls} mt-4`} rows={5} value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder="Explain in your own words. Partial answers still earn credit." />
          )}
          {submit.error && <p className="text-sm text-rust mt-2">{(submit.error as any).message}</p>}
          <div className="mt-4 flex items-center gap-3"><Button onClick={() => submit.mutate(q.id)} disabled={submit.isPending || (q.type === "mcq" ? choice === null : answer.trim().length < 1)}>{submit.isPending ? "Grading…" : "Submit answer"}</Button>{q.sources?.length > 0 && <span className="text-xs text-mute">Based on {q.sources.map((x: any) => x.label).join("; ")}</span>}</div>
        </Card>
      )}
      {result && (
        <Card>
          <Feedback r={result.result} />
          {result.result.mastery_impact && <p className="mt-3 text-xs text-mute">Mastery of {result.result.mastery_impact.concept}: {result.result.mastery_impact.previous == null ? "first evidence" : `${Math.round(result.result.mastery_impact.previous * 100)}%`} → {Math.round(result.result.mastery_impact.mastery * 100)}%</p>}
          <div className="mt-4"><Button onClick={next}>{result.next_question || result.session.status !== "completed" ? "Next question" : "See results"}</Button></div>
        </Card>
      )}
    </>
  );
}

function Feedback({ r }: { r: any }) {
  const g = r.grade || {};
  const pct = Math.round(r.score * 100);
  return (
    <div className="mt-2">
      <div className="flex items-center gap-2"><Badge tone={r.score >= 0.7 ? "moss" : r.score >= 0.4 ? "amber" : "rust"}>{r.type === "mcq" ? (r.score ? "Correct" : "Incorrect") : `Score ${pct}%`}</Badge></div>
      {g.feedback && <p className="text-sm mt-2">{g.feedback}</p>}
      {r.type === "open" && (
        <div className="mt-2 grid gap-2 sm:grid-cols-3 text-xs">
          {g.correct?.length > 0 && <div className="rounded-md bg-moss-soft p-2"><p className="font-medium text-moss">You covered</p><ul className="mt-1 list-disc pl-4">{g.correct.map((x: string) => <li key={x}>{x}</li>)}</ul></div>}
          {g.missing?.length > 0 && <div className="rounded-md bg-amber-soft p-2"><p className="font-medium text-amber">Missing</p><ul className="mt-1 list-disc pl-4">{g.missing.map((x: string) => <li key={x}>{x}</li>)}</ul></div>}
          {g.incorrect?.length > 0 && <div className="rounded-md bg-rust-soft p-2"><p className="font-medium text-rust">Incorrect</p><ul className="mt-1 list-disc pl-4">{g.incorrect.map((x: string) => <li key={x}>{x}</li>)}</ul></div>}
        </div>
      )}
      {r.type === "open" && r.reference_answer && <details className="mt-2 text-xs text-mute"><summary className="cursor-pointer">Reference answer</summary><p className="mt-1">{r.reference_answer}</p></details>}
    </div>
  );
}
