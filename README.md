# NFSU Placement Cell

Policy-checked register for the 2026–27 placement session. Five capabilities carry it: a drive-by-drive policy engine, a hash-linked audit trail, server-side access limits, statistics that keep people and offers apart, and an exception queue that records who approved a review.

## Run

```powershell
docker compose up --build
```

Open http://localhost:8090

| Role | Email | Password |
| --- | --- | --- |
| Placement Administrator | admin@nfsu.ac.in | Admin@2026! |
| Placement Officer | officer@nfsu.ac.in | Officer@2026! |
| Course Coordinator, M.Tech. CS | coord.cs@nfsu.ac.in | Coord@2026! |
| Kavach Security recruiter | recruiter@kavach.example | Recruit@2026! |
| Student, Ananya Shah | ananya.shah@nfsu.ac.in | Student@2026! |

These accounts are for the prototype. The sign-in page repeats them so the register can be evaluated without a separate credential store.

## What it enforces

- A+ at 16 LPA or above leaves the process. Exactly 16 LPA is A+.
- Category A can move only to A+. Category B needs at least 1.5× the current package. Category C can move only upward.
- Internship only blocks another internship. FTE only blocks another FTE. Internship + PPO/FTE blocks other organisations.
- Where those rules meet, the stricter result is used. A higher package does not by itself reopen an FTE-only lock.
- Acceptance uses the company timeline or 24 hours, whichever is earlier.
- An unexcused absence excludes the next three drives unless the Placement Cell approves an emergency exception.

Stipend and annual CTC are stored and reported separately. Placed students are counted once; offers are counted as events.

The requirements, role boundaries, and the reasons this register is built this way are in [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md). Schema, controls, tests, backup, and limitations are in [docs/TECHNICAL.md](docs/TECHNICAL.md).

## Tests

```powershell
cd backend
python -m pytest
```
