import { FormEvent, useEffect, useState } from "react";
import { ApiError, api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { Company, Course, Student, User } from "../lib/types";
import { Banner, Pill } from "../components/ui";

export function AccessPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<User[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [students, setStudents] = useState<Student[]>([]);
  const [form, setForm] = useState({ email: "", full_name: "", password: "", role: "officer", course: "", company_id: "", student_id: "" });
  const [secret, setSecret] = useState("");
  const [code, setCode] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  function load() {
    api<{ items: User[] }>("/api/users").then((payload) => setItems(payload.items));
    api<{ courses: Course[] }>("/api/meta").then((payload) => setCourses(payload.courses));
    api<{ items: Company[] }>("/api/companies").then((payload) => setCompanies(payload.items));
    api<{ items: Student[] }>("/api/students?limit=100").then((payload) => setStudents(payload.items));
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
          student_id: form.role === "student" ? form.student_id : null,
        }),
      });
      setMessage(form.role === "student" ? `${form.email} can sign in with the password you set and will see only that record.` : "Account created.");
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
                <td>{account.role === "student" ? "Own record" : account.course_name || account.company_id || "University"}</td>
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
          <label>Name<input value={form.full_name} onChange={(event) => setForm({ ...form, full_name: event.target.value })} required readOnly={form.role === "student"} /></label>
          <label>Email<input value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} required readOnly={form.role === "student"} /></label>
          <label>Password<input value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} required /></label>
          <label>
            Role
            <select value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })}>
              <option value="officer">Placement Officer</option>
              <option value="coordinator">Course Coordinator</option>
              <option value="recruiter">Company / Recruiter</option>
              <option value="student">Student</option>
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
          {form.role === "student" && (
            <label>
              Student record
              <select
                value={form.student_id}
                required
                onChange={(event) => {
                  const student = students.find((item) => item.id === event.target.value);
                  setForm({
                    ...form,
                    student_id: event.target.value,
                    email: student?.email || "",
                    full_name: student?.full_name || "",
                  });
                }}
              >
                <option value="">Select a record that has no sign-in</option>
                {students.filter((student) => !items.some((account) => account.student_id === student.id)).map((student) => (
                  <option key={student.id} value={student.id}>{student.full_name} · {student.placement_id}</option>
                ))}
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
