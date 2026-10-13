import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, api, formatNumber } from "../lib/api";
import { Banner, Pill } from "../components/ui";

interface ExceptionItem {
  id: string;
  kind: string;
  message: string;
  status: string;
  created_at: string;
  student_id: string;
  student_name: string;
  placement_id: string;
  offer_company: string | null;
  reasons: string[];
  history: Array<{ company: string; offer_type: string; acceptance_status: string; category: string | null; ctc_lpa: number | null }>;
  resolution_note: string | null;
  resolved_at: string | null;
  resolved_by: string | null;
}

export function ExceptionsPage() {
  const [items, setItems] = useState<ExceptionItem[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  function load() {
    api<{ items: ExceptionItem[] }>("/api/compliance").then((payload) => setItems(payload.items)).catch((err: ApiError) => setError(err.message));
  }

  useEffect(() => { load(); }, []);

  const open = items.filter((item) => item.status === "open");
  const closed = items.filter((item) => item.status !== "open");

  async function resolve(item: ExceptionItem) {
    const note = window.prompt(`Justification for ${item.student_name}`);
    if (!note || note.trim().length < 4) return;
    setError("");
    try {
      await api(`/api/compliance/${item.id}/resolve`, { method: "POST", body: JSON.stringify({ note: note.trim() }) });
      setMessage("Decision recorded with your name and the time.");
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not record the decision");
    }
  }

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Exceptions</h1>
          <p className="lede">
            A review, an expired offer, or an administrator override waits here. The applicable rule and the offer history stay with the case.
            Closing it records who approved it, when, and why.
          </p>
        </div>
      </header>
      {message && <Banner tone="good">{message}</Banner>}
      {error && <Banner tone="bad">{error}</Banner>}
      <section className="stack">
        {open.length === 0 && <article className="card"><p>No case is waiting for the Placement Cell.</p></article>}
        {open.map((item) => (
          <article className="card" key={item.id}>
            <div className="page-head">
              <div>
                <h2><Link to={`/students/${item.student_id}`}>{item.student_name}</Link></h2>
                <p className="note">{item.placement_id} · {item.created_at.replace("T", " ")} · {item.kind.replaceAll("_", " ")}</p>
              </div>
              <Pill tone="warn">Review</Pill>
            </div>
            <p>{item.message}</p>
            {item.reasons.length > 0 && (
              <ul>{item.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
            )}
            {item.history.length > 0 && (
              <p className="note">
                Offer history: {item.history.map((offer) => `${offer.company} ${offer.offer_type} ${offer.acceptance_status}${offer.ctc_lpa != null ? ` ${formatNumber(offer.ctc_lpa)} LPA` : ""}${offer.category ? ` ${offer.category}` : ""}`).join(" · ")}
              </p>
            )}
            <button type="button" onClick={() => resolve(item)}>Record decision</button>
          </article>
        ))}
      </section>
      {closed.length > 0 && (
        <section className="card">
          <h2>Decided</h2>
          <table>
            <thead><tr><th>Student</th><th>Case</th><th>Decision</th><th>By</th></tr></thead>
            <tbody>
              {closed.map((item) => (
                <tr key={item.id}>
                  <td>{item.student_name}</td>
                  <td>{item.message}</td>
                  <td>{item.resolution_note || "—"}</td>
                  <td>{item.resolved_by}<div className="note">{item.resolved_at?.replace("T", " ")}</div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </>
  );
}