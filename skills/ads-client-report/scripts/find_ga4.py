#!/usr/bin/env python3
"""Find a client's GA4 property id, so nobody ever writes null into a config again.

A missing ga4_property silently drops the whole visitor-behaviour section from the
report — the output still looks complete, which is the dangerous kind of wrong.

  python3 find_ga4.py                 # list every property the studio credential sees
  python3 find_ga4.py --match serenite
  python3 find_ga4.py --verify 504027223 --domain serenitemedicalandspa.com
"""
import argparse, json, subprocess, sys, urllib.request

def tok():
    return subprocess.check_output(["gcloud","auth","application-default","print-access-token"], text=True).strip()
def get(url, t):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"Authorization":f"Bearer {t}"}), timeout=20))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--match"); ap.add_argument("--verify"); ap.add_argument("--domain")
    a=ap.parse_args(); t=tok()
    if a.verify:
        d=get(f"https://analyticsadmin.googleapis.com/v1alpha/properties/{a.verify}/dataStreams", t)
        ok=False
        for s in d.get("dataStreams",[]):
            w=s.get("webStreamData",{}); uri=w.get("defaultUri","")
            print(f"  stream {s.get('displayName')}  measurement={w.get('measurementId')}  uri={uri}")
            if a.domain and a.domain.lower() in uri.lower(): ok=True
        if a.domain:
            print(f"\n  {'MATCHES' if ok else 'DOES NOT MATCH'} {a.domain}")
            sys.exit(0 if ok else 1)
        return
    d=get("https://analyticsadmin.googleapis.com/v1beta/accountSummaries?pageSize=200", t)
    for acc in d.get("accountSummaries",[]):
        for p in acc.get("propertySummaries",[]):
            line=f"{acc.get('displayName')} / {p.get('displayName')}"
            if a.match and a.match.lower() not in line.lower(): continue
            print(f"  {p.get('property'):<26} {line}")

if __name__=="__main__": main()
