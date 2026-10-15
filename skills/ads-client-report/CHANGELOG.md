# ads-client-report — changelog
- 2026-10-14 v0.1 — first version. Extracted from the Eliminatis Oct-14 report after
  the client format was validated. Config-driven for any client; handles Search,
  Display and Local Services; optional GA4 behaviour section. Tested end to end on
  Eliminatis (Search only, GA4 present) and Serenite (Search + Display + LSA, no GA4).
- 2026-10-15 v0.2 — find_ga4.py added and a missing ga4_property now warns loudly (a null silently dropped the behaviour section); LSA short-call dispute detection (`lsa_dispute_candidates`); verify.py media counter fixed; docx resolves from the skill dir.
