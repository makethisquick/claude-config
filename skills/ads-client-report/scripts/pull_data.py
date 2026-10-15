#!/usr/bin/env python3
"""Pull everything a client report needs, into one JSON blob.

Run with the Ads venv: /Users/mike/projects/mcp/google-ads-write/.venv/bin/python

Why one blob: the chart script and the document builder both need the same numbers,
and recomputing them in two places is how a report ends up with a chart that
disagrees with its own table.
"""
import argparse, datetime, json, os, re, subprocess, sys, urllib.request, zoneinfo

def ads_client(mcc):
    os.environ["GOOGLE_ADS_LOGIN_CUSTOMER_ID"] = str(mcc)
    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", os.path.expanduser("~/.config/gcloud/application_default_credentials.json"))
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "sereniteintelligence")
    if not os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN"):
        os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"] = subprocess.check_output(
            ["security","find-generic-password","-a","claude","-s","google-ads-dev-token","-w"], text=True).strip()
    from gads_write.client import get_client
    return get_client()

def windows(period, start, end):
    """Three comparison windows. Direction beats a single number."""
    s = datetime.date.fromisoformat(start); e = datetime.date.fromisoformat(end)
    span = (e - s).days + 1
    if span < 6: return [("Full period", start, end)]
    a = span // 3
    return [("Period 1", str(s), str(s + datetime.timedelta(days=a-1))),
            ("Period 2", str(s + datetime.timedelta(days=a)), str(s + datetime.timedelta(days=2*a-1))),
            ("Latest",   str(s + datetime.timedelta(days=2*a)), str(e))]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--period", default="month", choices=["month","week","custom"])
    ap.add_argument("--start"); ap.add_argument("--end")
    a = ap.parse_args()
    cfg = json.load(open(os.path.expanduser(a.config)))
    C = str(cfg["customer_id"]); MCC = str(cfg["mcc_customer_id"])
    tz = zoneinfo.ZoneInfo(cfg.get("timezone","America/New_York"))
    today = datetime.datetime.now(tz).date()

    end = a.end or str(today)
    if a.start: start = a.start
    elif cfg.get("launch_date") and a.period == "month":
        # never claim a window that predates the client's launch
        ld = datetime.date.fromisoformat(cfg["launch_date"])
        start = str(max(ld, today - datetime.timedelta(days=29)))
    else:
        start = str(today - datetime.timedelta(days=29 if a.period=="month" else 6))

    c = ads_client(MCC); ga = c.get_service("GoogleAdsService")
    def q(sql):
        try: return list(ga.search(customer_id=C, query=sql))
        except Exception as e:
            print(f"[warn] query failed: {str(e).split('message: ')[-1][:120]}", file=sys.stderr); return []

    out = {"client": cfg["client_name"], "period": {"start": start, "end": end},
           "generated": str(datetime.datetime.now(tz).replace(microsecond=0)),
           "currency": cfg.get("currency","USD")}

    # --- which conversion actions actually count as leads -------------------
    counting, noncounting = [], []
    for r in q("SELECT conversion_action.id, conversion_action.name, conversion_action.type, conversion_action.include_in_conversions_metric FROM conversion_action WHERE conversion_action.status='ENABLED'"):
        ca = r.conversion_action
        (counting if ca.include_in_conversions_metric else noncounting).append(
            {"id": str(ca.id), "name": ca.name, "type": ca.type_.name})
    out["conversion_actions"] = {"counted_as_leads": counting, "not_leads": noncounting}

    # --- totals + per-window ------------------------------------------------
    def totals(s, e):
        rows = q(f"SELECT metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.all_conversions FROM customer WHERE segments.date BETWEEN '{s}' AND '{e}'")
        if not rows: return {"impressions":0,"clicks":0,"cost":0.0,"leads":0.0,"all_conversions":0.0,"days":0}
        m = rows[0].metrics; d = (datetime.date.fromisoformat(e)-datetime.date.fromisoformat(s)).days+1
        return {"impressions": m.impressions, "clicks": m.clicks, "cost": round(m.cost_micros/1e6,2),
                "leads": round(m.conversions,1), "all_conversions": round(m.all_conversions,1), "days": d,
                "ctr": round(100*m.clicks/max(m.impressions,1),2),
                "cpc": round(m.cost_micros/1e6/max(m.clicks,1),2),
                "cvr": round(100*m.conversions/max(m.clicks,1),2),
                "cpl": round(m.cost_micros/1e6/m.conversions,2) if m.conversions else None,
                "per_day": round(m.cost_micros/1e6/max(d,1),2)}
    out["totals"] = totals(start, end)
    out["windows"] = [{"label": l, "start": s, "end": e, **totals(s,e)} for l,s,e in windows(a.period, start, end)]

    # --- per channel: Search / Display / LSA never blended -------------------
    chan = {}
    for r in q(f"SELECT campaign.name, campaign.advertising_channel_type, campaign_budget.amount_micros, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions FROM campaign WHERE segments.date BETWEEN '{start}' AND '{end}'"):
        m = r.metrics; t = r.campaign.advertising_channel_type.name
        d = chan.setdefault(t, {"impressions":0,"clicks":0,"cost":0.0,"leads":0.0,"campaigns":[],"budget_per_day":0.0})
        d["impressions"] += m.impressions; d["clicks"] += m.clicks
        d["cost"] = round(d["cost"]+m.cost_micros/1e6,2); d["leads"] = round(d["leads"]+m.conversions,1)
        d["budget_per_day"] = round(d["budget_per_day"] + r.campaign_budget.amount_micros/1e6, 2)
        d["campaigns"].append(r.campaign.name)
    out["by_channel"] = chan
    out["budget_per_day_total"] = round(sum(v["budget_per_day"] for v in chan.values()), 2)

    # --- ad groups (the per-service table) ----------------------------------
    out["ad_groups"] = [{"name": r.ad_group.name, "campaign": r.campaign.name,
        "impressions": r.metrics.impressions, "clicks": r.metrics.clicks,
        "cost": round(r.metrics.cost_micros/1e6,2), "leads": round(r.metrics.conversions,1),
        "ctr": round(100*r.metrics.ctr,2)}
        for r in q(f"SELECT ad_group.name, campaign.name, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.ctr FROM ad_group WHERE segments.date BETWEEN '{start}' AND '{end}' AND metrics.impressions > 0 ORDER BY metrics.cost_micros DESC")]

    # --- every individual lead, with the search that produced it ------------
    leads = []
    for r in q(f"SELECT segments.date, campaign.name, ad_group.name, segments.conversion_action_name, metrics.conversions FROM ad_group WHERE segments.date BETWEEN '{start}' AND '{end}' AND metrics.conversions > 0"):
        leads.append({"date": str(r.segments.date), "campaign": r.campaign.name,
                      "ad_group": r.ad_group.name, "action": r.segments.conversion_action_name,
                      "count": round(r.metrics.conversions,1)})
    for L in leads:   # enrich with keyword + device + hour where Google exposes it
        for r in q(f"SELECT ad_group_criterion.keyword.text, metrics.conversions FROM keyword_view WHERE segments.date='{L['date']}' AND metrics.conversions > 0 AND ad_group.name = '{L['ad_group']}'"):
            L["keyword"] = r.ad_group_criterion.keyword.text; break
        for r in q(f"SELECT segments.device, segments.hour, metrics.conversions FROM campaign WHERE segments.date='{L['date']}' AND metrics.conversions > 0"):
            L.setdefault("device", r.segments.device.name); L.setdefault("hour", r.segments.hour)
    out["leads"] = leads

    # --- daily series (for the spend chart) ---------------------------------
    out["daily"] = [{"date": str(r.segments.date), "impressions": r.metrics.impressions,
                     "clicks": r.metrics.clicks, "cost": round(r.metrics.cost_micros/1e6,2),
                     "leads": round(r.metrics.conversions,1)}
        for r in q(f"SELECT segments.date, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions FROM customer WHERE segments.date BETWEEN '{start}' AND '{end}' ORDER BY segments.date")]

    # --- GA4 behaviour, optional ---------------------------------------------
    out["ga4"] = None
    prop = cfg.get("ga4_property")
    if prop:
        try:
            tok = subprocess.check_output(["gcloud","auth","application-default","print-access-token"], text=True).strip()
            def ga4(s, e):
                body = json.dumps({"dateRanges":[{"startDate":s,"endDate":e}],
                    "dimensions":[{"name":"sessionDefaultChannelGroup"}],
                    "metrics":[{"name":"sessions"},{"name":"bounceRate"},{"name":"averageSessionDuration"},{"name":"engagementRate"}],
                    "dimensionFilter":{"filter":{"fieldName":"sessionDefaultChannelGroup","stringFilter":{"value":"Paid Search"}}}}).encode()
                rq = urllib.request.Request(f"https://analyticsdata.googleapis.com/v1beta/properties/{prop}:runReport",
                    data=body, headers={"Authorization":f"Bearer {tok}","Content-Type":"application/json"})
                d = json.load(urllib.request.urlopen(rq, timeout=20))
                if not d.get("rows"): return None
                m = [float(x["value"]) for x in d["rows"][0]["metricValues"]]
                return {"sessions": int(m[0]), "bounce": round(100*m[1]), "avg_session_s": round(m[2]), "engagement": round(100*m[3])}
            w = out["windows"]
            out["ga4"] = {"first": ga4(w[0]["start"], w[0]["end"]), "latest": ga4(w[-1]["start"], w[-1]["end"])}
        except Exception as e:
            print(f"[warn] GA4 unavailable ({str(e)[:90]}) — report will omit the behaviour section", file=sys.stderr)

    out["config"] = {k: cfg.get(k) for k in ("client_name","contact_first_name","currency","services_label","notes_for_writer")}
    json.dump(out, sys.stdout, indent=1, ensure_ascii=False)

if __name__ == "__main__":
    main()
