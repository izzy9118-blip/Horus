# Horus Charter

## The File Standard

One file per principal. Persons and bodies are never merged: persons get conduct records; bodies get structure and faction records.

Tiers, in mandatory order:

- **T1 OWN WORDS** — speeches, decrees, signed texts, official transcripts from the principal's own channels, **in the principal's own language**. Quotations short and cited. T1 is FILLED only if it holds original-language primary matter: the Russian transcript, the Ukrainian decree, the German Regierungserklärung as delivered. Translations and English renderings of a non-anglophone principal's words are admissible as supplements, marked as translations, and they do **not** fill the tier. Without original-language primary matter T1 is THIN, however much translated material it holds. For an anglophone principal the original language is English and this rule adds nothing; for every other principal it is the whole of the tier.
- **T2 CONDUCT** — dated acts only. What was done, when, per what source.
- **T3 PERSONNEL** — appointments, dismissals, command changes, read as documented events (interpretation belongs to ministers, not Horus).
- **T4 FIELD** — what is held, taken, lost, deployed, signed, paid. The material state, dated.
- **T5 OTHERS' ACCOUNTS** — what adversaries, allies, mediators, and press say, admitted last, each marked with whose account it is.

Every file header: principal name; person|body; assembly date; per-tier last-refresh date; per-tier status (FILLED | THIN | EMPTY); T1 language; T1 language state (ORIGINAL | TRANSLATION_ONLY | NONE); completeness: PENDING_PROBE.

## The Language of the Ground

A principal heard only in translation has not been heard. Translation is an account of the words, and an account of a thing is outranked by the thing; a rendering carries the renderer's choices, and those choices are invisible in the rendered text.

Original-language secondary sources are not primary matter either, and they are the harder trap: commentary in the principal's own language reads as the principal's own voice. The tier is filled by what the principal issued through his own channel, not by what was written about him in the language he speaks.

The mark is per principal and it travels with every judgment drawn from the file: no reading of a principal may stand above the tier at which that principal was actually heard.

## Decay

Tiers age at different speeds. Default tolerances (owner may override per board): T1 90 days; T2 30 days; T3 60 days; T4 7 days for war boards / 90 days otherwise; T5 30 days. A tier past tolerance is STALE and must be flagged in any parity manifest that cites it.

## The Parity Gate

Per board: `manifests/<board>-<date>.yaml` listing every principal on the board, each file's per-tier status and staleness, and the gate verdict: PASS only if all principals' files exist with T1, T2, T4 FILLED and within tolerance. Otherwise: HOLD, with the gaps named. No minister deed may fire across a HOLD without carrying the mark. Bias enters as file depth; the gate makes depth visible before thought.

The manifest records, per principal, the language of the T1 material and whether that material is original or translated. A T1 declared FILLED on translation alone is a gap, not a fill, and the gate names it as one. A board on which any principal is heard only in translation or in commentary carries that mark in its PASS/HOLD reasoning, and the mark travels into any run made across it.

Bias enters as file depth — and depth has a language. A thick file of translations is a thin file wearing a thick coat.

## Minister-Directed Gathering

Every reasoned ministerial run must contain at least one explicit Minister-to-Horus query before final judgment. The request is itself an attributable Assembly record.

A minister may specify:

- what information is needed;
- why the information is material to the inquiry;
- what evidentiary characteristics would count as adequate ground;
- acceptable evidence tiers, language requirements, principal scope, and time scope;
- substitutions that would not answer the request; and
- a specifically identified document when the minister's method or corpus makes that document itself material.

A minister does **not** acquire general source-selection authority. Except for an explicit document request, Horus determines which qualifying sources to search and use. The judge may direct attention; the judge may not silently curate its own ground.

For every query Horus must return a provenance-bearing response recording, separately:

- the request exactly as received;
- every source searched;
- every source used;
- every source rejected and the reason for rejection;
- the records returned and the exact source references supporting each one;
- every information need that remained unfilled and why;
- the Horus repository commit and retrieval time; and
- `completeness: PENDING_PROBE`.

The allowed response states are `GATHERED`, `PARTIALLY_GATHERED`, and `NOT_GATHERED`. Missing ground is never silently converted into absence of the thing. A minister may continue only under the Assembly's applicable gate and must carry any unfilled request into the report as a visible limitation.

The machine-readable response contract lives at `contracts/horus-query-response.schema.json`. Minister request syntax is governed by the paired Sanctum contract. Query identifiers and their source trails must travel into any reasoned Ministerial Report that relies on the returned ground.

## Adversarial Gathering

A reasoned ministerial run must not move directly from provisional judgment to final judgment. After the ordinary investigative exchange, the minister must state each substantive provisional proposition together with the documentary information that could weaken, qualify, or overturn it. Sanctum converts those minister-stated vulnerabilities into a distinct adversarial request identified by `MHAQ-`.

Horus must answer that request under the same source-selection independence and provenance rules as any other query. For an adversarial request Horus searches for qualifying ground responsive to the stated disconfirmation need. Horus does **not** decide whether the material actually defeats, weakens, or leaves untouched the provisional proposition; that remains the minister's judgment.

