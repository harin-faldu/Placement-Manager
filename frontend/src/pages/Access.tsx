import { FormEvent, useEffect, useState } from "react";
import { ApiError, api } from "../api";
import { useAuth } from "../auth";
import type { Company, Course, User } from "../types";
import { Banner, Pill } from "../ui";

export function AccessPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<User[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [form, setForm] = useState({ email: "", full_name: "", password: "", role: "officer", course: "", company_id: "" });
  const [secret, setSecret] = useState("");
  const [code, setCode] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  function load() {
    api<{ items: User[] }>("/api/users").then((payload) => setItems(payload.items));
    api<{ courses: Course[] }>("/api/meta").then((payload) => setCourses(payload.courses));
    api<{ items: Company[] }>("/api/companies").then((payload) => setCompanies(payload.items));
  }
  useEffect(() => { load(); }, []);

  async function create(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api("/api/users", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          course: form.role === "coordinator" ? form.course : null,
          company_id: form.role === "recruiter" ? form.company_id : null,
          student_id: null,
        }),
      });
      setMessage("Account created.");
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the account");
    }
  }

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Access</h1>
          <p className="lede">Four operating roles, plus a student account that can read only its own record.</p>
        </div>
      </header>
      <div className="card">
        <table>
          <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Scope</th><th></th></tr></thead>
          <tbody>
            {items.map((account) => (
              <tr key={account.id}>
                <td>{account.full_name}</td>
                <td>{account.email}</td>
                <td>{account.role_label}</td>
                <td>{account.course_name || account.company_id || "University"}</td>
                <td>
                  {account.id !== user?.id && (
                    <button
                      className="secondary"
                      onClick={async () => {
                        await api(`/api/users/${account.id}`, {
                          method: "PATCH",
                          body: JSON.stringify({ is_active: !account.is_active }),
                        });
                        load();
                      }}
                    >
                      {account.is_active ? "Deactivate" : "Activate"}
                    </button>
                  )}
                  {!account.is_active && <Pill tone="bad">Inactive</Pill>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <section className="grid split">
        <form className="card stack" onSubmit={create}>
          <h2>New account</h2>
          <label>Name<input value={form.full_name} onChange={(event) => setForm({ ...form, full_name: event.target.value })} required /></label>
          <label>Email<input value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} required /></label>
          <label>Password<input value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} required /></label>
          <label>
            Role
            <select value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })}>
              <option value="officer">Placement Officer</option>
              <option value="coordinator">Course Coordinator</option>
              <option value="recruiter">Company / Recruiter</option>
              <option value="admin">Placement Administrator</option>
            </select>
          </label>
          {form.role === "coordinator" && (
            <label>
              Programme
              <select value={form.course} onChange={(event) => setForm({ ...form, course: event.target.value })} required>
                <option value="">Select</option>
                {courses.map((course) => <option key={course.code} value={course.code}>{course.name}</option>)}
              </select>
            </label>
          )}
          {form.role === "recruiter" && (
            <label>
              Company
              <select value={form.company_id} onChange={(event) => setForm({ ...form, company_id: event.target.value })} required>
                <option value="">Select</option>
                {companies.map((company) => <option key={company.id} value={company.id}>{company.name}</option>)}
              </select>
            </label>
          )}
          {error && <Banner tone="bad">{error}</Banner>}
          {message && <Banner tone="good">{message}</Banner>}
          <button type="submit">Create account</button>
        </form>
        <article className="card stack">
          <h2>Your second factor</h2>
          <p className="note">Optional for this prototype. When enabled, sign-in asks for a time-based code after the password.</p>
          <button
            type="button"
            className="secondary"
            onClick={async () => {
              const payload = await api<{ secret: string }>("/api/auth/mfa/setup", { method: "POST" });
              setSecret(payload.secret);
            }}
          >
            Generate a key
          </button>
          {secret && <p>Key: {secret}</p>}
          <label>Code<input value={code} onChange={(event) => setCode(event.target.value)} /></label>
          <button
            type="button"
            onClick={async () => {
              await api("/api/auth/mfa/confirm", { method: "POST", body: JSON.stringify({ code }) });
              setMessage("Second factor enabled for this account.");
            }}
          >
            Enable
          </button>
        </article>
      </section>
    </>
  );
}
