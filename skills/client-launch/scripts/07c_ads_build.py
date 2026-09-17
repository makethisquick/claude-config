"""Phase 7c — build the approved Ads plan into the client account, EVERYTHING PAUSED. Idempotent by name.
Run through ads_env.sh. --dry-run validates the campaign objects with validate_only and prints what would be built.
Enabling campaigns is a separate, explicit human decision (never done here)."""
import sys, json, os, re, requests, time
cfg = json.load(open(sys.argv[1])); A = cfg["ads"]; b = cfg["brand"]; dry = "--dry-run" in sys.argv
os.environ["GOOGLE_ADS_LOGIN_CUSTOMER_ID"] = A["mcc_customer_id"]
from gads_write.client import get_client
client = get_client(); CID = A["customer_id"]; ga = client.get_service("GoogleAdsService")
def q(query): return list(ga.search(customer_id=CID, query=query))
def micros(d): return int(round(d * 1_000_000))
log = []
def say(s): log.append(s); print(s)

# ---- geo + language constants
geo = client.get_service("GeoTargetConstantService")
req = client.get_type("SuggestGeoTargetConstantsRequest"); req.locale = "en"; req.country_code = A.get("country_code", "US")
req.location_names.names.extend(A["locations"])
geos = {}
for s in geo.suggest_geo_target_constants(request=req).geo_target_constant_suggestions:
    g = s.geo_target_constant
    if g.target_type in ("County",) and g.country_code == "US" and s.search_term not in geos: geos[s.search_term] = g.resource_name
missing = [l for l in A["locations"] if l not in geos]
if missing: say(f"GEO NOT RESOLVED: {missing}"); sys.exit(1)
say("geo: " + ", ".join(f"{k.split(',')[0]}→{v.split('/')[-1]}" for k, v in geos.items()))
LANG = {"en": "languageConstants/1000", "es": "languageConstants/1003"}

# ---- conversion action (website lead = thank-you page)
conv_svc = client.get_service("ConversionActionService")
existing = q("SELECT conversion_action.id, conversion_action.name, conversion_action.tag_snippets FROM conversion_action WHERE conversion_action.name = '%s'" % A["conversion"]["name"])
if existing: conv = existing[0].conversion_action; say(f"conversion action exists: {conv.id}")
else:
    op = client.get_type("ConversionActionOperation"); ca = op.create
    ca.name = A["conversion"]["name"]; ca.type_ = client.enums.ConversionActionTypeEnum.WEBPAGE
    ca.category = getattr(client.enums.ConversionActionCategoryEnum, A["conversion"].get("category", "SUBMIT_LEAD_FORM"))
    ca.status = client.enums.ConversionActionStatusEnum.ENABLED; ca.counting_type = client.enums.ConversionActionCountingTypeEnum.ONE_PER_CLICK
    ca.value_settings.default_value = A["conversion"].get("value", 50); ca.value_settings.always_use_default_value = True
    ca.click_through_lookback_window_days = 30; ca.attribution_model_settings.attribution_model = client.enums.AttributionModelEnum.GOOGLE_ADS_LAST_CLICK
    creq = client.get_type("MutateConversionActionsRequest"); creq.customer_id = CID; creq.operations.append(op); creq.validate_only = dry
    r = conv_svc.mutate_conversion_actions(request=creq)
    if dry: say("[dry] conversion action validates"); conv = None
    else:
        rn = r.results[0].resource_name; conv = q(f"SELECT conversion_action.id, conversion_action.tag_snippets FROM conversion_action WHERE conversion_action.resource_name = '{rn}'")[0].conversion_action; say(f"conversion action created: {conv.id}")
if conv is not None:
    snip = [s for s in conv.tag_snippets if s.type_.name == "WEBPAGE" and s.page_format.name == "HTML"]
    if snip:
        m = re.search(r"AW-\d+/[A-Za-z0-9_-]+", snip[0].event_snippet); send_to = m.group(0) if m else None
        A["conversion"]["send_to"] = send_to; say(f"conversion send_to: {send_to}")

