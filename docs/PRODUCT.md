# How the placement register works

This is the map for exploring the product. Open http://localhost:8090 beside this file. Passwords are in `.env`, and the sign-in page fills them in for the prototype accounts.

The register is the Placement Cell’s working record for the 2026–27 session. It keeps one student per Placement ID, records every offer as an event, and decides — before a drive is used — whether that student may enter. The decision is allow, block, or review, and it always names the rule.

Five programmes share the register:

| Code | Programme |
| --- | --- |
| `MTECH_CS` | M.Tech. Computer Science |
| `MTECH_AIDS` | M.Tech. Artificial Intelligence and Data Science |
| `BTECH_MTECH_CSE` | B.Tech.–M.Tech. Computer Science and Engineering |
| `MSC_CS` | M.Sc. Computer Science |
| `MSC_DFIS` | M.Sc. Digital Forensics and Information Security |

## What to click first

Sign in as the Placement Officer (`officer@nfsu.ac.in`). That account can see the policy, the students, and the drives, and it cannot change the rules or the account list. Use it to learn the product. Then repeat the same screens as administrator, coordinator, recruiter, and student. The sidebar changes with the role. A hidden page is still refused by the API.

| Role | Email | Start here |
| --- | --- | --- |
| Placement Administrator | admin@nfsu.ac.in | Access, then try an override on a blocked offer |
| Placement Officer | officer@nfsu.ac.in | Recruitment, then Exceptions |
| Course Coordinator, M.Tech. CS | coord.cs@nfsu.ac.in | Dashboard, then a student outside M.Tech. CS |
| Kavach Security recruiter | recruiter@kavach.example | Recruitment, Kavach FTE 2026 |
| Student, Ananya Shah | ananya.shah@nfsu.ac.in | My record |

## The placement workflow

This is the path a real drive follows. The software does not invent the offer. A person records it. The software refuses the record when the rules say no.

1. An administrator or officer creates the student and sets a password. That email and password are the student's sign-in. A registered, eligible student is included in drive checks immediately. Placement status is not typed in. It is derived later from accepted offers. An administrator can also open Access and attach a sign-in to a student record that does not have one yet.
2. The officer adds a company, then a drive. The drive carries the offer type, the CTC or stipend, the programmes, the CGPA cutoff, and the acceptance window. A later offer copied from that drive cannot claim a higher package than the drive.
3. Before names are shared, the officer opens the drive. The policy engine checks every student in the drive’s programmes and labels each row allow, block, or review, with the reason. Students who fail are withheld from the company. The company sees the allowed names and a withheld count, not the reasons.
4. The officer marks attendance. An unexcused absence excludes the student from the next three drives. An emergency claim waits for review and does not exclude anyone until it is rejected.
5. When a company makes an offer, the officer records it against the drive. The server copies type, CTC, and stipend from the drive, runs the same policy check, and either saves the offer, blocks it, or saves it and opens an exception.
6. Acceptance, decline, joining, PPO, and void are later events on that offer. The original package is not overwritten. Voiding keeps the row and writes a reason.
7. Accepting an offer refreshes the student’s placement status: unplaced, internship only, FTE only, or internship + PPO/FTE. The next drive is checked against that new standing.
8. Reports count placed students once and offer events separately. Monthly stipend is never added to annual CTC.
9. Anything sensitive — the offer, the policy, an archive, an exception — is appended to the audit chain with the actor, the time, and the before and after values.

## How one click is decided

The browser never talks to Postgres. Nginx in the web container serves the React app and forwards `/api` to FastAPI. FastAPI checks the session cookie, checks the role, loads the student and the drive, and calls `evaluate()` in `backend/app/domain/policy.py`. That function is pure: it does not write to the database. It returns a list of checks. Any failing check makes the verdict **block**. Otherwise any review check makes the verdict **review**. Otherwise the verdict is **allow**.

