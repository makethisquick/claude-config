"""Apply Joan's 2026-09-16 answers to the live pages. Every edit is keyed by css id or exact text; idempotent."""
from wpapi import *
import json, re, html
ALL=dict(PAGES); ALL.update({43:"thank-you",44:"gracias",45:"privacy",46:"privacidad"})
ES={29,30,31,32,33,34,35,44,46}
HOURS_EN="Phones answered Monday to Saturday 7am–9pm, Sunday 7am–5pm."
HOURS_ES="Atendemos el teléfono de lunes a sábado de 7am a 9pm y los domingos de 7am a 5pm."
LIC_EN="NJ Certified Commercial Pesticide Applicator — Joan Volquez, #65136B."
LIC_ES="Aplicadora comercial de pesticidas certificada en NJ — Joan Volquez, N.º 65136B."
PRICE_EN="Every job is priced after a free inspection — it depends on the size of the home and the job. Call 908-285-3404 to book one."
PRICE_ES="Cada trabajo se cotiza después de una inspección gratuita: depende del tamaño de la casa y del trabajo. Llame al 908-285-3404 para programarla."
TOWN_EN="Town-level pages for Newark, Paterson, Elizabeth, Jersey City, East Orange, New Brunswick, Union City, Woodbridge and North Plainfield are in preparation."
TOWN_ES="Las páginas por pueblo de Newark, Paterson, Elizabeth, Jersey City, East Orange, New Brunswick, Union City, Woodbridge y North Plainfield están en preparación."
CTA={"Request a Quote":"Get a Free Inspection","Pida una cotización":"Solicite una inspección gratuita","Or request a quote →":"Or book a free inspection →","O pida una cotización →":"O solicite una inspección gratuita →"}
SVC_LINKS={"elm-h3-g2":"/services/pest-control/","elm-h3-g3":"/services/rodent-control/","elm-h3-g4":"/services/cockroach-control/","elm-h3-g5":"/services/termite-control/","elm-h3-g6":"/services/integrated-pest-management/",
           "elm-h3-svc2":"/services/pest-control/","elm-h3-svc3":"/services/rodent-control/","elm-h3-svc4":"/services/cockroach-control/","elm-h3-svc5":"/services/termite-control/","elm-h3-svc6":"/services/integrated-pest-management/"}
ES_SVC={"control de plagas":"/es/servicios/control-de-plagas/","roedores":"/es/servicios/control-de-roedores/","cucarachas":"/es/servicios/control-de-cucarachas/","termitas":"/es/servicios/control-de-termitas/","manejo integrado":"/es/servicios/manejo-integrado-de-plagas/","integrado":"/es/servicios/manejo-integrado-de-plagas/"}
PEST_EN={"/services/":"/services/pest-control/"}  # pest-grid tiles pointing at the hub now point at the service pages
GRID_MAP_EN={"Cockroaches":"/services/cockroach-control/","Rats & mice":"/services/rodent-control/","Termites":"/services/termite-control/","Spiders":"/services/pest-control/","Wasps & bees":"/services/pest-control/"}
GRID_MAP_ES={"Cucarachas":"/es/servicios/control-de-cucarachas/","Ratas y ratones":"/es/servicios/control-de-roedores/","Termitas":"/es/servicios/control-de-termitas/","Arañas":"/es/servicios/control-de-plagas/","Avispas y abejas":"/es/servicios/control-de-plagas/"}
def txt(s):
    for k in ("paragraph","title","text"):
        v=s.get(k)
        if isinstance(v,dict): return k, v["value"]["content"]["value"]
    return None, ""
