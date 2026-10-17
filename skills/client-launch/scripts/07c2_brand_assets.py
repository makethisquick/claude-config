#!/usr/bin/env python3
"""Phase 7c2 — give the ads a logo and a business name, before they ever run.

Why this exists: a client asked why his search ads showed no logo beside the website.
His site's favicon was flawless — Site Icon set, square 512x512 PNG, correctly
declared in <link rel="icon">. All of that is irrelevant to the ad. **Google renders
the search-ad logo from BUSINESS_LOGO + BUSINESS_NAME assets in the Ads account**,
and the account had none: only CALL, CALLOUT, SITELINK, STRUCTURED_SNIPPET, LOCATION
and TEXT. It went unnoticed for four weeks of paid traffic because nothing is broken
when they are missing — the ads simply look more anonymous than the competitors'.

Run between 07c (build) and go-live, through the Ads env wrapper:
  ads_env.sh 07c2_brand_assets.py ~/projects/<Client>/launch.json          # dry run
  ads_env.sh 07c2_brand_assets.py ~/projects/<Client>/launch.json --go

Reads `assets.site_icon_id` and `brand.short_name` from launch.json — both already
exist from earlier phases, so there is nothing new to configure.

Google's rules, enforced here so a rejection never reaches the account:
  logo  — square 1:1, at least 128x128, under 5120KB, PNG or JPG
  name  — 25 characters maximum
"""
import json, os, subprocess, sys, urllib.request, struct

def die(msg): sys.exit(f"ABORT: {msg}")

def png_or_jpg_size(data):
    if data[:8] == bytes([137,80,78,71,13,10,26,10]):
        w,h = struct.unpack(">II", data[16:24]); return ("PNG", w, h)
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF: i += 1; continue
            m = data[i+1]
            if m in (0xC0,0xC1,0xC2,0xC3):
                h,w = struct.unpack(">HH", data[i+5:i+9]); return ("JPEG", w, h)
            i += 2 + struct.unpack(">H", data[i+2:i+4])[0]
    return (None, 0, 0)

