import { useEffect, useState } from "react";
import { NavLink, Navigate, Outlet, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { Check, Role, Student } from "../lib/types";

const NAV: Array<{ to: string; label: string; roles: Role[] }> = [
  { to: "/", label: "Dashboard", roles: ["admin", "officer", "coordinator", "recruiter", "student"] },
  { to: "/students", label: "Students", roles: ["admin", "officer", "coordinator", "student"] },
  { to: "/recruitment", label: "Recruitment", roles: ["admin", "officer", "recruiter"] },
  { to: "/policy", label: "Policy", roles: ["admin", "officer", "coordinator"] },
  { to: "/exceptions", label: "Exceptions", roles: ["admin", "officer"] },
  { to: "/reports", label: "Reports", roles: ["admin", "officer", "coordinator"] },
  { to: "/audit", label: "Audit", roles: ["admin", "officer"] },
  { to: "/access", label: "Access", roles: ["admin"] },
];

export function RequireAuth() {
  const { user, ready } = useAuth();
  if (!ready) return <p className="main">Opening the placement register…</p>;
  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
}

export function Shell() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();
  if (!user) return null;
  const items = NAV.filter((item) => item.roles.includes(user.role));

  async function logout() {
    await api("/api/auth/logout", { method: "POST" });
    setUser(null);
    navigate("/login");
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <small>NFSU · Session 2026–27</small>
          <strong>Placement</strong>
          <em>Five programmes, one register</em>
        </div>
        <nav className="nav">
          {items.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.to === "/"}>
              {user.role === "student" && item.to === "/students" ? "My record" : item.label}
            </NavLink>
          ))}
        </nav>
        <footer>
          <div className="who">
            <strong>{user.full_name}</strong>
            <span>{user.role_label}</span>
          </div>
          <button className="secondary" onClick={logout}>Sign out</button>
          <p>Decisions assist the Placement Cell. They do not replace the competent authority.</p>
        </footer>
      </aside>
      <main className="main">
        <div className="page">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

export function Pill({ children, tone }: { children: React.ReactNode; tone?: "good" | "bad" | "warn" }) {
  return <span className={tone ? `pill ${tone}` : "pill"}>{children}</span>;
}

export function toneFor(value: string) {
  if (["eligible", "registered", "accepted", "joined", "allow", "issued"].includes(value)) return "good" as const;
  if (["ineligible", "deregistered", "declined", "expired", "block", "rejected", "not_joined"].includes(value)) return "bad" as const;
  if (["pending", "pending_verification", "review", "not_registered"].includes(value)) return "warn" as const;
  return undefined;
}

export function Banner({ children, tone = "warn" }: { children: React.ReactNode; tone?: "good" | "bad" | "warn" }) {
  return <div className={`banner ${tone}`}>{children}</div>;
}

export function Checks({ checks }: { checks: Check[] }) {
  return (
    <ol className="checks">
      {checks.map((check) => (
        <li key={check.code} className={check.status}>
          <div>
            <strong>{check.title}</strong>
            <em>{check.status}</em>
          </div>
          <p>{check.detail}</p>
        </li>
      ))}
    </ol>
  );
}

export function StudentPicker({ onSelect }: { onSelect: (student: Student) => void }) {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<Student[]>([]);

  useEffect(() => {
    if (query.trim().length < 2) {
      setItems([]);
      return;
    }
    const timer = window.setTimeout(() => {
      api<{ items: Student[] }>(`/api/students?q=${encodeURIComponent(query)}&limit=8`)
        .then((payload) => setItems(payload.items))
        .catch(() => setItems([]));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [query]);

  return (
    <div className="picker">
      <label>
        Student
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Name or Placement ID" />
      </label>
      {items.length > 0 && (
        <ul>
          {items.map((student) => (
            <li key={student.id}>
              <button
                type="button"
                onClick={() => {
                  onSelect(student);
                  setQuery(`${student.full_name} · ${student.placement_id}`);
                  setItems([]);
                }}
              >
                {student.full_name} · {student.placement_id}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
