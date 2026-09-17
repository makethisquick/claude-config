"""Phase 4 — Fluent Forms: install, build each language's quick-quote form from launch.json, notifications,
honeypot, attribution hidden fields, thank-you redirect, site-wide attribution script, styling class,
then an end-to-end proof (real submit path + rejection matrix) and cleanup of the test entries.
Idempotent: forms are found by title; re-running updates them in place."""
import sys, json, time, re, html as htmlmod, requests
from urllib.parse import urlencode
from wp import *
cfg = load(sys.argv[1]); wp = WP(cfg); lines = []; F = cfg["forms"]; b = cfg["brand"]
ATTR = ["gclid","gbraid","wbraid","utm_source","utm_medium","utm_campaign","utm_term","utm_content","landing_page","referrer","first_seen","ga_client_id","page_url"]

p = wp.plugin("fluentform/fluentform")
if not p: p = wp.install_plugin("fluentform", "active"); lines.append(f"installed Fluent Forms {p.get('version')}")
elif p["status"] != "active": wp.set_plugin("fluentform/fluentform", "active"); lines.append("activated Fluent Forms")

def ff(path, **params): return wp.get("/fluentform/v1" + path, **params)
def ffpost(path, payload): return wp.post("/fluentform/v1" + path, payload)
def uk(i): return f"el_{int(time.time()*1000)}_{i}"
def text(i, f, REQ):
    return {"index":i,"element":"input_text","attributes":{"type":f.get("type","text"),"name":f["name"],"value":"","class":"","id":"","placeholder":"","maxlength":""},
            "settings":{"container_class":"","label":f["label"],"label_placement":"","admin_field_label":f["label"],"help_message":f.get("help",""),"conditional_logics":[],
                        "validation_rules":{"required":{"value":f.get("required",True),"message":REQ}},"is_unique":"no","unique_validation_message":""},
            "editor_options":{"title":"Simple Text","icon_class":"ff-edit-text","template":"inputText"},"uniqElKey":uk(i)}
def email(i, f, REQ, EMSG):
    return {"index":i,"element":"input_email","attributes":{"type":"email","name":f["name"],"value":"","class":"","id":"","placeholder":""},
            "settings":{"container_class":"","label":f["label"],"label_placement":"","admin_field_label":f["label"],"help_message":"","conditional_logics":[],
                        "validation_rules":{"required":{"value":f.get("required",False),"message":REQ},"email":{"value":True,"message":EMSG}},"is_unique":"no","unique_validation_message":""},
            "editor_options":{"title":"Email Address","icon_class":"ff-edit-email","template":"inputText"},"uniqElKey":uk(i)}
def select(i, f, REQ):
    return {"index":i,"element":"select","attributes":{"name":f["name"],"value":"","class":"","id":""},
            "settings":{"container_class":"","label_placement":"","admin_field_label":f["label"],"label":f["label"],"help_message":"","placeholder":f.get("placeholder",""),
                        "advanced_options":[{"label":o,"value":o,"calc_value":""} for o in f["options"]],"calc_value_status":False,"enable_select_2":"no","enable_image_input":False,
                        "validation_rules":{"required":{"value":f.get("required",True),"message":REQ}},"randomize_options":"no","conditional_logics":[]},
            "editor_options":{"title":"Dropdown","icon_class":"ff-edit-dropdown","element":"select","template":"select"},"uniqElKey":uk(i)}
def consent(i, f, CMSG):
    return {"index":i,"element":"terms_and_condition","attributes":{"type":"checkbox","name":f["name"],"value":False,"class":""},
            "settings":{"tnc_html":f["html"],"has_checkbox":True,"admin_field_label":f.get("label","Consent"),"container_class":"elm-consent-ff",
                        "validation_rules":{"required":{"value":True,"message":CMSG}},"conditional_logics":[]},
            "editor_options":{"title":"Terms & Conditions","icon_class":"ff-edit-terms-condition","template":"termsCheckbox"},"uniqElKey":uk(i)}
