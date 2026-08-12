"""Display Network targeting — audiences, topics, placements, demographics.

`create_display_campaign` applies geo and language targeting only. On the
Display Network that is effectively untargeted: geo narrows *where* the
impression lands, nothing narrows *what page or app* it lands on. The result is
spray — and the account's 1.38% Display CTR (3-10x a normal Display CTR) is the
classic signature of mobile-app inventory and accidental fat-finger clicks.

These tools are the fix. In rough order of value on a wasteful Display campaign:

1. `exclude_mobile_app_placements` — kills the junk-click inventory outright.
2. `add_audience_targeting` — affinity / in-market / remarketing.
3. `add_topic_targeting`, `add_placement_targeting` — content-side narrowing.
4. `add_demographic_targeting` — trims the tails.

Everything here is a *criterion*, and criteria live at two levels:

| Level    | Proto                | Set via                        |
|----------|----------------------|--------------------------------|
| campaign | `CampaignCriterion`  | `campaign_criterion_operation` |
| ad group | `AdGroupCriterion`   | `ad_group_criterion_operation` |

There is no `NegativeCampaignCriterion` resource in v25 — a negative is the same
criterion message with `negative = True`. Both messages carry that field.

Numeric criterion IDs are not guessable. Resolve names to IDs first with
`find_targeting_criteria` in `lookup.py`.
"""

from typing import Any

from ..client import get_client, normalize_customer_id
from ..safety import apply

# --------------------------------------------------------------------------
# mobile app exclusions
# --------------------------------------------------------------------------

# "App categories > All Apps" — the root of the mobile app category tree.
# Google Ads Editor and the UI's bulk placement box express this exclusion as
# the string `mobileappcategory::69500`; through the API it is a
# MobileAppCategoryConstant resource name.
_ALL_APPS_CATEGORY_ID = "69500"

# The historic AdSense-for-mobile-apps pseudo-domain. Excluding it as a
# placement is the second half of the standard app exclusion; it catches app
# inventory served through the AdSense/AdMob app network that the category tree
# misses. Google has quietly deprecated it more than once and it still validates,
# so it is included but kept switchable.
_ADSENSE_FOR_MOBILE_APPS = "adsenseformobileapps.com"


# --------------------------------------------------------------------------
# demographic value maps — human-readable in, v25 enum name out
# --------------------------------------------------------------------------

_AGE_RANGES = {
    "18-24": "AGE_RANGE_18_24",
    "25-34": "AGE_RANGE_25_34",
    "35-44": "AGE_RANGE_35_44",
    "45-54": "AGE_RANGE_45_54",
    "55-64": "AGE_RANGE_55_64",
    "65+": "AGE_RANGE_65_UP",
    "65-up": "AGE_RANGE_65_UP",
    "65": "AGE_RANGE_65_UP",
    "undetermined": "AGE_RANGE_UNDETERMINED",
    "unknown": "AGE_RANGE_UNDETERMINED",
}

_GENDERS = {
    "male": "MALE",
    "female": "FEMALE",
    "undetermined": "UNDETERMINED",
    "unknown": "UNDETERMINED",
}

_PARENTAL_STATUS = {
    "parent": "PARENT",
    "not-a-parent": "NOT_A_PARENT",
    "not-parent": "NOT_A_PARENT",
    "non-parent": "NOT_A_PARENT",
    "undetermined": "UNDETERMINED",
    "unknown": "UNDETERMINED",
}

_INCOME_RANGES = {
    "0-50": "INCOME_RANGE_0_50",
    "50-60": "INCOME_RANGE_50_60",
    "60-70": "INCOME_RANGE_60_70",
    "70-80": "INCOME_RANGE_70_80",
    "80-90": "INCOME_RANGE_80_90",
    "90+": "INCOME_RANGE_90_UP",
    "90-up": "INCOME_RANGE_90_UP",
    "undetermined": "INCOME_RANGE_UNDETERMINED",
    "unknown": "INCOME_RANGE_UNDETERMINED",
}

# What a rejection offers the caller. The canonical spellings only — the alias
# keys above are accepted but not advertised.
_AGE_RANGE_CHOICES = ["18-24", "25-34", "35-44", "45-54", "55-64", "65+", "undetermined"]
_GENDER_CHOICES = ["male", "female", "undetermined"]
_PARENTAL_CHOICES = ["parent", "not-a-parent", "undetermined"]
_INCOME_CHOICES = ["0-50", "50-60", "60-70", "70-80", "80-90", "90+", "undetermined"]


# --------------------------------------------------------------------------
# paths
# --------------------------------------------------------------------------


