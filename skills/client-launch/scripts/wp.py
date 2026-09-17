"""Shared REST helper for client-launch. Everything is scoped by launch.json — never a hard-coded site.
ZERO-TOLERANCE ISOLATION: the site, user and Keychain service all come from the one config file
passed on the command line; nothing here can reach any other client's site."""
import subprocess, json, sys, os, requests

def load(path):
    cfg = json.load(open(path)); cfg["_path"] = os.path.abspath(path)
    cfg.setdefault("keychain_service", "wp-" + cfg["slug"])
    return cfg

class WP:
    def __init__(self, cfg):
        self.cfg = cfg; self.site = cfg["site_url"].rstrip("/")
        pw = subprocess.check_output(["security", "find-generic-password", "-s", cfg["keychain_service"], "-w"]).decode().strip()
        self.auth = (cfg["wp_user"], pw)
    def get(self, path, **params):
        r = requests.get(self.site + "/wp-json" + path, auth=self.auth, params=params); r.raise_for_status(); return r.json()
    def post(self, path, payload=None, **kw):
        r = requests.post(self.site + "/wp-json" + path, auth=self.auth, json=payload, **kw)
        if r.status_code >= 400: print("ERR", path, r.status_code, r.text[:300], file=sys.stderr)
        return r.json() if r.text else None
    def delete(self, path, **params):
        r = requests.delete(self.site + "/wp-json" + path, auth=self.auth, params=params); return r.status_code, (r.json() if r.text else None)
    def page_data(self, pid):
        return self.get(f"/wp/v2/pages/{pid}", context="edit", _fields="id,slug,meta")["meta"]["_elementor_data"]
    def set_page_data(self, pid, data_str):
        return self.post(f"/wp/v2/pages/{pid}", {"meta": {"_elementor_data": data_str}})
    def clear_cache(self):
        r = requests.delete(self.site + "/wp-json/elementor/v1/cache", auth=self.auth); return r.status_code
    def pages(self, status="publish"):
        out, page = [], 1
        while True:
            b = self.get("/wp/v2/pages", per_page=100, page=page, status=status, _fields="id,slug,link,parent,title,template")
            out += b
            if len(b) < 100: return out
            page += 1
    def plugin(self, plugin_file):
        try: return self.get(f"/wp/v2/plugins/{plugin_file}")
        except Exception: return None
    def plugins(self): return self.get("/wp/v2/plugins")
    def install_plugin(self, slug, status="active"):
        r = self.post("/wp/v2/plugins", {"slug": slug, "status": status}); return r
    def set_plugin(self, plugin_file, status):
        return self.post(f"/wp/v2/plugins/{plugin_file}", {"status": status})

def cid(e):
    s = e.get("settings", {}); c = s.get("_cssid")
    return (c.get("value") if isinstance(c, dict) else None) or s.get("_element_id") or ""

def walk(elements, fn):
    """Depth-first over an Elementor tree; fn(element, parent_list, index) may mutate in place."""
    for i, e in enumerate(list(elements)):
        fn(e, elements, i); walk(e.get("elements", []), fn)

def dumps(els): return json.dumps(els, ensure_ascii=False, separators=(",", ":"))

def report(cfg, step, lines):
    """Append to the run log next to launch.json — the client-side record of what the skill did."""
    d = os.path.dirname(cfg["_path"]); os.makedirs(os.path.join(d, "launch-runs"), exist_ok=True)
    import datetime; ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(os.path.join(d, "launch-runs", "RUNLOG.md"), "a") as f:
        f.write(f"\n## {ts} — {step}\n" + "\n".join("- " + l for l in lines) + "\n")
    for l in lines: print(f"[{step}] {l}")
