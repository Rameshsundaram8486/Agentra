from app.modules.requirements.quality_checks import CheckedItem, check_items
from app.modules.requirements.rendering import render_brd
from app.modules.requirements.schemas import DraftItem, RequirementItemView, SourceRef
from app.modules.requirements.service import parse_item_id, status_for

GOOD = ["Submitting a request shows it in the manager's list within 5 seconds"]


def _item(item_id: str, kind: str, statement: str, criteria: list[str] | None = None, **kwargs: object) -> CheckedItem:
    return CheckedItem(item_id, kind, item_id, statement, GOOD if criteria is None else criteria, **kwargs)  # type: ignore[arg-type]


def _checks(items: list[CheckedItem]) -> dict[str, set[str]]:
    flags, _ = check_items(items)
    return {item_id: {flag.check for flag in item_flags} for item_id, item_flags in flags.items()}


def test_clear_distinct_requirements_raise_no_flags() -> None:
    items = [
        _item("REQ-F-001", "functional", "Employees can request annual leave online."),
        _item("REQ-F-002", "functional", "Line managers can approve or reject a request."),
        _item("REQ-NF-001", "non_functional", "Pages load in under 2 seconds for 200 concurrent users."),
        _item("OBJ-001", "objective", "HR stops reconciling balances by hand.", criteria=[]),
    ]

    assert _checks(items) == {item.item_id: set() for item in items}


def test_missing_acceptance_criteria_and_untestable_wording() -> None:
    checks = _checks([
        _item("REQ-F-001", "functional", "Employees can request leave.", criteria=[]),
        _item("REQ-F-002", "functional", "The approval screen is user-friendly and fast.", criteria=["Managers find it easy"]),
        _item("REQ-NF-001", "non_functional", "The system is highly available.", criteria=["Downtime is rare"]),
    ])

    assert checks["REQ-F-001"] == {"completeness"}
    assert checks["REQ-F-002"] == {"testability"}
    assert checks["REQ-NF-001"] == {"testability"}  # no number or unit to test against


def test_vague_word_with_a_measurable_criterion_is_accepted() -> None:
    checks = _checks([_item("REQ-NF-001", "non_functional", "Search is fast.", criteria=["Results appear within 1 second"])])

    assert checks["REQ-NF-001"] == set()


def test_duplicates_and_opposites_are_flagged_on_both_items() -> None:
    checks = _checks([
        _item("REQ-F-001", "functional", "Managers can approve leave requests from their phone."),
        _item("REQ-F-002", "functional", "Managers can approve leave requests from their phones."),
        _item("BR-001", "business_rule", "Unpaid leave must be approved by HR."),
        _item("BR-002", "business_rule", "Unpaid leave must not be approved by HR."),
    ])

    assert checks["REQ-F-001"] == checks["REQ-F-002"] == {"duplicate"}
    assert checks["BR-001"] == checks["BR-002"] == {"conflict"}


def test_different_values_for_the_same_measure_conflict() -> None:
    checks = _checks([
        _item("REQ-NF-001", "non_functional", "Pages load in under 2 seconds for 200 users."),
        _item("REQ-NF-002", "non_functional", "Pages load in under 5 seconds for 200 users."),
        _item("REQ-NF-003", "non_functional", "Backups are kept for 30 days."),
    ])

    assert checks["REQ-NF-001"] == checks["REQ-NF-002"] == {"conflict"}
    assert checks["REQ-NF-003"] == set()


def test_set_level_gaps_and_open_questions() -> None:
    _, set_flags = check_items([
        _item("REQ-F-001", "functional", "Employees can request leave."),
        _item("Q-001", "open_question", "Import balances?", criteria=[]),
    ])

    assert [flag.message for flag in set_flags] == ["No objectives yet", "No stakeholders yet", "1 open question(s) to answer"]


def _draft(kind: str = "functional", label: str = "fact", answer: str | None = "Power Platform", source_type: str = "decision") -> DraftItem:
    source = SourceRef(type=source_type, name="Stack", answer=answer) if source_type == "decision" else SourceRef(type="document", name="Brief v1", quote="x")  # type: ignore[arg-type]
    return DraftItem(ref="new-1", kind=kind, title="t", statement="s", label=label, priority="must", acceptance_criteria=[], sources=[source])  # type: ignore[arg-type]


def test_status_is_derived_and_only_facts_with_settled_sources_are_confirmed() -> None:
    assert status_for(_draft(source_type="document")) == "confirmed"
    assert status_for(_draft(answer="Power Platform")) == "confirmed"
    assert status_for(_draft(answer=None)) == "proposed"  # rests on an unanswered decision
    assert status_for(_draft(label="assumption", source_type="document")) == "proposed"
    assert status_for(_draft(label="suggestion", source_type="document")) == "proposed"
    assert status_for(_draft(kind="assumption", source_type="document")) == "proposed"
    assert status_for(_draft(kind="open_question", label="open_question", source_type="document")) == "open"


def test_item_ids_parse() -> None:
    assert parse_item_id("REQ-NF-012") == ("REQ-NF", 12)
    assert parse_item_id("OBJ-001") == ("OBJ", 1)
    assert parse_item_id("new-1") is None and parse_item_id("REQ-F-1") is None


def test_the_brd_rendering_is_deterministic() -> None:
    item = RequirementItemView(
        item_id="REQ-F-001", kind="functional", title="Request leave", statement="Employees request leave.", label="fact",
        status="confirmed", priority="must", acceptance_criteria=GOOD, quality_flags=[],
        sources=[SourceRef(type="document", name="project brief 'Brief' v1", quote="Employees request leave online.")],
    )
    kwargs = dict(project_name="Leave", summary="S", items=[item], set_flags=[], process_flow_mermaid="flowchart TD\n A-->B", input_refs=["DOC-1: brief"])

    first, second = render_brd(**kwargs), render_brd(**kwargs)  # type: ignore[arg-type]

    assert first == second
    assert "### REQ-F-001 Request leave" in first and '- project brief \'Brief\' v1: "Employees request leave online."' in first
    assert "*Label: fact. Status: confirmed. Priority: must.*" in first
