import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { Company, Course, Drive, Student } from "../lib/types";
import { Banner, Pill, StudentPicker } from "../components/ui";

export function Recruitment() {
  const { user } = useAuth();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [drives, setDrives] = useState<Drive[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [candidates, setCandidates] = useState<{ eligible: Array<Record<string, string | number | null>>; eligible_count: number; withheld_count: number } | null>(null);
  const [precheck, setPrecheck] = useState<{ allow: number; review: number; block: number; items: Array<{ id: string; full_name: string; placement_id: string; course_short: string; verdict: "allow" | "block" | "review"; reasons: string[] }> } | null>(null);
  const [companyName, setCompanyName] = useState("");
  const [driveForm, setDriveForm] = useState({ company_id: "", title: "", offer_type: "F", ctc_lpa: "", stipend_amount: "", courses: [] as string[] });
  const [student, setStudent] = useState<Student | null>(null);
  const [activity, setActivity] = useState("ppt");
  const [attended, setAttended] = useState(true);
  const [emergency, setEmergency] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const canEdit = user?.role === "admin" || user?.role === "officer";
  const canExplain = canEdit || user?.role === "coordinator";

  function load() {
    api<{ items: Company[] }>("/api/companies").then((payload) => setCompanies(payload.items));
    api<{ items: Drive[] }>("/api/drives").then((payload) => {
      setDrives(payload.items);
      setSelected((current) => current || payload.items[0]?.id || "");
    });
    api<{ courses: Course[] }>("/api/meta").then((payload) => setCourses(payload.courses));
  }

  useEffect(() => { load(); }, []);
  useEffect(() => {
    if (!selected) return;
    api<{ eligible: Array<Record<string, string | number | null>>; eligible_count: number; withheld_count: number }>(`/api/drives/${selected}/candidates`)
      .then(setCandidates)
      .catch((err: ApiError) => setError(err.message));
    if (canExplain) {
      api<{ allow: number; review: number; block: number; items: Array<{ id: string; full_name: string; placement_id: string; course_short: string; verdict: "allow" | "block" | "review"; reasons: string[] }> }>(`/api/drives/${selected}/precheck`)
        .then(setPrecheck)
        .catch(() => setPrecheck(null));
    } else {
      setPrecheck(null);
    }
  }, [selected, canExplain]);

  async function addCompany(event: FormEvent) {
    event.preventDefault();
    await api("/api/companies", { method: "POST", body: JSON.stringify({ name: companyName }) });
    setCompanyName("");
    load();
  }

  async function addDrive(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api("/api/drives", {
        method: "POST",
        body: JSON.stringify({
          company_id: driveForm.company_id,
          title: driveForm.title,
          offer_type: driveForm.offer_type,
          ctc_lpa: driveForm.offer_type === "I" ? null : Number(driveForm.ctc_lpa),
          stipend_amount: driveForm.offer_type === "F" ? null : Number(driveForm.stipend_amount),
          stipend_period: driveForm.offer_type === "F" ? null : "monthly",
          courses: driveForm.courses,
          acceptance_hours: 24,
        }),
      });
      setMessage("Drive added.");
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not add the drive");
    }
  }

  async function markAttendance(event: FormEvent) {
    event.preventDefault();
    if (!student || !selected) return;
    setError("");
    try {
      await api(`/api/drives/${selected}/attendance`, {
        method: "POST",
        body: JSON.stringify({ student_id: student.id, activity, attended, emergency_claimed: !attended && emergency }),
      });
      setMessage(attended ? "Attendance recorded." : "Absence recorded. An unexcused absence excludes the next three drives.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not record attendance");
    }
  }

  const drive = drives.find((item) => item.id === selected);

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Recruitment</h1>
          <p className="lede">
            Before a drive is used, the register checks registration, existing offers, category, and offer type.
            {canExplain ? " Each row below says why a student is allowed, blocked, or waiting for review." : " Companies see students the rules allow. Withheld students are counted, not named, and the reason is not shared."}
          </p>
        </div>
      </header>
      {message && <Banner tone="good">{message}</Banner>}
      {error && <Banner tone="bad">{error}</Banner>}
      <section className="grid split">
        <article className="card">
          <h2>Drives</h2>
          <table>
            <thead><tr><th>Drive</th><th>Type</th><th>Package</th></tr></thead>
            <tbody>
              {drives.map((item) => (
                <tr key={item.id} className="clickable" onClick={() => setSelected(item.id)}>
                  <td>{item.company_name}<div className="note">{item.title}</div></td>
                  <td>{item.offer_type_label}</td>
                  <td>{item.ctc_lpa != null ? `${item.ctc_lpa} LPA` : item.stipend_amount != null ? `₹${item.stipend_amount}` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>
        <article className="card">
          <h2>{drive ? drive.title : "Select a drive"}</h2>
          {candidates && (
            <>
              <p>{candidates.eligible_count} eligible · {candidates.withheld_count} withheld by policy</p>
              <ul>
                {candidates.eligible.map((person, index) => (
                  <li key={String(person.id ?? person.full_name ?? index)}>
                    {person.id ? <Link to={`/students/${person.id}`}>{person.full_name}</Link> : person.full_name}
                    {" "}· {person.course_short} · {person.batch}
                  </li>
                ))}
              </ul>
            </>
          )}
          {canEdit && (
            <form className="stack" onSubmit={markAttendance}>
              <StudentPicker onSelect={setStudent} />
              <label>
                Activity
                <select value={activity} onChange={(event) => setActivity(event.target.value)}>
                  <option value="ppt">Pre-placement talk</option>
                  <option value="test">Test</option>
                  <option value="interview">Interview</option>
                  <option value="other">Other</option>
                </select>
              </label>
              <label><input type="checkbox" checked={attended} onChange={(event) => setAttended(event.target.checked)} /> Attended</label>
              {!attended && <label><input type="checkbox" checked={emergency} onChange={(event) => setEmergency(event.target.checked)} /> Emergency exception claimed</label>}
              <button type="submit">Record attendance</button>
            </form>
          )}
        </article>
      </section>
      {precheck && (
        <section className="card">
          <h2>Policy check before this drive</h2>
          <p className="note">{precheck.allow} allowed · {precheck.review} for review · {precheck.block} blocked</p>
          <table>
            <thead><tr><th>Student</th><th>Result</th><th>Why</th></tr></thead>
            <tbody>
              {precheck.items.map((item) => (
                <tr key={item.id}>
                  <td><Link to={`/students/${item.id}`}>{item.full_name}</Link><div className="note">{item.placement_id} · {item.course_short}</div></td>
                  <td><Pill tone={item.verdict === "allow" ? "good" : item.verdict === "block" ? "bad" : "warn"}>{item.verdict}</Pill></td>
                  <td>{item.reasons.join(" ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
      {canEdit && (
        <section className="grid split">
          <form className="card stack" onSubmit={addCompany}>
            <h2>Company</h2>
            <label>Name<input value={companyName} onChange={(event) => setCompanyName(event.target.value)} required /></label>
            <button type="submit">Add company</button>
            <p className="note">{companies.map((company) => company.name).join(" · ")}</p>
          </form>
          <form className="card stack" onSubmit={addDrive}>
            <h2>New drive</h2>
            <label>
              Company
              <select value={driveForm.company_id} onChange={(event) => setDriveForm({ ...driveForm, company_id: event.target.value })} required>
                <option value="">Select</option>
                {companies.map((company) => <option key={company.id} value={company.id}>{company.name}</option>)}
              </select>
            </label>
            <label>Title<input value={driveForm.title} onChange={(event) => setDriveForm({ ...driveForm, title: event.target.value })} required /></label>
            <label>
              Offer type
              <select value={driveForm.offer_type} onChange={(event) => setDriveForm({ ...driveForm, offer_type: event.target.value })}>
                <option value="I">Internship only</option>
                <option value="F">FTE only</option>
                <option value="IF">Internship + PPO/FTE</option>
              </select>
            </label>
            {driveForm.offer_type !== "I" && <label>CTC LPA<input value={driveForm.ctc_lpa} onChange={(event) => setDriveForm({ ...driveForm, ctc_lpa: event.target.value })} required /></label>}
            {driveForm.offer_type !== "F" && <label>Monthly stipend<input value={driveForm.stipend_amount} onChange={(event) => setDriveForm({ ...driveForm, stipend_amount: event.target.value })} required /></label>}
            <fieldset>
              <legend>Programmes</legend>
              {courses.map((course) => (
                <label key={course.code}>
                  <input
                    type="checkbox"
                    checked={driveForm.courses.includes(course.code)}
                    onChange={(event) => {
                      const coursesSelected = event.target.checked
                        ? [...driveForm.courses, course.code]
                        : driveForm.courses.filter((code) => code !== course.code);
                      setDriveForm({ ...driveForm, courses: coursesSelected });
                    }}
                  />
                  {course.short}
                </label>
              ))}
            </fieldset>
            <button type="submit">Add drive</button>
          </form>
        </section>
      )}
    </>
  );
}
