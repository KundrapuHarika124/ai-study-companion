import { useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Upload, RefreshCw, Trash2, FileText } from "lucide-react";
import { api, upload, post, del, fetchBlobUrl } from "../lib/api";
import { Button, Card, Empty, ErrorBox, Loading, PageTitle, Badge, statusTone, fmtDate } from "../components/ui";

export default function Materials() {
  const { projectId } = useParams();
  const [params] = useSearchParams();
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState<string | null>(params.get("open"));
  const [uploadErr, setUploadErr] = useState("");
  const q = useQuery({ queryKey: ["materials", projectId], queryFn: () => api(`/projects/${projectId}/materials`),
    refetchInterval: (query) => (query.state.data as any[])?.some((m) => m.status === "queued" || m.status === "processing") ? 2500 : false });
  const up = useMutation({ mutationFn: (f: File) => upload(`/projects/${projectId}/materials`, f), onSuccess: () => { setUploadErr(""); qc.invalidateQueries({ queryKey: ["materials", projectId] }); qc.invalidateQueries({ queryKey: ["project", projectId] }); }, onError: (e: any) => setUploadErr(e.message) });
  const retry = useMutation({ mutationFn: (id: string) => post(`/materials/${id}/retry`), onSuccess: () => qc.invalidateQueries({ queryKey: ["materials", projectId] }) });
  const remove = useMutation({ mutationFn: (id: string) => del(`/materials/${id}`), onSuccess: () => { setOpen(null); qc.invalidateQueries({ queryKey: ["materials", projectId] }); qc.invalidateQueries({ queryKey: ["project", projectId] }); } });

  return (
    <>
      <PageTitle title="Materials" sub="PDFs are processed in the background: text and figures are extracted, concepts identified, and searchable knowledge built." action={<><input ref={fileRef} type="file" accept="application/pdf" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) up.mutate(f); e.target.value = ""; }} /><Button onClick={() => fileRef.current?.click()} disabled={up.isPending}><Upload size={15} />{up.isPending ? "Uploading…" : "Upload PDF"}</Button></>} />
      {uploadErr && <p role="alert" className="mb-4 text-sm text-rust">{uploadErr}</p>}
      {q.isLoading ? <Loading /> : q.error ? <ErrorBox error={q.error} retry={q.refetch} /> : !q.data.length ? (
        <Empty title="No materials yet" body="Upload any PDF: lecture notes, a textbook chapter, a paper. Scanned pages are OCR'd when Tesseract is installed." action={<Button onClick={() => fileRef.current?.click()}>Upload a PDF</Button>} />
      ) : (
        <div className="space-y-3">
          {q.data.map((m: any) => (
            <div key={m.id} className="rounded-lg border border-line bg-surface p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-3 min-w-0"><FileText size={18} className="text-mute mt-0.5 shrink-0" /><div className="min-w-0"><p className="font-medium truncate">{m.title}</p><p className="text-xs text-mute">{(m.size_bytes / 1024 / 1024).toFixed(1)} MB · uploaded {fmtDate(m.created_at)}{m.page_count ? ` · ${m.page_count} pages` : ""}{m.chunk_count ? ` · ${m.chunk_count} chunks` : ""}{m.visual_count ? ` · ${m.visual_count} figures` : ""}{m.ocr_pages ? ` · ${m.ocr_pages} OCR pages` : ""}</p></div></div>
                <Badge tone={statusTone(m.status)}>{m.status === "processing" ? "processing…" : m.status}</Badge>
              </div>
              {m.status === "failed" && <div className="mt-3 rounded-md bg-rust-soft p-3 text-sm text-rust"><p className="font-medium">Processing failed</p><p>{m.error}</p><Button variant="secondary" className="mt-2" onClick={() => retry.mutate(m.id)}><RefreshCw size={14} />Retry processing</Button></div>}
              {m.status === "ready" && m.concepts?.length > 0 && <p className="mt-2 text-xs text-mute">Concepts: {m.concepts.join(", ")}</p>}
              <div className="mt-3 flex gap-2">
                {m.status === "ready" && <Button variant="secondary" onClick={() => setOpen(open === m.id ? null : m.id)}>{open === m.id ? "Hide" : "Inspect"}</Button>}
                <Button variant="ghost" onClick={() => { if (confirm("Delete this material and its knowledge?")) remove.mutate(m.id); }}><Trash2 size={14} />Delete</Button>
              </div>
              {open === m.id && <Inspect id={m.id} page={Number(params.get("page") || 0)} />}
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function Inspect({ id, page }: { id: string; page: number }) {
  const q = useQuery({ queryKey: ["material", id], queryFn: () => api(`/materials/${id}`) });
  const [pdf, setPdf] = useState<string | null>(null);
  useEffect(() => { let url = ""; fetchBlobUrl(`/materials/${id}/file`).then((u) => { url = u; setPdf(u); }).catch(() => {}); return () => { if (url) URL.revokeObjectURL(url); }; }, [id]);
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} />;
  const { chunks, visuals, job } = q.data;
  const pages = Array.from(new Set(chunks.map((c: any) => c.page))) as number[];
  return (
    <div className="mt-4 grid gap-4 lg:grid-cols-2">
      <Card title="What was extracted">
        <p className="text-xs text-mute mb-2">{chunks.length} chunks across {pages.length} pages · {visuals.length} figures · job {job?.status}{job?.attempts > 1 ? ` (attempt ${job.attempts})` : ""}</p>
        <div className="max-h-96 overflow-y-auto space-y-2 pr-1">
          {chunks.slice(0, 60).map((c: any) => <div key={c.chunk_id} className={`rounded-md border p-2 text-xs ${c.page === page ? "border-teal bg-teal-soft" : "border-line"}`}><p className="text-mute">Page {c.page}{c.heading ? ` · ${c.heading}` : ""}{c.concepts.length ? ` · ${c.concepts.join(", ")}` : ""}</p><p className="mt-1 line-clamp-3">{c.text}</p></div>)}
        </div>
      </Card>
      <Card title="Source">
        {pdf ? <iframe title="PDF" src={`${pdf}#page=${page || 1}`} className="w-full h-96 rounded-md border border-line" /> : <p className="text-sm text-mute">Loading PDF…</p>}
      </Card>
    </div>
  );
}
