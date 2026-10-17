#!/usr/bin/env python3
"""Pull everything a client report needs, into one JSON blob.

Run with the Ads venv: /Users/mike/projects/mcp/google-ads-write/.venv/bin/python

Why one blob: the chart script and the document builder both need the same numbers,
and recomputing them in two places is how a report ends up with a chart that
disagrees with its own table.
"""
import argparse, datetime, json, os, re, subprocess, sys, urllib.request, zoneinfo

def ads_client(mcc):
    # An account shared with the studio login directly (client added us as admin,
    # not linked under the manager account) must NOT send a login-customer-id —
    # Google rejects the manager id for an account it does not manage.
    if mcc: os.environ["GOOGLE_ADS_LOGIN_CUSTOMER_ID"] = str(mcc)
    else: os.environ.pop("GOOGLE_ADS_LOGIN_CUSTOMER_ID", None)
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
    C = str(cfg["customer_id"]); MCC = str(cfg["mcc_customer_id"]) if cfg.get("mcc_customer_id") else None
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
    for r in q(f"SELECT campaign.name, campaign.status, campaign.advertising_channel_type, campaign_budget.amount_micros, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions FROM campaign WHERE segments.date BETWEEN '{start}' AND '{end}'"):
        m = r.metrics; t = r.campaign.advertising_channel_type.name
        # a paused campaign with no activity is not part of the planned budget
        if r.campaign.status.name != "ENABLED" and not m.impressions: continue
        d = chan.setdefault(t, {"impressions":0,"clicks":0,"cost":0.0,"leads":0.0,"campaigns":[],"budget_per_day":0.0})
        d["impressions"] += m.impressions; d["clicks"] += m.clicks
        d["cost"] = round(d["cost"]+m.cost_micros/1e6,2); d["leads"] = round(d["leads"]+m.conversions,1)
        if r.campaign.status.name == "ENABLED":
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
    # Enrich each lead with keyword, device and hour. These MUST be scoped to the
    # lead's own ad group: querying device/hour at campaign level returns one row
    # per segment for the whole campaign, so two leads on the same day silently
    # inherit the same hour. (Caught 2026-10-17 — two leads both reported 02:00
    # when one was actually 17:00.)
    for L in leads:
        ag = L["ad_group"].replace("'", "\\'")
        for r in q(f"SELECT ad_group_criterion.keyword.text, metrics.conversions FROM keyword_view WHERE segments.date='{L['date']}' AND metrics.conversions > 0 AND ad_group.name = '{ag}'"):
            L["keyword"] = r.ad_group_criterion.keyword.text; break
        for r in q(f"SELECT segments.device, segments.hour, metrics.conversions FROM ad_group WHERE segments.date='{L['date']}' AND metrics.conversions > 0 AND ad_group.name = '{ag}'"):
            L["device"] = r.segments.device.name; L["hour"] = r.segments.hour; break
    out["leads"] = leads

    # --- Local Services leads: flag short calls as dispute candidates --------
    # An LSA lead is charged whether or not it was a real enquiry. A very short
    # call is almost never a genuine booking, and Google will credit it back —
    # but only inside roughly a 30-day window, so a report that does not surface
    # this is quietly costing the client money.
    lsa = []
    if any(k == "LOCAL_SERVICES" for k in chan):
        durs = {}
        for r in q("SELECT local_services_lead_conversation.id, local_services_lead_conversation.conversation_channel, local_services_lead_conversation.event_date_time, local_services_lead_conversation.phone_call_details.call_duration_millis FROM local_services_lead_conversation"):
            cv = r.local_services_lead_conversation
            if cv.phone_call_details.call_duration_millis:
                durs[str(cv.event_date_time)[:19]] = cv.phone_call_details.call_duration_millis / 1000
        for r in q("SELECT local_services_lead.id, local_services_lead.lead_type, local_services_lead.lead_status, local_services_lead.creation_date_time, local_services_lead.lead_charged, local_services_lead.credit_details.credit_state FROM local_services_lead"):
            L = r.local_services_lead
            created = str(L.creation_date_time)[:19]
            secs = durs.get(created)
            disputed = L.credit_details.credit_state.name not in ("UNSPECIFIED", "UNKNOWN", "")
            rec = {"id": str(L.id), "created": created, "type": L.lead_type.name,
                   "charged": bool(L.lead_charged), "call_seconds": secs,
                   "credit_state": L.credit_details.credit_state.name, "disputed": disputed}
            if L.lead_charged and secs is not None and secs < 60 and not disputed:
                age = (datetime.date.today() - datetime.date.fromisoformat(created[:10])).days
                rec["dispute_candidate"] = True
                rec["days_since_lead"] = age
                rec["dispute_note"] = (f"{secs:.0f}s call, charged, never disputed — "
                    f"{age} days old; the LSA credit window is about 30 days.")
            lsa.append(rec)
    out["local_services_leads"] = lsa
    out["lsa_dispute_candidates"] = [x for x in lsa if x.get("dispute_candidate")]

    # --- explicit lead definition (overrides metrics.conversions) -------------
    # Smart Campaigns (and some other auto-managed accounts) put Google-hosted
    # actions such as "Local actions - Directions" and "Clicks to call" into
    # metrics.conversions even when include_in_conversions_metric is false — one
    # account showed 1,143 "conversions" that were 4 confirmed calls, 32 call-button
    # taps and 1,107 direction requests. When the config names lead_actions, leads
    # are recounted from exactly those actions, and secondary_actions (e.g.
    # directions for a walk-in venue) are reported separately, never blended.
    LA = cfg.get("lead_actions"); SA = cfg.get("secondary_actions") or {}
    if LA:
        def by_action(s, e):
            agg = {}
            for r in q(f"SELECT segments.conversion_action_name, metrics.conversions FROM customer WHERE segments.date BETWEEN '{s}' AND '{e}'"):
                n = r.segments.conversion_action_name; agg[n] = agg.get(n,0) + r.metrics.conversions
            return agg
        def relead(t, s, e):
            agg = by_action(s, e)
            t["google_conversions"] = round(sum(agg.values()),1)
            t["leads"] = round(sum(agg.get(n,0) for n in LA),1)
            t["secondary"] = {lbl: round(sum(agg.get(n,0) for n in names),1) for lbl,names in SA.items()}
            t["cvr"] = round(100*t["leads"]/max(t["clicks"],1),2)
            t["cpl"] = round(t["cost"]/t["leads"],2) if t["leads"] else None
            return t
        out["totals"] = relead(out["totals"], start, end)
        out["windows"] = [relead(w, w["start"], w["end"]) for w in out["windows"]]
        out["lead_definition"] = {"lead_actions": LA, "secondary_actions": SA}
        # per campaign + per day, by action
        camp = {}
        for r in q(f"SELECT campaign.name, segments.conversion_action_name, metrics.conversions FROM campaign WHERE segments.date BETWEEN '{start}' AND '{end}' AND metrics.conversions > 0"):
            camp.setdefault(r.campaign.name, {})[r.segments.conversion_action_name] = round(r.metrics.conversions,1)
        out["conversions_by_campaign_action"] = camp
        for g in out["ad_groups"]:
            acts = camp.get(g["campaign"], {})
            g["leads"] = round(sum(acts.get(n,0) for n in LA),1)
            g["secondary"] = {lbl: round(sum(acts.get(n,0) for n in names),1) for lbl,names in SA.items()}
        for t, d in chan.items():
            d["leads"] = round(sum(sum(camp.get(c,{}).get(n,0) for n in LA) for c in d["campaigns"]),1)
        out["leads"] = [L for L in out["leads"] if L["action"] in LA]

    # --- daily series (for the spend chart) ---------------------------------
    out["daily"] = [{"date": str(r.segments.date), "impressions": r.metrics.impressions,
                     "clicks": r.metrics.clicks, "cost": round(r.metrics.cost_micros/1e6,2),
                     "leads": round(r.metrics.conversions,1)}
        for r in q(f"SELECT segments.date, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions FROM customer WHERE segments.date BETWEEN '{start}' AND '{end}' ORDER BY segments.date")]

    if LA:
        per = {}
        for r in q(f"SELECT segments.date, segments.conversion_action_name, metrics.conversions FROM customer WHERE segments.date BETWEEN '{start}' AND '{end}'"):
            if r.segments.conversion_action_name in LA:
                per[str(r.segments.date)] = per.get(str(r.segments.date),0) + r.metrics.conversions
        for d in out["daily"]: d["leads"] = round(per.get(d["date"],0),1)

    # --- GA4 behaviour, optional ---------------------------------------------
    out["ga4"] = None
    prop = cfg.get("ga4_property")
    if prop is False:
        out["ga4_missing_reason"] = "client has no GA4 property (set false explicitly in config)"
    elif not prop:
        # Silently omitting the behaviour section produces a report that looks
        # complete and isn't. Most clients DO have GA4 — the id was just never
        # looked up. Find it with: scripts/find_ga4.py --match <client>
        print("[WARN] no ga4_property in config — the visitor-behaviour section will be MISSING.\n"
              "       Most clients have GA4. Find the id with:  scripts/find_ga4.py --match <client>\n"
              "       Set it to false explicitly if this client genuinely has no analytics.", file=sys.stderr)
        out["ga4_missing_reason"] = "ga4_property not set in config"
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