def _campaign_path(client, cid, campaign_id):
    return client.get_service("CampaignService").campaign_path(cid, campaign_id)


def _ad_group_path(client, cid, ad_group_id):
    return client.get_service("AdGroupService").ad_group_path(cid, ad_group_id)


def _qualified(value: str, builder) -> str:
    """Accepts a bare numeric ID or an already-qualified resource name."""
    value = str(value).strip()
    if "/" in value:
        return value
    return builder(value)


def _user_interest_path(cid, user_interest_id):
    # No UserInterestService exists in v25 — UserInterest is a read-only,
    # customer-scoped resource with no path helper, so the name is built by hand.
    return f"customers/{cid}/userInterests/{user_interest_id}"


def _topic_constant_path(topic_id):
    # Global constant, not customer-scoped. No service, no path helper.
    return f"topicConstants/{topic_id}"


def _mobile_app_category_path(category_id):
    # Global constant. No service, no path helper.
    return f"mobileAppCategoryConstants/{category_id}"


def _user_list_path(client, cid, user_list_id):
    return client.get_service("UserListService").user_list_path(cid, user_list_id)


def _custom_audience_path(client, cid, custom_audience_id):
    return client.get_service("CustomAudienceService").custom_audience_path(
        cid, custom_audience_id
    )


# --------------------------------------------------------------------------
# shared helpers
# --------------------------------------------------------------------------


def _run(cid, operations, problems, confirm, summary):
    if problems:
        return {"status": "rejected", "applied": False, "errors": problems}
    if not operations:
        return {
            "status": "rejected",
            "applied": False,
            "errors": ["nothing to do — no targeting values were given"],
        }
    return apply(cid, operations, confirm, summary)


def _new_criterion(client, op, cid, campaign_id, ad_group_id, negative: bool):
    """Starts a campaign- or ad-group-level criterion on `op` and returns it.

    Status is set to ENABLED for positive criteria only. Google rejects a status
    on a negative criterion — a negative has no serving state to enable.
    """
    if campaign_id:
        criterion = op.campaign_criterion_operation.create
        criterion.campaign = _campaign_path(client, cid, campaign_id)
        if not negative:
            criterion.status = client.enums.CampaignCriterionStatusEnum.ENABLED
    else:
        criterion = op.ad_group_criterion_operation.create
        criterion.ad_group = _ad_group_path(client, cid, ad_group_id)
        if not negative:
            criterion.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
    if negative:
        criterion.negative = True
    return criterion


def _resolve_enum(values, table, choices, label) -> tuple[list[str], list[str]]:
    """Maps human-readable demographic values onto v25 enum names.

    Returns (enum_names, problems). A bad value is named in the problem, with
    the valid set — the API's own error for this is an opaque enum parse failure.
    """
    resolved, problems = [], []
    for raw in values or []:
        # "not a parent", "NOT_A_PARENT", "65 up" all collapse to one key form.
        key = "-".join(str(raw).strip().lower().replace("_", " ").replace("-", " ").split())
        # An enum name passed straight through, e.g. "AGE_RANGE_25_34".
        upper = str(raw).strip().upper()
        if upper in table.values():
            resolved.append(upper)
            continue
        if key in table:
            resolved.append(table[key])
            continue
        problems.append(
            f"unknown {label} {raw!r} — valid values are: {', '.join(choices)}"
        )
    # Duplicate criteria in one mutate are rejected as duplicates by the API.
    deduped = list(dict.fromkeys(resolved))
    return deduped, problems


# --------------------------------------------------------------------------
# 1. mobile app exclusions — the highest-value Display cleanup
# --------------------------------------------------------------------------


