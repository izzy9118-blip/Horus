# Horus Charter

## The File Standard

One file per principal. Persons and bodies are never merged: persons get conduct records; bodies get structure and faction records.

Tiers, in mandatory order:

- **T1 OWN WORDS** — speeches, decrees, signed texts, official transcripts from the principal's own channels. Quotations short and cited.
- **T2 CONDUCT** — dated acts only. What was done, when, per what source.
- **T3 PERSONNEL** — appointments, dismissals, command changes, read as documented events (interpretation belongs to ministers, not Horus).
- **T4 FIELD** — what is held, taken, lost, deployed, signed, paid. The material state, dated.
- **T5 OTHERS' ACCOUNTS** — what adversaries, allies, mediators, and press say, admitted last, each marked with whose account it is.

Every file header: principal name; person|body; assembly date; per-tier last-refresh date; per-tier status (FILLED | THIN | EMPTY); completeness: PENDING_PROBE.

## Decay

Tiers age at different speeds. Default tolerances (owner may override per board): T1 90 days; T2 30 days; T3 60 days; T4 7 days for war boards / 90 days otherwise; T5 30 days. A tier past tolerance is STALE and must be flagged in any parity manifest that cites it.

## The Parity Gate

Per board: `manifests/<board>-<date>.yaml` listing every principal on the board, each file's per-tier status and staleness, and the gate verdict: PASS only if all principals' files exist with T1, T2, T4 FILLED and within tolerance. Otherwise: HOLD, with the gaps named. No minister deed may fire across a HOLD without carrying the mark. Bias enters as file depth; the gate makes depth visible before thought.

## The Boundary

Horus gathers; Horus never judges. Outputs are records in briefing language. The moment the eyes editorialize, the invisible curator returns. Ministers query Horus; queries are logged publicly in `queries.log`.
