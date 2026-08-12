"""Conversion actions and conversion goals.

Everything else in this server builds *traffic*. This module is about what
counts as a result once the traffic arrives, which is what bidding optimises
towards.

There are two separate layers in v25, and they are easy to confuse:

| Layer | Resource | What it controls |
|---|---|---|
| The action | `ConversionAction` | One trackable event — a form submit, a call, a tap on "Directions". Carries `status` and `primary_for_goal`. |
| The goal | `CustomerConversionGoal` / `CampaignConversionGoal` | A `(category, origin)` *bucket* of actions, carrying `biddable`. |

A goal is not a thing you create. Google materialises one row per
`(category, origin)` combination the account has actions for, and the only
writable field on it is `biddable`. So there is no create and no remove here —
`CustomerConversionGoalOperation` and `CampaignConversionGoalOperation` have an
`update` field and nothing else. All four tools below are updates with a
`FieldMask`.

`FieldMask` is imported from protobuf directly. `client.get_type("FieldMask")`
raises — it is a protobuf well-known type, not a Google Ads type, so it is not
in the v25 type registry. That bug killed every update tool in this server once
already; do not reintroduce it.

**Not every conversion action is mutable.** `GOOGLE_HOSTED` actions (the
Google Business Profile ones: "Local actions - Directions", "Clicks to call")
are owned by Google, not by the advertiser, and may reject `status` or
`primary_for_goal` mutations. When that happens the API error is reported
verbatim rather than worked around — the goal-level `biddable` flag is the
supported lever for those.
"""

from typing import Any

from google.protobuf.field_mask_pb2 import FieldMask

from ..client import get_client, normalize_customer_id
from ..safety import apply

# --------------------------------------------------------------------------
# value maps — human-readable in, v25 enum name out
# --------------------------------------------------------------------------

# ConversionActionStatusEnum. There is no PAUSED: HIDDEN is the "stop counting
# it, keep the history" state, REMOVED is the delete.
_STATUSES = {
    "enabled": "ENABLED",
    "active": "ENABLED",
    "on": "ENABLED",
    "removed": "REMOVED",
    "deleted": "REMOVED",
    "hidden": "HIDDEN",
    "hide": "HIDDEN",
    "off": "HIDDEN",
}
_STATUS_CHOICES = ["ENABLED", "REMOVED", "HIDDEN"]

# ConversionActionCategoryEnum, minus UNSPECIFIED/UNKNOWN which are never
# writable. Keys are the enum names in lower-hyphen form; the aliases below add
# the words the Google Ads UI actually shows.
_CATEGORY_NAMES = [
    "DEFAULT",
    "PAGE_VIEW",
    "PURCHASE",
    "SIGNUP",
    "DOWNLOAD",
    "ADD_TO_CART",
    "BEGIN_CHECKOUT",
    "SUBSCRIBE_PAID",
    "PHONE_CALL_LEAD",
    "IMPORTED_LEAD",
    "SUBMIT_LEAD_FORM",
    "BOOK_APPOINTMENT",
    "REQUEST_QUOTE",
    "GET_DIRECTIONS",
    "OUTBOUND_CLICK",
    "CONTACT",
    "ENGAGEMENT",
    "STORE_VISIT",
    "STORE_SALE",
    "QUALIFIED_LEAD",
    "CONVERTED_LEAD",
    "YOUTUBE_FOLLOW_ON_VIEWS",
]

_CATEGORY_ALIASES = {
    "directions": "GET_DIRECTIONS",
    "get-direction": "GET_DIRECTIONS",
    "phone-call": "PHONE_CALL_LEAD",
    "phone-calls": "PHONE_CALL_LEAD",
    "call": "PHONE_CALL_LEAD",
    "calls": "PHONE_CALL_LEAD",
    "contacts": "CONTACT",
    "lead-form": "SUBMIT_LEAD_FORM",
    "lead-forms": "SUBMIT_LEAD_FORM",
    "appointment": "BOOK_APPOINTMENT",
    "appointments": "BOOK_APPOINTMENT",
    "quote": "REQUEST_QUOTE",
    "quotes": "REQUEST_QUOTE",
    "purchases": "PURCHASE",
    "sale": "PURCHASE",
    "sales": "PURCHASE",
    "signups": "SIGNUP",
    "sign-up": "SIGNUP",
    "page-views": "PAGE_VIEW",
    "outbound-clicks": "OUTBOUND_CLICK",
    "store-visits": "STORE_VISIT",
    "other": "DEFAULT",
}