def hidden(i, name):
    return {"index":i,"element":"input_hidden","attributes":{"type":"hidden","name":name,"value":""},"settings":{"admin_field_label":name},
            "editor_options":{"title":"Hidden Field","icon_class":"ff-edit-hidden-field","template":"inputHidden"},"uniqElKey":f"el_attr_{name}"}
def submit(label):
    return {"uniqElKey":"el_submit","element":"button","attributes":{"type":"submit","class":"elm-ff-submit"},
            "settings":{"align":"left","button_style":"","container_class":"","help_message":"","background_color":b.get("primary_color","#E31A1C"),"button_size":"md","color":"#ffffff",
                        "button_ui":{"type":"default","text":label,"img_url":""},"normal_styles":{"backgroundColor":b.get("primary_color","#E31A1C"),"borderColor":b.get("primary_color","#E31A1C"),"color":"#ffffff","borderRadius":"","minWidth":""},
                        "hover_styles":{"backgroundColor":b.get("primary_color_dark","#CD1517"),"borderColor":b.get("primary_color_dark","#CD1517"),"color":"#ffffff","borderRadius":"","minWidth":""},"current_state":"normal_styles"},
            "editor_options":{"title":"Submit Button"}}

def build(lang, spec):
    M = spec["messages"]; fields = []
    for i, f in enumerate(spec["fields"]):
        k = f["kind"]
        fields.append(text(i, f, M["required"]) if k == "text" else email(i, f, M["required"], M["email"]) if k == "email" else select(i, f, M["required"]) if k == "select" else consent(i, f, M["consent"]))
    for j, n in enumerate(ATTR): fields.append(hidden(len(fields) + j, n))
    existing = [x for x in ff("/forms", per_page=50)["data"] if x["title"] == spec["title"]]
    fid = existing[0]["id"] if existing else ffpost("/forms", {"title": spec["title"], "predefined": "blank_form"})["formId"]
    ffpost(f"/forms/{fid}", {"title": spec["title"], "status": "published", "formFields": json.dumps({"fields": fields, "submitButton": submit(spec["submit"])})})
    # settings rows: UPDATE by meta_id (a POST without meta_id INSERTS a duplicate and Fluent Forms reads the first row)
    rows = ff(f"/settings/{fid}", meta_key="formSettings"); base = rows[0]["value"] if rows else {}
    base.update({"confirmation": {"redirectTo": "customUrl", "messageToShow": spec.get("thanks_message", ""), "customPage": None, "samePageFormBehavior": "hide_form", "customUrl": spec["thank_you_url"]},
                 "layout": {"labelPlacement": "top", "helpMessagePlacement": "under_input", "errorMessagePlacement": "inline", "cssClassName": "elm-ff", "asteriskPlacement": "asterisk-right"}})
    base.setdefault("restrictions", {"limitNumberOfEntries": {"enabled": False, "numberOfEntries": None, "period": "total", "limitReachedMsg": ""}, "scheduleForm": {"enabled": False, "start": None, "end": None, "selectedDays": ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"], "pendingMsg": "", "expiredMsg": ""}, "requireLogin": {"enabled": False, "requireLoginMsg": ""}, "denyEmptySubmission": {"enabled": True, "message": M["required"]}})
    base.setdefault("delete_entry_on_submission", "no")
    if rows: ffpost(f"/settings/{fid}", {"meta_key": "formSettings", "value": json.dumps(base), "meta_id": rows[0]["id"]})
    else: ffpost(f"/settings/{fid}", {"meta_key": "formSettings", "value": json.dumps(base)})
    for extra in rows[1:]: wp.delete(f"/fluentform/v1/settings/{fid}", meta_id=extra["id"])
    ATTR_BLOCK = "<hr><p><strong>Where this lead came from</strong> (blank = not from an ad / not set)</p><ul>" + "".join(f"<li>{n}: {{inputs.{n}}}</li>" for n in ATTR) + "</ul>"
    msg = spec["message"] if "Where this lead came from" in spec["message"] else spec["message"] + ATTR_BLOCK   # {all_data} hides blank fields — attribution must be explicit
    notif = {"name": "Lead notification", "sendTo": {"type": "email", "email": ", ".join(cfg["leads"]["recipients"]), "field": "", "routing": [{"email": None, "field": None, "operator": "=", "value": None}]},
             "fromName": b["site_title"] + " website", "fromEmail": "", "replyTo": spec.get("reply_to", ""), "bcc": "", "subject": spec["subject"], "message": msg,
             "conditionals": {"status": False, "type": "all", "conditions": [{"field": None, "operator": "=", "value": None}]}, "enabled": True, "email_template": ""}
    nrows = ff(f"/settings/{fid}", meta_key="notifications"); mine = [n for n in nrows if n["value"].get("name") == "Lead notification"]
    if mine: ffpost(f"/settings/{fid}", {"meta_key": "notifications", "value": json.dumps(notif), "meta_id": mine[0]["id"]})
    else: ffpost(f"/settings/{fid}", {"meta_key": "notifications", "value": json.dumps(notif)})
    for n in nrows:
        if n["value"].get("name") != "Lead notification" or (mine and n["id"] != mine[0]["id"]): wp.delete(f"/fluentform/v1/settings/{fid}", meta_id=n["id"])
    lines.append(f"{lang}: form {fid} '{spec['title']}' — {len(spec['fields'])} fields + {len(ATTR)} attribution fields, redirect -> {spec['thank_you_url']}, leads -> {cfg['leads']['recipients']}")
    return fid

ids = {lang: build(lang, spec) for lang, spec in F["languages"].items()}
g = ff("/global-settings", key="_fluentform_global_form_settings")["_fluentform_global_form_settings"]
g.setdefault("misc", {}).update({"honeypotStatus": "yes", "isIpLogingDisabled": True})
cap = F.get("captcha")   # {"type": "recaptcha"|"turnstile"|"hcaptcha", "autoload": true} — keys are pasted by a human in Fluent Forms → Global Settings → Security (secret = credential)
if cap and cap.get("autoload"):
    status_key = {"recaptcha": "_fluentform_reCaptcha_keys_status", "turnstile": "_fluentform_turnstile_keys_status", "hcaptcha": "_fluentform_hCaptcha_keys_status"}[cap["type"]]
    if ff("/global-settings", key=status_key).get(status_key): g["misc"].update({"autoload_captcha": True, "captcha_type": cap["type"]}); lines.append(f"captcha ON for all forms: {cap['type']}")
    else: lines.append(f"CAPTCHA NOT ENABLED: {cap['type']} keys are not saved/valid in Fluent Forms — human pastes site+secret keys (Global Settings → Security), then re-run")
ffpost("/global-settings", {"key": "saveGlobalLayoutSettings", "form_settings": json.dumps(g)}); lines.append("honeypot ON, IP logging OFF")

# embed: the widget whose html contains the marker (a <form ...> or a placeholder) becomes a shortcode widget
for lang, spec in F["languages"].items():
    pid = spec["page_id"]; els = json.loads(wp.page_data(pid)); hit = [0]
    def fn(e, lst, i):
        s = e.get("settings", {})
        if e.get("widgetType") == "html" and (("<form" in str(s.get("html", ""))) or (spec.get("embed_marker") and spec["embed_marker"] in str(s.get("html", "")))):
            e["widgetType"] = "shortcode"; e["settings"] = {"shortcode": f'[fluentform id="{ids[lang]}"]'}; hit[0] += 1
        elif e.get("widgetType") == "shortcode" and "fluentform" in str(s.get("shortcode", "")):
            e["settings"] = {"shortcode": f'[fluentform id="{ids[lang]}"]'}; hit[0] += 1
    walk(els, fn)
    if hit[0]: wp.set_page_data(pid, dumps(els))
    lines.append(f"{lang}: embedded on page {pid} ({hit[0]} widget)")

# site-wide attribution script — appended as an html widget at the end of every published page if missing
SCRIPT = open(__file__.replace("04_fluentforms.py", "attribution.js")).read()
n = 0
for pg in wp.pages():
    els = json.loads(wp.page_data(pg["id"]) or "[]")
    if not els or "data-elm-attr" in dumps(els): continue
    els.append({"id": f"a{pg['id']:06x}"[:7], "elType": "e-flexbox", "isInner": False, "settings": {"classes": {"$$type": "classes", "value": []}, "tag": {"$$type": "string", "value": "div"}, "_cssid": {"$$type": "string", "value": f"elm-attr-{pg['id']}"}},
                "elements": [{"id": f"b{pg['id']:06x}"[:7], "elType": "widget", "widgetType": "html", "elements": [], "settings": {"html": "<script data-elm-attr=\"1\">" + SCRIPT + "</script>"}}], "styles": {}, "interactions": [], "editor_settings": [], "version": "4.2.2"})
    wp.set_page_data(pg["id"], dumps(els)); n += 1
lines.append(f"attribution script present on all pages (added to {n})"); wp.clear_cache()

# ---- PROOF: submit through the real path, rejection matrix, then delete the test entries ----
def submit_via_page(page_url, fid, data):
    S = requests.Session(); h = S.get(page_url, params={"nolang": 1, "cb": "t"}).text
    frm = re.search(r'<form[^>]*frm-fluent-form.*?</form>', h, re.S).group(0)
    hidden_ = {m.group(1): htmlmod.unescape(m.group(2)) for m in re.finditer(r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"', frm)}
    names = set(re.findall(r'name="([^"]+)"', frm)); payload = dict(hidden_); payload.update(data)
    for nm in names - set(payload): payload[nm] = ""
    def go(p): return S.post(wp.site + "/wp-admin/admin-ajax.php", data={"action": "fluentform_submit", "form_id": fid, "data": urlencode(p)}, headers={"X-Requested-With": "XMLHttpRequest", "Referer": page_url})
    return payload, go
results = []
for lang, spec in F["languages"].items():
    t = spec["test"]; fid = ids[lang]; payload, go = submit_via_page(spec["page_url"], fid, t["good"])
    r = go(payload); ok = r.status_code == 200 and r.json().get("success"); redirect = (r.json().get("data", {}).get("result", {}).get("redirectUrl") or "") if ok else ""
    if cap and cap.get("autoload"):
        results.append(f"{lang} scripted submit with captcha on -> {r.status_code} (want 422 captcha rejection): {r.text[:80]}  — a real-browser submission must be proven separately (Chrome extension), captcha needs a live token")
    else:
        results.append(f"{lang} accept: {r.status_code} redirect={redirect.replace(wp.site, '') or 'none'}")
    hp = dict(payload); hp[f"item_{fid}__fluent_sf"] = "http://spam"; results.append(f"{lang} honeypot filled -> {go(hp).status_code} (want 422)")
    nc = {k: v for k, v in payload.items() if k != t["consent_field"]}; rr = go(nc); results.append(f"{lang} no consent -> {rr.status_code} (want 423): {rr.text[:80]}")
    bl = dict(payload); [bl.__setitem__(k, "") for k in t["required_fields"]]; rr = go(bl); results.append(f"{lang} blank required -> {rr.status_code} (want 423)")
    be = dict(payload); be[t["email_field"]] = "not-an-email"; results.append(f"{lang} bad email -> {go(be).status_code} (want 423)")
    subs = ff("/submissions", form_id=fid, per_page=20)["data"]; deleted = 0
    for s in subs:
        resp = json.loads(s["response"]) if isinstance(s["response"], str) else s["response"]
        if any(str(v).startswith(t["marker"]) for v in resp.values()): wp.delete(f"/fluentform/v1/submissions/{s['id']}"); deleted += 1
    results.append(f"{lang} entries stored during test: {len(subs)} → deleted {deleted}; entries remaining: {ff('/submissions', form_id=fid)['total']}")
report(cfg, "04 fluent forms", lines + results)
json.dump(ids, open(cfg["_path"].replace("launch.json", "launch-runs/fluentform_ids.json"), "w"))