def exclude_mobile_app_placements(
    customer_id: str,
    campaign_id: str,
    app_category_ids: list[str] | None = None,
    exclude_adsense_for_mobile_apps: bool = True,
    extra_placement_urls: list[str] | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Excludes mobile-app inventory from a Display campaign.

    A Display campaign with no placement exclusions serves in mobile apps by
    default. In-app banners sit under the thumb in games and utilities, so they
    collect accidental clicks — a Display CTR several times the normal 0.1-0.5%
    is usually this and nothing else.

    Emits, as one atomic mutate at **campaign** level:

    * a negative `MOBILE_APP_CATEGORY` criterion on
      `mobileAppCategoryConstants/69500` — "App categories > All Apps", the root
      of the app category tree (the UI/Editor spelling is
      `mobileappcategory::69500`);
    * a negative `PLACEMENT` criterion on `adsenseformobileapps.com`, the
      AdSense-for-mobile-apps pseudo-domain.

    **What this does NOT exclude:**

    * **Mobile web.** A page viewed in a phone browser is a WEBSITE placement,
      not an app. Untouched — use device bid modifiers if mobile web is the
      problem.
    * **In-app webviews.** Plenty of in-app ad slots report as the publisher's
      web domain. They look like websites to the API and survive this.
    * **Apps Google has not categorised.** The exclusion is on the *category*
      tree; an app sitting outside it is not covered. New apps inside existing
      categories are, because the tree is resolved at serve time.
    * **YouTube.** In-stream and YouTube-app inventory are
      `youtube_video`/`youtube_channel` criteria, not app placements.
    * **Kids / games content as such.** That is a `content_label` exclusion, a
      different criterion type, not emitted here.
    * **Anything outside this one campaign.** No account-level or shared
      placement-exclusion list is created. Performance Max placement exclusions
      are account-level only and cannot be set by this tool at all.
    * **Individual named apps.** Pass their `2-com.package.name` /
      `1-476943146` IDs to a `MOBILE_APPLICATION` criterion if you need
      surgical exclusions; not exposed here.

    Args:
      app_category_ids: MobileAppCategoryConstant IDs. Defaults to ["69500"]
        (all apps). Find others with find_targeting_criteria(kind="mobile_app_category").
      exclude_adsense_for_mobile_apps: also add the adsenseformobileapps.com
        negative placement. On by default.
      extra_placement_urls: further domains to exclude in the same mutate.
    """
    client = get_client()
    cid = normalize_customer_id(customer_id)

    categories = [str(c).strip() for c in (app_category_ids or [_ALL_APPS_CATEGORY_ID])]
    urls = list(extra_placement_urls or [])
    if exclude_adsense_for_mobile_apps:
        urls.insert(0, _ADSENSE_FOR_MOBILE_APPS)
    urls = [u.strip() for u in urls if str(u).strip()]

    problems = []
    for category in categories:
        if not category:
            problems.append("empty app_category_ids entry")
        elif "/" not in category and not category.isdigit():
            problems.append(
                f"app_category_ids must be numeric IDs or full resource names, got {category!r}"
            )

    operations = []
    campaign_rn = _campaign_path(client, cid, campaign_id)

    for category in categories:
        op = client.get_type("MutateOperation")
        criterion = op.campaign_criterion_operation.create
        criterion.campaign = campaign_rn
        criterion.negative = True
        criterion.mobile_app_category.mobile_app_category_constant = _qualified(
            category, _mobile_app_category_path
        )
        operations.append(op)

    for url in urls:
        op = client.get_type("MutateOperation")
        criterion = op.campaign_criterion_operation.create
        criterion.campaign = campaign_rn
        criterion.negative = True
        criterion.placement.url = url
        operations.append(op)

    return _run(
        cid,
        operations,
        problems,
        confirm,
        {
            "action": "exclude_mobile_app_placements",
            "level": "campaign",
            "campaign_id": campaign_id,
            "app_categories_excluded": categories,
            "placements_excluded": urls,
            "does_not_cover": [
                "mobile web (browser) placements",
                "in-app webview inventory reporting as a website",
                "apps outside the excluded category tree",
                "YouTube video/channel inventory",
                "other campaigns, and account-level/PMax exclusions",
            ],
        },
    )


# --------------------------------------------------------------------------
# 2. audiences
# --------------------------------------------------------------------------


def add_audience_targeting(
    customer_id: str,
    campaign_id: str | None = None,
    ad_group_id: str | None = None,
    user_interest_ids: list[str] | None = None,
    user_list_ids: list[str] | None = None,
    custom_audience_ids: list[str] | None = None,
    negative: bool = False,
    confirm: bool = False,
) -> dict[str, Any]:
    """Targets (or excludes) audiences on a campaign or an ad group.

    Three flavours, all criteria on the same operation:

    * `user_interest_ids` — Google's own affinity and in-market taxonomy.
      Both live in the `user_interest` resource; the `taxonomy_type` field
      distinguishes AFFINITY from IN_MARKET. Resolve names with
      `find_targeting_criteria(kind="user_interest")`.
    * `user_list_ids` — remarketing / customer-match lists already in the
      account. `find_targeting_criteria(kind="user_list")`.
    * `custom_audience_ids` — custom audiences built from interests, URLs or
      apps. `find_targeting_criteria(kind="custom_audience")`.

    Exactly one of campaign_id / ad_group_id. Campaign level is the blunt
    instrument; ad group level is what lets different creative serve to
    different audiences.

    A remarketing list needs enough members to be eligible for Display (Google's
    threshold is 100 active visitors in 30 days); an undersized list validates
    fine and then never serves.
    """
    if bool(campaign_id) == bool(ad_group_id):
        return {
            "status": "rejected",
            "applied": False,
            "errors": ["provide exactly one of campaign_id or ad_group_id"],
        }

    client = get_client()
    cid = normalize_customer_id(customer_id)

    interests = [str(v).strip() for v in (user_interest_ids or []) if str(v).strip()]
    lists = [str(v).strip() for v in (user_list_ids or []) if str(v).strip()]
    customs = [str(v).strip() for v in (custom_audience_ids or []) if str(v).strip()]

    problems = []
    if not (interests or lists or customs):
        problems.append(
            "give at least one of user_interest_ids, user_list_ids, custom_audience_ids"
        )

    operations = []

    for value in interests:
        op = client.get_type("MutateOperation")
        criterion = _new_criterion(client, op, cid, campaign_id, ad_group_id, negative)
        criterion.user_interest.user_interest_category = _qualified(
            value, lambda v: _user_interest_path(cid, v)
        )
        operations.append(op)

    for value in lists:
        op = client.get_type("MutateOperation")
        criterion = _new_criterion(client, op, cid, campaign_id, ad_group_id, negative)
        criterion.user_list.user_list = _qualified(
            value, lambda v: _user_list_path(client, cid, v)
        )
        operations.append(op)

    for value in customs:
        op = client.get_type("MutateOperation")
        criterion = _new_criterion(client, op, cid, campaign_id, ad_group_id, negative)
        criterion.custom_audience.custom_audience = _qualified(
            value, lambda v: _custom_audience_path(client, cid, v)
        )
        operations.append(op)

    return _run(
        cid,
        operations,
        problems,
        confirm,
        {
            "action": "add_audience_targeting",
            "level": "campaign" if campaign_id else "ad_group",
            "target_id": campaign_id or ad_group_id,
            "negative": negative,
            "user_interest_ids": interests,
            "user_list_ids": lists,
            "custom_audience_ids": customs,
        },
    )


# --------------------------------------------------------------------------
# 3. topics
# --------------------------------------------------------------------------


def add_topic_targeting(
    customer_id: str,
    ad_group_id: str,
    topic_ids: list[str],
    negative: bool = False,
    confirm: bool = False,
) -> dict[str, Any]:
    """Targets (or excludes) Display topics on an ad group.

    A topic is a content category the page falls into — "Beauty & Fitness/Spas
    & Beauty Services". Broader than placements, far narrower than nothing.
    IDs come from the global `topic_constant` taxonomy; resolve names with
    `find_targeting_criteria(kind="topic")`.

    `negative=True` excludes instead, which is the cheaper first move on a
    campaign that is already spending badly.
    """
    client = get_client()
    cid = normalize_customer_id(customer_id)

    values = [str(v).strip() for v in (topic_ids or []) if str(v).strip()]
    problems = []
    if not values:
        problems.append("topic_ids is required and must contain at least one ID")
    for value in values:
        if "/" not in value and not value.isdigit():
            problems.append(
                f"topic_ids must be numeric IDs or full resource names, got {value!r}"
            )

    operations = []
    for value in values:
        op = client.get_type("MutateOperation")
        criterion = _new_criterion(client, op, cid, None, ad_group_id, negative)
        criterion.topic.topic_constant = _qualified(value, _topic_constant_path)
        operations.append(op)

    return _run(
        cid,
        operations,
        problems,
        confirm,
        {
            "action": "add_topic_targeting",
            "level": "ad_group",
            "ad_group_id": ad_group_id,
            "negative": negative,
            "topic_ids": values,
        },
    )


# --------------------------------------------------------------------------
# 4. placements
# --------------------------------------------------------------------------


def add_placement_targeting(
    customer_id: str,
    ad_group_id: str,
    urls: list[str],
    negative: bool = False,
    confirm: bool = False,
) -> dict[str, Any]:
    """Managed placements on an ad group — target specific sites, or exclude them.

    `negative=False` creates *managed placements*: the ad group serves on those
    sites and nowhere else in the content network. That is the tightest Display
    targeting there is, and also the fastest way to starve a campaign of volume,
    so use it deliberately.

    `negative=True` excludes the sites instead, leaving the rest of the network
    intact. This is what a placement report cleanup wants.

    URLs are domains or paths — "example.com", "example.com/section". Google
    normalises scheme and "www."; a full "https://example.com/" is accepted.
    """
    client = get_client()
    cid = normalize_customer_id(customer_id)

    values = [str(u).strip() for u in (urls or []) if str(u).strip()]
    problems = []
    if not values:
        problems.append("urls is required and must contain at least one placement")
    for url in values:
        if " " in url:
            problems.append(f"placement URL contains a space: {url!r}")

    operations = []
    for url in values:
        op = client.get_type("MutateOperation")
        criterion = _new_criterion(client, op, cid, None, ad_group_id, negative)
        criterion.placement.url = url
        operations.append(op)

    return _run(
        cid,
        operations,
        problems,
        confirm,
        {
            "action": "add_placement_targeting",
            "level": "ad_group",
            "ad_group_id": ad_group_id,
            "negative": negative,
            "urls": values,
        },
    )


# --------------------------------------------------------------------------
# 5. demographics
# --------------------------------------------------------------------------


def add_demographic_targeting(
    customer_id: str,
    ad_group_id: str,
    age_ranges: list[str] | None = None,
    genders: list[str] | None = None,
    parental_status: list[str] | None = None,
    income_ranges: list[str] | None = None,
    exclude: bool = False,
    confirm: bool = False,
) -> dict[str, Any]:
    """Demographic criteria on an ad group. Human-readable values in.

    | Parameter | Accepts |
    |---|---|
    | `age_ranges` | 18-24, 25-34, 35-44, 45-54, 55-64, 65+, undetermined |
    | `genders` | male, female, undetermined |
    | `parental_status` | parent, not-a-parent, undetermined |
    | `income_ranges` | 0-50, 50-60, 60-70, 70-80, 80-90, 90+, undetermined |

    Raw v25 enum names ("AGE_RANGE_25_34") also pass through. Anything else is
    rejected by name before a request is built.

    `exclude=True` emits the same criteria with `negative = True`.

    Two things worth knowing before excluding:

    * Google serves a demographic to *everyone in the group it did not exclude*.
      Excluding four of seven age bands is targeting the other three — there is
      no separate "include" list to keep in sync.
    * "undetermined" is a large share of Display traffic, not a rounding error.
      Excluding it is a real reach cut, and it is also where a lot of app traffic
      hides.

    Income ranges are US/AU/JP/NZ only; elsewhere they validate and never serve.
    """
    client = get_client()
    cid = normalize_customer_id(customer_id)

    ages, problems = _resolve_enum(age_ranges, _AGE_RANGES, _AGE_RANGE_CHOICES, "age range")
    gender_names, p = _resolve_enum(genders, _GENDERS, _GENDER_CHOICES, "gender")
    problems += p
    parental_names, p = _resolve_enum(
        parental_status, _PARENTAL_STATUS, _PARENTAL_CHOICES, "parental status"
    )
    problems += p
    income_names, p = _resolve_enum(
        income_ranges, _INCOME_RANGES, _INCOME_CHOICES, "income range"
    )
    problems += p

    if not (ages or gender_names or parental_names or income_names) and not problems:
        problems.append(
            "give at least one of age_ranges, genders, parental_status, income_ranges"
        )

    operations = []
    if not problems:
        for name in ages:
            op = client.get_type("MutateOperation")
            criterion = _new_criterion(client, op, cid, None, ad_group_id, exclude)
            criterion.age_range.type_ = getattr(client.enums.AgeRangeTypeEnum, name)
            operations.append(op)
        for name in gender_names:
            op = client.get_type("MutateOperation")
            criterion = _new_criterion(client, op, cid, None, ad_group_id, exclude)
            criterion.gender.type_ = getattr(client.enums.GenderTypeEnum, name)
            operations.append(op)
        for name in parental_names:
            op = client.get_type("MutateOperation")
            criterion = _new_criterion(client, op, cid, None, ad_group_id, exclude)
            criterion.parental_status.type_ = getattr(
                client.enums.ParentalStatusTypeEnum, name
            )
            operations.append(op)
        for name in income_names:
            op = client.get_type("MutateOperation")
            criterion = _new_criterion(client, op, cid, None, ad_group_id, exclude)
            criterion.income_range.type_ = getattr(client.enums.IncomeRangeTypeEnum, name)
            operations.append(op)

    return _run(
        cid,
        operations,
        problems,
        confirm,
        {
            "action": "add_demographic_targeting",
            "level": "ad_group",
            "ad_group_id": ad_group_id,
            "exclude": exclude,
            "age_ranges": ages,
            "genders": gender_names,
            "parental_status": parental_names,
            "income_ranges": income_names,
        },
    )