# ConversionOriginEnum, minus UNSPECIFIED/UNKNOWN.
_ORIGIN_NAMES = [
    "WEBSITE",
    "GOOGLE_HOSTED",
    "APP",
    "CALL_FROM_ADS",
    "STORE",
    "YOUTUBE_HOSTED",
    "LOCAL_SERVICES_ADS",
]

_ORIGIN_ALIASES = {
    "web": "WEBSITE",
    "site": "WEBSITE",
    "google": "GOOGLE_HOSTED",
    "google-business-profile": "GOOGLE_HOSTED",
    "gbp": "GOOGLE_HOSTED",
    "business-profile": "GOOGLE_HOSTED",
    "maps": "GOOGLE_HOSTED",
    "local": "GOOGLE_HOSTED",
    "mobile-app": "APP",
    "calls-from-ads": "CALL_FROM_ADS",
    "call-from-ad": "CALL_FROM_ADS",
    "youtube": "YOUTUBE_HOSTED",
    "local-services": "LOCAL_SERVICES_ADS",
    "lsa": "LOCAL_SERVICES_ADS",
}


def _key(value: str) -> str:
    """'Get Directions', 'get_directions', 'get directions' -> 'get-direction'-ish key."""
    return "-".join(str(value).strip().lower().replace("_", " ").replace("-", " ").split())


def _resolve(value: str, names: list[str], aliases: dict[str, str], label: str):
    """Maps one human-readable value onto a v25 enum name.

    Returns (enum_name, problem). Unknown values are rejected by name with the
    valid set — the API's own error for a bad enum is an opaque parse failure,
    and for a goal it is worse than that: a wrong category or origin produces a
    perfectly well-formed resource name for a goal row that does not exist.
    """
    if value is None:
        return None, f"{label} is required — one of: {', '.join(names)}"
    canonical = {_key(name): name for name in names}
    key = _key(value)
    if key in canonical:
        return canonical[key], None
    if key in aliases:
        return aliases[key], None
    return None, f"unknown {label} {value!r} — valid values are: {', '.join(names)}"


def _rejected(errors: list[str]) -> dict[str, Any]:
    return {"status": "rejected", "applied": False, "errors": errors}


# --------------------------------------------------------------------------
# paths
# --------------------------------------------------------------------------


def _conversion_action_path(client, cid, conversion_action_id):
    return client.get_service("ConversionActionService").conversion_action_path(
        cid, str(conversion_action_id).strip()
    )


def _customer_goal_path(client, cid, category, origin):
    return client.get_service(
        "CustomerConversionGoalService"
    ).customer_conversion_goal_path(cid, category, origin)


def _campaign_goal_path(client, cid, campaign_id, category, origin):
    return client.get_service(
        "CampaignConversionGoalService"
    ).campaign_conversion_goal_path(cid, str(campaign_id).strip(), category, origin)


# --------------------------------------------------------------------------
# 1. the action level — primary_for_goal
# --------------------------------------------------------------------------


