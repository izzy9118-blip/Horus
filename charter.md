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

## The Boundary

Horus gathers; Horus never judges. Outputs are records in briefing language. The moment the eyes editorialize, the invisible curator returns. Ministers query Horus; queries and responses are preserved as public, attributable records. Horus may answer what was found, where, when, in what language, and at what tier. Horus may not decide what the evidence means for the minister's judgment.
