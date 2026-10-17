# Meta Ads and Local Presence — studio offering spec

*MakeThisQuick · v1 · 2026-10-17 · prepared for Mike's decision*

## What this decides

Whether to build a Meta Ads server and offering alongside the Google Ads one, and
whether Google Business Profile belongs in the same product. The short answer:

- **Build the Meta *offering*, not the Meta *server*.** Not yet, and possibly never.
- **Treat Google Business Profile as a separate product**, not a Meta variant. For
  local service businesses it may be worth more than paid social.
- **Prove Meta on a non-healthcare client first**, because the one client it runs on
  today is the hardest possible case for it.

Everything below argues those three positions and then specifies the work.

## 1. Why Meta is not a second Google Ads

The Google Ads server earned its place because **Google Search is a mechanical
problem**: keywords, match types, negatives, account structure, impression share.
All of it is high-volume, repetitive and API-shaped. On one client, five scripted
negatives rounds moved wasted spend from **71% to about 5%** — work no human would
do by hand at that cadence, and exactly what an API is for.

**Meta is a creative and audience problem.** The lever is the image, the offer and
who sees it. An API cannot design a captivating picture ad, and designing it is the
thing being sold. Building a Meta server first would automate the part that is not
the bottleneck, and would do so before knowing whether the offering sells.

This is not an argument that the API is useless — it is an argument about sequence.
See §6 for what would actually justify building one.

## 2. What already exists, and it is the hard part

Meta attribution is **already built and verified** on Serenite, and it is portable:

- The quickform (Fluent Forms id 3) carries **25 hidden trackers**, verified live
  against a simulated Meta click: `fbclid`, `fb_fbc`, `fb_fbp`, plus
  platform-neutral `ad_campaign_id` / `ad_adset_id` / `ad_creative_id` /
  `ad_placement` / `ad_network`.
- **The discriminator is clean: `fbclid` present and `gclid` empty means Meta.**
- Meta appends `fbclid` on every ad click **automatically, with or without a Pixel** —
  which is what makes the next point possible.
- The buyer-side URL template is written and handed off
  (`~/reports/serenite/meta-ads-tracking-handoff.md`): `utm_medium=paid_social`,
  never `cpc`, so Meta never collides with Google in GA4 or in reports.

**Consequence worth stating plainly: we can measure Meta without a Pixel.** That is
the asset. It means an exploratory offering can report real, attributable leads from
day one, on any client, without touching the Pixel question.

## 3. The Serenite result is more encouraging than it looks

Mike reports Meta driving more traction than Google on Serenite. Context that makes
this a stronger signal than the raw comparison suggests:

- Serenite's Google account has produced **4 lifetime leads**, so the bar is low.
- **Serenite is running Meta blind.** A four-panel counsel review concluded **do not
  install the Meta Pixel** — Serenite is a HIPAA covered entity (it accepts
  insurance and bills clinical services), no ad platform signs a BAA, and the
  Virginia VCPA § 59.1-200(A)(85) exposure carries a private right of action with no
  entity-level HIPAA exemption. Separately, *European Wax Center* — a retail chain
  with no HIPAA count — settled for up to $5M on wiretap statutes over tag
  sequencing.
- **Meta cannot optimise delivery without a Pixel or Conversions API.** It is bidding
  with no conversion signal, the same failure mode as running Maximize Conversions
  with no data.

So Meta is outperforming Google on Serenite **with one hand tied behind its back**.
A pest-control, trades, restaurant or retail client — no health data, Pixel freely
allowed — should do materially better. That is the case for productising it, and it
is also the reason the first proof should **not** be Serenite.

## 4. The offering: an exploratory creative sprint

Shaped so the client buys a small, bounded experiment rather than a retainer, and so
the studio sells the thing it is actually good at.

**What the client gets**
1. A short intake: who the customer is, the one offer worth testing, what a lead is worth.
2. **Three to five picture ads** — real creative, written and designed, not stock with a logo.
3. Campaign build and launch in the client's own ad account, billed to their card.
4. A **two-week test** at a deliberately small daily budget.
5. An **engagement and lead report** in the existing illustrated `.docx` format,
   showing which creative earned attention and which produced contacts.
6. A clear recommendation: stop, iterate, or scale.

**What it is not:** an ongoing management retainer. That is the second sale, and it
should only be offered when the test earns it.