The screen then shows those checks. Saving an offer, listing candidates, and the drive precheck all call this same function, so the three screens cannot disagree.

Placement status, category (A+, A, B, C), and the package statistics are computed on the server. The client is not allowed to send them. Pydantic rejects extra fields, which is why a request that includes `placement_status` fails.

## The rules, in the order the engine applies them

Thresholds live in one policy row, seeded from `DEFAULT_CONFIG` in `backend/app/domain/catalog.py`. An administrator can change later decisions from the Policy screen. Past offers stay as they were recorded.

| Check | What it does |
| --- | --- |
| Registration | Only a registered student can proceed. |
| Eligibility | Ineligible blocks. Pending verification is a review. |
| Programme | The student’s course must be on the drive. |
| Company cutoff | CGPA below the drive cutoff blocks. A missing CGPA on a drive that has a cutoff is a review. |
| Attendance | Remaining absence exclusions block. A pending emergency claim is a review. |
| A+ exit | An accepted FTE or internship + PPO/FTE of 16 LPA or more takes the student out of the process. Exactly 16 LPA is A+. |
| Internship + PPO/FTE | An accepted I+F closes I, F, and I+F at every other organisation. Another role at the same organisation is a review. |
| Internship-only lock | After an internship-only selection, another internship-only role is blocked. FTE and I+F are not blocked by this lock. |
| FTE-only lock | After an FTE-only selection, another FTE-only role is blocked, even when the new package would satisfy the category rule. |
| FTE then I+F | Moving from FTE-only to internship + PPO/FTE is a review, unless an administrator changes that setting. |
| Category switch | Applied only when the new drive has an FTE package and the student already has an accepted FTE package. A may move only to A+. B needs at least 1.5× the current package. C may move only upward. Internship-only has no category ceiling. |
| Same organisation | An accepted offer of the same type at the same company blocks a duplicate. |

The stricter result wins. A higher package does not reopen an FTE-only lock.

Acceptance deadline is the earlier of the company’s stated hours and 24 hours, measured from 09:00 IST on the offer date.

## Roles

The sidebar is only a convenience. Every mutation is checked again in `backend/app/core/deps.py` (`require`) and, for a student record, in `can_read_student`. Asking for another student’s id returns 404, so the API does not reveal that the record exists.

### Placement Administrator

**Purpose.** Owns the register: who may sign in, what the rules are, and the rare case where a block must be set aside.

**Screens.** Dashboard, Students, Recruitment, Policy, Exceptions, Reports, Audit, Access.

**Can do.**

- Create, disable, and edit accounts, and reset someone’s authenticator.
- Create a student and the sign-in for that student in one step, then import, export, archive, and restore records. Attach a sign-in to an older record from Access.
- Create companies and drives, mark attendance, review an emergency absence, record offers.
- Change the policy thresholds. This is the only role that can.
- When an offer is blocked, record it anyway by typing a justification of at least eight characters. The offer is marked as an override, a compliance flag is opened, and the audit stores the reason.
- Close an exception, with a note that stores who decided and when.

**Cannot do.** Set placement status or category by hand. Change an offer’s CTC after it is saved. The package changes only by voiding the offer and recording a new event.

**Walk through.** Sign in, open Access, and see the five accounts. Open Policy and read the thresholds without saving. Open a student who already has an FTE offer, choose a second FTE drive, and submit. The checks explain the block. The justification field appears only after that block, and only for this role.

### Placement Officer

**Purpose.** Runs the day: students, drives, attendance, offers, and the exception queue. Does not own the rules or the account list.

**Screens.** Dashboard, Students, Recruitment, Policy, Exceptions, Reports, Audit.

**Can do.**

- Create and edit students, import them, export them, and adjust an absence exclusion.
- Create companies and drives, record applications, mark attendance, and approve or reject an emergency absence.
- Record, accept, decline, mark joined, and void offers.
- Read the policy and run a one-student check.
- Read the drive precheck, with reasons.
- Close an exception.
- Read and verify the audit chain.

