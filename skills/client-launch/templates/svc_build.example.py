"""Build the service pages from svc/*.json by cloning the bed-bug template (EN 15 / ES 31)."""
from wpapi import *
import json, copy, secrets, re, html, requests, sys
SITE="https://eliminatis.com"
EN_MAP={"elm-eyebrow-bb":"eyebrow","elm-h1-bb":"h1","elm-lede-bb":"lede","elm-proof-bb1":"proof1","elm-proof-bb2":"proof2","elm-proof-bb3":"proof3",
 "elm-h2-symptom":"symptom_h2","elm-lede-symptom":"symptom_lede","elm-sym1":"sym1","elm-sym2":"sym2","elm-sym3":"sym3","elm-sym4":"sym4","elm-sym5":"sym5","elm-link-symptomcall":"symptom_call",
 "elm-h2-methodbb":"method_h2","elm-p-methodbb":"method_p","elm-mb1":"mb1","elm-mb2":"mb2","elm-mb3":"mb3","elm-mb4":"mb4","elm-mb5":"mb5",
 "elm-h2-prep":"prep_h2","elm-pr1":"pr1","elm-pr2":"pr2","elm-pr3":"pr3","elm-pr4":"pr4","elm-pr5":"pr5",
 "elm-h2-njlaw":"nj_h2","elm-p-njlaw1":"nj_p1","elm-p-njlaw2":"nj_p2","elm-p-njlaw3":"nj_p3","elm-p-njlaw4":"nj_p4","elm-p-njdisclaim":"nj_disclaim",
 "elm-h2-safety":"safety_h2","elm-p-safety1":"safety_p1","elm-p-safety2":"safety_p2","elm-p-safety3":"safety_p3",
 "elm-h2-plans":"plans_h2","elm-p-plans":"plans_p","elm-p-plans-price":"plans_price","elm-h2-faqbb":"faq_h2","elm-h2-bbcta":"cta_h2","elm-p-bbcta":"cta_p"}
ES_MAP={"elm-eyebrow-chi":"eyebrow","elm-h1-chi":"h1","elm-lede-chi":"lede","elm-proof-chi0":"proof1","elm-proof-chi1":"proof2","elm-proof-chi2":"proof3",
 "elm-h2-sintomas":"symptom_h2","elm-lede-sintomas":"symptom_lede","elm-xlist-sintomas-0":"sym1","elm-xlist-sintomas-1":"sym2","elm-xlist-sintomas-2":"sym3","elm-xlist-sintomas-3":"sym4","elm-xlist-sintomas-4":"sym5","elm-link-sintomascall":"symptom_call",
 "elm-h2-metodochi":"method_h2","elm-p-metodochi":"method_p","elm-xlist-metodochi-0":"mb1","elm-xlist-metodochi-1":"mb2","elm-xlist-metodochi-2":"mb3","elm-xlist-metodochi-3":"mb4","elm-xlist-metodochi-4":"mb5",
 "elm-h2-prepchi":"prep_h2","elm-xlist-prepchi-0":"pr1","elm-xlist-prepchi-1":"pr2","elm-xlist-prepchi-2":"pr3","elm-xlist-prepchi-3":"pr4","elm-xlist-prepchi-4":"pr5",
 "elm-h2-njlawes":"nj_h2","elm-p-njes1":"nj_p1","elm-p-njes2":"nj_p2","elm-p-njes3":"nj_p3","elm-p-njes4":"nj_p4","elm-p-njesdisc":"nj_disclaim",
 "elm-h2-faqchi":"faq_h2","elm-h2-chicta":"cta_h2","elm-p-chicta":"cta_p"}
TEMPLATES={"en":(15,EN_MAP,"/services/bed-bug-treatment/","Bed Bug Treatment","Bed bug treatment"),"es":(31,ES_MAP,"/es/servicios/control-de-chinches/","Control de chinches","Control de chinches")}
PARENT={"en":13,"es":30}
def newids(e):
    e["id"]=secrets.token_hex(4)[:7]
    for k in e.get("elements",[]): newids(k)
def esc(t): return html.escape(t, quote=False)
def faq_html(fid, items, lang):
    parts=[]
    for i,it in enumerate(items):
        parts.append(f'<details{" open" if i==0 else ""}><summary><h3>{esc(it["q"])}</h3></summary><div><p{" lang=\"es\"" if lang=="es" else ""}>{esc(it["a"])}</p></div></details>')
    return f'<div id="elm-faq-{fid}">'+"".join(parts)+'</div>'
