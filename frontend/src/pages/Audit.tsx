import { useEffect, useState } from "react";
import { api } from "../api";
import { Banner, Pill } from "../ui";

interface AuditRow {
  id: number;
  created_at: string;
  action: string;
  actor_email: string | null;
  actor_role: string | null;
  entity_type: string;
  before: unknown;
  after: unknown;
}

const SENSITIVE = ["offer.", "policy.", "user.", "student.archive", "student.exclusion", "student.export", "compliance.", "application."];

function isSensitive(action: string) {
  return SENSITIVE.some((prefix) => action.startsWith(prefix));
}

function describeChange(before: unknown, after: unknown) {
  if (!after || typeof after !== "object") return "—";
  const next = after as Record<string, unknown>;
  const previous = before && typeof before === "object" ? before as Record<string, unknown> : {};
  return Object.keys(next)
    .map((key) => {
      const was = previous[key];
      const now = next[key];
      if (was !== undefined && was !== now) return `${key}: ${String(was)} → ${String(now)}`;
      return `${key}: ${String(now)}`;
    })
    .join("; ");
}

export function AuditPage() {
  const [items, setItems] = useState<AuditRow[]>([]);
  const [verdict, setVerdict] = useState("");
  const [sensitiveOnly, setSensitiveOnly] = useState(true);

  function load() {
    api<{ items: AuditRow[] }>("/api/audit").then((payload) => setItems(payload.items));
  }

  useEffect(() => { load(); }, []);

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Audit</h1>
          <p className="lede">
            Package, placement, access, and policy changes record who acted, when, and the values before and after.
            Rows are hash-linked, so an altered record breaks the chain.
          </p>
        </div>
        <button
          type="button"
          onClick={async () => {
            const result = await api<{ valid: boolean; checked: number; failed_at: number | null }>("/api/audit/verify", { method: "POST" });
            setVerdict(result.valid ? `Chain intact across ${result.checked} rows.` : `Chain broke at row ${result.failed_at}.`);
            load();
          }}
        >
          Verify chain
        </button>
      </header>
      {verdict && <Banner tone={verdict.startsWith("Chain intact") ? "good" : "bad"}>{verdict}</Banner>}
      <label className="note">
        <input type="checkbox" checked={sensitiveOnly} onChange={(event) => setSensitiveOnly(event.target.checked)} /> Sensitive changes only
      </label>
      <div className="card">
        <table>
          <thead><tr><th>When</th><th>Actor</th><th>Action</th><th>Before → after</th></tr></thead>
          <tbody>
            {items.filter((item) => !sensitiveOnly || isSensitive(item.action || "")).map((item) => (
              <tr key={item.id}>
                <td>{item.created_at.replace("T", " ")}</td>
                <td>{item.actor_email}<div className="note">{item.actor_role}</div></td>
                <td>{item.action}{isSensitive(item.action || "") && <div><Pill tone="warn">Sensitive</Pill></div>}</td>
                <td className="note">{describeChange(item.before, item.after)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
