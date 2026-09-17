"""Phase 7b — the Google Ads DRAFT for client approval. Renders launch.json's `ads` section as a prose document
(markdown → Google Doc via the Drive MCP) so what the client signs off is byte-for-byte what 07c will build.
Nothing is created in Google Ads by this script."""
import sys, json, datetime
cfg = json.load(open(sys.argv[1])); A = cfg["ads"]; b = cfg["brand"]; out = sys.argv[2]
today = datetime.date.today().strftime("%B %-d, %Y")
total = round(sum(c["daily_budget"] for c in A["campaigns"]), 2); monthly = round(total * 30.4)
L = []
L.append(f"# Google Ads plan for {b['site_title']} — draft for approval\n")
L.append(f"*Prepared by MakeThisQuick, {today}. Nothing in this plan is live. Ads start only after you approve it and a payment method is on the account.*\n")
L.append("## What this is\n")
L.append(f"A search-advertising plan for {b['short_name']}: when someone in your service area types a pest problem into Google, a short text ad appears above the results, and a click lands them on {cfg['site_url']} where they can call {b['phone']} or send the free-inspection form. You pay only when someone clicks. Every lead that comes through the form is tagged with the ad that produced it, so within a few weeks we can say exactly which searches turn into customers and which do not.\n")
if A.get("monthly_budget_note"): L.append(f"**Budget:** {A['monthly_budget_note']}.\n")
L.append("## The two campaigns\n")
for c in A["campaigns"]:
    L.append(f"### {c['name']}\n")
    lang = "English" if c["language"] == "en" else "Spanish"
    L.append(f"{lang}-language searches from people located in {', '.join(x.replace(', New Jersey', '') for x in A['locations'])}. Daily budget **${c['daily_budget']:g}** (about ${round(c['daily_budget']*30.4)} a month), with a ceiling of ${c['cpc_ceiling']} per click so no single click can run away. " + (f"Ads run {A['schedule']}." if A.get("schedule") else "Ads run every day; we can restrict hours once your answering hours are confirmed.") + "\n")
    for g in c["ad_groups"]:
        L.append(f"**{g['name']}** — the ad shows for searches like: " + ", ".join(f"“{k}”" for k, _ in g["keywords"]) + f". It sends people to `{cfg['site_url']}{g['url']}`.\n")
        L.append("Google assembles each ad from these headlines (it picks three at a time) and descriptions (two at a time). Please read them as the words your customers will see:\n")
        L.append("- Headlines: " + " · ".join(g["headlines"]) + "\n")
        for d in g["descriptions"]: L.append(f"- Description: {d}\n")
L.append("## What we will NOT say in the ads\n")
L.append("No “licensed” claim until the New Jersey business licence number is confirmed; " + ("“free inspection” appears throughout because you confirmed every inspection is free; " if A.get("free_inspection") else "no “free inspection” unless you tell us that is genuinely offered to everyone; ") + ("“same-day callback” and “same-day free inspection” appear because you told us you promise both — if that ever stops being true, tell us the same day and the ads change. " if A.get("same_day") else "no “24/7” or “same day”. ") + "We say “NJ-certified applicators” rather than “licensed”: your applicator certification is on the site under your name; a company business licence is a different number. Every ad says who you are (veteran-owned, bilingual, six counties) and what you do (written documentation on every visit). If any of those is not right, tell us before approving.\n")
L.append("## Searches we deliberately block\n")
L.append("Some searches look relevant but never turn into customers — people looking for jobs, do-it-yourself advice, products to buy, or training. These words stop the ad from showing: " + ", ".join(A["negatives"]) + ". The list grows every week as we read the actual search terms that triggered the ads.\n")
L.append("## What appears with the ad\n")
L.append(f"A tap-to-call button with {A['phone']}; short links to " + ", ".join(s[0] for s in A["sitelinks"]) + "; and the strap lines " + ", ".join(A["callouts"]) + ".\n")
L.append("## How we will know it is working\n")
L.append(f"A lead is counted when someone reaches the thank-you page after sending the form, or taps the phone number in the ad. Each lead records the search that produced it. The first month is about learning which searches produce calls at what cost; the budget then moves toward what works. We will send you a short plain-language report every week.\n")
L.append("## Money\n")
L.append(f"Total media budget as drafted: **${total:g} a day, about ${monthly} a month**, paid by you directly to Google from a payment method you add to the account (we never hold your card). " + A.get("management_note","Management is invoiced separately by MakeThisQuick.") + " You can pause everything at any time with one message.\n")
L.append("## What we need from you to go live\n")
L.append("1. Approval of this plan — or your edits to the wording, the areas, or the budget.\n2. A payment method on the Google Ads account (we will send you the link; it takes two minutes).\n" + ("" if A.get("schedule") else "3. Your answering hours, so ads can be limited to when someone picks up.\n"))
open(out, "w").write("\n".join(L)); print("wrote", out, len("\n".join(L)), "chars")
