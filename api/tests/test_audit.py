"""The audit runs on the real catalogue and finds no errors; its checks catch what they claim to."""

from mde.audit.engine import Context, load_context, run_audit


def test_catalogue_has_no_audit_errors():
    _, findings = run_audit(load_context())
    errors = [f for f in findings if f.severity == "error"]
    assert not errors, "\n".join(f"{f.rule} {f.key}: {f.message}" for f in errors)


def test_checks_catch_bad_data():
    ctx = load_context()
    bad = dict(ctx.works[0], year=3000, summary="too short", terms={"genre:not-a-real-tag": 0.5})
    ctx2 = Context(**{**ctx.__dict__, "works": [bad, dict(bad)]})
    _, findings = run_audit(ctx2, {"W001", "W003", "W005", "W007"}, set())
    assert {f.rule for f in findings} == {"W001", "W003", "W005", "W007"}


def test_baseline_silences_a_finding():
    ctx = load_context()
    bad = dict(ctx.works[0], year=3000)
    ctx2 = Context(**{**ctx.__dict__, "works": [bad]})
    _, findings = run_audit(ctx2, {"W003"}, {("W003", bad["slug"])})
    assert findings == []
