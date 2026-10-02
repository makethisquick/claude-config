# Seed negative keywords — applied at SETUP, before a campaign ever serves

Eliminatis paid to learn this list: week 1 ran at **71% wasted spend**, and three later passes were
needed before the account stopped matching poison shoppers and job seekers. None of it was unforeseeable.
Seed these at phase 07c, before enabling, so the first week buys traffic instead of lessons.

## Three facts that shape the format

1. **Negative keywords do NOT match close variants.** `kill` does not block *killing*; `trap` does not
   block *trapping*; `product` does not block *products*. Every inflection must be listed. A `*` suffix in
   these files tells `seed_negatives.py` to expand `word` -> `word`, `words`, `wording`-style inflections.
2. **Google does NOT normalise Spanish accents in negatives.** `que es bueno para` did not block
   `qué es bueno para…` — it served and took a paid click. The expander emits both forms for every
   Spanish term automatically.
3. **Zero-click junk impressions are not free.** Product/DIY searches that never click still drag
   predicted CTR -> quality score -> ad rank. On Eliminatis these were 23% of impressions while ad rank
   was the binding constraint (81.8% impression share lost to rank). Block them even though they cost $0
   in clicks.

## Files
- `base-en.txt` / `base-es.txt` — universal: job seekers, students, DIY, retail, freebie hunters.
  Apply to **every** client in that language.
- `<vertical>-en.txt` / `<vertical>-es.txt` — trade-specific product and brand terms.
- Client-specific exclusions (services not offered, out-of-area cities, competitor names the client
  wants left alone) belong in `launch.json`, never here.

## Use
    python seed_negatives.py --config ~/projects/<Client>/launch.json --verticals pest-control    # dry run
    python seed_negatives.py --config ... --verticals pest-control --go                           # apply
Idempotent: skips anything already live on the campaign.
