import { ReactNode, ButtonHTMLAttributes } from "react";
import { Link } from "react-router-dom";
import { AlertCircle, Loader2 } from "lucide-react";

export function Button({ children, variant = "primary", className = "", ...rest }: { children: ReactNode; variant?: "primary" | "secondary" | "ghost" | "danger"; className?: string } & ButtonHTMLAttributes<HTMLButtonElement>) {
  const base = "inline-flex items-center gap-1.5 rounded-md px-3.5 py-2 text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed";
  const variants: Record<string, string> = { primary: "bg-teal text-white hover:bg-teal-deep", secondary: "bg-surface border border-line text-ink hover:bg-paper", ghost: "text-teal hover:bg-teal-soft", danger: "bg-rust-soft text-rust hover:bg-rust hover:text-white" };
  const v = variants[variant];
  return <button className={`${base} ${v} ${className}`} {...rest}>{children}</button>;
}

export function LinkButton({ to, children, variant = "primary", className = "" }: { to: string; children: ReactNode; variant?: "primary" | "secondary" | "ghost"; className?: string }) {
  const base = "inline-flex items-center gap-1.5 rounded-md px-3.5 py-2 text-sm font-medium transition-colors";
  const v = { primary: "bg-teal text-white hover:bg-teal-deep", secondary: "bg-surface border border-line text-ink hover:bg-paper", ghost: "text-teal hover:bg-teal-soft" }[variant];
  return <Link to={to} className={`${base} ${v} ${className}`}>{children}</Link>;
}

export function Card({ children, className = "", title, action }: { children: ReactNode; className?: string; title?: ReactNode; action?: ReactNode }) {
  return (
    <section className={`bg-surface border border-line rounded-lg ${className}`}>
      {(title || action) && <header className="flex items-center justify-between px-5 pt-4 pb-2"><h3 className="font-medium text-ink">{title}</h3>{action}</header>}
      <div className={title ? "px-5 pb-5" : "p-5"}>{children}</div>
    </section>
  );
}

export function PageTitle({ title, sub, action }: { title: ReactNode; sub?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3 mb-6">
      <div><h1 className="text-2xl font-semibold text-ink">{title}</h1>{sub && <p className="text-mute mt-1 max-w-2xl">{sub}</p>}</div>
      {action}
    </div>
  );
}

export function Loading({ label = "Loading", full = false }: { label?: string; full?: boolean }) {
  return <div className={`flex items-center gap-2 text-mute text-sm ${full ? "min-h-screen justify-center" : "py-10 justify-center"}`}><Loader2 className="animate-spin" size={16} aria-hidden /> {label}…</div>;
}

export function ErrorBox({ error, retry }: { error: any; retry?: () => void }) {
  const msg = error?.message || "Something went wrong.";
  return (
    <div role="alert" className="flex items-start gap-3 rounded-lg border border-rust/30 bg-rust-soft p-4 text-sm text-rust">
      <AlertCircle size={18} className="mt-0.5 shrink-0" />
      <div className="flex-1"><p className="font-medium">Couldn't load this</p><p className="mt-0.5">{msg}</p></div>
      {retry && <Button variant="secondary" onClick={retry}>Try again</Button>}
    </div>
  );
}

export function Empty({ title, body, action }: { title: string; body?: string; action?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-line bg-surface px-6 py-10 text-center">
      <p className="font-medium text-ink">{title}</p>
      {body && <p className="text-sm text-mute mt-1 max-w-md mx-auto">{body}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "teal" | "amber" | "moss" | "rust" }) {
  const t = { neutral: "bg-paper text-mute border-line", teal: "bg-teal-soft text-teal border-teal/20", amber: "bg-amber-soft text-amber border-amber/20", moss: "bg-moss-soft text-moss border-moss/20", rust: "bg-rust-soft text-rust border-rust/20" }[tone];
  return <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${t}`}>{children}</span>;
}

export function statusTone(s: string): "neutral" | "teal" | "amber" | "moss" | "rust" {
  return ({ ready: "moss", completed: "moss", processing: "teal", queued: "amber", retrying: "amber", failed: "rust", improving: "moss", stable: "teal", attention: "amber", insufficient_evidence: "neutral" } as any)[s] || "neutral";
}

export function MasteryBar({ value, label, sub }: { value: number | null; label: string; sub?: string }) {
  const pct = value == null ? 0 : Math.round(value * 100);
  const color = value == null ? "bg-line" : value < 0.6 ? "bg-amber" : value < 0.75 ? "bg-teal" : "bg-moss";
  return (
    <div className="py-2">
      <div className="flex items-baseline justify-between text-sm"><span className="text-ink">{label}</span><span className="text-mute tabular-nums">{value == null ? "not yet assessed" : `${pct}%`}</span></div>
      <div className="mt-1.5 h-1.5 w-full rounded-full bg-paper overflow-hidden" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={label}><div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} /></div>
      {sub && <p className="text-xs text-mute mt-1">{sub}</p>}
    </div>
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return <div className="rounded-lg border border-line bg-surface px-4 py-3"><p className="text-sm text-mute">{label}</p><p className="text-xl font-semibold text-ink mt-0.5 tabular-nums">{value}</p>{hint && <p className="text-xs text-mute mt-0.5">{hint}</p>}</div>;
}

export const fmtDate = (s?: string) => (s ? new Date(s).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "");
export const fmtRel = (s?: string) => {
  if (!s) return "";
  const d = (Date.now() - new Date(s).getTime()) / 1000;
  if (d < 60) return "just now"; if (d < 3600) return `${Math.floor(d / 60)} min ago`; if (d < 86400) return `${Math.floor(d / 3600)} h ago`; return `${Math.floor(d / 86400)} d ago`;
};
export const eventLabel = (t: string) => ({ space_created: "Created a space", project_created: "Created a project", material_uploaded: "Uploaded material", material_processing_started: "Started processing material", material_processed: "Material ready", material_failed: "Material processing failed", tutor_interaction: "Asked the Tutor", quiz_started: "Started a quiz", question_answered: "Answered a question", assessment_completed: "Completed a quiz", mastery_updated: "Mastery updated", recommendation_generated: "New recommendation", repeated_mistake_detected: "Repeated mistake detected" } as any)[t] || t.replace(/_/g, " ");

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="block text-sm"><span className="text-mute">{label}</span><div className="mt-1">{children}</div></label>;
}
export const inputCls = "w-full rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-mute/70 focus:border-teal";
