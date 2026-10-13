# Requirements

Session 2026–27 placement register for the NFSU Placement Cell.

## Roles

| Role | What they can do |
| --- | --- |
| Placement Administrator | Full register, policy thresholds, accounts, archive/restore, audited overrides |
| Placement Officer | Students, drives, offers, attendance, reports, audit. No account administration and no archive |
| Course Coordinator | One programme. Can correct contact, CGPA, and remarks. Cannot change registration, eligibility, offers, or other programmes |
| Company / Recruiter | Own drives only. Sees students the policy would allow, without phone, email, or compensation. Withheld students are counted, not named |
| Student | Own record only. Cannot change placement status, packages, or offers |

The student role is required by the security challenge: a student must not be able to alter an outcome or read another student's confidential record.

## Functional requirements

- Student register with a unique Placement ID, name, mobile, email, one of the five programmes, batch, registration, eligibility, and derived placement status.
- Placement status is Unplaced, Internship only, FTE only, or Internship + PPO/FTE. It is calculated from accepted offers.
- Offers keep history. Package and offer type are not edited in place. A correction voids the old event and records a new one.
- Offer types I, F, and I+F, with stipend and annual CTC stored separately.
- PPO, acceptance, joining, offer date, off-campus flag, and NOC.
- Company drives, attendance at talks, tests, and interviews, and absence exclusions.
- Policy checks for registration, eligibility, programme, company CGPA cutoff, absence, A+ exit, offer-type locks, and category switching.
- Each check returns allow, block, or review, with the clause that produced it.
- Acceptance deadline is the company timeline or 24 hours, whichever is earlier, starting at 09:00 IST on the offer date.
- Dashboard and reports: registered, eligible, ineligible, placed, unplaced; course and batch outcomes; offer-type counts; company offers; highest, average, and median CTC; stipend statistics kept separate; students still open for a further drive; pending acceptance, joining, and compliance.
- Placed students are unique people. Offer events are counted separately.
- CSV import and audited CSV export.
- Optional time-based second factor.

## Category rules

- A+: 16 LPA and above. The student leaves the process. Exactly 16 LPA is A+.
- A: 10 LPA up to, but not including, 16. A further packaged offer is allowed only in A+.
- B: 6 LPA up to, but not including, 10. A further package must be at least 1.5 times the current package.
- C: below 6 LPA. Only a higher category is allowed.

Offer-type rules also apply, and the stricter result wins. After an FTE-only selection, another FTE-only role is closed even when the category table would allow a higher package. A move from FTE-only to internship + PPO/FTE is referred for review.

## Non-functional requirements

- Passwords hashed with bcrypt. Sessions are random tokens stored only as hashes, with an 8-hour absolute lifetime and a 30-minute idle timeout.
- Role checks run on the server. The interface hiding a button is not the control.
- Mobile numbers are encrypted at the application layer. Contact and compensation are omitted from responses the role cannot see.
- Queries are parameterised. Names reject markup. Mutating requests must carry the application header.
- Audit rows store actor, time, action, and before/after values. Each row hashes the previous row. The database rejects updates and deletes of the log.
- Placement ID, email, and mobile are unique. Placement status cannot be written directly.
- Exports are limited to authorised roles, sent with `Cache-Control: no-store`, and written to the audit log.
- The prototype runs as Docker Compose: Postgres, API, and the web interface.

## The five distinguishing capabilities

1. **Real-time placement policy engine.** Before a drive is used, the register checks eligibility, existing offers, company category, and switching rules. A+, A, B, and C, and the I, F, and I+F locks, each produce allow, block, or review with a stated reason.
2. **Tamper-evident placement audit trail.** Sensitive changes store the actor, time, action, and before/after values. Hash-linked rows make a later alteration detectable. Offer events stay on the ledger.
3. **Security-first access.** A student cannot change an offer or package. A coordinator sees one programme. A recruiter receives names the policy would allow, without contact details, compensation, or the reason someone was withheld. Those limits are enforced on the server, including against direct requests for another student's record.
4. **Trustworthy placement analytics.** Unique placed students are counted apart from offer events. Monthly stipends are counted apart from annual FTE CTC. Reports include course and batch outcomes, median, average, and highest packages, and who can still enter a later drive.
5. **Explainable decisions and exceptions.** A blocked or referred student carries the rule and the offer history. An authorised officer records the justification. The audit keeps who approved it and when.
