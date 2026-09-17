---
name: client-site-spec
description: "Produce a dev-ready website design + content specification for a client, from their supplied materials plus competitive research, validated by an adversarial expert review panel. Use when onboarding a new client site, when asked for a website spec, brand/design direction, competitor analysis feeding a build, or 'what should this client's site look like'. Ends with a build-handoff doc another agent can execute from."
---

# Client site spec

Turn a client's raw materials — a rough mockup, a product, a logo, a vague idea — into a specification a developer and designer can build from without re-litigating any decision. The output is a reference document, not a design.

The method has four phases. **Do not skip phase 1**, and do not let a subagent write the spec.

---

## Phase 1 — Ground truth (do this first, alone)

Before any research, audit what the client actually gave you and write it to `reference/00-brand-inputs-ground-truth.md`. This file is what every later claim about "the existing brand" must trace back to.

- **Create the workspace:** `<Client Name>/` with `reference/`, `research/`, `spec/`, `review/`. Copy the client's assets into `reference/` with descriptive filenames.
- **Sample colors from the pixels, not from your impression of them.** No ImageMagick or Pillow on this machine — there is a working pure-stdlib PNG sampler pattern (zlib + struct, handles filters) you can rewrite in ~40 lines. Report exact hexes. Clients routinely have three different "brand navies" across two assets and don't know it.
- **Transcribe every piece of copy** on labels, packaging, and mockups verbatim. You will need the exact words later for the claims review.
- **Hunt for internal contradictions.** This is where the value is. Check the arithmetic on anything numeric. Real examples from prior runs: a supplement label whose "%DV" column was actually each ingredient's share of blend weight; a dosing protocol that emptied a 30-serving bottle in 15 days; a mockup publishing a sentence that argued against its own product.
- **List what's missing** — logo variants, light-background treatments, real contact details, pricing, legal pages.

Write findings as findings. Say "this is a label defect, flag to client" rather than silently designing around it.

---

## Phase 2 — Parallel research fan-out

Spawn research agents **in one message so they run concurrently**. Default them to **Sonnet**. Each writes a full file to `research/` and returns only a ~700-word synthesis — that's the point, the raw pages stay out of your context.

Standard set, adapt per industry:

1. **Aspirational competitors** — the big, well-funded players the client will be compared to. What's table stakes vs. budget-heavy and skippable.
2. **Direct competitors** — who actually sells the same thing. Pricing, offer structure, guarantees, conversion mechanics, site archetypes.
3. **SEO / keyword strategy** — tiered keyword universe, *live* SERP composition for the priority queries, realistic ranking thesis, site architecture with slugs, technical requirements, content plan.
4. **Regulatory / compliance** — if the industry has any. Claims rules, required disclosures, advertising-platform restrictions, an explicit list of language the client CAN use.
5. **Design / brand research** — reference sites with real hexes and font stacks pulled from live CSS, candidate palettes with computed contrast, type pairings, art direction.

**In every research prompt, require:**
- Cited URLs for every material claim; primary sources over explainers.
- Explicit flagging of anything unverified rather than smoothing it over. `.gov` sites bot-block constantly; a law-firm summary is fine if labeled as one.
- Real research, not recall.

**Budget warning:** WebSearch is capped per session (200 calls). A five-agent fan-out can exhaust it. Sequence the highest-value research first.

---

## Phase 3 — Write the spec yourself

**You are the principal designer. Do not delegate this.** Delegating synthesis to a subagent loses the cross-cutting judgment that makes the document worth reading.

Read the research files directly — you need the palettes, keyword lists, and slug tables, not the summaries.

**Verify every number you publish.** Compute contrast ratios with the WCAG formula rather than trusting an agent's table. Check the physical arithmetic on anything the spec asserts. **Normalize before comparing** — a prior run overstated a formulation problem threefold by comparing extract amounts to study amounts without accounting for extract ratios. If you're comparing two numbers, confirm they're in the same units first.

### Structure that works

