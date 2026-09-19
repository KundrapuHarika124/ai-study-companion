import { useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, post, del } from "../lib/api";
import { Button, Card, Empty, ErrorBox, Field, Loading, PageTitle, MasteryBar, inputCls, eventLabel, fmtRel } from "../components/ui";

export default function SpaceDetail() {
  const { spaceId } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["space", spaceId], queryFn: () => api(`/spaces/${spaceId}`) });
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", learning_goal: "" });
  const create = useMutation({ mutationFn: () => post("/projects", { ...form, space_id: spaceId }), onSuccess: (p: any) => { qc.invalidateQueries({ queryKey: ["space", spaceId] }); nav(`/projects/${p.id}`); } });
  const remove = useMutation({ mutationFn: () => del(`/spaces/${spaceId}`), onSuccess: () => nav("/spaces") });
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} retry={q.refetch} />;
  const { space, projects, activity, attention } = q.data;

  return (
    <>
      <PageTitle title={<span><span className="inline-block h-3 w-3 rounded-full mr-2 align-middle" style={{ background: space.color }} />{space.name}</span>} sub={space.description} action={<div className="flex gap-2"><Button variant="secondary" onClick={() => { if (confirm("Delete this space?")) remove.mutate(); }} disabled={projects.length > 0} title={projects.length ? "Delete its projects first" : ""}>Delete</Button><Button onClick={() => setShow(!show)}>{show ? "Cancel" : "New project"}</Button></div>} />
      {show && (
        <Card className="mb-5">
          <form className="grid gap-3" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
            <Field label="Project name"><input className={inputCls} required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. TCP/IP fundamentals" /></Field>
            <Field label="Description"><input className={inputCls} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
            <Field label="Learning goal"><textarea className={inputCls} rows={2} value={form.learning_goal} onChange={(e) => setForm({ ...form, learning_goal: e.target.value })} placeholder="What do you want to be able to do? The Tutor and quizzes use this." /></Field>
            {create.error && <p className="text-sm text-rust">{(create.error as any).message}</p>}
            <div><Button type="submit" disabled={create.isPending}>{create.isPending ? "Creating…" : "Create project"}</Button></div>
          </form>
        </Card>
      )}
      <div className="grid gap-4 md:grid-cols-[1.4fr_1fr]">
        <div>
          <h2 className="text-lg font-semibold mb-2">Projects</h2>
          {!projects.length ? <Empty title="No projects in this space" body="A project is one focused learning journey with its own materials, Tutor, quizzes and mastery." action={<Button onClick={() => setShow(true)}>Create a project</Button>} /> : (
            <div className="space-y-3">
              {projects.map((p: any) => (
                <Link key={p.id} to={`/projects/${p.id}`} className="block rounded-lg border border-line bg-surface p-4 hover:border-teal">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0"><p className="font-medium text-ink">{p.name}</p><p className="text-sm text-mute line-clamp-1">{p.learning_goal || p.description || "No goal set"}</p></div>
                    <span className="text-sm text-mute tabular-nums shrink-0">{p.mastery.avg == null ? "no evidence" : `${Math.round(p.mastery.avg * 100)}% avg`}</span>
                  </div>
                  <p className="text-xs text-mute mt-2">{p.materials_ready} material{p.materials_ready === 1 ? "" : "s"} ready · {p.mastery.concepts} concept{p.mastery.concepts === 1 ? "" : "s"} assessed · {fmtRel(p.last_activity_at)}</p>
                  {p.recommendation && <p className="text-xs text-teal mt-1">Next: {p.recommendation.title}</p>}
                </Link>
              ))}
            </div>
          )}
        </div>
        <div className="space-y-4">
          <Card title="Needs attention">{attention.length ? attention.map((a: any) => <MasteryBar key={a.project_id + a.concept} value={a.mastery} label={a.concept} sub={a.project} />) : <p className="text-sm text-mute">No weak concepts detected yet.</p>}</Card>
          <Card title="Recent activity">{activity.length ? <ul className="space-y-2 text-sm">{activity.map((e: any) => <li key={e.id} className="flex justify-between gap-2"><span className="text-ink">{eventLabel(e.type)}</span><span className="text-mute shrink-0">{fmtRel(e.created_at)}</span></li>)}</ul> : <p className="text-sm text-mute">No activity yet.</p>}</Card>
        </div>
      </div>
    </>
  );
}
