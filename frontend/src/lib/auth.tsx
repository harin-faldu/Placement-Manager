import { createContext, useContext, useEffect, useState } from "react";
import { api } from "./api";
import type { User } from "./types";

interface AuthState {
  user: User | null;
  ready: boolean;
  setUser: (user: User | null) => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    api<{ user: User }>("/api/auth/me")
      .then((payload) => setUser(payload.user))
      .catch(() => setUser(null))
      .finally(() => setReady(true));
    const onUnauthorized = () => setUser(null);
    window.addEventListener("placement-unauthorized", onUnauthorized);
    return () => window.removeEventListener("placement-unauthorized", onUnauthorized);
  }, []);

  return <AuthContext.Provider value={{ user, ready, setUser }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("AuthProvider is missing");
  return value;
}