def build(spec, lang):
    tid,MAP,tpath,tcrumb,tname=TEMPLATES[lang]; C=spec[lang]; other=spec["es" if lang=="en" else "en"]
    path=("/services/" if lang=="en" else "/es/servicios/")+C["slug"]+"/"; opath=("/es/servicios/" if lang=="en" else "/services/")+other["slug"]+"/"
    en_path=path if lang=="en" else opath; es_path=opath if lang=="en" else path
    src=json.loads(page_data(tid)); out=[]
    for e in src:
        e=copy.deepcopy(e); newids(e); out.append(e)
    def walk(l):
        for e in l:
            s=e.get("settings",{}); c=s.get("_cssid",{}).get("value") if isinstance(s.get("_cssid"),dict) else ""
            if c in MAP:
                key=MAP[c]
                for k in ("paragraph","title","text"):
                    v=s.get(k)
                    if isinstance(v,dict): v["value"]["content"]["value"]=C[key]
            h=s.get("html")
            if isinstance(h,str):
                if "data-elm-bilingual" in h:
                    h=re.sub(r'SELF="[^"]*"', f'SELF="{path}"', h); h=re.sub(r'\bEN="[^"]*"', f'EN="{en_path}"', h); h=re.sub(r'\bES="[^"]*"', f'ES="{es_path}"', h)
                elif "elm-langswitch" in h: h=h.replace(tpath, path).replace(TEMPLATES["es" if lang=="en" else "en"][2], opath)
                elif "elm-breadcrumb-list" in h: h=h.replace(f'aria-current="page">{tcrumb}<', f'aria-current="page">{C["crumb"]}<').replace("elm-crumb-bb-ol","elm-crumb-svc-ol").replace("elm-crumb-chi-ol","elm-crumb-svc-ol")
                elif "<details" in h: h=faq_html("svc", C["faq"], lang)
                elif "application/ld+json" in h:
                    g=json.loads(re.search(r"<script[^>]*>(.*)</script>", h, re.S).group(1))
                    for node in g["@graph"]:
                        t=node.get("@type")
                        if t=="BreadcrumbList": node["itemListElement"][-1]["name"]=C["crumb"]
                        elif t=="Service": node.update({"serviceType":C["crumb"],"name":C["crumb"],"description":C["lede"][:200]})
                        elif t=="FAQPage": node["mainEntity"]=[{"@type":"Question","name":it["q"],"acceptedAnswer":{"@type":"Answer","text":it["a"]}} for it in C["faq"]]
                        elif t=="WebPage" or (isinstance(t,str) and t.endswith("Page") and t!="FAQPage"):
                            for k in ("@id","url"):
                                if k in node: node[k]=node[k].replace(tpath, path)
                            if "name" in node: node["name"]=C["seo_title"]
                            if "description" in node: node["description"]=C["seo_desc"]
                    h='<script type="application/ld+json">'+json.dumps(g, ensure_ascii=False, separators=(",",":"))+'</script>'
                h=h.replace(tpath, path)
                s["html"]=h
            walk(e.get("elements",[]))
    walk(out)
    # hero photo: reuse the services-hub hero id so the bed photo does not appear on a roach page
    for e in out:
        c=e["settings"].get("_cssid",{}).get("value","")
        if c.startswith("elm-hero-"): e["settings"]["_cssid"]["value"]="elm-hero-services" if lang=="en" else "elm-hero-servicios"
    data=json.dumps(out, ensure_ascii=False, separators=(",",":"))
    ex=[p for p in get("/wp/v2/pages", slug=C["slug"], status="any") if p["parent"]==PARENT[lang]]
    payload={"title":C["crumb"],"slug":C["slug"],"status":"publish","template":"elementor_canvas","parent":PARENT[lang],"meta":{"_elementor_data":data,"_elementor_edit_mode":"builder","_elementor_template_type":"wp-page"}}
    r=post(f"/wp/v2/pages/{ex[0]['id']}", payload) if ex else post("/wp/v2/pages", payload)
    pid=r["id"]; link=r["link"]
    og=json.load(open("media_ids.json"))["eliminatis-og-es.png" if lang=="es" else "eliminatis-og-en.png"]
    requests.post(SITE+"/wp-json/rankmath/v1/updateMeta", auth=AUTH, json={"objectID":pid,"objectType":"post","meta":{"rank_math_title":C["seo_title"],"rank_math_description":C["seo_desc"],"rank_math_robots":["index"],"rank_math_facebook_image":og["url"],"rank_math_facebook_image_id":og["id"],"rank_math_twitter_use_facebook":"on"}})
    return pid, link, path
if __name__=="__main__":
    out={}
    for slug in ("pest-control","rodent-control","cockroach-control","termite-control","integrated-pest-management"):
        spec=json.load(open(f"svc/{slug}.json"))
        for lang in ("en","es"):
            pid,link,path=build(spec,lang); out[f"{slug}:{lang}"]={"id":pid,"url":link}; print(lang, pid, link)
    json.dump(out, open("svc_ids.json","w"), indent=1); clear_elementor_cache()