def main():
    if len(sys.argv) < 2: die("usage: 07c2_brand_assets.py <launch.json> [--go]")
    GO = "--go" in sys.argv
    cfg = json.load(open(os.path.expanduser(sys.argv[1])))
    ads = cfg["ads"]; C = str(ads["customer_id"]); MCC = str(ads["mcc_customer_id"])
    name = (cfg.get("brand", {}).get("short_name") or "").strip()
    if not name: die("brand.short_name is empty — it becomes the ad's business name")
    if len(name) > 25:
        die(f"brand.short_name is {len(name)} chars ('{name}'); Google allows 25. "
            "Add an explicit ads.business_name to launch.json with a shorter form.")
    name = cfg.get("ads", {}).get("business_name", name)

    icon_id = (cfg.get("assets") or {}).get("site_icon_id")
    if not icon_id:
        die("assets.site_icon_id is not set — run the earlier phases, or add an "
            "ads.logo_url to launch.json pointing at a square logo.")

    # resolve the logo URL from the client's own media library
    logo_url = (cfg.get("ads") or {}).get("logo_url")
    if not logo_url:
        site = cfg["site_url"].rstrip("/")
        user = cfg.get("wp_user") or cfg.get("wp_username")
        pw = subprocess.check_output(["security","find-generic-password","-s",
                cfg.get("keychain_service", "wp-"+cfg["slug"]), "-w"], text=True).strip()
        import base64
        req = urllib.request.Request(f"{site}/wp-json/wp/v2/media/{icon_id}?_fields=source_url,media_details",
            headers={"Authorization":"Basic "+base64.b64encode(f"{user}:{pw}".encode()).decode()})
        m = json.load(urllib.request.urlopen(req, timeout=20))
        logo_url = m["source_url"]
    img = urllib.request.urlopen(logo_url, timeout=20).read()
    fmt, w, h = png_or_jpg_size(img)
    print(f"  logo source : {logo_url}")
    print(f"  logo        : {fmt} {w}x{h}, {len(img)//1024}KB")
    if not fmt: die("the site icon is neither PNG nor JPEG")
    if w != h: die(f"the logo is {w}x{h} — Google requires a SQUARE (1:1) business logo. "
                   "Crop a square version and set ads.logo_url in launch.json.")
    if w < 128: die(f"the logo is {w}px — Google requires at least 128x128.")
    if len(img) > 5120*1024: die("the logo exceeds Google's 5120KB limit.")
    print(f"  business name: '{name}' ({len(name)}/25 chars)")

    os.environ["GOOGLE_ADS_LOGIN_CUSTOMER_ID"] = MCC
    from gads_write.client import get_client
    c = get_client(); ga = c.get_service("GoogleAdsService")
    asset_svc = c.get_service("AssetService"); ca_svc = c.get_service("CampaignAssetService")

    have_linked = {r.campaign_asset.field_type.name for r in ga.search(customer_id=C,
        query="SELECT campaign_asset.field_type FROM campaign_asset")}
    if {"BUSINESS_LOGO","BUSINESS_NAME"} <= have_linked:
        print("\n  both BUSINESS_LOGO and BUSINESS_NAME are already linked — nothing to do."); return

    existing = {}
    for r in ga.search(customer_id=C, query="SELECT asset.id, asset.type, asset.name FROM asset WHERE asset.type IN ('IMAGE','TEXT')"):
        existing.setdefault(r.asset.type_.name, {})[r.asset.name] = str(r.asset.id)

    asset_name = f"{name} logo {w}"
    logo_rn = bn_rn = None
    mk = []
    if asset_name in existing.get("IMAGE", {}):
        logo_rn = f"customers/{C}/assets/{existing['IMAGE'][asset_name]}"
    else:
        o = c.get_type("AssetOperation"); a = o.create
        a.name = asset_name; a.type_ = c.enums.AssetTypeEnum.IMAGE
        a.image_asset.data = img; a.image_asset.file_size = len(img)
        a.image_asset.mime_type = (c.enums.MimeTypeEnum.IMAGE_PNG if fmt=="PNG" else c.enums.MimeTypeEnum.IMAGE_JPEG)
        a.image_asset.full_size.width_pixels = w; a.image_asset.full_size.height_pixels = h
        a.image_asset.full_size.url = logo_url
        mk.append(("logo", o))
    if name in existing.get("TEXT", {}):
        bn_rn = f"customers/{C}/assets/{existing['TEXT'][name]}"
    else:
        o = c.get_type("AssetOperation"); a = o.create
        a.name = name; a.type_ = c.enums.AssetTypeEnum.TEXT; a.text_asset.text = name
        mk.append(("name", o))

    if not GO:
        if mk:
            req = c.get_type("MutateAssetsRequest"); req.customer_id = C
            req.operations.extend(op for _, op in mk); req.validate_only = True
            asset_svc.mutate_assets(request=req)
        print(f"\n  DRY RUN OK — would create {[k for k,_ in mk]} and link both to every enabled search campaign.")
        print("  re-run with --go"); return

    for kind, op in mk:
        rn = asset_svc.mutate_assets(customer_id=C, operations=[op]).results[0].resource_name
        if kind == "logo": logo_rn = rn
        else: bn_rn = rn
        print(f"  created {kind}: {rn}")

    camps = [str(r.campaign.id) for r in ga.search(customer_id=C,
        query="SELECT campaign.id FROM campaign WHERE campaign.status != 'REMOVED' AND campaign.advertising_channel_type = 'SEARCH'")]
    link_ops = []
    for camp in camps:
        for rn, ft in ((logo_rn, c.enums.AssetFieldTypeEnum.BUSINESS_LOGO),
                       (bn_rn,  c.enums.AssetFieldTypeEnum.BUSINESS_NAME)):
            o = c.get_type("CampaignAssetOperation"); la = o.create
            la.campaign = f"customers/{C}/campaigns/{camp}"; la.asset = rn; la.field_type = ft
            link_ops.append(o)
    try:
        ca_svc.mutate_campaign_assets(customer_id=C, operations=link_ops)
        print(f"  linked {len(link_ops)} campaign assets across {len(camps)} search campaign(s)")
    except Exception as e:
        print("  LINK FAILED:", str(e).split("message: ")[-1][:250]); sys.exit(2)
    for r in ga.search(customer_id=C, query="SELECT campaign.name, campaign_asset.field_type, campaign_asset.status FROM campaign_asset WHERE campaign_asset.field_type IN ('BUSINESS_LOGO','BUSINESS_NAME')"):
        print(f"  verified: {r.campaign.name[:30]:<30} {r.campaign_asset.field_type.name} {r.campaign_asset.status.name}")

if __name__ == "__main__": main()
