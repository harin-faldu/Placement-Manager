from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.persistence.models import AuditLog


def write_audit(
    db: Session,
    *,
    actor_id: str | None,
    actor_email: str | None,
    actor_role: str | None,
    action: str,
    entity_type: str,
    entity_id: str | None,
    before: dict | None,
    after: dict | None,
    ip: str | None,
) -> AuditLog:
    previous = db.scalar(select(AuditLog.row_hash).order_by(AuditLog.id.desc()).limit(1))
    prev_hash = previous or "GENESIS"
    payload = json.dumps(
        {
            "action": action,
            "actor_email": actor_email,
            "actor_id": actor_id,
            "actor_role": actor_role,
            "after": after,
            "before": before,
            "entity_id": entity_id,
            "entity_type": entity_type,
            "at": utcnow().isoformat(timespec="seconds"),
        },
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    row_hash = hashlib.sha256(f"{prev_hash}|{payload}".encode()).hexdigest()
    row = AuditLog(ip=ip, prev_hash=prev_hash, payload=payload, row_hash=row_hash)
    db.add(row)
    db.flush()
    return row


def verify_chain(rows: list[AuditLog]) -> dict:
    previous = "GENESIS"
    for index, row in enumerate(rows, start=1):
        expected = hashlib.sha256(f"{previous}|{row.payload}".encode()).hexdigest()
        if row.prev_hash != previous or row.row_hash != expected:
            return {"valid": False, "checked": index - 1, "failed_at": row.id}
        previous = row.row_hash
    return {"valid": True, "checked": len(rows), "failed_at": None}
