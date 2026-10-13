import { FormEvent, useEffect, useState } from "react";
import { ApiError, api } from "../api";
import { useAuth } from "../auth";
import type { Drive, Evaluation, Student } from "../types";
import { Banner, Checks, StudentPicker } from "../ui";

interface PolicyPayload {
  narrative: string[];
  config: Record<string, number | boolean | string>;
  can_edit: boolean;
}

export function PolicyPage() {
  const { user } = useAuth();
  const [policy, setPolicy] = useState<PolicyPayload | null>(null);
  const [drives, setDrives] = useState<Drive[]>([]);
  const [student, setStudent] = useState<Student | null>(null);
  const [driveId, setDriveId] = useState("");
  const [result, setResult] = useState<Evaluation | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<PolicyPayload>("/api/policy").then(setPolicy);
    if (user && user.role !== "student" && user.role !== "recruiter") {
      api<{ items: Drive[] }>("/api/drives").then((payload) => setDrives(payload.items));
    }
  }, [user]);

  async function check(event: FormEvent) {
    event.preventDefault();
    if (!student || !driveId) return;
    setError("");
    try {
      setResult(await api<Evaluation>("/api/policy/check", {
        method: "POST",
        body: JSON.stringify({ student_id: student.id, drive_id: driveId }),
      }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not run the check");
    }
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!policy) return;
    const next = await api<PolicyPayload>("/api/policy", { method: "PUT", body: JSON.stringify(policy.config) });
    setPolicy({ ...policy, narrative: next.narrative, config: next.config });
  }

  if (!policy) return <p>Loading the placement rules…</p>;

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Policy</h1>
          <p className="lede">Every participation check explains the clause that passed, blocked, or needs review. The stricter result stands. Cases that need a person are listed under Exceptions.</p>
        </div>
      </header>
      <section className="grid split">
        <article className="card">
          <h2>Session rules</h2>
          <ol>
            {policy.narrative.map((line) => <li key={line}>{line}</li>)}
          </ol>
        </article>
        {user?.role !== "recruiter" && user?.role !== "student" && (
          <form className="card stack" onSubmit={check}>
            <h2>Check a student against a drive</h2>
            <StudentPicker onSelect={setStudent} />
            <label>
              Drive
              <select value={driveId} onChange={(event) => setDriveId(event.target.value)} required>
                <option value="">Select</option>
                {drives.map((drive) => <option key={drive.id} value={drive.id}>{drive.company_name} — {drive.title}</option>)}
              </select>
            </label>
            <button type="submit">Explain the decision</button>
            {error && <Banner tone="bad">{error}</Banner>}
            {result && (
              <>
                <Banner tone={result.verdict === "allow" ? "good" : result.verdict === "block" ? "bad" : "warn"}>
                  {result.verdict === "allow" ? "Allowed" : result.verdict === "block" ? "Blocked" : "Needs review"}
                  {result.governing_category ? ` · current category ${result.governing_category}` : ""}
                </Banner>
                <Checks checks={result.checks} />
              </>
            )}
          </form>
        )}
      </section>
      {policy.can_edit && (
        <form className="card stack" onSubmit={save}>
          <h2>Thresholds</h2>
          <p className="note">Changing a threshold changes later decisions. It does not rewrite offers already on the ledger.</p>
          <div className="filters">
            {([
              ["a_plus_min", "A+ from"],
              ["a_min", "A from"],
              ["b_min", "B from"],
              ["b_multiplier", "B multiplier"],
              ["acceptance_hours_cap", "Acceptance cap, hours"],
              ["absence_exclusion_drives", "Absence exclusion"],
            ] as const).map(([key, label]) => (
              <label key={key}>
                {label}
                <input
                  type="number"
                  step="0.1"
                  value={String(policy.config[key])}
                  onChange={(event) => setPolicy({ ...policy, config: { ...policy.config, [key]: Number(event.target.value) } })}
                />
              </label>
            ))}
          </div>
          <label>
            <input
              type="checkbox"
              checked={Boolean(policy.config.a_plus_exits_process)}
              onChange={(event) => setPolicy({ ...policy, config: { ...policy.config, a_plus_exits_process: event.target.checked } })}
            />
            A+ selection leaves the process
          </label>
          <label>
            <input
              type="checkbox"
              checked={Boolean(policy.config.category_can_override_fte_lock)}
              onChange={(event) => setPolicy({ ...policy, config: { ...policy.config, category_can_override_fte_lock: event.target.checked } })}
            />
            Let a qualifying category switch override the FTE-only lock
          </label>
          <button type="submit">Save thresholds</button>
        </form>
      )}
    </>
  );
}
