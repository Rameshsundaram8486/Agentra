from app.composition import CONFIG_DIR
from app.modules.oversight.rules import load_incident_rules
from app.modules.reporting.catalog import load_report_catalog
from app.modules.reporting.rendering import TEMPLATE_FILES, template_version

RULES = load_incident_rules(CONFIG_DIR / "policies" / "incident_rules.yaml")
CATALOG = load_report_catalog(CONFIG_DIR / "policies" / "report_visibility.yaml")


def test_waiting_states_do_not_open_incidents_and_unknown_codes_use_the_default() -> None:
    assert not RULES.for_code("missing_input").open and not RULES.for_code("precondition").open
    assert (RULES.for_code("refused").severity, RULES.for_code("budget_exceeded").severity) == ("high", "high")
    assert RULES.for_code("guardrail_blocked").severity == "medium"
    assert RULES.for_code("something_new") == RULES.default and RULES.default.open
    assert RULES.closing.independent_verification


def test_customers_see_the_summary_only_and_every_type_has_a_template() -> None:
    assert {key for key, kind in CATALOG.report_types.items() if kind.customer_visible} == {"requirements_summary", "design_summary"}
    assert set(CATALOG.report_types) == set(TEMPLATE_FILES)
    assert len(template_version()) == 16
