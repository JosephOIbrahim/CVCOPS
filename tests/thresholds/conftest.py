"""Judge plumbing: which object is graded, and a record of every outcome for tools/check.py. Locked."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import impls  # noqa: E402

_results = {}


@pytest.fixture(scope="session")
def impl():
    return impls.make_impl(os.environ.get("CVCOPS_IMPL", "product"))


@pytest.fixture(scope="session")
def cache():
    return {}


def pytest_runtest_logreport(report):
    if report.when != "call" and report.passed:
        return
    outcome = report.outcome
    if report.failed:
        crash = getattr(report.longrepr, "reprcrash", None)
        first = crash.message if crash is not None else str(report.longrepr or "")
        if first.split(":", 1)[0].rsplit(".", 1)[-1] == "EnvironmentProblem":
            outcome = "environment"
    entry = {"outcome": outcome, "when": report.when}
    entry.update({k: v for k, v in report.user_properties})
    if report.failed:
        crash = getattr(report.longrepr, "reprcrash", None)
        text = crash.message if crash is not None else str(report.longrepr or "")
        entry["message"] = " ".join(text.split())[:600]
    previous = _results.get(report.nodeid)
    if previous is None or previous["outcome"] == "passed":
        _results[report.nodeid] = entry


def pytest_sessionfinish(session, exitstatus):
    path = os.environ.get("CVCOPS_RESULTS")
    if path:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(_results, f, indent=1, default=str)
