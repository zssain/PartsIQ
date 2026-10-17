"""AWS free-plan deployment preflight (prompt 26).

Contract: ``def preflight(account: AccountReceipt, sizing: SizingReceipt) -> DeploymentDecision``.

Gates provisioning on OPERATOR-VERIFIED receipts (never an automatic paid upgrade): the
account must be on the free plan with unexpired remaining credit, and the chosen instance's
memory must actually fit the MEASURED peak of the real workload (BGE-M3 + Chromium) with
headroom — free micro capacity is not assumed adequate. ``allowed`` is True only when there
are no blocking reasons; otherwise ``reasons`` explains what the operator must resolve first.
"""
from __future__ import annotations

from datetime import UTC, datetime

from partsiq_common.contracts import AccountReceipt, DeploymentDecision, SizingReceipt

# ap-south-1 is the default operational PROPOSAL (user proximity); availability is verified by
# the operator against the account, not assumed here.
PROPOSED_REGION = "ap-south-1"
HEADROOM = 1.2  # require 20% memory headroom above the measured peak


def preflight(account: AccountReceipt, sizing: SizingReceipt, *, now: datetime | None = None) -> DeploymentDecision:
    now = now or datetime.now(UTC)
    reasons: list[str] = []

    if account.plan != "free":
        reasons.append("account is not on the free plan; no automatic paid upgrade is authorized")
    if account.credit_usd <= 0:
        reasons.append("no remaining free credit on the account")
    if account.expires_at <= now:
        reasons.append("account free credit has expired")

    if sizing.instance_memory_mib < sizing.peak_memory_mib:
        reasons.append(
            f"measured peak {sizing.peak_memory_mib} MiB exceeds instance memory "
            f"{sizing.instance_memory_mib} MiB ({sizing.instance_type}); free micro is not assumed adequate"
        )
    elif sizing.instance_memory_mib < sizing.peak_memory_mib * HEADROOM:
        reasons.append(
            f"insufficient memory headroom: instance {sizing.instance_memory_mib} MiB is under "
            f"{HEADROOM:.0%} of the measured peak {sizing.peak_memory_mib} MiB"
        )

    return DeploymentDecision(allowed=not reasons, reasons=reasons)


def _main(argv: list[str] | None = None) -> int:
    """CLI gate for the deploy workflow: exit 0 only when deployment is allowed."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="AWS free-plan deployment preflight")
    parser.add_argument("--account", required=True, help="AccountReceipt JSON")
    parser.add_argument("--sizing", required=True, help="SizingReceipt JSON")
    args = parser.parse_args(argv)
    decision = preflight(
        AccountReceipt.model_validate_json(args.account),
        SizingReceipt.model_validate_json(args.sizing),
    )
    if not decision.allowed:
        print("preflight BLOCKED:", "; ".join(decision.reasons), file=sys.stderr)
        return 1
    print("preflight OK")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(_main(sys.argv[1:]))
