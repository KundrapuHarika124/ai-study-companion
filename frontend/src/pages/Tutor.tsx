import { useEffect, useRef, useState } from "react";
import { useParams, useSearchParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import { Send, Plus } from "lucide-react";
import { api, post, fetchBlobUrl } from "../lib/api";
import { Button, ErrorBox, Loading, Badge, fmtRel } from "../components/ui";

const ACTIONS: [string, string][] = [["explain_simpler", "Explain simpler"], ["example", "Give an example"], ["hint", "Just a hint"], ["visual", "Show me a visual"], ["summarize", "Summarise so far"], ["test_me", "Test me"]];

export default function Tutor() {
  const { projectId } = useParams();
  const [params, setParams] = useSearchParams();
  const qc = useQueryClient();
  const [convId, setConvId] = useState<string | null>(params.get("c"));
  const [text, setText] = useState(params.get("ask") || "");
  const [pending, setPending] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const convs = useQuery({ queryKey: ["convs", projectId], queryFn: () => api(`/projects/${projectId}/tutor/conversations`) });
  const conv = useQuery({ queryKey: ["conv", projectId, convId], queryFn: () => api(`/projects/${projectId}/tutor/conversations/${convId}`), enabled: !!convId });
  const ask = useMutation({
    mutationFn: (b: { message: string; action?: string }) => post(`/projects/${projectId}/tutor/ask`, { message: b.message, action: b.action || "ask", conversation_id: convId }),
    onMutate: (b) => setPending(b.message),
    onSuccess: (r: any) => { setPending(null); setConvId(r.conversation_id); setParams({ c: r.conversation_id }, { replace: true }); qc.invalidateQueries({ queryKey: ["conv", projectId, r.conversation_id] }); qc.invalidateQueries({ queryKey: ["convs", projectId] }); },
    onError: () => setPending(null),
  });
  const messages: any[] = conv.data?.messages || [];
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth" }); }, [messages.length, pending]);
  const send = (message: string, action?: string) => { if (!message.trim() || ask.isPending) return; setText(""); ask.mutate({ message, action }); };

  return (
    <div className="grid gap-4 md:grid-cols-[200px_1fr] min-h-[70vh]">
      <aside className="md:border-r md:border-line md:pr-3">
        <Button variant="secondary" className="w-full justify-center mb-3" onClick={() => { setConvId(null); setParams({}, { replace: true }); }}><Plus size={14} />New conversation</Button>
        <ul className="space-y-0.5 text-sm max-h-[60vh] overflow-y-auto">
          {(convs.data || []).map((c: any) => <li key={c.id}><button onClick={() => { setConvId(c.id); setParams({ c: c.id }, { replace: true }); }} className={`w-full text-left rounded-md px-2 py-1.5 hover:bg-paper ${c.id === convId ? "bg-teal-soft text-teal" : "text-mute"}`}><span className="block truncate text-ink">{c.title}</span><span className="text-xs">{fmtRel(c.updated_at)}</span></button></li>)}
        </ul>
      </aside>
      <section className="flex flex-col">
        <div className="flex-1 space-y-5 overflow-y-auto pb-4">
          {!convId && !pending && (
            <div className="rounded-lg border border-line bg-surface p-5">
              <h1 className="text-xl font-semibold">Ask about your material</h1>
              <p className="text-sm text-mute mt-1">Answers are grounded in what you uploaded to this project, with page citations. If your material doesn't cover something, the Tutor says so instead of guessing.</p>
              <div className="mt-3 flex flex-wrap gap-2">{["Summarise the key ideas in my material", "What are the most important concepts I should master first?", "Explain the hardest concept with a diagram"].map((s) => <button key={s} onClick={() => send(s)} className="rounded-full border border-line px-3 py-1 text-sm hover:border-teal">{s}</button>)}</div>
            </div>
          )}
          {conv.isLoading && <Loading label="Loading conversation" />}
          {conv.error && <ErrorBox error={conv.error} />}
          {messages.map((m) => <Message key={m.id} m={m} onFollowUp={(s) => send(s)} />)}
          {pending && <><div className="flex justify-end"><div className="max-w-[80%] rounded-lg bg-teal text-white px-4 py-2.5 text-sm">{pending}</div></div><Loading label="Reading your material" /></>}
          {ask.error && <ErrorBox error={ask.error} />}
          <div ref={bottom} />
        </div>
        <div className="sticky bottom-0 bg-paper pt-2">
          {messages.length > 0 && <div className="flex flex-wrap gap-1.5 mb-2">{ACTIONS.map(([a, l]) => <button key={a} disabled={ask.isPending} onClick={() => send(l, a)} className="rounded-full border border-line bg-surface px-2.5 py-1 text-xs text-mute hover:border-teal hover:text-teal disabled:opacity-50">{l}</button>)}</div>}
          <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); send(text); }}>
            <textarea value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(text); } }} rows={2} placeholder="Ask a question about your material…" className="flex-1 rounded-md border border-line bg-surface px-3 py-2 text-sm focus:border-teal resize-none" />
            <Button type="submit" disabled={ask.isPending || !text.trim()} aria-label="Send"><Send size={16} /></Button>
          </form>
        </div>
      </section>
    </div>
  );
}

function Message({ m, onFollowUp }: { m: any; onFollowUp: (s: string) => void }) {
  if (m.role === "user") return <div className="flex justify-end"><div className="max-w-[80%] rounded-lg bg-teal text-white px-4 py-2.5 text-sm whitespace-pre-wrap">{m.content}</div></div>;
  return (
    <div className="max-w-[92%]">
      <div className="rounded-lg border border-line bg-surface px-4 py-3 text-sm prose-answer"><ReactMarkdown>{m.content}</ReactMarkdown></div>
      {m.visual && <Visual v={m.visual} />}
      {m.citations?.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">{m.citations.map((c: any) => <Link key={c.chunk_id} to={`../materials?open=${c.material_id}&page=${c.page}`} relative="path" title={c.snippet} className="rounded-full border border-teal/30 bg-teal-soft px-2.5 py-0.5 text-xs text-teal hover:bg-teal hover:text-white">{c.label}</Link>)}</div>
      )}
      {m.sufficient === false && <div className="mt-2"><Badge tone="amber">Not covered by your material</Badge></div>}
      {m.follow_ups?.length > 0 && <div className="mt-2 flex flex-wrap gap-1.5">{m.follow_ups.map((f: string) => <button key={f} onClick={() => onFollowUp(f)} className="rounded-full border border-line px-2.5 py-0.5 text-xs text-mute hover:border-teal hover:text-teal">{f}</button>)}</div>}
    </div>
  );
}

function Visual({ v }: { v: any }) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => { if (v.source === "material" && v.url) { let u = ""; fetchBlobUrl(v.url.replace(/^\/api/, "")).then((x) => { u = x; setSrc(x); }).catch(() => {}); return () => { if (u) URL.revokeObjectURL(u); }; } }, [v.url, v.source]);
  return (
    <figure className="mt-2 rounded-lg border border-line bg-surface p-3">
      {v.source === "generated" ? <div className="visual-svg" dangerouslySetInnerHTML={{ __html: v.svg }} /> : src ? <img src={src} alt={v.title || "Figure from your material"} className="max-h-96 mx-auto rounded" /> : <p className="text-xs text-mute">Loading figure…</p>}
      <figcaption className="mt-2 text-xs text-mute flex items-center gap-2"><Badge tone={v.source === "generated" ? "amber" : "teal"}>{v.label}</Badge>{v.title && <span className="truncate">{v.title}</span>}{v.page && <span>· page {v.page}</span>}</figcaption>
    </figure>
  );
}