**Cannot do.** Change policy. Archive or restore a student. Create accounts. Override a block. See another programme’s private data is not a limit here: an officer sees the whole session.

**Walk through.** Open Recruitment and select Kavach FTE 2026. The policy table lists who is allowed, who is blocked, and why. Rohan Mehta is blocked because an FTE-only selection is already on record and a Category A package may move only to A+. Open Exceptions. Open cases show the rule and the offer history. Closing one asks for a justification and then shows your email and the time under Decided.

### Course Coordinator

**Purpose.** Looks after one programme. The seeded coordinator is Kavita Rao, and she is bound to M.Tech. Computer Science.

**Screens.** Dashboard, Students, Policy, Reports. Recruitment is not in the sidebar.

**Can do.**

- See the dashboard, the student list, the export, and the reports for that one programme.
- Correct mobile, email, CGPA, and remarks on a student in that programme.
- Read the policy and run a check for a student in that programme.
- Open a student and read offer history.

**Cannot do.** See or edit another programme. A direct request for another student’s id returns 404. Change registration, eligibility, programme, or batch. Create students, drives, or offers. Change policy. See the exception queue or the audit. Archive anyone.

**Walk through.** The dashboard title is the programme, not “University register”. Search for a student from another course. The list does not contain them. Open Policy and check a student from M.Tech. CS. The same check against a student you do not coordinate is refused.

### Company / Recruiter

**Purpose.** See who the rules would allow into this company’s drives, and nothing else. The seeded recruiter is Neha Kulkarni at Kavach Security.

**Screens.** Dashboard, Recruitment.

**Can do.**

- See this company’s drives.
- See students the policy would allow: name, programme, batch, and CGPA.
- See how many students were withheld.

**Cannot do.** See the withheld names. See why someone was withheld. A request to the precheck URL returns 403. See Placement ID, email, mobile, offers, CTC, or stipend. See students for another company. Create drives or record offers.

**Walk through.** Open Recruitment. The page says companies see students the rules allow, and that withheld students are counted rather than named. Compare that screen with the officer’s policy table for the same drive. The officer has a reason on every row. The recruiter has a shorter list and a number.

### Student

**Purpose.** Read one record: their own. The seeded student is Ananya Shah, Placement ID `NFSU-2026-007`, unplaced, M.Tech. Computer Science.

**Screens.** Dashboard, and My record. My record is the Students link, renamed.

**Can do.**

- Read her own profile, the rules that currently apply, her offers, and her attendance.
- Read the history of one of her own offers.

**Cannot do.** Edit the profile, an offer, a package, or a status. Open another student’s URL. See the register, the drives, the policy settings, the reports, the exceptions, or the audit.

**Walk through.** The dashboard says what further drives the rules would allow. My record is the same student. Paste another student’s id into the address bar. The API responds as if that record is not there.

## What each screen is for

| Screen | Route | What you are looking at |
| --- | --- | --- |
| Sign in | `/login` | Password, then an authenticator code if that account has one. Prototype passwords are filled from `.env` when the interface is built. |
| Dashboard | `/` | Session figures for the role’s scope. Placed students and offer events are separate. CTC and stipend are separate. Officers also see who needs a decision. |
| Students | `/students` | Search, filter, create, import, export. A student is sent straight to their own record. |
| Student | `/students/:id` | Standing, offers, attendance, and — for officer and administrator — the form that checks and records an offer. |
| Recruitment | `/recruitment` | Companies, drives, the precheck, attendance, and the redacted candidate list. |
| Policy | `/policy` | The live thresholds, and a one-student check that prints every clause. |
| Exceptions | `/exceptions` | Open reviews, expired offers, and overrides. Closing a case stores the note, the person, and the time. |
| Reports | `/reports` | Course and batch outcomes, median, average, and highest FTE, and who can still enter a later drive. |
| Audit | `/audit` | Who changed what, the before and after values, and a check that the hash chain is intact. |
| Access | `/access` | Accounts and the optional authenticator. Administrator only. |