log={}
def bump(k): log[k]=log.get(k,0)+1
for pid,slug in ALL.items():
    els=json.loads(page_data(pid)); es=pid in ES; drop=[]
    def walk(l, parent=None):
        for e in list(l):
            s=e.get("settings",{}); c=s.get("_cssid",{}).get("value") if isinstance(s.get("_cssid"),dict) else (s.get("_element_id") or "")
            k,t=txt(s); th=html.unescape(t)
            # 1 hours
            if c.startswith("elm-pending") and c.endswith("-hours") or c in ("elm-pending-conhours","elm-pending-conhours-es","elm-pending-foot-hours"):
                s[k]["value"]["content"]["value"]=HOURS_ES if es else HOURS_EN; s["_cssid"]["value"]=c.replace("elm-pending","elm-foot").replace("elm-foot-conhours","elm-p-conhours"); bump("hours")
            # 2 licence
            elif c.startswith("elm-pending") and c.endswith("-licence") or c in ("elm-pending-abtlicence",):
                s[k]["value"]["content"]["value"]=LIC_ES if es else LIC_EN; s["_cssid"]["value"]=c.replace("elm-pending","elm-foot"); bump("licence")
            # 3 prices
            elif c=="elm-pending-plans-price": s[k]["value"]["content"]["value"]=PRICE_EN; s["_cssid"]["value"]="elm-p-plans-price"; bump("price")
            # 7 reviews, 8 ants/mosquito/tick, 3 bios → delete
            elif c in ("elm-p-abtnoreview","elm-p-abtnoreview-es","elm-pending-svc-more","elm-pending-svces-more","elm-pending-bios","elm-pending-bios-es"):
                l.remove(e); bump("removed:"+c); continue
            # 6 town note
            elif c in ("elm-pending-njnote","elm-pending-njnota-es"): s[k]["value"]["content"]["value"]=TOWN_ES if es else TOWN_EN; s["_cssid"]["value"]=c.replace("elm-pending","elm-p"); bump("town")
            # 9 CTAs
            elif k and th.strip() in CTA: s[k]["value"]["content"]["value"]=CTA[th.strip()]; bump("cta")
            # 8 service card links (EN) + ES by title keyword
            if c in SVC_LINKS: s["link"]={"$$type":"link","value":{"destination":{"$$type":"url","value":SVC_LINKS[c]},"tag":{"$$type":"string","value":"a"}}}; bump("cardlink")
            elif es and e.get("widgetType")=="e-heading" and c.startswith(("elm-h3-sv","elm-h3-svces","elm-h3-card","elm-h3-g")) and "chinches" not in th.lower():
                for key,url in ES_SVC.items():
                    if key in th.lower(): s["link"]={"$$type":"link","value":{"destination":{"$$type":"url","value":url},"tag":{"$$type":"string","value":"a"}}}; bump("cardlink-es"); break
            # html widgets: pest grid tiles, credential table, SAM row
            h=s.get("html")
            if isinstance(h,str) and "elm-pestgrid" in h:
                for label in ("Ants","Mosquitoes","Hormigas","Mosquitos"):
                    h2=re.sub(r'<li><a href="[^"]*"><svg.*?</svg><span>'+re.escape(label)+r'</span></a></li>', '', h, flags=re.S)
                    if h2!=h: h=h2; bump("tile-removed:"+label)
                for label,url in (GRID_MAP_ES if es else GRID_MAP_EN).items():
                    h=re.sub(r'(<li><a href=")[^"]*("><svg.*?</svg><span>'+re.escape(label)+r'</span>)', r'\g<1>'+url+r'\2', h, flags=re.S)
                s["html"]=h; bump("pestgrid")
            if isinstance(h,str) and "elm-table-creds" in h:
                h=h.replace("Active. <em>Expiry date &mdash; verification in progress, available on request.</em>","Active; renewed annually each June.")
                h=h.replace("<em>Verification in progress, available on request.</em>","Joan Volquez, NJ Certified Commercial Pesticide Applicator #65136B (individual certification)")
                h=h.replace("Activo. <em>Fecha de vencimiento &mdash; verificaci&oacute;n en curso, disponible a solicitud.</em>","Activo; se renueva cada año en junio.").replace("<em>Verificaci&oacute;n en curso, disponible a solicitud.</em>","Joan Volquez, aplicadora comercial de pesticidas certificada en NJ, N.º 65136B (certificación individual)")
                h=re.sub(r"<caption>.*?</caption>", "<caption>Credential register for ELIMINATIS LLC.</caption>" if not es else "<caption>Registro de credenciales de ELIMINATIS LLC.</caption>", h, count=1, flags=re.S)
                s["html"]=h; bump("credtable")
            walk(e.get("elements",[]), e)
    walk(els)
    # 9b government internal note; 3 About h1/h2 handled in about_rewrite.py
    set_page_data(pid, json.dumps(els, ensure_ascii=False, separators=(",",":")))
print(json.dumps(log, indent=1)); clear_elementor_cache()
