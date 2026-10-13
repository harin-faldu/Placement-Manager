import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { Course, Student } from "../lib/types";
import { Banner, Pill, toneFor } from "../components/ui";

const EMPTY = {
  placement_id: "",
  full_name: "",
  mobile: "",
  email: "",
  password: "",
  course: "MTECH_CS",
  batch: "2026",
  registration_status: "registered",
  eligibility_status: "eligible",
  cgpa: "",
};

export function Students() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [courses, setCourses] = useState<Course[]>([]);
  const [items, setItems] = useState<Student[]>([]);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState({ q: "", course: "", batch: "", placement_status: "" });
  const [form, setForm] = useState(EMPTY);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (user?.role === "student" && user.student_id) {
      navigate(`/students/${user.student_id}`, { replace: true });
      return;
    }
    api<{ courses: Course[] }>("/api/meta").then((payload) => setCourses(payload.courses));
  }, [user, navigate]);

  function load(next = filters) {
    const params = new URLSearchParams();
    Object.entries(next).forEach(([key, value]) => value && params.set(key, value));
    api<{ items: Student[]; total: number }>(`/api/students?${params.toString()}`)
      .then((payload) => {
        setItems(payload.items);
        setTotal(payload.total);
      })
      .catch((err: ApiError) => setError(err.message));
  }

  useEffect(() => {
    if (user && user.role !== "student") load();
    // initial directory load
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  async function create(event: FormEvent) {
    event.preventDefault();
    setError("");
    setMessage("");
    try {
      const created = await api<Student & { sign_in_email: string }>("/api/students", {
        method: "POST",
        body: JSON.stringify({ ...form, cgpa: form.cgpa ? Number(form.cgpa) : null }),
      });
      setMessage(`${created.full_name} can sign in as ${created.sign_in_email} with the password you set. The record is included in drive checks.`);
      setForm(EMPTY);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the record");
    }
  }

  if (user?.role === "student") return null;

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Students</h1>
          <p className="lede">{total} records in this view. Search by name, Placement ID, or email. Archived records stay out of the working list.</p>
        </div>
      </header>
      <form
        className="filters card"
        onSubmit={(event) => {
          event.preventDefault();
          load();
        }}
      >
        <label className="grow">Search<input value={filters.q} onChange={(event) => setFilters({ ...filters, q: event.target.value })} /></label>
        <label>
          Programme
          <select value={filters.course} onChange={(event) => setFilters({ ...filters, course: event.target.value })}>
            <option value="">All visible</option>
            {courses.map((course) => <option key={course.code} value={course.code}>{course.short}</option>)}
          </select>
        </label>
        <label>Batch<input value={filters.batch} onChange={(event) => setFilters({ ...filters, batch: event.target.value })} placeholder="2026" /></label>
        <label>
          Placement
          <select value={filters.placement_status} onChange={(event) => setFilters({ ...filters, placement_status: event.target.value })}>
            <option value="">Any</option>
            <option value="unplaced">Unplaced</option>
            <option value="internship_only">Internship only</option>
            <option value="fte_only">FTE only</option>
            <option value="internship_ppo_fte">Internship + PPO/FTE</option>
          </select>
        </label>
        <button type="submit">Apply</button>
      </form>
      <div className="grid directory">
        <div className="card">
          <table>
            <thead>
              <tr><th>Placement ID</th><th>Name</th><th>Programme</th><th>Batch</th><th>Registration</th><th>Placement</th></tr>
            </thead>
            <tbody>
              {items.map((student) => (
                <tr key={student.id} className="clickable" onClick={() => navigate(`/students/${student.id}`)}>
                  <td>{student.placement_id}</td>
                  <td>{student.full_name}</td>
                  <td>{student.course_short}</td>
                  <td>{student.batch}</td>
                  <td><Pill tone={toneFor(student.registration_status)}>{student.registration_label}</Pill></td>
                  <td><Pill tone={toneFor(student.placement_status)}>{student.placement_status_label}</Pill></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {(user?.role === "admin" || user?.role === "officer") && (
          <form className="card stack" onSubmit={create}>
            <h2>New record</h2>
            <p className="note">Placement ID is permanent. The email and password are the student's sign-in. Registered and eligible students appear in drive checks. Placement status is derived later from offers.</p>
            {(["placement_id", "full_name", "mobile", "email", "batch"] as const).map((field) => (
              <label key={field}>
                {field.replaceAll("_", " ")}
                <input value={form[field]} onChange={(event) => setForm({ ...form, [field]: event.target.value })} required />
              </label>
            ))}
            <label>
              Password
              <input type="password" autoComplete="new-password" minLength={10} value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} required />
            </label>
            <p className="note">At least 10 characters, with upper case, lower case, and a number.</p>
            <label>
              Programme
              <select value={form.course} onChange={(event) => setForm({ ...form, course: event.target.value })}>
                {courses.map((course) => <option key={course.code} value={course.code}>{course.name}</option>)}
              </select>
            </label>
            <label>CGPA<input value={form.cgpa} onChange={(event) => setForm({ ...form, cgpa: event.target.value })} /></label>
            <label>
              Registration
              <select value={form.registration_status} onChange={(event) => setForm({ ...form, registration_status: event.target.value })}>
                <option value="registered">Registered</option>
                <option value="not_registered">Not registered</option>
                <option value="deregistered">Deregistered</option>
              </select>
            </label>
            <label>
              Eligibility
              <select value={form.eligibility_status} onChange={(event) => setForm({ ...form, eligibility_status: event.target.value })}>
                <option value="eligible">Eligible</option>
                <option value="pending_verification">Pending verification</option>
                <option value="ineligible">Ineligible</option>
              </select>
            </label>
            {error && <Banner tone="bad">{error}</Banner>}
            {message && <Banner tone="good">{message}</Banner>}
            <button type="submit">Create record</button>
          </form>
        )}
      </div>
    </>
  );
}