def set_conversion_action_primary(
    customer_id: str,
    conversion_action_id: str,
    primary: bool,
    confirm: bool = False,
) -> dict[str, Any]:
    """Sets `conversion_action.primary_for_goal` on one conversion action.

    `primary_for_goal = true` is what puts an action in the main **Conversions**
    column and makes it eligible for the account's conversion goals. Setting it
    false demotes the action to "Secondary": it keeps recording, keeps showing
    in the *All conversions* column and in segmented reports, and stops being
    reported as a conversion or optimised towards.

    This is the action-level half of the picture. The goal-level half is
    `biddable` on the `(category, origin)` goal — see
    `set_customer_conversion_goal`. An action can be primary while its goal is
    non-biddable; the two are set independently and are not kept in sync for
    you.

    `GOOGLE_HOSTED` actions (Google Business Profile: directions, clicks to
    call) are owned by Google. If the API refuses the mutation the error is
    returned verbatim — use the goal-level tools instead.

    Nothing is written unless confirm=true.
    """
    client = get_client()
    cid = normalize_customer_id(customer_id)

    op = client.get_type("MutateOperation")
    action = op.conversion_action_operation.update
    action.resource_name = _conversion_action_path(client, cid, conversion_action_id)
    action.primary_for_goal = bool(primary)
    client.copy_from(
        op.conversion_action_operation.update_mask,
        FieldMask(paths=["primary_for_goal"]),
    )

    return apply(
        cid,
        [op],
        confirm,
        {
            "action": "set_conversion_action_primary",
            "conversion_action_id": str(conversion_action_id),
            "resource_name": action.resource_name,
            "primary_for_goal": bool(primary),
            "effect": (
                "counted in the Conversions column and eligible for bidding"
                if primary
                else "demoted to secondary — still recorded under All conversions, "
                "no longer in the Conversions column"
            ),
        },
    )


# --------------------------------------------------------------------------
# 2. the action level — status
# --------------------------------------------------------------------------


def set_conversion_action_status(
    customer_id: str,
    conversion_action_id: str,
    status: str,
    confirm: bool = False,
) -> dict[str, Any]:
    """ENABLED | REMOVED | HIDDEN for a conversion action.

    | Status | Means |
    |---|---|
    | `ENABLED` | Recording, and reported. |
    | `HIDDEN` | Stops recording new conversions; history and reporting rows stay. This is the reversible one, and what the UI does when you "remove" an imported/GA4 action. |
    | `REMOVED` | Deleted. Not reversible through the API. |

    There is no PAUSED. Prefer `HIDDEN` over `REMOVED` unless the action is
    genuinely junk — and prefer `set_conversion_action_primary(primary=false)`
    over both if the intent is only "stop counting this in the Conversions
    column", because that keeps the data flowing for later analysis.

    Case-insensitive; unknown values are rejected by name before any request is
    built. `GOOGLE_HOSTED` actions may refuse the mutation — the error is
    reported as Google returned it.

    Nothing is written unless confirm=true.
    """
    client = get_client()
    cid = normalize_customer_id(customer_id)

    key = _key(status)
    resolved = _STATUSES.get(key) or (
        str(status).strip().upper() if str(status).strip().upper() in _STATUS_CHOICES else None
    )
    if not resolved:
        return _rejected(
            [f"unknown status {status!r} — valid values are: {', '.join(_STATUS_CHOICES)}"]
        )

    op = client.get_type("MutateOperation")
    action = op.conversion_action_operation.update
    action.resource_name = _conversion_action_path(client, cid, conversion_action_id)
    action.status = getattr(client.enums.ConversionActionStatusEnum, resolved)
    client.copy_from(
        op.conversion_action_operation.update_mask,
        FieldMask(paths=["status"]),
    )

    return apply(
        cid,
        [op],
        confirm,
        {
            "action": "set_conversion_action_status",
            "conversion_action_id": str(conversion_action_id),
            "resource_name": action.resource_name,
            "status": resolved,
            "reversible": resolved != "REMOVED",
        },
    )


# --------------------------------------------------------------------------
# 3. the goal level — account-wide
# --------------------------------------------------------------------------


