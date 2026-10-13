import { FormEvent, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { ApiError, api, formatNumber, todayInput } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { Drive, Evaluation, Offer, Standing, Student } from "../lib/types";
import { Banner, Checks, Pill, toneFor } from "../components/ui";

interface Detail {
  student: Student;
  offers: Offer[];
  attendance: Array<{ id: string; drive_title: string | null; activity: string; attended: boolean; review_status: string; note: string | null }>;
  standing: Standing;
}

export function StudentDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const [detail, setDetail] = useState<Detail | null>(null);
  const [drives, setDrives] = useState<Drive[]>([]);
  const [driveId, setDriveId] = useState("");
  const [offerDate, setOfferDate] = useState(todayInput());
  const [acceptance, setAcceptance] = useState("pending");
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [overrideReason, setOverrideReason] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const canEdit = user?.role === "admin" || user?.role === "officer";

  function load() {
    if (!id) return;
    api<Detail>(`/api/students/${id}`).then(setDetail).catch((err: ApiError) => setError(err.message));
  }

  useEffect(() => {
    load();
    if (canEdit) api<{ items: Drive[] }>("/api/drives").then((payload) => setDrives(payload.items));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, canEdit]);

  async function recordOffer(event: FormEvent) {
    event.preventDefault();
    setError("");
    setMessage("");
    setEvaluation(null);
    try {
      const payload = await api<{ offer: Offer; evaluation: Evaluation }>("/api/offers", {
        method: "POST",
        body: JSON.stringify({
          student_id: id,
          drive_id: driveId,
          offer_date: offerDate,
          acceptance_status: acceptance,
          override_reason: user?.role === "admin" && overrideReason.trim().length >= 8 ? overrideReason.trim() : undefined,
        }),
      });
      setOverrideReason("");
      setEvaluation(payload.evaluation);
      setMessage(payload.evaluation.verdict === "review" ? "Offer recorded and referred for review." : "Offer recorded on the ledger.");
      load();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
        setEvaluation(err.evaluation);
      }
    }
  }

  async function patchOffer(offerId: string, body: Record<string, string>) {
    setError("");
    try {
      await api(`/api/offers/${offerId}`, { method: "PATCH", body: JSON.stringify(body) });
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not update the offer");
    }
  }

  if (error && !detail) return <Banner tone="bad">{error}</Banner>;
  if (!detail) return <p>Opening the student record…</p>;
  const student = detail.student;

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">{student.placement_id}</p>
          <h1>{student.full_name}</h1>
          <p className="lede">{student.course_name} · batch {student.batch}{student.cgpa != null ? ` · CGPA ${student.cgpa.toFixed(2)}` : ""}</p>
        </div>
        <div className="actions">
          <Pill tone={toneFor(student.registration_status)}>{student.registration_label}</Pill>
          <Pill tone={toneFor(student.eligibility_status)}>{student.eligibility_label}</Pill>
          <Pill tone={toneFor(student.placement_status)}>{student.placement_status_label}</Pill>
        </div>
      </header>
      <section className="grid split">
        <article className="card">
          <h2>Standing</h2>
          <p>
            {detail.standing.governing_category
              ? `Governing package ${formatNumber(detail.standing.governing_ctc)} LPA · category ${detail.standing.governing_category}`
              : "No accepted FTE package is governing this record."}
          </p>
          <p className="note">
            Further paths the rules would allow: {detail.standing.further_allow.length ? detail.standing.further_allow.join(", ") : "none"}.
            {detail.standing.further_review.length ? ` Referred: ${detail.standing.further_review.join(", ")}.` : ""}
          </p>
          <ul>{detail.standing.locks.map((lock) => <li key={lock}>{lock}</li>)}</ul>
          {student.email && <p>Email {student.email}<br />Mobile {student.mobile}</p>}
          {student.remarks && <p className="note">{student.remarks}</p>}
        </article>
        <article className="card">
          <h2>Contact and control</h2>
          <p className="note">Compensation and contact stay with roles that are allowed to see this programme. A student cannot change an outcome.</p>
          {canEdit && student.exclusion_drives_remaining > 0 && (
            <button
              className="secondary"
              onClick={async () => {
                const reason = window.prompt("Reason for clearing the absence exclusion");
                if (!reason) return;
                await api(`/api/students/${student.id}/exclusion`, { method: "POST", body: JSON.stringify({ action: "clear", reason }) });
                load();
              }}
            >
              Clear exclusion ({student.exclusion_drives_remaining} drives)
            </button>
          )}
          {user?.role === "admin" && (
            <button
              className="secondary"
              onClick={async () => {
                const path = student.archived ? "restore" : "archive";
                if (!window.confirm(student.archived ? "Restore this record?" : "Archive this record? Offer history is kept.")) return;
                await api(`/api/students/${student.id}/${path}`, { method: "POST" });
                load();
              }}
            >
              {student.archived ? "Restore record" : "Archive record"}
            </button>
          )}
        </article>
      </section>
      <section className="card">
        <h2>Offer ledger</h2>
        <p className="note">Each offer is an event. Package and type are not overwritten; a correction is a new event after the old one is voided.</p>
        <table>
          <thead>
            <tr><th>Company</th><th>Type</th><th>Package</th><th>Acceptance</th><th>Joining</th><th>PPO</th><th></th></tr>
          </thead>
          <tbody>
            {detail.offers.map((offer) => (
              <tr key={offer.id}>
                <td>
                  {offer.company_name}
                  {offer.is_off_campus ? " · off campus" : ""}
                  {offer.voided ? " · void" : ""}
                  <div className="note">{offer.offer_date}{offer.acceptance_deadline ? ` · deadline ${offer.acceptance_deadline.replace("T", " ").slice(0, 16)} UTC` : ""}</div>
                </td>
                <td>{offer.offer_type_label}{offer.category ? ` · ${offer.category}` : ""}</td>
                <td>
                  {offer.ctc_lpa != null ? `${formatNumber(offer.ctc_lpa)} LPA` : "—"}
                  {offer.stipend_amount != null ? <div className="note">Stipend {formatNumber(offer.stipend_amount, 0)} {offer.stipend_period}</div> : null}
                </td>
                <td><Pill tone={toneFor(offer.acceptance_status)}>{offer.acceptance_status}</Pill></td>
                <td>{offer.joining_status}</td>
                <td>{offer.ppo_status}</td>
                <td>
                  {canEdit && !offer.voided && (
                    <div className="actions">
                      {offer.acceptance_status === "pending" && (
                        <button type="button" onClick={() => patchOffer(offer.id, { acceptance_status: "accepted" })}>Accept</button>
                      )}
                      {offer.acceptance_status === "pending" && (
                        <button type="button" className="secondary" onClick={() => patchOffer(offer.id, { acceptance_status: "declined" })}>Decline</button>
                      )}
                      {offer.acceptance_status === "accepted" && offer.joining_status !== "joined" && (
                        <button type="button" className="secondary" onClick={() => patchOffer(offer.id, { joining_status: "joined" })}>Joined</button>
                      )}
                      <button
                        type="button"
                        className="secondary"
                        onClick={async () => {
                          const reason = window.prompt("Reason for voiding this offer");
                          if (!reason) return;
                          await api(`/api/offers/${offer.id}/void`, { method: "POST", body: JSON.stringify({ reason }) });
                          load();
                        }}
                      >
                        Void
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      {canEdit && (
        <form className="card stack" onSubmit={recordOffer}>
          <h2>Record an offer</h2>
          <div className="filters">
            <label className="grow">
              Drive
              <select value={driveId} onChange={(event) => setDriveId(event.target.value)} required>
                <option value="">Select a drive</option>
                {drives.map((drive) => (
                  <option key={drive.id} value={drive.id}>
                    {drive.company_name} — {drive.title}
                  </option>
                ))}
              </select>
            </label>
            <label>Offer date<input type="date" value={offerDate} onChange={(event) => setOfferDate(event.target.value)} required /></label>
            <label>
              Acceptance
              <select value={acceptance} onChange={(event) => setAcceptance(event.target.value)}>
                <option value="pending">Pending</option>
                <option value="accepted">Accepted</option>
                <option value="declined">Declined</option>
              </select>
            </label>
            <button type="submit">Check and record</button>
          </div>
          <p className="note">The package is taken from the drive. A blocked offer is not saved unless an administrator records a justification of at least eight characters.</p>
          {user?.role === "admin" && evaluation?.verdict === "block" && (
            <label className="grow">
              Administrator justification
              <input value={overrideReason} onChange={(event) => setOverrideReason(event.target.value)} minLength={8} placeholder="Why this block is being overridden" />
            </label>
          )}
          {message && <Banner tone="good">{message}</Banner>}
          {error && <Banner tone="bad">{error}</Banner>}
          {evaluation && <Checks checks={evaluation.checks} />}
        </form>
      )}
      <section className="card">
        <h2>Attendance</h2>
        {detail.attendance.length === 0 && <p className="note">No recruitment activity is recorded yet.</p>}
        <ul>
          {detail.attendance.map((row) => (
            <li key={row.id}>
              {row.drive_title} · {row.activity} · {row.attended ? "attended" : "absent"} · {row.review_status}
              {row.note ? ` · ${row.note}` : ""}
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
