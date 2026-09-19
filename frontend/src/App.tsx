import { ReactElement } from "react";
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./lib/auth";
import Shell from "./components/Shell";
import { Loading } from "./components/ui";
import Login from "./pages/Login";
import Home from "./pages/Home";
import Spaces from "./pages/Spaces";
import SpaceDetail from "./pages/SpaceDetail";
import ProjectDashboard from "./pages/ProjectDashboard";
import Materials from "./pages/Materials";
import Tutor from "./pages/Tutor";
import Quiz from "./pages/Quiz";
import Mastery from "./pages/Mastery";
import Growth from "./pages/Growth";
import Analytics from "./pages/Analytics";
import Activity from "./pages/Activity";
import Admin from "./pages/Admin";

function Protected({ children, admin = false }: { children: ReactElement; admin?: boolean }) {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <Loading label="Signing you in" full />;
  if (!user) return <Navigate to="/login" state={{ from: loc.pathname }} replace />;
  if (admin && !user.is_admin) return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Protected><Shell /></Protected>}>
        <Route path="/" element={<Home />} />
        <Route path="/spaces" element={<Spaces />} />
        <Route path="/spaces/:spaceId" element={<SpaceDetail />} />
        <Route path="/projects/:projectId" element={<ProjectDashboard />} />
        <Route path="/projects/:projectId/materials" element={<Materials />} />
        <Route path="/projects/:projectId/tutor" element={<Tutor />} />
        <Route path="/projects/:projectId/quiz" element={<Quiz />} />
        <Route path="/projects/:projectId/mastery" element={<Mastery />} />
        <Route path="/projects/:projectId/growth" element={<Growth />} />
        <Route path="/projects/:projectId/analytics" element={<Analytics />} />
        <Route path="/projects/:projectId/activity" element={<Activity />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/activity" element={<Activity />} />
        <Route path="/admin" element={<Protected admin><Admin /></Protected>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
