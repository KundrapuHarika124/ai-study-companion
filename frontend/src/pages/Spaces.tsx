import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, post } from "../lib/api";
import { Button, Card, Empty, ErrorBox, Field, Loading, PageTitle, inputCls } from "../components/ui";

const COLORS = ["#2F5D62", "#2E7D5B", "#B7791F", "#A93F2E", "#4B5FA5", "#7A4E8C"];

export default function Spaces() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["spaces"], queryFn: () => api("/spaces") });
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", color: COLORS[0] });
  const create = useMutation({ mutationFn: () => post("/spaces", form), onSuccess: () => { qc.invalidateQueries({ queryKey: ["spaces"] }); setShow(false); setForm({ name: "", description: "", color: COLORS[0] }); } });

  return (
    <>
      <PageTitle title="Spaces" sub="Broad areas you are learning. Each holds focused projects." action={<Button onClick={() => setShow(!show)}>{show ? "Cancel" : "New space"}</Button>} />
      {show && (
        <Card className="mb-5">
          <form className="grid gap-3 md:grid-cols-2" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
            <Field label="Name"><input className={inputCls} required maxLength={120} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Computer Networks" /></Field>
            <Field label="Colour"><div className="flex gap-2 pt-1">{COLORS.map((c) => <button type="button" key={c} aria-label={c} onClick={() => setForm({ ...form, color: c })} className={`h-7 w-7 rounded-full border-2 ${form.color === c ? "border-ink" : "border-transparent"}`} style={{ background: c }} />)}</div></Field>
            <div className="md:col-span-2"><Field label="Description"><textarea className={inputCls} rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="What this space is for" /></Field></div>
            {create.error && <p className="text-sm text-rust md:col-span-2">{(create.error as any).message}</p>}
            <div className="md:col-span-2"><Button type="submit" disabled={create.isPending}>{create.isPending ? "Creating…" : "Create space"}</Button></div>
          </form>
        </Card>
      )}
      {q.isLoading ? <Loading /> : q.error ? <ErrorBox error={q.error} retry={q.refetch} /> : !q.data.length ? (
        <Empty title="No spaces yet" body="Create a space to organise your learning, then add a project inside it." action={<Button onClick={() => setShow(true)}>Create a space</Button>} />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {q.data.map((s: any) => (
            <Link key={s.id} to={`/spaces/${s.id}`} className="block rounded-lg border border-line bg-surface p-5 hover:border-teal">
              <span className="inline-block h-2 w-8 rounded-full mb-3" style={{ background: s.color }} />
              <p className="font-medium text-ink">{s.name}</p>
              <p className="text-sm text-mute mt-1 line-clamp-2">{s.description || "No description"}</p>
              <p className="text-xs text-mute mt-3">{s.project_count} project{s.project_count === 1 ? "" : "s"}</p>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
