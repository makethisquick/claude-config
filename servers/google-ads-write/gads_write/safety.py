"""The confirm gate.

Every mutating tool routes through `apply()`. With `confirm=False` (the default
everywhere) the request goes to the API with `validate_only=True`: Google fully
validates it — policy, budget rules, referential integrity — and persists nothing.
Only an explicit `confirm=True` writes.

All operations for one logical change go in a single `GoogleAdsService.mutate`
call so they succeed or fail together. That is also what makes a dry run
meaningful: temporary resource IDs let a campaign reference a budget that does
not exist yet, so the whole chain validates as a unit.
"""

from typing import Any

from google.ads.googleads.errors import GoogleAdsException

from .client import get_client, normalize_customer_id


class TempIds:
    """Allocates the negative resource IDs used to chain operations in one mutate."""

    def __init__(self) -> None:
        self._next = -1

    def take(self) -> int:
        value = self._next
        self._next -= 1
        return value


def _operation_index(error) -> int | None:
    """Which operation in the batch this error belongs to."""
    if not error.location:
        return None
    for element in error.location.field_path_elements:
        if element.field_name in ("mutate_operations", "operations"):
            try:
                if "index" in element:
                    return element.index
            except TypeError:
                pass
    return None


def _format_errors(exc: GoogleAdsException) -> list[dict[str, Any]]:
    errors = []
    for error in exc.failure.errors:
        entry: dict[str, Any] = {
            "message": error.message,
            "code": str(error.error_code).strip(),
        }
        index = _operation_index(error)
        if index is not None:
            entry["operation_index"] = index
        if error.location and error.location.field_path_elements:
            entry["field"] = ".".join(
                el.field_name for el in error.location.field_path_elements
            )
        if error.trigger and error.trigger.string_value:
            entry["trigger"] = error.trigger.string_value

        # Policy rejections carry the actual policy name and whether an exemption
        # can be requested — far more actionable than the generic message.
        details = getattr(error, "details", None)
        violation = getattr(details, "policy_violation_details", None) if details else None
        if violation and violation.external_policy_name:
            entry["policy"] = violation.external_policy_name
            entry["policy_description"] = violation.external_policy_description
            entry["exemptible"] = violation.is_exemptible
            if violation.key and violation.key.violating_text:
                entry["violating_text"] = violation.key.violating_text

        errors.append(entry)
    return errors


def _attach_exemptions(operations: list, exc: GoogleAdsException) -> int:
    """Adds exemption keys for exemptible policy violations, in place.

    Google blocks some legitimate advertising outright but marks the violation
    exemptible — the remedy is to resubmit the same operation declaring the
    violation knowingly. Returns how many were attached.
    """
    attached = 0
    for error in exc.failure.errors:
        details = getattr(error, "details", None)
        violation = getattr(details, "policy_violation_details", None) if details else None
        if not violation or not violation.is_exemptible or not violation.key:
            continue
        index = _operation_index(error)
        if index is None or index >= len(operations):
            continue

        operation = operations[index]
        sub_name = operation._pb.WhichOneof("operation")
        if not sub_name:
            continue
        sub_operation = getattr(operation, sub_name)
        if not hasattr(sub_operation, "exempt_policy_violation_keys"):
            continue

        existing = [
            (k.policy_name, k.violating_text)
            for k in sub_operation.exempt_policy_violation_keys
        ]
        if (violation.key.policy_name, violation.key.violating_text) in existing:
            continue
        sub_operation.exempt_policy_violation_keys.append(violation.key)
        attached += 1
    return attached


def _rejection(customer_id, summary, errors, exemptible) -> dict[str, Any]:
    result = {
        "status": "rejected",
        "applied": False,
        "customer_id": customer_id,
        "intended": summary,
        "errors": errors,
        "hint": (
            "The API rejected this before writing anything. Fix the fields "
            "above and retry."
        ),
    }
    if exemptible:
        result["exemptible_violations"] = [
            {"text": e.get("trigger") or e.get("violating_text"), "policy": e.get("policy")}
            for e in exemptible
        ]
        result["hint"] = (
            f"{len(exemptible)} of these are exemptible policy violations — Google "
            "allows them if you declare them knowingly. Re-run with "
            "request_policy_exemptions=true to submit an exemption, but only if "
            "the advertiser genuinely qualifies to make these claims."
        )
    return result


def apply(
    customer_id: str,
    operations: list,
    confirm: bool,
    summary: dict[str, Any],
    request_policy_exemptions: bool = False,
) -> dict[str, Any]:
    """Validates or executes a batch of MutateOperations atomically.

    Args:
      customer_id: target account, with or without dashes.
      operations: MutateOperation protos, in dependency order.
      confirm: False validates only; True writes.
      summary: human-readable description of the intended change, echoed back so
        a dry run can show what *would* happen (validate_only returns no results).
    """
    client = get_client()
    customer_id = normalize_customer_id(customer_id)

    request = client.get_type("MutateGoogleAdsRequest")
    request.customer_id = customer_id
    request.mutate_operations.extend(operations)
    request.validate_only = not confirm
    request.partial_failure = False

    service = client.get_service("GoogleAdsService")

    exemptions_requested = 0
    try:
        response = service.mutate(request=request)
    except GoogleAdsException as exc:
        errors = _format_errors(exc)
        exemptible = [e for e in errors if e.get("exemptible")]

        if request_policy_exemptions and exemptible:
            exemptions_requested = _attach_exemptions(operations, exc)
            if exemptions_requested:
                # Operations were mutated in place; rebuild and retry once.
                request = client.get_type("MutateGoogleAdsRequest")
                request.customer_id = customer_id
                request.mutate_operations.extend(operations)
                request.validate_only = not confirm
                request.partial_failure = False
                try:
                    response = service.mutate(request=request)
                except GoogleAdsException as retry_exc:
                    return {
                        "status": "rejected",
                        "applied": False,
                        "customer_id": customer_id,
                        "intended": summary,
                        "errors": _format_errors(retry_exc),
                        "exemptions_attempted": exemptions_requested,
                        "hint": (
                            "Policy exemptions were requested but the API still "
                            "rejected this. The remaining errors are not exemptible."
                        ),
                    }
            else:
                return _rejection(customer_id, summary, errors, exemptible)
        else:
            return _rejection(customer_id, summary, errors, exemptible)

    if not confirm:
        return {
            "status": "validated",
            "applied": False,
            "customer_id": customer_id,
            "intended": summary,
            "operation_count": len(operations),
            "policy_exemptions_requested": exemptions_requested,
            "next_step": (
                "Nothing was created — this was a dry run. Re-run the same call "
                "with confirm=true to apply it."
            ),
        }

    created = []
    for result in response.mutate_operation_responses:
        # Exactly one result field is populated per operation.
        name = result._pb.WhichOneof("response")
        if not name:
            continue
        resource_name = getattr(getattr(result, name), "resource_name", None)
        if resource_name:
            created.append({"type": name.replace("_result", ""), "resource_name": resource_name})

    return {
        "status": "applied",
        "applied": True,
        "customer_id": customer_id,
        "summary": summary,
        "policy_exemptions_requested": exemptions_requested,
        "created": created,
    }
