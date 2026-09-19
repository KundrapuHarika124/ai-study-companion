import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { onAuthStateChanged, signInWithEmailAndPassword, createUserWithEmailAndPassword, signOut as fbSignOut, GoogleAuthProvider, signInWithPopup } from "firebase/auth";
import { authMode, firebaseAuth } from "./firebase";
import { api } from "./api";

type Me = { id: string; email: string; name: string; is_admin: boolean };
type Ctx = { user: Me | null; loading: boolean; signIn: (email: string, password?: string) => Promise<void>; register: (email: string, password: string) => Promise<void>; google: () => Promise<void>; signOut: () => Promise<void>; refresh: () => Promise<void> };
const AuthCtx = createContext<Ctx>(null as any);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    try { setUser(await api<Me>("/me")); } catch { setUser(null); }
  };

  useEffect(() => {
    if (authMode === "dev") {
      (localStorage.getItem("dev_user") ? refresh() : Promise.resolve()).finally(() => setLoading(false));
      return;
    }
    const auth = firebaseAuth()!;
    return onAuthStateChanged(auth, async (u) => { if (u) await refresh(); else setUser(null); setLoading(false); });
  }, []);

  const value: Ctx = {
    user, loading, refresh,
    signIn: async (email, password) => {
      if (authMode === "dev") { localStorage.setItem("dev_user", email.trim().toLowerCase()); await refresh(); return; }
      await signInWithEmailAndPassword(firebaseAuth()!, email, password!); await refresh();
    },
    register: async (email, password) => { await createUserWithEmailAndPassword(firebaseAuth()!, email, password); await refresh(); },
    google: async () => { await signInWithPopup(firebaseAuth()!, new GoogleAuthProvider()); await refresh(); },
    signOut: async () => { if (authMode === "dev") localStorage.removeItem("dev_user"); else await fbSignOut(firebaseAuth()!); setUser(null); },
  };
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