| § | Contents |
|---|---|
| 0 | How to read this · **decision log** — every call made, with its one-line rationale |
| 1 | Strategic foundation — market, positioning statement, audience, competitive map. Be honest about what the chosen strategy *costs* |
| 2 | **Blockers** — product/business problems upstream of design. Put them early; two of them usually change what the site can say |
| 3 | Design system — color tokens with verified contrast and **hard usage rules**, typography with full scales, spacing, components, motion, accessibility |
| 4 | Art direction — shoot list, explicit do-not-shoot list, grade, asset gaps |
| 5 | Information architecture — page inventory with exact slugs, navigation, internal linking |
| 6 | Page-by-page — section order, each section stating its job |
| 7 | Content and copy — voice, **approved/prohibited/conditional claims**, CTA inventory, pricing, what to delete from the client's draft |
| 8 | SEO — ranking thesis, targets, technical, content plan, **off-page authority**, measurement |
| 9 | Compliance — if applicable |
| 10 | Build spec — stack, performance budget, QA gates |
| 11 | Deliverables and **the decisions table** |

### Rules that keep the document honest

- **State a recommendation, not a survey.** Where you're genuinely unsure, say so in a dedicated section rather than hedging everywhere — a spec that presents everything with equal confidence lies about which parts are load-bearing.
- **Never hardcode a value in two places.** Reference the section that owns it.
- **Every deferred/uncertain item goes in the decisions table** with what it blocks, ordered by blast radius.
- **Mark what you could not verify.** A "Known gaps" section at the end costs nothing and prevents someone building on sand.
- **Contradictions in the client's material are findings, not obstacles.** Name them plainly.

---

## Phase 4 — Adversarial review, then revise

Spawn **three reviewers in parallel**, Sonnet, one per domain (typically compliance/regulatory, SEO+conversion, brand/design). Give each the spec path, the relevant research, and the client's actual asset images where useful.

**The prompt pattern that produces real findings:**

- Cast them as a peer with authority — "you are the compliance gate," "critique as a peer of the principal designer."
- Give them a numbered list of the specific things to attack, including the calls you're least sure about.
- Demand a format: `VERDICT: SIGN OFF / SIGN OFF WITH CONDITIONS / DO NOT SIGN OFF`, then blocking issues with section + problem + specific fix, then non-blocking, then **what the spec got right** (so you know what not to break), then **their single strongest disagreement, argued properly**.
- Close with: *"Be adversarial and specific. Do not rubber-stamp. Don't invent problems to appear rigorous — false findings cost as much as missed ones."*
- Ask them to spot-check your factual assertions against primary sources and to say plainly what they could not verify.

**Then actually fix things.** Reviewers will find genuine problems — self-contradictions between sections, a strategy declared solved in one section and violated in another, arithmetic that doesn't survive contact. Fix them, renumber cross-references carefully, and record the round in `review/REVIEW-ROUND-1.md`: each finding, its resolution, verification notes, and what the panel agreed to protect.

**When a reviewer or the client corrects you, own it plainly in the document** — a `⚠ CORRECTION` block appended to the research file, with the original text left intact for provenance. Don't quietly rewrite history.

---

## Finish with a handoff

Write `BUILD-HANDOFF.md` at the workspace root for the next agent or conversation:

- **Read-these-in-order** list, and an explicit "do not re-run the research."
- **Environment** — MCP server name and whether you actually confirmed it responds, host, stack versions, existing pages, what's already configured.
- **What can be built right now**, unblocked. There is almost always a real answer here (design tokens, component library, page scaffolding, technical plumbing) even when content is fully blocked.
- **What's blocked, and by exactly what** — as a table.
- **The things most likely to go wrong**, concretely.
- Open decisions with current state.

Also write a short `README.md` mapping the workspace, and save a project memory with any items the client explicitly deferred.

---

## Hard rules

- **Cross-client isolation.** Multiple client MCP servers expose near-identical tool names. Verify the server prefix on every write call. A misrouted call writes another client's live site.
- **Never publish a fabricated testimonial, review, or rating** — not in a mockup, not in staging, not "temporarily." In regulated categories this carries per-violation civil penalties.
- **Don't let the client's existing marketing copy into the spec** without a claims review. It is usually the riskiest text in the project.
- **Verify a named person before putting them on a site.** Public registries (NPI for US clinicians, state license boards, bar directories) are directly fetchable even when search is exhausted. Report what the registry does and does not establish.
- **Research agents occasionally bleed context between projects.** Skim returned files for names or details that don't belong.

## Adapting

Drop the compliance research for unregulated industries and fold the essentials (privacy, accessibility, subscription terms) into a single section. Keep everything else: ground truth, parallel research, self-authored spec, adversarial panel, handoff. The panel is what turns a good document into a defensible one — three reviewers on Sonnet is cheap relative to what they catch.