An adversarial search returning no qualifying record is `NOT_GATHERED`, not confirmation of the provisional proposition. The absence of acquired disconfirming ground may never be rewritten as proof that no disconfirming ground exists. Every unfilled adversarial information need travels into the final ministerial record as a limitation.

The distinction is constitutional and auditable: ordinary investigative requests use `MHQ-`; adversarial requests use `MHAQ-`. The same Horus response contract accepts both identifiers, and both exchanges must be preserved separately.

## Source-Absence Taxonomy

Horus must state the epistemic condition of every returned or unfilled information need. Search failure, acquisition failure, partial acquisition, contradictory evidence, and documented absence are different records and may never be collapsed into a generic negative result.

Returned evidentiary records use exactly one of these states:

- `SUPPORTED` — qualifying source material positively supports the returned record.
- `CONTRADICTORY_RECORD` — qualifying source material materially conflicts within the relevant record. Horus records the conflict and does not resolve it.
- `DOCUMENTED_ABSENCE` — qualifying source material positively documents an absence within a stated scope. This is positive evidence and therefore requires exact source references, an `absence_scope`, and an `absence_basis`.

Unfilled information needs use exactly one of these states:

- `NOT_SEARCHED` — no search was performed for the information need.
- `SEARCHED_NOT_FOUND` — qualifying locations were searched but no qualifying record was found.
- `SOURCE_EXISTS_NOT_ACQUIRED` — a source known to exist could not be acquired or accessed.
- `SOURCE_ACQUIRED_INCOMPLETE` — some source material was acquired, but not enough to answer the information need.

Every unresolved state carries `absence_claim: false`. `SEARCHED_NOT_FOUND` is not `DOCUMENTED_ABSENCE`. `SOURCE_EXISTS_NOT_ACQUIRED` is not evidence about the contents of the inaccessible source. `SOURCE_ACQUIRED_INCOMPLETE` is not permission to infer what the missing portion contains. `NOT_SEARCHED` says nothing about the world beyond the fact that no search occurred.

`DOCUMENTED_ABSENCE` may appear only as a returned evidentiary record supported by sources actually used. It may never appear inside `unfilled_requests`. The machine-readable taxonomy identifier is `HORUS-SOURCE-STATE-1.0`.

## Deterministic Primary-Source Acquisition

A source gap may be reported only after the acquisition procedure that produced the gap is itself recorded. The absence of a search path is not the absence of a source.

For any information need requiring original-language T1, Horus must resolve each named principal through the pinned Principal Source Registry before searching. The profile supplies the principal's original language, local timezone, relevant local calendar, first-party channels, alternate first-party channels, and first-party diplomatic channels. Search terms may vary with the inquiry; the required search procedure may not.

Dates used to search a principal's archive are normalized by code, not by model recollection. The canonical Gregorian date and every required local-calendar rendering travel together in the acquisition receipt. A manually inferred calendar date does not satisfy the protocol.

The minimum original-language T1 acquisition ladder is:

1. `DIRECT_FIRST_PARTY_ARCHIVE` — search the principal's own dated archive or equivalent first-party publication record;
2. `DIRECT_FIRST_PARTY_SITE_SEARCH` — search the principal's first-party channel in the principal's own language;
3. `ALTERNATE_FIRST_PARTY_CHANNEL` — search an alternate first-party state, ministry, legal, or diplomatic channel appropriate to the principal;
4. `FIRST_PARTY_DOMAIN_RECOVERY` — use broader discovery only to recover material on a registered first-party domain.

Secondary reporting may be used for discovery after or alongside those steps, but a secondary account never fills T1 and never substitutes for a required first-party step. A discovered reference to an official statement is a lead to the primary record, not the primary record itself.

Every attempted route is an acquisition record distinct from every documentary source. Horus records the principal, channel, search method, language, canonical date, local date, query, result, retrieval time, and any recovered source reference. `sources_searched` therefore records documentary sources; `search_attempts` records the acquisition procedure that may or may not have found a source.

`SEARCHED_NOT_FOUND` is valid for an original-language T1 request only when every required ladder step was both attempted and reachable enough to return either `FOUND` or `NO_MATCH`. A blocked archive, unavailable endpoint, index error, timeout, or discovered-but-unacquired source prevents that state. The appropriate unresolved state remains an acquisition failure or incomplete acquisition, never an asserted negative.

The canonical acquisition engine is `runtime/gather.py`. It computes the acquisition plan and receipt from the pinned Horus source registry. A host may execute searches and return raw attempt records, but it may not supply its own acquisition receipt, source-state floor, Horus commit, or completeness claim. If no executed acquisition trace is supplied, the canonical engine fails closed as `NOT_SEARCHED`.

The machine-readable protocol identifier is `HORUS-ACQUISITION-1.0`. The principal profile contract lives at `contracts/principal-source-profile.schema.json`; the receipt contract lives at `contracts/acquisition-receipt.schema.json`.

## The Boundary

Horus gathers; Horus never judges. Outputs are records in briefing language. The moment the eyes editorialize, the invisible curator returns. Ministers query Horus; queries and responses are preserved as public, attributable records. Horus may answer what was found, where, when, in what language, and at what tier. Horus may not decide what the evidence means for the minister's judgment.
