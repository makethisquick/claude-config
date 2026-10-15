---
name: ads-client-report
description: Build an illustrated, client-ready Google Ads report as a .docx with charts — monthly or weekly — for any studio client (Eliminatis, Serenite, or a new one). Use whenever asked for a Google Ads report, monthly/weekly ads report, "how are the ads doing" written up for a client, an ads performance summary to send or share, a report with charts, or a client-facing marketing report. Also use when asked to refresh or regenerate last month's ads report. Pulls live Google Ads + GA4 data, renders charts, writes the Word file, and sweeps it for anything that should never reach a client.
---

# Client-facing Google Ads report (.docx)

Produces the report a small-business owner actually reads: a few charts, plain
language, and a clear answer to "is this working?". It is a **deliverable**, not an
analysis dump — the internal diagnosis lives in the actions ledger, not here.

The format was validated with a real client on 2026-10-14 and liked. Keep the
shape unless the client asks otherwise.

## Run it

```bash
S=~/.claude/skills/ads-client-report/scripts
python3 $S/pull_data.py   --config <client-report.json> --period month   > /tmp/r.json
python3 $S/charts.py      --data /tmp/r.json --out <workdir>
node     $S/build_docx.js --data /tmp/r.json --charts <workdir> --out <file.docx>
python3 $S/verify.py      <file.docx>
```

`pull_data.py` needs the Ads venv (it imports `gads_write.client`); run it with
`/Users/mike/projects/mcp/google-ads-write/.venv/bin/python`. See **Environment** below.

Config: copy `templates/report-config.example.json`, fill it per client, and keep
it next to that client's other config (e.g. `~/projects/<Client>/report.json`).

## The one judgement call that matters

Before writing a word, decide **which story the data tells**, then lead with it.
Only three shapes come up:

- **Working** — leads up or cost-per-lead down. Lead with the trend, name what
  caused it, keep the asks short.
- **Too early** — spend is controlled and traffic is improving but leads haven't
  landed. Say so plainly and give the one thing being worked on. Do not pad.
- **Not working** — money out, nothing back, and no improving trend. Say that in
  the first paragraph. A report that buries this is worthless and the client will
  know. Pair it with what changes next and by when.

Everything below serves that call. If the data is thin (under ~30 clicks or
under ~150 sessions in a segment), say it is early rather than reading noise as a
trend — a confident story built on 9 sessions destroys trust when it reverses.

## Document shape

1. **Cover band** — client name, "Google Ads Report", date range, "prepared by".
2. **"Where things stand" callout** — leads → money → the one thing next. Three
   sentences. This is the only part some clients read.
3. **Leads** — the trend chart, then a table of every lead: when, what they
   searched, which page, device. Naming the actual searches is what makes the
   report feel like evidence rather than assertion.
4. **What it costs** — cost-per-lead chart, daily-spend-vs-budget chart.
5. **How visitors behave** — before/after bounce and time-on-site, if GA4 is
   readable.
6. **What we changed** — bullets, plain language, each tied to an outcome.
7. **What we recommend next** — numbered, each with a one-line why.
8. **"What would help us" callout** — what only the client can supply.
9. **The numbers** — period-comparison table and a per-service table.
10. **Plain English** — glossary of every term used.

## Writing rules that keep it client-safe

`verify.py` enforces the mechanical ones; these are the judgement ones.

- **Never the word "waste."** Write "searches that cost money and brought nobody."
- **No internal identifiers** — account/campaign/ad-group IDs, `gclid`, form plugin
  names, config filenames, agent or tool names, GAQL.
- **No platform jargon** unglossed — impression share, quality score, match type.
  If a concept needs three sentences to explain, it probably belongs in the
  internal ledger, not the client report.
- **Gloss non-English search terms inline**: *"control de cucarachas — cockroach
  control"*. The client may not speak the second language their ads run in.
- **A phone tap is intent, not a conversation.** Say "someone tapped your number
  to call you", never "you received a call" — tracking cannot prove it connected.
  Ask the client to confirm against their own phone log; that is how the loop
  closes.
- **Never compare cost-per-lead between services on small samples.** Under ~10
  leads each it is noise. Write "too early to say which service is cheapest."
- **No probability language.** "Normal for the first few weeks", not "29% likely".
- **Don't ask for budget by default.** If the account cannot spend what it already
  has, say so — it buys credibility for the ask that eventually matters.

## Counting leads correctly

Getting this wrong is the fastest way to destroy a report's credibility.

- Count **only** conversion actions with `include_in_conversions_metric = true`.
  Google-hosted "Local actions — Directions / Website visits / Menu views" look
  like conversions and are **not leads**. One account showed 16 "conversions"
  that were 1 real lead and 15 Business Profile taps.
- **Local Services (LSA) and Display report separately**, never blended into
  Search. Their cost-per-lead is a different number and mixing them flatters or
  damns the wrong campaign. `pull_data.py` splits them automatically.
- Conversions credit back to the **click** date, so recent days keep rising for
  weeks. Never present a conversion rate for the last 2–3 days as final.

## Period comparison

Monthly is the default. The comparison that reads best is **three windows**:
the first period, the middle, and the latest — it shows direction, which a single
month cannot. `pull_data.py --period month` returns these automatically; override
with `--windows` if the client's engagement has natural phases (a launch, a
budget change, a site rebuild).

## Environment (all three have bitten us)

- **matplotlib** is not installed system-wide. Use the client-launch venv:
  `~/.claude/skills/client-launch/.venv/bin/python` (install once with
  `pip install matplotlib`).
- **`docx` (npm) must be installed in the working directory** — `require('docx')`
  fails from an arbitrary cwd. Run `npm install docx` in the output folder first.
- **No LibreOffice or pandoc on this machine**, so the .docx cannot be rendered to
  images for a visual check. `verify.py` validates structure, images and language
  instead. **Tell the user you could not see it and ask them to open it once** —
  claiming a visual check you did not do is worse than admitting the gap.

## After building

Report honestly: what the data shows, what you could not verify, and what is
waiting on the client. Append anything newly learned to `LEARNINGS.md` — this
skill is expected to improve every time it runs.