def set_customer_conversion_goal(
    customer_id: str,
    category: str,
    origin: str,
    biddable: bool,
    confirm: bool = False,
) -> dict[str, Any]:
    """Sets `biddable` on one account-level `(category, origin)` conversion goal.

    This is the account default every campaign inherits unless the campaign has
    its own goal override. `biddable = true` means Smart Bidding optimises
    towards that bucket of conversion actions; `false` means it does not.

    Goals are not created or deleted — Google materialises one row per
    `(category, origin)` pair, and `biddable` is the only writable field. The
    resource name is built from the two enum names, e.g.
    `customers/{cid}/customerConversionGoals/GET_DIRECTIONS~GOOGLE_HOSTED`, so a
    typo in either would address a goal that does not exist. Both are therefore
    resolved against the v25 enums first and unknown values rejected by name.

    Accepts UI wording — "directions", "phone calls", "Google Business Profile"
    — as well as raw enum names.

    Nothing is written unless confirm=true.
    """
    client = get_client()
    cid = normalize_customer_id(customer_id)

    category_name, problem_a = _resolve(category, _CATEGORY_NAMES, _CATEGORY_ALIASES, "category")
    origin_name, problem_b = _resolve(origin, _ORIGIN_NAMES, _ORIGIN_ALIASES, "origin")
    problems = [p for p in (problem_a, problem_b) if p]
    if problems:
        return _rejected(problems)

    op = client.get_type("MutateOperation")
    goal = op.customer_conversion_goal_operation.update
    goal.resource_name = _customer_goal_path(client, cid, category_name, origin_name)
    goal.biddable = bool(biddable)
    client.copy_from(
        op.customer_conversion_goal_operation.update_mask,
        FieldMask(paths=["biddable"]),
    )

    return apply(
        cid,
        [op],
        confirm,
        {
            "action": "set_customer_conversion_goal",
            "level": "customer",
            "category": category_name,
            "origin": origin_name,
            "biddable": bool(biddable),
            "resource_name": goal.resource_name,
            "effect": (
                f"account-wide: {category_name} conversions from {origin_name} "
                + ("are optimised towards by Smart Bidding"
                   if biddable
                   else "are NOT optimised towards by Smart Bidding")
            ),
        },
    )


# --------------------------------------------------------------------------
# 4. the goal level — one campaign
# --------------------------------------------------------------------------


def set_campaign_conversion_goal(
    customer_id: str,
    campaign_id: str,
    category: str,
    origin: str,
    biddable: bool,
    confirm: bool = False,
) -> dict[str, Any]:
    """Sets `biddable` on one campaign's `(category, origin)` conversion goal.

    The campaign-level override of `set_customer_conversion_goal`. A campaign
    only follows its own goals when it has been switched off the account
    default; the `ConversionGoalCampaignConfig` resource records which mode a
    campaign is in, and this tool does not change that mode — it writes the
    campaign's goal row either way, which is what makes the row meaningful if
    the campaign is later switched to custom goals.

    Same `(category, origin)` resolution as the customer-level tool. The
    resource name is `{campaign_id}~{CATEGORY}~{ORIGIN}` under the account.

    Nothing is written unless confirm=true.
    """
    client = get_client()
    cid = normalize_customer_id(customer_id)

    category_name, problem_a = _resolve(category, _CATEGORY_NAMES, _CATEGORY_ALIASES, "category")
    origin_name, problem_b = _resolve(origin, _ORIGIN_NAMES, _ORIGIN_ALIASES, "origin")
    problems = [p for p in (problem_a, problem_b) if p]
    if problems:
        return _rejected(problems)

    op = client.get_type("MutateOperation")
    goal = op.campaign_conversion_goal_operation.update
    goal.resource_name = _campaign_goal_path(
        client, cid, campaign_id, category_name, origin_name
    )
    goal.biddable = bool(biddable)
    client.copy_from(
        op.campaign_conversion_goal_operation.update_mask,
        FieldMask(paths=["biddable"]),
    )

    return apply(
        cid,
        [op],
        confirm,
        {
            "action": "set_campaign_conversion_goal",
            "level": "campaign",
            "campaign_id": str(campaign_id),
            "category": category_name,
            "origin": origin_name,
            "biddable": bool(biddable),
            "resource_name": goal.resource_name,
            "effect": (
                f"campaign {campaign_id}: {category_name} conversions from "
                f"{origin_name} "
                + ("are optimised towards" if biddable else "are NOT optimised towards")
            ),
        },
    )
