import { NavLink, Outlet, useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Home, LayoutGrid, BarChart3, ListChecks, ShieldCheck, LogOut, FileText, MessageSquare, BrainCircuit, Gauge, TrendingUp, Activity as ActivityIcon, Menu } from "lucide-react";
import { useState } from "react";
import { useAuth } from "../lib/auth";
import { api } from "../lib/api";

const nav = "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm text-mute hover:bg-paper hover:text-ink";
const active = "bg-teal-soft text-teal font-medium hover:bg-teal-soft";

export default function Shell() {
  const { user, signOut } = useAuth();
  const { projectId } = useParams();
  const [open, setOpen] = useState(false);
  const project = useQuery({ queryKey: ["project-nav", projectId], queryFn: () => api(`/projects/${projectId}`), enabled: !!projectId });
  const p = project.data?.project;
  const space = project.data?.space;

  const links = (
    <>
      <nav className="space-y-0.5">
        <NavLink to="/" end className={({ isActive }) => `${nav} ${isActive ? active : ""}`} onClick={() => setOpen(false)}><Home size={16} />Home</NavLink>
        <NavLink to="/spaces" className={({ isActive }) => `${nav} ${isActive ? active : ""}`} onClick={() => setOpen(false)}><LayoutGrid size={16} />Spaces</NavLink>
        <NavLink to="/analytics" end className={({ isActive }) => `${nav} ${isActive ? active : ""}`} onClick={() => setOpen(false)}><BarChart3 size={16} />Analytics</NavLink>
        <NavLink to="/activity" end className={({ isActive }) => `${nav} ${isActive ? active : ""}`} onClick={() => setOpen(false)}><ListChecks size={16} />Activity</NavLink>
        {user?.is_admin && <NavLink to="/admin" className={({ isActive }) => `${nav} ${isActive ? active : ""}`} onClick={() => setOpen(false)}><ShieldCheck size={16} />Admin</NavLink>}
      </nav>
      {projectId && (
        <div className="mt-6">
          <div className="px-3 mb-1 text-xs text-mute">
            {space && <Link to={`/spaces/${space.id}`} className="hover:text-ink" style={{ color: space.color }}>{space.name}</Link>}
            <p className="text-sm text-ink font-medium truncate">{p?.name || "Project"}</p>
          </div>
          <nav className="space-y-0.5">
            {[["", "Overview", Gauge], ["/materials", "Materials", FileText], ["/tutor", "Tutor", MessageSquare], ["/quiz", "Quiz", BrainCircuit], ["/mastery", "Mastery", Gauge], ["/growth", "Growth", TrendingUp], ["/analytics", "Analytics", BarChart3], ["/activity", "Activity", ActivityIcon]].map(([path, label, Icon]: any) => (
              <NavLink key={label} to={`/projects/${projectId}${path}`} end className={({ isActive }) => `${nav} ${isActive ? active : ""}`} onClick={() => setOpen(false)}><Icon size={16} />{label}</NavLink>
            ))}
          </nav>
        </div>
      )}
    </>
  );

  return (
    <div className="min-h-screen md:grid md:grid-cols-[240px_1fr]">
      <aside className="hidden md:flex flex-col border-r border-line bg-surface px-3 py-5 sticky top-0 h-screen">
        <Link to="/" className="px-3 mb-6 display text-lg font-semibold text-ink">Study Companion</Link>
        <div className="flex-1 overflow-y-auto">{links}</div>
        <div className="border-t border-line pt-3 px-3 text-xs text-mute flex items-center justify-between">
          <span className="truncate" title={user?.email}>{user?.email}</span>
          <button onClick={signOut} className="text-mute hover:text-ink" aria-label="Sign out"><LogOut size={14} /></button>
        </div>
      </aside>
      <div className="md:hidden flex items-center justify-between border-b border-line bg-surface px-4 py-3">
        <Link to="/" className="display font-semibold">Study Companion</Link>
        <button onClick={() => setOpen(!open)} aria-label="Menu"><Menu size={20} /></button>
      </div>
      {open && <div className="md:hidden border-b border-line bg-surface px-3 py-3">{links}<button onClick={signOut} className="mt-3 text-sm text-mute px-3">Sign out</button></div>}
      <main className="px-4 py-6 md:px-10 md:py-8 max-w-5xl w-full">
        <Outlet />
      </main>
    </div>
  );
}
