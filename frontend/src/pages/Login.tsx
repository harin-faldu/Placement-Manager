import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, api } from "../api";
import { useAuth } from "../auth";
import type { User } from "../types";

const ACCOUNTS = [
  ["Administrator", "admin@nfsu.ac.in", "Admin@2026!"],
  ["Officer", "officer@nfsu.ac.in", "Officer@2026!"],
  ["Coordinator", "coord.cs@nfsu.ac.in", "Coord@2026!"],
  ["Recruiter", "recruiter@kavach.example", "Recruit@2026!"],
  ["Student", "ananya.shah@nfsu.ac.in", "Student@2026!"],
];

export function Login() {
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const [email, setEmail] = useState("admin@nfsu.ac.in");
  const [password, setPassword] = useState("Admin@2026!");
  const [challenge, setChallenge] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      if (challenge) {
        const payload = await api<{ user: User }>("/api/auth/mfa", {
          method: "POST",
          body: JSON.stringify({ challenge, code }),
        });
        setUser(payload.user);
      } else {
        const payload = await api<{ user?: User; mfa_required?: boolean; challenge?: string }>("/api/auth/login", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        });
        if (payload.mfa_required && payload.challenge) {
          setChallenge(payload.challenge);
          return;
        }
        if (payload.user) setUser(payload.user);
      }
      navigate("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sign-in failed");
    }
  }

  return (
    <div className="login">
      <section className="story">
        <div>
          <p>National Forensic Sciences University</p>
          <h1>Placement Cell</h1>
          <p>Session 2026–27. A policy-checked register of student recruitment, offers, and outcomes.</p>
          <ul>
            <li>M.Tech. Computer Science</li>
            <li>M.Tech. Artificial Intelligence and Data Science</li>
            <li>B.Tech.–M.Tech. Computer Science and Engineering</li>
            <li>M.Sc. Computer Science</li>
            <li>M.Sc. Digital Forensics and Information Security</li>
          </ul>
        </div>
        <p>Internship stipends and annual CTC are kept apart. A placed student is counted once.</p>
      </section>
      <section className="sign">
        <form className="panel" onSubmit={onSubmit}>
          <h2>{challenge ? "Verification code" : "Sign in"}</h2>
          <p className="lede">Prototype access for the placement session. Do not load live personal data.</p>
          {!challenge ? (
            <>
              <label className="stack">
                Email
                <input value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="username" />
              </label>
              <label>
                Password
                <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" />
              </label>
            </>
          ) : (
            <label>
              Authenticator code
              <input value={code} onChange={(event) => setCode(event.target.value)} inputMode="numeric" />
            </label>
          )}
          {error && <p className="banner bad">{error}</p>}
          <button className="wide" type="submit">{challenge ? "Verify" : "Enter the register"}</button>
          <div className="accounts">
            {ACCOUNTS.map(([role, mail, pass]) => (
              <div key={mail}>
                <span>{role}</span>
                <span>{mail}</span>
                <button
                  type="button"
                  className="linkish"
                  onClick={() => {
                    setEmail(mail);
                    setPassword(pass);
                    setChallenge(null);
                  }}
                >
                  Use
                </button>
              </div>
            ))}
          </div>
        </form>
      </section>
    </div>
  );
}
