# NFSU Placement Cell

Policy-checked register for the 2026–27 placement session. Five capabilities carry it: a drive-by-drive policy engine, a hash-linked audit trail, server-side access limits, statistics that keep people and offers apart, and an exception queue that records who approved a review.

## Run

```powershell
docker compose up --build
```

Open http://localhost:8090

| Role | Email |
| --- | --- |
| Placement Administrator | admin@nfsu.ac.in |
| Placement Officer | officer@nfsu.ac.in |
| Course Coordinator, M.Tech. CS | coord.cs@nfsu.ac.in |
| Kavach Security recruiter | recruiter@kavach.example |
| Student, Ananya Shah | ananya.shah@nfsu.ac.in |

Passwords, the database login, and the encryption keys are in `.env`. Copy `.env.example` to `.env` before the first start. The sign-in page shows the prototype passwords from that file.

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
