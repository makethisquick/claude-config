"""Phase 7a — Google Ads: create the client account under the studio MCC (empty, no campaigns, no billing) and
write the customer id back into launch.json. Idempotent (matches by descriptive name).
Run through the Ads env wrapper so the developer token comes from the Keychain:
  ~/.claude/skills/client-launch/scripts/ads_env.sh 07_ads_account.py ~/projects/<Client>/launch.json
Campaign BUILD is 07c and runs only after the client approves the draft (07b). Billing is a human step:
Ads → Billing → payments profile — never entered by the agent.

Self-test (no account created, nothing to clean up):
  ~/.claude/skills/client-launch/scripts/ads_env.sh 07_ads_account.py --selftest
sends CreateCustomerClient with validate_only=True against the studio MCC. Google checks the whole request —
including whether the developer token's access level (must be Basic+) permits the call — and returns an empty
response on success. The Ads API has NO delete/cancel-account call, so this is the only residue-free test;
a real dummy account could only be cancelled by hand in the UI. Preflight (00) runs this automatically."""
import sys, json
import os
SELFTEST = "--selftest" in sys.argv
if SELFTEST:
    A = {"mcc_customer_id": os.environ.get("GOOGLE_ADS_MCC", "1018945450"), "account_name": "client-launch selftest (validate_only)"}
else:
    cfg = json.load(open(sys.argv[1])); A = cfg["ads"]
# Reuse the studio's ADC-based client factory (google-ads-write/gads_write/client.py): ADC credentials + dev token
# from the env the wrapper sets. The raw GoogleAdsClient.load_from_dict needs client_id/secret/refresh_token,
# which we deliberately do not keep — ADC is the one credential.
os.environ["GOOGLE_ADS_LOGIN_CUSTOMER_ID"] = A["mcc_customer_id"]
from gads_write.client import get_client
client = get_client()
svc = client.get_service("CustomerService"); ga = client.get_service("GoogleAdsService"); MCC = A["mcc_customer_id"]
existing = [r for r in ga.search(customer_id=MCC, query="SELECT customer_client.id, customer_client.descriptive_name FROM customer_client WHERE customer_client.level = 1") if r.customer_client.descriptive_name == A["account_name"]]
def create_request(validate_only=False):
    req = client.get_type("CreateCustomerClientRequest"); req.customer_id = MCC; req.validate_only = validate_only
    req.customer_client.descriptive_name = A["account_name"]; req.customer_client.currency_code = A.get("currency", "USD"); req.customer_client.time_zone = A.get("time_zone", "America/New_York")
    return req
def explain_block(e):
    if "DEVELOPER_TOKEN_NOT_APPROVED" in str(e) or "explorer access" in str(e).lower():
        print("BLOCKED: the developer token is below Basic access; Google does not allow CreateCustomerClient at Explorer.")
        print("HUMAN STEP (once): console.cloud.google.com → Google Ads API → Overview → Apply for access (Basic). Needs Brand Verification on the OAuth app first — see LEARNINGS.md 2026-09-18.")
        return True
    return False
if SELFTEST:
    try: svc.create_customer_client(request=create_request(validate_only=True)); print("ok   CreateCustomerClient validate_only accepted (dev token access level permits account creation)"); sys.exit(0)
    except Exception as e:
        explain_block(e) or print("ERR:", str(e)[:400]); sys.exit(2)
if existing: cid = str(existing[0].customer_client.id); print("account already exists:", cid)
else:
    try:
        r = svc.create_customer_client(request=create_request()); cid = r.resource_name.split("/")[-1]; print("created:", r.resource_name)
    except Exception as e:
        if explain_block(e):
            print(f"HUMAN STEP (now): ads.google.com → MCC {MCC} → Accounts → + → Create new account → '{A['account_name']}', {A.get('currency','USD')}, {A.get('time_zone','America/New_York')}; then re-run this script — it will find the account by name and write the id.")
            sys.exit(2)
        raise
row = next(iter(ga.search(customer_id=cid, query="SELECT customer.descriptive_name, customer.currency_code, customer.time_zone, customer.status FROM customer")))
print(cid, "|", row.customer.descriptive_name, row.customer.currency_code, row.customer.time_zone, row.customer.status.name)
A["customer_id"] = cid; json.dump(cfg, open(sys.argv[1], "w"), indent=1, ensure_ascii=False)
print(f"HUMAN STEP: add a payment method — https://ads.google.com/aw/billing/summary?ocid=&__c={cid} (Ads → Billing → Payments profile). Media spend should bill to the CLIENT's payments profile; the studio invoices management separately.")
