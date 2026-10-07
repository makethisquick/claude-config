"""Account-level settings.

These live on the Customer resource and go through CustomerService, not the
GoogleAdsService batch everything else uses. They are few, they are blunt, and
each one changes behaviour across every campaign at once.
"""

from typing import Any

from google.protobuf.field_mask_pb2 import FieldMask

from ..client import get_client, normalize_customer_id
from ..safety import apply_customer


def set_call_reporting(
    customer_id: str,
    enabled: bool,
    conversion_reporting_enabled: bool | None = None,
    call_conversion_action_id: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Turns Google forwarding numbers (call reporting) on or off for the account.

    When call reporting is ON, Google swaps the advertiser's number for a
    forwarding number in call assets and call ads, which is the only way calls
    from ads get a duration, a status and a conversion. When it is OFF, ad-driven
    phone calls produce no data at all — for a business whose main conversion is
    a phone call that means the primary lead channel is invisible.

    The catch: forwarding numbers are also how Google records calls. On a
    healthcare account that is a HIPAA question, not a preference. Serenite has a
    written call-recording exemption (ticket 1-1882000041684, approved
    2026-09-23) covering call assets and call ads, which is what makes turning
    this back on safe there. Do not enable it on a covered entity that lacks one.

    conversion_reporting_enabled and call_conversion_action_id control which
    conversion action counts the calls; leave them unset to keep what the account
    already has.
    """
    client = get_client()
    cid = normalize_customer_id(customer_id)

    op = client.get_type("CustomerOperation")
    customer = op.update
    customer.resource_name = client.get_service("CustomerService").customer_path(cid)
    customer.call_reporting_setting.call_reporting_enabled = bool(enabled)

    paths = ["call_reporting_setting.call_reporting_enabled"]
    summary: dict[str, Any] = {
        "action": "set_call_reporting",
        "call_reporting_enabled": bool(enabled),
    }

    if conversion_reporting_enabled is not None:
        customer.call_reporting_setting.call_conversion_reporting_enabled = bool(
            conversion_reporting_enabled
        )
        paths.append("call_reporting_setting.call_conversion_reporting_enabled")
        summary["call_conversion_reporting_enabled"] = bool(conversion_reporting_enabled)

    if call_conversion_action_id:
        customer.call_reporting_setting.call_conversion_action = client.get_service(
            "ConversionActionService"
        ).conversion_action_path(cid, call_conversion_action_id)
        paths.append("call_reporting_setting.call_conversion_action")
        summary["call_conversion_action_id"] = call_conversion_action_id

    client.copy_from(op.update_mask, FieldMask(paths=paths))

    return apply_customer(cid, op, confirm, summary)
