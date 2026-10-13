import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatNumber } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { Offer, Overview, Standing, Student } from "../lib/types";
import { Pill, toneFor } from "../components/ui";

export function Dashboard() {
  const { user } = useAuth();
  if (!user) return null;
  if (user.role === "student") return <StudentHome />;
  if (user.role === "recruiter") return <RecruiterHome />;
  return <CellHome />;
}

function CellHome() {
  const { user } = useAuth();
  const [report, setReport] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api<Overview>("/api/reports/overview").then(setReport).catch((err) => setError(err.message));
  }, []);
  if (error) return <p className="banner bad">{error}</p>;
  if (!report?.totals) return <p>Gathering the session figures…</p>;
  const totals = report.totals;
  return (
    <>
      <header className="page-head">
        <div>
          <h1>{report.scope === "course" ? report.course_name : "University register"}</h1>
          <p className="lede">
            Session {report.session}. Placed students are unique people. Offer events are counted separately.
            Annual CTC and monthly stipends are never combined.
          </p>
        </div>
      </header>
      <section className="grid stats">
        <Stat label="Registered" value={totals.registered} />
        <Stat label="Eligible" value={totals.eligible} />
        <Stat label="Ineligible" value={totals.ineligible} />
        <Stat label="Placed students" value={totals.placed} note={`${totals.offers} offer events`} />
        <Stat label="Unplaced" value={totals.unplaced} note="Registered, no accepted offer" />
      </section>
      <section className="grid stats-3">
        <Stat label="Internship only" value={totals.internship_only} />
        <Stat label="FTE only" value={totals.fte_only} />
        <Stat label="Internship + PPO/FTE" value={totals.internship_ppo_fte} />
      </section>
      <section className="grid split">
        <article className="card">
          <h2>Packages</h2>
          <p className="note">{report.definitions.ctc}</p>
          <div className="grid stats-3">
            <Stat label="Highest CTC" value={formatNumber(report.ctc?.highest)} note="LPA" />
            <Stat label="Average CTC" value={formatNumber(report.ctc?.average)} note="LPA" />
            <Stat label="Median CTC" value={formatNumber(report.ctc?.median)} note="LPA" />
          </div>
          <p className="note">{report.definitions.stipend}</p>
          <div className="grid stats-3">
            <Stat label="Highest stipend" value={formatNumber(report.stipend_monthly?.highest, 0)} note="₹ / month" />
            <Stat label="Average stipend" value={formatNumber(report.stipend_monthly?.average, 0)} note="₹ / month" />
            <Stat label="Median stipend" value={formatNumber(report.stipend_monthly?.median, 0)} note="₹ / month" />
          </div>
        </article>
        <article className="card">
          <h2>Needs a decision</h2>
          <p className="note">
            {totals.further_eligible} students still have a further drive the rules would allow.
            {(user?.role === "admin" || user?.role === "officer") && <> <Link to="/exceptions">Open the exception queue</Link></>}
          </p>
          <ul className="checks">
            {(report.attention ?? []).slice(0, 8).map((item) => (
              <li key={`${item.student_id}-${item.kind}-${item.message}`}>
                <div>
                  <strong><Link to={`/students/${item.student_id}`}>{item.student_name}</Link></strong>
                  <Pill tone={toneFor(item.kind)}>{item.kind.replaceAll("_", " ")}</Pill>
                </div>
                <p>{item.message}</p>
              </li>
            ))}
          </ul>
        </article>
      </section>
    </>
  );
}

function RecruiterHome() {
  const [report, setReport] = useState<Overview | null>(null);
  useEffect(() => {
    api<Overview>("/api/reports/overview").then(setReport);
  }, []);
  if (!report) return <p>Loading company drives…</p>;
  return (
    <>
      <header className="page-head">
        <div>
          <h1>{report.company}</h1>
          <p className="lede">{report.definitions.eligible}</p>
        </div>
      </header>
      <div className="card">
        <table>
          <thead>
            <tr><th>Drive</th><th>Type</th><th>Eligible</th><th>Withheld</th></tr>
          </thead>
          <tbody>
            {(report.drives ?? []).map((drive) => (
              <tr key={drive.id}>
                <td>{drive.title}</td>
                <td>{drive.offer_type_label}</td>
                <td>{drive.eligible_count}</td>
                <td>{drive.withheld_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function StudentHome() {
  const { user } = useAuth();
  const [record, setRecord] = useState<{ student: Student; offers: Offer[]; standing: Standing } | null>(null);
  useEffect(() => {
    if (user?.student_id) {
      api<{ student: Student; offers: Offer[]; standing: Standing }>(`/api/students/${user.student_id}`).then(setRecord);
    }
  }, [user]);
  if (!record) return <p>Loading your placement record…</p>;
  return (
    <>
      <header className="page-head">
        <div>
          <h1>{record.student.full_name}</h1>
          <p className="lede">
            {record.student.course_name} · batch {record.student.batch}. You can read this record.
            Placement status and packages can be changed only by the Placement Cell.
          </p>
        </div>
        <Pill tone={toneFor(record.student.placement_status)}>{record.standing.placement_status_label}</Pill>
      </header>
      <article className="card">
        <h2>What the rules currently allow</h2>
        <p>{record.standing.further_allow.length ? record.standing.further_allow.join(", ") : "No further drive is open under the current rules."}</p>
        <ul>{record.standing.locks.map((lock) => <li key={lock}>{lock}</li>)}</ul>
        <Link className="button" to={`/students/${record.student.id}`}>Open the full record</Link>
      </article>
    </>
  );
}

function Stat({ label, value, note }: { label: string; value: number | string; note?: string }) {
  return (
    <div className="stat">
      <span>{label}</span>
      <b>{value}</b>
      {note && <em>{note}</em>}
    </div>
  );
}
