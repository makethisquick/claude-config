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
