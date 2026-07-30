# /// script
# requires-python = ">=3.12"
# ///
"""Offline checks for the expected-findings gate.

A baseline exists so a known spec gap stays visible rather than silenced. It must
therefore fail on anything it does not name, and on a named rule whose count,
path, severity or message does not match the entry exactly. A ceiling was the
earlier design and it was the wrong one, see apply_baseline in check_catalogs.py.

This runs on every pull request with no path filter, and it is the only check
that does. That is why the assertions on the committed baseline below are exact
values rather than shape. A widened path_glob or message_glob is a real change to
what the catalog tolerates, and it lands with no rashid run of its own unless
something here objects to it.
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


ITEM = "imagery/colorado-2023/co_m_1/item.json"
MSG = "asset 'image' has no file:checksum"
BASE = {"accepted": [{"rule": "PTL-AST-003", "severity": "error", "count": 2,
                      "path_glob": "imagery/*/*/item.json",
                      "message_glob": "asset '*' has no file:checksum",
                      "why": "x", "issue": "y"}]}


def _report(rules: list[str], severity: str = "error", path: str = ITEM,
            message: str = MSG) -> dict:
    return {"findings": [{"rule_id": r, "severity": severity, "path": path,
                          "message": message} for r in rules],
            "error_count": len(rules), "warning_count": 0, "info_count": 0,
            "files_checked": 1}


def check_exact_count_passes() -> None:
    unexpected, reasons = check_catalogs.apply_baseline(
        _report(["PTL-AST-003", "PTL-AST-003"]), BASE)
    assert unexpected == [], unexpected
    assert reasons == [], reasons


def check_unlisted_rule_fails() -> None:
    unexpected, reasons = check_catalogs.apply_baseline(
        _report(["PTL-AST-003", "PTL-AST-003", "PTL-LNK-001"]), BASE)
    assert len(unexpected) == 1, unexpected
    assert unexpected[0]["rule_id"] == "PTL-LNK-001", unexpected
    assert reasons, "an unlisted rule must give the gate a reason to fail"


def check_over_count_fails() -> None:
    unexpected, reasons = check_catalogs.apply_baseline(
        _report(["PTL-AST-003"] * 4), BASE)
    assert any("PTL-AST-003" in r and "4" in r for r in reasons), reasons


def check_under_count_fails() -> None:
    """A shrunken upstream must fail too, not slip under an old ceiling.

    This is the gutted-catalog case. publish_catalogs.py runs s5cmd sync
    --delete, so a build from a truncated upstream search would replace a good
    published catalog with a smaller one. A ceiling accepts that silently.
    """
    unexpected, reasons = check_catalogs.apply_baseline(
        _report(["PTL-AST-003"]), BASE)
    assert unexpected == [], unexpected
    assert any("PTL-AST-003" in r and "1" in r for r in reasons), reasons


def check_wrong_path_is_not_accepted() -> None:
    """The same rule on a locally hosted file is a real defect, not a known gap.

    items.parquet is a file this project writes and must checksum, so
    PTL-AST-003 there has nothing to do with the 1848 remote assets the entry
    documents.
    """
    unexpected, _ = check_catalogs.apply_baseline(
        _report(["PTL-AST-003"], path="imagery/colorado-2023/collection.json"),
        BASE)
    assert len(unexpected) == 1, unexpected


def check_glob_star_does_not_cross_a_slash() -> None:
    unexpected, _ = check_catalogs.apply_baseline(
        _report(["PTL-AST-003"], path="imagery/a/b/c/item.json"), BASE)
    assert len(unexpected) == 1, "a deeper path must not match imagery/*/*/item.json"
    assert check_catalogs.path_matches(ITEM, "imagery/*/*/item.json")
    assert not check_catalogs.path_matches(ITEM, "*/item.json")


def check_a_different_message_is_not_accepted() -> None:
    """The same rule failing for a new reason is a new defect.

    This is what covers the profile-schema collapse that an exact count cannot.
    PTL-SCH-001 stays at one finding per file however many things are wrong
    inside the object, so the count never moves, but jsonschema reports a
    best-match error and a fresh defect often outranks the checksum one.
    """
    unexpected, _ = check_catalogs.apply_baseline(
        _report(["PTL-AST-003", "PTL-AST-003"],
                message="'roles' is a required property"), BASE)
    assert len(unexpected) == 2, unexpected


def check_wrong_severity_is_not_accepted() -> None:
    """A rule promoted from warning to error, or demoted, is a change to look at."""
    unexpected, _ = check_catalogs.apply_baseline(
        _report(["PTL-AST-003", "PTL-AST-003"], severity="warning"), BASE)
    assert len(unexpected) == 2, unexpected


def check_missing_baseline_is_zero_tolerance() -> None:
    unexpected, reasons = check_catalogs.apply_baseline(_report(["PTL-AST-003"]), {})
    assert len(unexpected) == 1, "no baseline means every finding counts"


def check_real_baseline_loads() -> None:
    root = HERE.parent.parent.parent
    base = check_catalogs.load_baseline(root, root / "examples/catalog/naip-mosaic")
    assert base.get("data_scope") == "local", base
    assert base.get("data_scope_why", "").strip(), "a narrowed scope needs a reason"
    rules = {a["rule"] for a in base["accepted"]}
    assert rules == {"PTL-AST-003", "PTL-SCH-001"}, rules
    for entry in base["accepted"]:
        assert entry["why"].strip(), f"{entry['rule']} needs a justification"
        assert entry["issue"].strip(), f"{entry['rule']} needs an issue reference"
    # Pinned by value, not by shape. Every field here narrows what the gate will
    # accept, so relaxing any one of them widens the catalog's tolerance without
    # touching a line of code. path_glob is the sharpest: loosened to */*/*/* it
    # would excuse PTL-AST-003 on items.parquet, a file this project does host
    # and must checksum, which is the hole check_wrong_path_is_not_accepted
    # exists to prove closed. Update these together with the baseline, in a
    # commit that says why the catalog changed.
    assert {a["rule"]: (a["severity"], a["path_glob"], a["message_glob"], a["count"])
            for a in base["accepted"]} == {
        "PTL-AST-003": ("error", "imagery/*/*/item.json",
                        "asset '*' has no file:checksum", 1848),
        "PTL-SCH-001": ("error", "imagery/*/*/item.json",
                        "*'file:checksum' is a required property*", 924),
    }, base["accepted"]
    assert base.get("matching_why", "").strip(), "exact matching needs a reason"
    assert base.get("recount_how", "").strip(), "a reader needs the recount recipe"


def check_reference_catalog_has_no_baseline() -> None:
    root = HERE.parent.parent.parent
    base = check_catalogs.load_baseline(root, root / "examples/catalog/portolan-reference")
    assert base == {}, "the reference catalog stays at zero tolerance"


if __name__ == "__main__":
    print("check_baseline.py")
    check("the exact count passes", check_exact_count_passes)
    check("unlisted rule fails", check_unlisted_rule_fails)
    check("over the count fails", check_over_count_fails)
    check("under the count fails", check_under_count_fails)
    check("the wrong path is not accepted", check_wrong_path_is_not_accepted)
    check("a glob star does not cross a slash", check_glob_star_does_not_cross_a_slash)
    check("a different message is not accepted", check_a_different_message_is_not_accepted)
    check("the wrong severity is not accepted", check_wrong_severity_is_not_accepted)
    check("no baseline is zero tolerance", check_missing_baseline_is_zero_tolerance)
    check("the committed baseline loads", check_real_baseline_loads)
    check("the reference catalog has no baseline", check_reference_catalog_has_no_baseline)
    if FAILURES:
        raise SystemExit(f"{len(FAILURES)} failure(s)")
    print("all ok")