# ---- campaigns
camp_svc = client.get_service("CampaignService"); budget_svc = client.get_service("CampaignBudgetService")
crit_svc = client.get_service("CampaignCriterionService"); ag_svc = client.get_service("AdGroupService")
agc_svc = client.get_service("AdGroupCriterionService"); ad_svc = client.get_service("AdGroupAdService")
asset_svc = client.get_service("AssetService"); ca_svc = client.get_service("CampaignAssetService")
built = {}
for C in A["campaigns"]:
    name = C["name"]; ex = q(f"SELECT campaign.id, campaign.resource_name, campaign.status FROM campaign WHERE campaign.name = '{name}'")
    resume = False
    if ex:
        camp_rn = ex[0].campaign.resource_name; built[name] = camp_rn; resume = True; say(f"campaign exists: {name} ({ex[0].campaign.status.name}) — resuming missing pieces only")
    if resume and not dry: pass
    else:
      bop = client.get_type("CampaignBudgetOperation"); bud = bop.create; bud.name = f"{name} — budget"; bud.amount_micros = micros(C["daily_budget"]); bud.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD; bud.explicitly_shared = False
    if dry and not resume:
        breq = client.get_type("MutateCampaignBudgetsRequest"); breq.customer_id = CID; breq.operations.append(bop); breq.validate_only = True
        budget_svc.mutate_campaign_budgets(request=breq); say(f"[dry] budget ${C['daily_budget']}/day validates for {name}")
        cop = client.get_type("CampaignOperation"); c = cop.create; c.name = name; c.status = client.enums.CampaignStatusEnum.PAUSED
        c.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.SEARCH; c.campaign_budget = f"customers/{CID}/campaignBudgets/-1"
        c.target_spend.cpc_bid_ceiling_micros = micros(C["cpc_ceiling"]); c.network_settings.target_google_search = True; c.network_settings.target_search_network = False; c.network_settings.target_content_network = False
        c.geo_target_type_setting.positive_geo_target_type = client.enums.PositiveGeoTargetTypeEnum.PRESENCE
        creq2 = client.get_type("MutateCampaignsRequest"); creq2.customer_id = CID; creq2.operations.append(cop); creq2.validate_only = True
        try: camp_svc.mutate_campaigns(request=creq2); say(f"[dry] campaign validates: {name}")
        except Exception as e: say(f"[dry] campaign {name}: {str(e).split('message:')[-1][:200]}")
        continue
    if dry and resume: continue
    if not resume:
      bud_rn = budget_svc.mutate_campaign_budgets(customer_id=CID, operations=[bop]).results[0].resource_name
      cop = client.get_type("CampaignOperation"); c = cop.create; c.name = name; c.status = client.enums.CampaignStatusEnum.PAUSED
      c.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.SEARCH; c.campaign_budget = bud_rn
      c.target_spend.cpc_bid_ceiling_micros = micros(C["cpc_ceiling"])
      c.network_settings.target_google_search = True; c.network_settings.target_search_network = False; c.network_settings.target_content_network = False; c.network_settings.target_partner_search_network = False
      c.geo_target_type_setting.positive_geo_target_type = client.enums.PositiveGeoTargetTypeEnum.PRESENCE
      c.contains_eu_political_advertising = client.enums.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING
      camp_rn = camp_svc.mutate_campaigns(customer_id=CID, operations=[cop]).results[0].resource_name; built[name] = camp_rn; say(f"campaign created PAUSED: {name} ${C['daily_budget']}/day ceiling ${C['cpc_ceiling']}")
    # geo + language + negatives (skip when the campaign already has criteria)
    ncrit = len(q(f"SELECT campaign_criterion.criterion_id FROM campaign_criterion WHERE campaign.resource_name = '{camp_rn}'"))
    ops = [] if ncrit < 5 else None
    if ops is None: say(f"  criteria already present ({ncrit})")
    else:
      for rn in geos.values():
          op = client.get_type("CampaignCriterionOperation"); op.create.campaign = camp_rn; op.create.location.geo_target_constant = rn; ops.append(op)
      op = client.get_type("CampaignCriterionOperation"); op.create.campaign = camp_rn; op.create.language.language_constant = LANG[C["language"]]; ops.append(op)
      for kw in A["negatives"]:
          op = client.get_type("CampaignCriterionOperation"); op.create.campaign = camp_rn; op.create.negative = True; op.create.keyword.text = kw; op.create.keyword.match_type = client.enums.KeywordMatchTypeEnum.PHRASE; ops.append(op)
      crit_svc.mutate_campaign_criteria(customer_id=CID, operations=ops); say(f"  {len(geos)} counties, language {C['language']}, {len(A['negatives'])} negatives")
    # ad groups
    existing_ags = {r.ad_group.name: r.ad_group.resource_name for r in q(f"SELECT ad_group.name, ad_group.resource_name FROM ad_group WHERE campaign.resource_name = '{camp_rn}'")}
    for G in C["ad_groups"]:
        if G["name"] in existing_ags:
            ag_rn = existing_ags[G["name"]]
            ads = q(f"SELECT ad_group_ad.ad.id, ad_group_ad.resource_name, ad_group_ad.ad.responsive_search_ad.headlines, ad_group_ad.ad.responsive_search_ad.descriptions FROM ad_group_ad WHERE ad_group.resource_name = '{ag_rn}' AND ad_group_ad.status != 'REMOVED'")
            same = [a for a in ads if [h.text for h in a.ad_group_ad.ad.responsive_search_ad.headlines] == G["headlines"][:15] and [d.text for d in a.ad_group_ad.ad.responsive_search_ad.descriptions] == G["descriptions"][:4]]
            if same: say(f"  ad group {G['name']}: RSA matches config — skipped"); continue
            for a in ads:
                rop = client.get_type("AdGroupAdOperation"); rop.remove = a.ad_group_ad.resource_name; ad_svc.mutate_ad_group_ads(customer_id=CID, operations=[rop]); say(f"  ad group {G['name']}: removed stale RSA {a.ad_group_ad.ad.id}")
            nk = len(q(f"SELECT ad_group_criterion.criterion_id FROM ad_group_criterion WHERE ad_group.resource_name = '{ag_rn}' AND ad_group_criterion.type = 'KEYWORD'"))
            kops = [] if nk == 0 else None
        else:
            gop = client.get_type("AdGroupOperation"); g = gop.create; g.name = G["name"]; g.campaign = camp_rn; g.status = client.enums.AdGroupStatusEnum.ENABLED; g.type_ = client.enums.AdGroupTypeEnum.SEARCH_STANDARD
            ag_rn = ag_svc.mutate_ad_groups(customer_id=CID, operations=[gop]).results[0].resource_name; kops = []
        if kops is None: pass
        else:
          for text, mt in G["keywords"]:
              op = client.get_type("AdGroupCriterionOperation"); k = op.create; k.ad_group = ag_rn; k.status = client.enums.AdGroupCriterionStatusEnum.ENABLED; k.keyword.text = text; k.keyword.match_type = getattr(client.enums.KeywordMatchTypeEnum, mt); kops.append(op)
          agc_svc.mutate_ad_group_criteria(customer_id=CID, operations=kops)
        aop = client.get_type("AdGroupAdOperation"); ada = aop.create; ada.ad_group = ag_rn; ada.status = client.enums.AdGroupAdStatusEnum.ENABLED
        ada.ad.final_urls.append(C["final_domain"] + G["url"])
        for h in G["headlines"][:15]:
            t = client.get_type("AdTextAsset"); t.text = h; ada.ad.responsive_search_ad.headlines.append(t)
        for d in G["descriptions"][:4]:
            t = client.get_type("AdTextAsset"); t.text = d; ada.ad.responsive_search_ad.descriptions.append(t)
        ad_svc.mutate_ad_group_ads(customer_id=CID, operations=[aop]); say(f"  ad group {G['name']}: {len(G['keywords'])} keywords, RSA {len(G['headlines'][:15])}h/{len(G['descriptions'][:4])}d → {G['url']}")
    # assets: call, sitelinks, callouts (campaign level) — skip if already linked
    if len(q(f"SELECT campaign_asset.asset, campaign.resource_name FROM campaign_asset WHERE campaign.resource_name = '{camp_rn}'")): say("  assets already linked"); continue
    aops = []
    call = client.get_type("AssetOperation"); call.create.call_asset.country_code = A.get("country_code", "US"); call.create.call_asset.phone_number = A["phone"]; aops.append(call)
    for text, path in A["sitelinks"]:
        op = client.get_type("AssetOperation"); op.create.sitelink_asset.link_text = text; op.create.final_urls.append(C["final_domain"] + path); aops.append(op)
    for text in A["callouts"]:
        op = client.get_type("AssetOperation"); op.create.callout_asset.callout_text = text; aops.append(op)
    res = asset_svc.mutate_assets(customer_id=CID, operations=aops).results
    links = []
    for i, r in enumerate(res):
        ft = "CALL" if i == 0 else ("SITELINK" if i <= len(A["sitelinks"]) else "CALLOUT")
        op = client.get_type("CampaignAssetOperation"); op.create.campaign = camp_rn; op.create.asset = r.resource_name; op.create.field_type = getattr(client.enums.AssetFieldTypeEnum, ft); links.append(op)
    ca_svc.mutate_campaign_assets(customer_id=CID, operations=links); say(f"  assets: call, {len(A['sitelinks'])} sitelinks, {len(A['callouts'])} callouts")
if not dry:
    json.dump(cfg, open(sys.argv[1], "w"), indent=1, ensure_ascii=False)
    rows = q("SELECT campaign.id, campaign.name, campaign.status, campaign_budget.amount_micros FROM campaign")
    say("state: " + "; ".join(f"{r.campaign.name} [{r.campaign.status.name}] ${r.campaign_budget.amount_micros/1e6:g}/day" for r in rows))