**Pricing shape** (Mike to set): a fixed creative-sprint fee plus the client's own
media spend, paid direct to Meta. This mirrors the Google arrangement — the studio
never holds a card — and keeps the studio's revenue tied to the creative, which is
the defensible part. Video is explicitly **phase two**, after picture ads prove out.

**Why the report matters commercially:** the `ads-client-report` skill already
produces the illustrated .docx a client responded well to. Meta becomes a second data
source behind the same deliverable rather than a new report format. That is reuse,
not new build.

## 5. Google Business Profile is a different product

GBP is **not an ads platform** and should never be sold as a Meta alternative. What
it is: the thing that decides whether a local business appears in the map pack, and
the place reviews live.

**Both current clients have a provable, costly GBP problem:**

| | Eliminatis | Serenite |
|---|---|---|
| Reviews | **zero** (competitors show 4.9 with 67–205) | **2.7★** |
| Other faults | name truncated to "Eliminatis"; hours say 8 AM, actual 7 AM | — |

On Eliminatis, reviews were identified as **the single biggest conversion lever in
the account** — larger than anything inside the ad campaigns. For a local service
business choosing between three companies, a competitor at 4.9 with 200 reviews
against a listing with none is frequently the whole decision.

**The offering:** local presence management — correct the listing, establish a review
solicitation habit, respond to reviews, publish weekly Posts, report on map-pack
visibility. Recurring, low-labour, and it compounds.

**The API is allowlist-gated and historically slow to approve, so request access now
even though v1 is manual.** The Business Profile APIs cover locations, Local Posts,
reviews (read and reply) and insights. None of that is needed to start — it is needed
to scale past a handful of clients.

## 6. What would justify building a Meta server

Build it when at least two of these are true, not before:

- Three or more clients running Meta concurrently.
- Reporting is the repetitive cost (it will be) — and the fix is a Meta data source
  for `ads-client-report`, not a campaign-building server.
- Creative iteration volume makes bulk ad duplication worth automating.

**The access path, when it comes:** a Meta app, a Business Manager, App Review for
`ads_management`, and **Business Verification for Advanced Access**. This is the same
shape as the Google Ads Basic-access process — brand verification, a privacy policy
that genuinely describes the data use, and a wait measured in weeks. The studio's
privacy policy already carries a Google-API data section that would need a Meta
equivalent. Start this only when the offering is proven.

## 7. Constraints and risks to carry forward

- **Healthcare clients cannot run a Pixel.** Treat the Serenite counsel review as
  settled for any covered entity. Meta is still *runnable* there via Instant Forms,
  click-to-call and `fbclid` capture — just without optimisation.
- **Sequencing is the litigated defect**, not merely the presence of a tag. Where a
  Pixel is allowed, it must fire after consent, never on page load before a banner.
- **Never let `utm_medium=cpc` into Meta URLs** — it collides with Google in GA4 and
  corrupts both reports.
- **One client's Pixel, audiences and catalogues never touch another's.** The same
  zero-tolerance isolation rule that governs the Ads work applies here, and Business
  Manager makes cross-client leakage easy if assets are created in the wrong place.
- **A form that cannot capture `fbclid` makes Meta unmeasurable.** On Serenite the
  booking form (id 1) cannot be written via REST because the Defender WAF 403s on its
  definition — Meta traffic must land where the quickform is. Check this per client
  before selling a test.

## 8. Decisions for Mike

1. **Pricing for the exploratory sprint** — fixed fee, and what it includes.
2. **Which non-healthcare client proves it.** Needs a Pixel-eligible business and a
   form that captures `fbclid`. Eliminatis is the obvious candidate technically but
   is currently unpaid and paused.
3. **Whether GBP is sold separately, bundled, or used as the cheap opener** that
   leads to paid social.
4. **Whether to request GBP API allowlisting now** (recommended — approval is slow
   and costs nothing to start).
5. **Confirm Meta server work is deferred** until the §6 triggers are met.

## 9. First steps if approved

| Step | Effort |
|---|---|
| Write the exploratory-sprint one-pager the client actually sees | small |
| Port the `fbclid` capture block to the chosen proof client's forms | small — the pattern exists |
| Creative sprint: 3–5 picture ads for one client | medium — this is the product |
| Add Meta as a second data source to `ads-client-report` | medium |
| Request GBP API allowlisting | small, then wait |
| GBP v1 manual pass on both clients: name, hours, review flow | small, high value |
