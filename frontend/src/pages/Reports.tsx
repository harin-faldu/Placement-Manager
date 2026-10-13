import { useEffect, useState } from "react";
import { api, download, formatNumber } from "../api";
import { useAuth } from "../auth";
import type { Overview } from "../types";
import { Banner } from "../ui";

export function Reports() {
  const { user } = useAuth();
  const [report, setReport] = useState<Overview | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Overview>("/api/reports/overview").then(setReport).catch((err) => setError(err.message));
  }, []);

  if (error) return <Banner tone="bad">{error}</Banner>;
  if (!report?.totals) return <p>Preparing the placement report…</p>;
  const totals = report.totals;

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Placement report</h1>
          <p className="lede">Session {report.session}. {report.scope === "course" ? report.course_name : "All five programmes"}.</p>
        </div>
        <div className="actions noprint">
          <button type="button" className="secondary" onClick={() => window.print()}>Print</button>
          <button
            type="button"
            onClick={() => {
              if (window.confirm("This export contains contact details and will be written to the audit log. Continue?")) {
                download("/api/exports/students", "placement-students.csv");
              }
            }}
          >
            Export CSV
          </button>
        </div>
      </header>
      <section className="grid stats">
        <Figure label="Registered" value={totals.registered} />
        <Figure label="Eligible" value={totals.eligible} />
        <Figure label="Placed students" value={totals.placed} />
        <Figure label="Offer events" value={totals.offers} />
        <Figure label="Open for a further drive" value={totals.further_eligible} />
      </section>
      <section className="card">
        <h2>Course-wise outcomes</h2>
        <table>
          <thead>
            <tr>
              <th>Programme</th><th>Students</th><th>Registered</th><th>Placed</th><th>Unplaced</th><th>I</th><th>F</th><th>I+F</th><th>Median CTC</th>
            </tr>
          </thead>
          <tbody>
            {(report.by_course ?? []).map((row) => (
              <tr key={String(row.course)}>
                <td>{row.name}</td>
                <td>{row.students}</td>
                <td>{row.registered}</td>
                <td>{row.placed}</td>
                <td>{row.unplaced}</td>
                <td>{row.internship_only}</td>
                <td>{row.fte_only}</td>
                <td>{row.internship_ppo_fte}</td>
                <td>{formatNumber(row.median_ctc as number | null)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section className="grid split">
        <article className="card">
          <h2>Batch</h2>
          <table>
            <thead><tr><th>Batch</th><th>Registered</th><th>Placed</th><th>Unplaced</th><th>Median CTC</th></tr></thead>
            <tbody>
              {(report.by_batch ?? []).map((row) => (
                <tr key={String(row.batch)}>
                  <td>{row.batch}</td><td>{row.registered}</td><td>{row.placed}</td><td>{row.unplaced}</td>
                  <td>{formatNumber(row.median_ctc as number | null)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>
        <article className="card">
          <h2>Companies</h2>
          <table>
            <thead><tr><th>Company</th><th>Offers</th><th>Accepted</th><th>Categories</th><th>Avg CTC</th></tr></thead>
            <tbody>
              {(report.by_company ?? []).map((row) => (
                <tr key={String(row.company_id)}>
                  <td>{row.company}</td>
                  <td>{row.offers}</td>
                  <td>{row.accepted}</td>
                  <td>{Array.isArray(row.categories) ? row.categories.join(", ") : "—"}</td>
                  <td>{formatNumber(row.average_ctc as number | null)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>
      </section>
      <section className="card">
        <h2>How the figures are defined</h2>
        <dl>
          {Object.entries(report.definitions).map(([key, value]) => (
            <div key={key}><dt>{key}</dt><dd>{value}</dd></div>
          ))}
        </dl>
        {user?.role === "coordinator" && <p className="note">This report contains only your programme.</p>}
      </section>
    </>
  );
}

function Figure({ label, value }: { label: string; value: number }) {
  return <div className="stat"><span>{label}</span><b>{value}</b></div>;
}