## What is stored, and what is calculated

Stored in Postgres (`backend/app/persistence/models.py`):

| Table | Why it exists |
| --- | --- |
| `users`, `user_sessions`, `login_attempts`, `mfa_challenges` | Accounts, revocable sessions, lockout, optional second factor. The session token in the cookie is random. The database stores only its hash. |
| `students` | Placement identity. Mobile is encrypted. A hash of the mobile stops duplicates without storing the number in the clear. |
| `companies`, `drives` | Who is recruiting, and the package, type, programmes, and cutoff for each drive. |
| `offers`, `offer_events` | The offer, and the later history of acceptance, joining, PPO, void, and expiry. |
| `attendance`, `applications`, `exclusion_charges` | Who attended, who was put forward, and the one exclusion charged per drive. |
| `compliance_flags` | A review, an override, or an expired offer, plus the note and the person who closed it. |
| `audit_logs` | Append-only hash chain. The database trigger refuses update and delete. |
| `policy_config` | The single row of thresholds. |

Calculated, not stored as something a client may set:

- Placement status, from accepted offers that have not been voided.
- Category, from the highest accepted FTE or internship + PPO/FTE CTC.
- Package statistics, from that same per-student figure. Stipend statistics use the highest accepted monthly stipend.
- The next-drive verdict, from `evaluate()`.

## Where the files are, and why

### The running system

| File | Why it is there |
| --- | --- |
| `docker-compose.yml` | Starts Postgres, the API, and the web server. It does not contain passwords. It reads them from `.env`. |
| `.env` | Database password, signing key, encryption key, and the five prototype passwords. Git ignores this file. |
| `.env.example` | The same names with placeholders, so another machine knows what to set. |
| `frontend/Dockerfile` | Builds the interface. Prototype passwords are passed in at build time so the sign-in page can show them. |
| `backend/Dockerfile` | Runs the API as a non-root user. |
| `frontend/nginx.conf` | Serves the built interface and proxies `/api`. |

A request enters nginx, is proxied to FastAPI, and FastAPI uses SQLAlchemy with bound parameters. Tests use an in-memory SQLite database instead of Postgres, with the same models.

### Backend

`backend/app/main.py` is the front door. On startup it creates tables, adds any missing column, installs the audit trigger, and seeds the demo only when the database is empty. It then mounts the routers and requires the `X-Requested-With: placement` header on every change, so a foreign page cannot silently submit a form.

