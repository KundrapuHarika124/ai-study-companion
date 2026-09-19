import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Card, Empty, ErrorBox, Loading, PageTitle, eventLabel, fmtDate, inputCls } from "../components/ui";

const TYPES = ["", "material_uploaded", "material_processed", "material_failed", "tutor_interaction", "quiz_started", "question_answered", "assessment_completed", "mastery_updated", "recommendation_generated", "repeated_mistake_detected"];

export default function Activity() {
  const { projectId } = useParams();
  const [type, setType] = useState("");
  const q = useQuery({ queryKey: ["activity", projectId || "all", type], queryFn: () => api(projectId ? `/projects/${projectId}/activity?limit=100` : `/activity?limit=100${type ? `&type=${type}` : ""}`) });
  const rows: any[] = (q.data || []).filter((e: any) => !type || e.type === type);
  return (
    <>
      <PageTitle title="Activity" sub="A complete record of what happened, in order." action={<select className={inputCls} value={type} onChange={(e) => setType(e.target.value)}>{TYPES.map((t) => <option key={t} value={t}>{t ? eventLabel(t) : "All events"}</option>)}</select>} />
      {q.isLoading ? <Loading /> : q.error ? <ErrorBox error={q.error} retry={q.refetch} /> : !rows.length ? <Empty title="No activity yet" body="Upload material, ask the Tutor or take a quiz and it will show up here." /> : (
        <Card><ol className="divide-y divide-line">{rows.map((e) => <li key={e.id} className="py-2.5 text-sm flex flex-wrap justify-between gap-2"><div><p>{eventLabel(e.type)}</p><p className="text-xs text-mute">{describe(e)}</p></div><span className="text-xs text-mute">{fmtDate(e.created_at)}</span></li>)}</ol></Card>
      )}
    </>
  );
}

function describe(e: any): string {
  const p = e.payload || {};
  if (p.filename) return p.filename + (p.error ? ` — ${p.error}` : "");
  if (e.type === "question_answered") return `${p.concept} · ${p.type} · ${p.difficulty} · ${p.score >= 0.7 ? "correct" : p.score >= 0.4 ? "partial" : "incorrect"}`;
  if (e.type === "mastery_updated") return `${p.concept}: ${p.from == null ? "first evidence" : Math.round(p.from * 100) + "%"} → ${Math.round(p.to * 100)}%`;
  if (e.type === "assessment_completed") return `${p.questions} questions, average ${Math.round(p.avg_score * 100)}%`;
  if (e.type === "tutor_interaction") return p.sufficient === false ? "Question not covered by material" : `${p.concept || ""}${p.citations ? ` · ${p.citations} citation(s)` : ""}${p.visual ? ` · visual: ${p.visual}` : ""}`;
  if (e.type === "recommendation_generated") return p.title || "";
  if (e.type === "repeated_mistake_detected") return p.summary || "";
  if (e.type === "material_processed") return `${p.pages} pages, ${p.chunks} chunks, ${p.concepts} concepts`;
  return p.name || "";
}
