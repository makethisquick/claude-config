"""Phase 7a — Google Ads: create the client account under the studio MCC (empty, no campaigns, no billing) and
write the customer id back into launch.json. Idempotent (matches by descriptive name).
Run through the Ads env wrapper so the developer token comes from the Keychain:
  ~/.claude/skills/client-launch/scripts/ads_env.sh 07_ads_account.py ~/projects/<Client>/launch.json
Campaign BUILD is 07c and runs only after the client approves the draft (07b). Billing is a human step:
Ads → Billing → payments profile — never entered by the agent."""
import sys, json
import os
cfg = json.load(open(sys.argv[1])); A = cfg["ads"]
# Reuse the studio's ADC-based client factory (google-ads-write/gads_write/client.py): ADC credentials + dev token
# from the env the wrapper sets. The raw GoogleAdsClient.load_from_dict needs client_id/secret/refresh_token,
# which we deliberately do not keep — ADC is the one credential.
os.environ["GOOGLE_ADS_LOGIN_CUSTOMER_ID"] = A["mcc_customer_id"]
from gads_write.client import get_client
client = get_client()
svc = client.get_service("CustomerService"); ga = client.get_service("GoogleAdsService"); MCC = A["mcc_customer_id"]
existing = [r for r in ga.search(customer_id=MCC, query="SELECT customer_client.id, customer_client.descriptive_name FROM customer_client WHERE customer_client.level = 1") if r.customer_client.descriptive_name == A["account_name"]]
if existing: cid = str(existing[0].customer_client.id); print("account already exists:", cid)
else:
    cust = client.get_type("Customer"); cust.descriptive_name = A["account_name"]; cust.currency_code = A.get("currency", "USD"); cust.time_zone = A.get("time_zone", "America/New_York")
    try:
        r = svc.create_customer_client(customer_id=MCC, customer_client=cust); cid = r.resource_name.split("/")[-1]; print("created:", r.resource_name)
    except Exception as e:
        if "DEVELOPER_TOKEN_NOT_APPROVED" in str(e) or "explorer access" in str(e):
            print("BLOCKED: the developer token is at Explorer access; Google does not allow CreateCustomerClient below Basic.")
            print(f"HUMAN STEP (now): ads.google.com → MCC {MCC} → Accounts → + → Create new account → '{A['account_name']}', {A.get('currency','USD')}, {A.get('time_zone','America/New_York')}; then re-run this script — it will find the account by name and write the id.")
            print("HUMAN STEP (once): Ads → Tools → API Center → apply for Basic access, so this becomes automatic.")
            sys.exit(2)
        raise
row = next(iter(ga.search(customer_id=cid, query="SELECT customer.descriptive_name, customer.currency_code, customer.time_zone, customer.status FROM customer")))
print(cid, "|", row.customer.descriptive_name, row.customer.currency_code, row.customer.time_zone, row.customer.status.name)
A["customer_id"] = cid; json.dump(cfg, open(sys.argv[1], "w"), indent=1, ensure_ascii=False)
print(f"HUMAN STEP: add a payment method — https://ads.google.com/aw/billing/summary?ocid=&__c={cid} (Ads → Billing → Payments profile). Media spend should bill to the CLIENT's payments profile; the studio invoices management separately.")
