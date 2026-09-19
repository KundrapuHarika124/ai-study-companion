import { useState, FormEvent } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { authMode } from "../lib/firebase";
import { Button, Field, inputCls } from "../components/ui";

export default function Login() {
  const { user, signIn, register, google, loading } = useAuth();
  const loc = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"in" | "up">("in");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  if (!loading && user) return <Navigate to={(loc.state as any)?.from || "/"} replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault(); setErr(""); setBusy(true);
    try { mode === "in" || authMode === "dev" ? await signIn(email, password) : await register(email, password); }
    catch (ex: any) { setErr(ex?.message?.replace("Firebase: ", "") || "Sign-in failed"); }
    finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen grid place-items-center px-4">
      <div className="w-full max-w-sm">
        <h1 className="text-3xl font-semibold">Study Companion</h1>
        <p className="text-mute mt-2 mb-8">Learn from your own material, measure what you know, and always know what to do next.</p>
        <form onSubmit={submit} className="space-y-4 bg-surface border border-line rounded-lg p-5">
          <Field label="Email"><input className={inputCls} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" /></Field>
          {authMode === "firebase" && <Field label="Password"><input className={inputCls} type="password" required minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={mode === "in" ? "current-password" : "new-password"} /></Field>}
          {authMode === "dev" && <p className="text-xs text-amber">Development mode: any email signs you in. Enable Firebase for real authentication.</p>}
          {err && <p role="alert" className="text-sm text-rust">{err}</p>}
          <Button type="submit" className="w-full justify-center" disabled={busy}>{busy ? "Please wait…" : mode === "in" || authMode === "dev" ? "Sign in" : "Create account"}</Button>
          {authMode === "firebase" && (
            <>
              <Button type="button" variant="secondary" className="w-full justify-center" onClick={() => google().catch((e) => setErr(e.message))}>Continue with Google</Button>
              <button type="button" className="w-full text-sm text-teal" onClick={() => setMode(mode === "in" ? "up" : "in")}>{mode === "in" ? "New here? Create an account" : "Already have an account? Sign in"}</button>
            </>
          )}
        </form>
      </div>
    </div>
  );
}
