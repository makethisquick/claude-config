# ads-client-report — learnings

Append after every run. Mechanism and judgement only: never a client's figures,
account ids, search terms or lead details — this file is studio-wide.

## 2026-10-14 — first version, built from the Eliminatis report the client liked
- **`require('docx')` resolves from the SCRIPT's directory, not the cwd.** Installing
  the package in an output folder does nothing. `docx` now ships installed in the
  skill directory and `build_docx.js` resolves skill-dir → cwd → plain require.
- **matplotlib is not installed system-wide on this machine.** Use
  `~/.claude/skills/client-launch/.venv/bin/python` for `charts.py`.
- **No LibreOffice and no pandoc here**, so a .docx cannot be rendered to images.
  `verify.py` checks structure, images and language; say plainly that layout is
  unverified and ask the user to open it once. Claiming a visual check you did not
  do is the kind of thing that costs trust permanently.
- **Split the script from the prose.** The builder owns Word mechanics; a narrative
  JSON carries the words. Numbers always come from the data blob, so a chart can
  never disagree with the table beside it.
- **Bar labels collide at zero.** When a value is near zero the percentage and the
  count land on top of each other — stack them above the axis instead.
- **Counting leads is the credibility risk.** Google-hosted "Local actions"
  (Directions, Website visits, Menu views) inflate `all_conversions` enormously —
  one account showed 25 "conversions" that were 3 real leads and 22 map taps. Count
  only actions with `include_in_conversions_metric = true`, and report Search,
  Display and Local Services separately so none flatters another.
- **Three windows beat one number.** A single month cannot show direction, and
  direction is the thing a client actually wants to know.

## 2026-10-15 — two faults found by the studio owner reviewing the first run
- **A `null` in the config silently removed a whole section.** The first Serenite
  report shipped with no visitor-behaviour section because `ga4_property` was null —
  I had written null rather than looking the id up, and the report still *looked*
  complete, which is the dangerous kind of wrong. `pull_data.py` now prints a loud
  warning and records `ga4_missing_reason`; `find_ga4.py` lists and verifies
  properties so the id is never guessed. Verify with `--verify <id> --domain <site>`
  that the stream's URI actually matches the client's website — an account can own
  several properties and only one is collecting.
- **Local Services leads are charged whether or not they are leads.** A client was
  billed $65 for a lead that was a **23-second phone call**, never disputed, three
  weeks old, against a ~30-day credit window. `pull_data.py` now joins
  `local_services_lead` to `local_services_lead_conversation` and returns
  `lsa_dispute_candidates` — charged, under 60 seconds, undisputed — with the lead's
  age so the closing window is obvious. Raise these with the studio, not in the
  client report: disputing happens in the Local Services interface, owner-side.
- **General rule both faults share: absence is not evidence of absence.** A missing
  section and an undisputed charge both look like "nothing to report". Make the
  tooling say *why* something is missing rather than quietly omitting it.
