# Brief — write one service page for eliminatis.com (English + Spanish), as JSON

You are writing the copy for ONE service page of Eliminatis Precision Pest Control, a veteran-owned,
family-owned pest control company in North Plainfield, NJ, serving Essex, Hudson, Union, Passaic,
Middlesex and Somerset counties. Phone 908-285-3404. Bilingual crew. Every job ends in a written
record of what was applied (New Jersey requires it; N.J.A.C. 7:30-7.3). **All inspections are free.**

Read `bedbug-reference-en.json` first — it is the live bed-bug page and your model for voice, length
and structure. Plain, direct, specific, a little dry; second person; no marketing adjectives; no
invented programme names; honest about what a treatment can and cannot do.

## Hard rules (the site is live and legally reviewed)
- NEVER say: licensed, licence number, 24/7, same day, emergency, guaranteed, eco/green/safe-for-everything,
  "#1", "best", "5-star", any review or customer count. Do not invent statistics, prices, or statutes.
- The ONLY New Jersey legal citations you may use: N.J.A.C. 7:30-7.3 (written application record within 24 h,
  kept 3 years, 5 for termiticide) and, for multi-unit buildings (3+ units), "New Jersey's Hotel and Multiple
  Dwelling Health and Safety Code places the duty to remediate on the landlord" — nothing else. NJ-specific
  content should come from seasonality, housing stock (row houses, multi-family, older frame houses, basements),
  and practical realities, not from statutes.
- Ants, mosquitoes and ticks are NOT services — never mention them as something Eliminatis treats (the
  "a flying ant is not a termite swarmer" identification point is allowed on the termite page).
- No prices. Where price comes up: "Every job is priced after a free inspection — it depends on the size of
  the home and the job."
- CTAs: primary "Call 908-285-3404"; secondary "Get a Free Inspection". Spanish: "Llame al 908-285-3404" /
  "Solicite una inspección gratuita".
- Spanish is WRITTEN, not translated: neutral Latin American Spanish, usted, the way a bilingual NJ
  technician would say it. Do not mirror English sentence by sentence.
- Headline/description length limits: seo_title ≤ 60 chars with " | Eliminatis" last; seo_desc 150–160 chars,
  contains 908-285-3404 and the words "free inspection" / "inspección gratuita".

## Output
Write ONE file: `svc/<slug>.json` (slug given below) with exactly this shape, both languages fully filled:

{
 "en": {"slug": "...", "crumb": "Cockroach Control",
        "eyebrow": "NEW JERSEY · COCKROACHES", "h1": "...", "lede": "...",
        "proof1": "...", "proof2": "...", "proof3": "...",
        "symptom_h2": "...", "symptom_lede": "...", "sym1": "...", "sym2": "...", "sym3": "...", "sym4": "...", "sym5": "...",
        "symptom_call": "Found two or more? Call 908-285-3404 →",
        "method_h2": "...", "method_p": "...", "mb1": "...", "mb2": "...", "mb3": "...", "mb4": "...", "mb5": "...",
        "prep_h2": "...", "pr1": "...", "pr2": "...", "pr3": "...", "pr4": "...", "pr5": "...",
        "nj_h2": "...", "nj_p1": "...", "nj_p2": "...", "nj_p3": "...", "nj_p4": "...", "nj_disclaim": "...",
        "safety_h2": "Is it safe for children and pets?", "safety_p1": "...", "safety_p2": "...", "safety_p3": "...",
        "plans_h2": "...", "plans_p": "...", "plans_price": "...",
        "faq_h2": "...", "faq": [{"q": "...", "a": "..."}, ... 6 items],
        "cta_h2": "...", "cta_p": "...",
        "seo_title": "...", "seo_desc": "..."},
 "es": { same keys; "slug" is the Spanish slug given below; "crumb" in Spanish; symptom_call e.g. "¿Encontró dos o más? Llame al 908-285-3404 →" }
}

Each list item (sym*, mb*, pr*) is one or two sentences. Paragraphs (lede, nj_p*, safety_p*, plans_p, faq answers)
are 1–3 sentences. Total per language roughly 900–1,200 words. Use straight quotes inside JSON strings
properly escaped. Do not write anything else to disk.
