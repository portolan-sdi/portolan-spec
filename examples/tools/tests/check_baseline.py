# /// script
# requires-python = ">=3.12"
# ///
"""Offline checks for the expected-findings gate.

A baseline exists so a known spec gap stays visible instead of being silenced by
--no-validate. It must therefore fail on anything it does not name, and fail when
a named rule exceeds its ceiling. Otherwise it is just a mute button.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import check_catalogs  # noqa: E402

FAILURES: list[str] = []


def check(name: str, fn) -> None:
    try:
        fn()
        print(f"  ok   {name}")
    except AssertionError as exc:
        FAILURES.append(f"{name}: {exc}")
        print(f"  FAIL {name}: {exc}")


BASE = {"accepted": [{"rule": "PTL-AST-003", "severity": "error", "max_count": 3,
                      "why": "x", "issue": "y"}]}


def _report(rules: list[str]) -> dict:
    return {"findings": [{"rule_id": r, "severity": "error", "path": "p",
                          "message": "m"} for r in rules],
            "error_count": len(rules), "warning_count": 0, "info_count": 0,
            "files_checked": 1}


def check_accepted_within_ceiling_passes() -> None:
    unexpected, reasons = check_catalogs.apply_baseline(
        _report(["PTL-AST-003", "PTL-AST-003"]), BASE)
    assert unexpected == [], unexpected
    assert reasons == [], reasons


def check_unlisted_rule_fails() -> None:
    unexpected, reasons = check_catalogs.apply_baseline(
        _report(["PTL-AST-003", "PTL-LNK-001"]), BASE)
    assert len(unexpected) == 1, unexpected
    assert unexpected[0]["rule_id"] == "PTL-LNK-001", unexpected
    assert reasons, "an unlisted rule must give the gate a reason to fail"


def check_over_ceiling_fails() -> None:
    unexpected, reasons = check_catalogs.apply_baseline(
        _report(["PTL-AST-003"] * 4), BASE)
    assert any("PTL-AST-003" in r and "4" in r for r in reasons), reasons


def check_missing_baseline_is_zero_tolerance() -> None:
    unexpected, reasons = check_catalogs.apply_baseline(_report(["PTL-AST-003"]), {})
    assert len(unexpected) == 1, "no baseline means every finding counts"


def check_real_baseline_loads() -> None:
    root = HERE.parent.parent.parent
    base = check_catalogs.load_baseline(root, root / "examples/catalog/naip-mosaic")
    assert base.get("data_pass") is False, base
    rules = {a["rule"] for a in base["accepted"]}
    assert rules == {"PTL-AST-003", "PTL-SCH-001"}, rules
    for entry in base["accepted"]:
        assert entry["why"].strip(), f"{entry['rule']} needs a justification"
        assert entry["issue"].strip(), f"{entry['rule']} needs an issue reference"


def check_reference_catalog_has_no_baseline() -> None:
    root = HERE.parent.parent.parent
    base = check_catalogs.load_baseline(root, root / "examples/catalog/portolan-reference")
    assert base == {}, "the reference catalog stays at zero tolerance"


if __name__ == "__main__":
    print("check_baseline.py")
    check("accepted within ceiling passes", check_accepted_within_ceiling_passes)
    check("unlisted rule fails", check_unlisted_rule_fails)
    check("over ceiling fails", check_over_ceiling_fails)
    check("no baseline is zero tolerance", check_missing_baseline_is_zero_tolerance)
    check("the committed baseline loads", check_real_baseline_loads)
    check("the reference catalog has no baseline", check_reference_catalog_has_no_baseline)
    if FAILURES:
        raise SystemExit(f"{len(FAILURES)} failure(s)")
    print("all ok")
