"""Phase 7d — seed campaign negative keywords BEFORE enabling (run between 07c build and go-live).

Why this exists: Eliminatis launched with a 35-term hand-written list and still ran week 1 at 71%
wasted spend, needing three reactive passes. Every one of those terms was predictable. Seeding the
shared library costs nothing and buys the first week back.

Expansion rules encode three facts learned the expensive way:
  1. Negative keywords do NOT match close variants -> inflections are emitted explicitly ('*' suffix).
  2. Google does NOT fold Spanish accents in negatives -> accented and unaccented twins are both emitted.
  3. Plural/singular are different negatives -> both are emitted.

Usage:
  07d_seed_negatives.py --config ~/projects/<Client>/launch.json --verticals pest-control        # dry run
  07d_seed_negatives.py --config ... --verticals pest-control --go                               # apply
Reads report.campaign_languages (or ads.campaigns[].language) to decide which language files to use.
Idempotent; never removes an existing negative; never touches a campaign outside ads.customer_id.
"""
import argparse, json, os, re, subprocess, sys, unicodedata
from pathlib import Path

LIB = Path(__file__).resolve().parent.parent / "templates" / "negatives"

def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def inflect(term):
    """word* -> word, words, and the -ing form. Only for single words; phrases just lose the star."""
    out = {term}
    if " " in term: return out
    base = term
    out.add(base + "s" if not base.endswith("s") else base)
    if base.endswith("e"):   out.add(base[:-1] + "ing")
    elif re.search(r"[aeiou][bdglmnprt]$", base): out.add(base + base[-1] + "ing")   # trap -> trapping
    else: out.add(base + "ing")
    return out

def load(fname, spanish):
    p = LIB / fname
    if not p.exists(): return set()
    terms = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if not line: continue
        expanded = inflect(line[:-1]) if line.endswith("*") else {line}
        for t in expanded:
            terms.add(t)
            if spanish:
                bare = strip_accents(t)
                if bare != t: terms.add(bare)
    return terms

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True); ap.add_argument("--verticals", default="")
    ap.add_argument("--go", action="store_true"); a = ap.parse_args()
    cfg = json.load(open(os.path.expanduser(a.config))); ads = cfg["ads"]
    C, MCC = str(ads["customer_id"]), str(ads["mcc_customer_id"])
    os.environ["GOOGLE_ADS_LOGIN_CUSTOMER_ID"] = MCC
    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", os.path.expanduser("~/.config/gcloud/application_default_credentials.json"))
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "sereniteintelligence")
    if not os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN"):
        os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"] = subprocess.check_output(
            ["security", "find-generic-password", "-a", "claude", "-s", "google-ads-dev-token", "-w"], text=True).strip()
    from gads_write.client import get_client
    c = get_client(); ga = c.get_service("GoogleAdsService"); svc = c.get_service("CampaignCriterionService")

    # isolation guard — refuse anything that is not an enabled, non-manager leaf under our MCC
    ok = any(str(r.customer_client.id) == C and r.customer_client.status.name == "ENABLED"
             and not r.customer_client.manager and not r.customer_client.hidden
             for r in ga.search(customer_id=MCC, query="SELECT customer_client.id, customer_client.status, customer_client.manager, customer_client.hidden FROM customer_client WHERE customer_client.level = 1"))
    if not ok: sys.exit(f"ABORT: customer {C} is not an enabled leaf account under MCC {MCC}")

    camps = {}   # campaign_id -> language
    for r in ga.search(customer_id=C, query="SELECT campaign.id, campaign.name, campaign.status FROM campaign WHERE campaign.status != 'REMOVED'"):
        lang = "es" if re.search(r"espa|búsqueda|busqueda|\bes\b", r.campaign.name, re.I) else "en"
        camps[str(r.campaign.id)] = (r.campaign.name, lang)
    verticals = [v.strip() for v in a.verticals.split(",") if v.strip()]

    existing = {}
    for r in ga.search(customer_id=C, query="SELECT campaign.id, campaign_criterion.keyword.text FROM campaign_criterion WHERE campaign_criterion.type = 'KEYWORD' AND campaign_criterion.negative = TRUE"):
        existing.setdefault(str(r.campaign.id), set()).add(r.campaign_criterion.keyword.text.lower())

    ops, per = [], {}
    for cid, (name, lang) in camps.items():
        want = load(f"base-{lang}.txt", lang == "es")
        for v in verticals: want |= load(f"{v}-{lang}.txt", lang == "es")
        new = sorted(t for t in want if t.lower() not in existing.get(cid, set()))
        per[name] = (lang, len(want), len(new))
        for t in new:
            op = c.get_type("CampaignCriterionOperation"); cr = op.create
            cr.campaign = f"customers/{C}/campaigns/{cid}"; cr.negative = True
            cr.keyword.text = t; cr.keyword.match_type = c.enums.KeywordMatchTypeEnum.PHRASE
            ops.append(op)
    for name, (lang, want, new) in per.items():
        print(f"  {name[:40].ljust(40)} [{lang}] library {want}, already live {want-new}, to add {new}")
    if not ops: print("\nnothing to add — already seeded"); return
    req = c.get_type("MutateCampaignCriteriaRequest"); req.customer_id = C
    req.operations.extend(ops); req.validate_only = not a.go
    svc.mutate_campaign_criteria(request=req)
    print(("\nAPPLIED " if a.go else "\nDRY RUN OK — ") + f"{len(ops)} negatives" + ("" if a.go else " (--go to apply)"))

if __name__ == "__main__":
    main()
