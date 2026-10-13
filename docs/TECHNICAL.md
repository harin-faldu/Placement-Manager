# Technical notes

## Architecture

The browser talks only to the web container. Nginx serves the interface and proxies `/api` to the FastAPI application. The API uses SQLAlchemy with parameterised queries against Postgres. SQLite is used only for the automated tests.

Placement status, category, and package statistics are derived. Clients cannot submit a category or a placement status. When an offer is tied to a drive, the CTC and stipend are copied from the drive on the server.

## Schema

- `users`, `user_sessions`, `login_attempts`, `mfa_challenges` — accounts, revocable sessions, lockout, optional second factor.
- `students` — placement identity, encrypted mobile, mobile hash for duplicate detection, programme, batch, registration, eligibility, derived placement status, absence counter, archive time.
- `companies`, `drives` — recruiting organisations and the package, offer type, programmes, and cutoff for each drive.
- `offers`, `offer_events` — the offer ledger and the history of acceptance, joining, PPO, void, and expiry.
- `attendance`, `applications`, `exclusion_charges` — recruitment activity, policy decisions, and one exclusion charge per drive.
- `compliance_flags` — review, override, and expired-offer cases, including the justification and the officer who closed each one.
- `audit_logs` — append-only hash chain.
- `policy_config` — the single row of thresholds.

## Security controls

| Area | Control |
| --- | --- |
| Authentication | bcrypt passwords, generic failure text, five failures per email and IP in 15 minutes, optional TOTP |
| Session | HttpOnly, SameSite cookie, hashed token, idle and absolute timeout, logout revocation |
| Access | Server-side role checks and programme or company scope. Unknown or out-of-scope student IDs return 404 |
| Confidentiality | Mobile encrypted with Fernet. List and recruiter payloads omit contact and compensation. API responses use `Cache-Control: no-store` |
| Input | Pydantic validation, markup rejected in names, CSV size cap |
| Queries | SQLAlchemy bound parameters |
| Audit | Hash chain from a genesis value. Postgres and SQLite triggers reject update and delete |
| Export | Role-scoped, audited, not cached |
| Browser | Content Security Policy, frame denial, nosniff, and a required `X-Requested-With` header on changes |

The development key and password are in `docker-compose.yml` so the prototype starts without extra setup. Replace `SECRET_KEY`, `FERNET_KEY`, the database password, and the seeded passwords before any real data is stored. Put TLS in front of port 8090 and set `COOKIE_SECURE=true`.

## Backup

From the project directory, with the stack running:

```powershell
docker compose exec -T db pg_dump -U placement placement > backups\placement.sql
```

Restore into an empty database with `psql` or `docker compose exec -T db psql -U placement placement`. The dump contains personal data and should be stored with the same care as the database. This procedure was not executed against a second environment in this prototype.

## Tests

From `backend`:

```powershell
python -m pytest
```

Inside the stack:

```powershell
docker compose run --rm api python -m pytest
```

The tests cover category boundaries, offer-type locks, the 1.5× rule, absence review, unique placed-student statistics, duplicate Placement IDs, direct status assignment, programme isolation, recruiter redaction, drive precheck reasons hidden from companies, exception resolution, drive-package tampering, administrator override, export audit, the hash chain, idle timeout, optional MFA, login throttling, and a search string that attempts SQL injection.

## Limitations

- HTTP on port 8090 is for local evaluation. Transit encryption depends on a TLS proxy that is not included. Port 8080 is left free because it is often already taken by other local services.
- Application-layer encryption covers mobile numbers. The remaining columns rely on disk and database access control.
- The audit trigger stops ordinary updates. A database superuser can disable triggers.
- Package figures use decimal rounding to paise of an LPA, not integer currency subunits.
- Reports aggregate in the application. That is accurate at placement-cell scale and is not a warehouse.
- Seeded accounts and the sign-in panel exist for demonstration.
- Final disciplinary decisions stay with the Placement Cell. The software records an override; it does not invent one.
