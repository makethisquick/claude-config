# Pre-launch email to the client — send WITH the payment-method request, before campaigns are enabled

Why this exists: Eliminatis "launched" and then sat at zero impressions for three days because Google
Payments wanted the client to verify their card, and nobody had warned them it was coming. Every API
status read green the whole time. This email converts a silent multi-day outage into an expected step.

Keep it in plain language. No jargon, no ids, no account numbers.

---

**Subject:** One or two things Google may ask you for before your ads start

Hi {{client_first_name}},

Your campaigns are built and ready. Before they can start showing, Google usually asks the account
owner — that's you, not us — for one or two confirmations. None of them take long, but **ads do not run
until they're done**, so I want you to know what to expect rather than wonder why it's quiet.

**1. Verifying your payment method.** After you add a card, Google often places a small temporary charge
(around $1.95) and asks you to confirm a code. The code is *inside the description of that charge* on
your statement — your bank app may shorten it, so open the transaction detail or ring the bank and ask
for the full merchant description. Google refunds the charge automatically.

**2. Verifying your identity or business.** Google sometimes asks for photo ID or a business document
(your EIN letter or formation certificate). This is routine for new advertisers. It takes **1–3 business
days** after you upload, and only you can do it — we have no access to that part of your account.

**3. A terms box to tick.** If your ads show your phone number, Google will ask you to accept its Call
Ads terms. It's one click, and the phone button won't show until it's accepted.

**What we'll be doing meanwhile:** we'll watch the account daily and tell you the moment it starts
serving. If you get an email from Google Payments that looks like a request to verify something, it's
almost certainly genuine — but forward it to me if you'd like me to check before you act.

**One thing worth knowing about measurement.** We track form submissions and taps on your phone number
from the website, and we can tell you which search produced each one. What no system can tell us is
whether a call was *answered* or became a job — so if your phone rings and someone says they found you
on Google, that's worth telling me. It's how we learn which searches are actually worth paying for.

Thanks,
{{sender}}

---

## How to use
- Send at phase 07b (with the approval doc / payment-method request), NEVER after enabling.
- Fill `client_first_name` and `sender` from `launch.json`.
- Drop point 3 if the campaign has no call asset.
- Keep the last paragraph: it sets the expectation that the client reports back on calls, which is the
  only way to close the loop a `tel:` tap cannot (a tap proves intent, never a conversation).