| Folder | File | What it is responsible for |
| --- | --- | --- |
| `core` | `config.py` | Reads `.env`. Refuses to start without the database URL, the signing key, and the encryption key. |
| `core` | `database.py` | The engine, the session, the small schema patch, and the audit trigger. |
| `core` | `deps.py` | “Who is signed in?” and “is this role allowed?”. Idle timeout is 30 minutes. The absolute session limit is 8 hours. |
| `core` | `security.py` | Password hashing, the session-token hash, Fernet encryption of mobile numbers, and the mobile digest. |
| `core` | `http.py` | One shape for errors, including a policy block that carries the checks back to the screen. |
| `core` | `clock.py` | UTC for timestamps, and the IST calendar day used for offer dates and the 09:00 acceptance clock. |
| `domain` | `catalog.py` | The five programmes, the role labels, and the default policy numbers. Also the small snapshots the engine reads, so the engine does not depend on the database. |
| `domain` | `policy.py` | The rules. `evaluate` decides a drive. `standing` and `further_paths` describe what a student may still do. `acceptance_window` computes the deadline. |
| `domain` | `stats.py` | Counts unique placed students, separates stipend from CTC, and computes median, average, and highest. |
| `domain` | `validate.py` | Cleans names, emails, mobiles, Placement IDs, and money. Rejects markup in names. |
| `persistence` | `models.py` | The tables. |
| `persistence` | `schemas.py` | What a request is allowed to contain. Unknown fields are rejected. |
| `persistence` | `audit.py` | Writes the next hash-linked row and verifies the chain from a genesis value. |
| `persistence` | `seed.py` | The demo students, companies, drives, offers, and accounts. Passwords come from `.env`. If any user already exists, it does nothing. |
| `services` | `placement.py` | The operations the routers share: load policy, snapshot a student, refresh placement status, explain a drive, redact a recruiter’s list, and shape the records the screens receive. |
| `routers` | `auth.py` | Sign-in, lockout after five failures in 15 minutes, optional authenticator, sign-out. |
| `routers` | `students.py` | List, create, edit, archive, import, export, and the single-student read. |
| `routers` | `offers.py` | Record, update, void, and history. This is where a block becomes a 409, a review becomes a flag, and an administrator override is recorded. |
| `routers` | `recruitment.py` | Companies, drives, candidates, precheck, applications, attendance. |
| `routers` | `policy.py` | Read and update thresholds, the one-student check, and the exception queue. |
| `routers` | `reports.py` | The overview each role is allowed to see. |
| `routers` | `audit.py` | The log and the chain check. |
| `routers` | `users.py` | Accounts. Administrator only. |
| `tests` | `test_policy.py`, `test_stats.py`, `test_api.py` | The rules, the statistics, and the role boundaries. The API tests include a student asking for someone else’s record, a recruiter asking for the precheck, and an officer resolving an exception. |

### Frontend

The interface is a set of pages over one API client. It does not reimplement the rules. When a save is blocked, it displays the checks the server returned.

| File | What it is responsible for |
| --- | --- |
| `src/main.tsx` | Starts React, the router, and the signed-in state. |
| `src/App.tsx` | The routes. Anything except the sign-in page requires a session. |
| `src/components/ui.tsx` | The sidebar, which items each role sees, and the small pieces used on every page: pills, banners, policy checks, and the student search box. |
| `src/lib/api.ts` | `fetch` to `/api`, the session cookie, and the header required on changes. |
| `src/lib/auth.tsx` | Asks `/api/auth/me` on load and keeps the current user. |
| `src/lib/types.ts` | The shapes the pages expect from the API. |
| `src/styles/global.css` | Layout and spacing. |
| `src/pages/Login.tsx` | Sign-in, and the prototype account buttons. |
| `src/pages/Dashboard.tsx` | Three different home screens: the cell, the recruiter, and the student. |
| `src/pages/Students.tsx` | The directory and the create form. |
| `src/pages/StudentDetail.tsx` | One student, their offers, and the record-an-offer form. |
| `src/pages/Recruitment.tsx` | Drives, the precheck for the cell, and the redacted list for a company. |
| `src/pages/Policy.tsx` | Thresholds and a single check. |
| `src/pages/Exceptions.tsx` | The queue and the decision note. |
| `src/pages/Reports.tsx` | The printable outcomes. |
| `src/pages/Audit.tsx` | The chain, with sensitive rows called out. |
| `src/pages/Access.tsx` | Accounts and the authenticator setup. |

## A few things worth noticing while you explore

- Refresh the dashboard after recording an accepted offer. The placed-student count moves because the status was derived, not because a form field was edited.
- Void an offer and look at the offer history. The voided row remains. The student’s status is recalculated from what is still accepted.
- On Audit, turn on “Sensitive changes only”, then record an offer or close an exception. The new row shows the actor and the before and after values. “Verify chain” walks the hashes.
- Sign in as the student and request the officer’s student id. The interesting result is 404, from the server, not a hidden button.
- Sign in as the recruiter and compare Kavach FTE 2026 with the officer’s precheck of the same drive.

The register assists the Placement Cell. An override is recorded. It is not silent, and it does not replace the person who is allowed to make the exception.
