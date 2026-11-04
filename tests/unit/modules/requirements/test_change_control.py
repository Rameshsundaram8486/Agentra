from app.modules.requirements.change_control import ComparableItem, change_violations
from app.modules.requirements.schemas import RequirementItemView, SourceRef, TraceabilityView
from app.modules.requirements.traceability import build_rows, to_csv


def _item(ref: str, statement: str = "Employees request leave online.", **changes: object) -> ComparableItem:
    fields: dict[str, object] = dict(kind="functional", title="Request leave", statement=statement, label="fact", priority="must", acceptance_criteria=["Saved within 5 seconds"])
    fields.update(changes)
    return ComparableItem(ref, **fields)  # type: ignore[arg-type]


BASELINE = [_item("REQ-F-001"), _item("REQ-F-002", "Managers approve leave.")]


def test_unlisted_items_may_only_change_whitespace() -> None:
    draft = [_item("REQ-F-001", "Employees  request leave\nonline."), _item("REQ-F-002", "Managers approve leave.")]

    assert change_violations(BASELINE, draft, affected=set(), allows_new_items=False) == []


def test_listed_items_may_change_or_go_and_others_may_not() -> None:
    draft = [_item("REQ-F-001", "Employees request full or half days online.")]

    assert change_violations(BASELINE, draft, affected={"REQ-F-001"}, allows_new_items=False) == [
        ("REQ-F-002", "REQ-F-002 was removed, but the change request does not list it")
    ]
    assert change_violations(BASELINE, draft, affected={"REQ-F-001", "REQ-F-002"}, allows_new_items=False) == []


def test_every_compared_field_counts_and_new_items_need_permission() -> None:
    for change in ({"priority": "could"}, {"label": "assumption"}, {"acceptance_criteria": ["Saved"]}, {"title": "Other"}):
        violations = change_violations(BASELINE, [_item("REQ-F-001", **change), BASELINE[1]], affected=set(), allows_new_items=False)
        assert violations == [("REQ-F-001", "REQ-F-001 was changed, but the change request does not list it")], change

    added = [*BASELINE, _item("new-1", "Half days are allowed.")]
    assert change_violations(BASELINE, added, affected=set(), allows_new_items=False) == [("new-1", "The change request does not allow new items")]
    assert change_violations(BASELINE, added, affected=set(), allows_new_items=True) == []


def _view(item_id: str, kind: str, related: list[str] | None = None, criteria: list[str] | None = None) -> RequirementItemView:
    return RequirementItemView(
        item_id=item_id, kind=kind, title=item_id, statement="s", label="fact", status="confirmed", priority="must",  # type: ignore[arg-type]
        acceptance_criteria=criteria or [], sources=[SourceRef(type="document", name="brief v1", quote="a, \"quoted\" line")],
        quality_flags=[], related=related or [],
    )


def test_matrix_rows_and_csv_are_deterministic() -> None:
    items = [
        _view("OBJ-001", "objective"),
        _view("REQ-F-001", "functional", ["OBJ-001"], ["Works"]),
        _view("BR-001", "business_rule"),
        _view("US-001", "user_story", ["REQ-F-001"]),
    ]
    rows, gaps = build_rows(items)
    view = TraceabilityView(version_id="00000000-0000-0000-0000-000000000001", version_no=1, approval_status="approved", rows=rows, gaps=gaps)  # type: ignore[arg-type]

    assert [(r.item_id, r.objectives, r.user_stories, r.gaps) for r in rows] == [
        ("REQ-F-001", ["OBJ-001"], ["US-001"], []),
        ("BR-001", [], [], ["No objective"]),  # business rules need no acceptance criteria
    ]
    assert to_csv(view) == to_csv(view)
    assert to_csv(view).splitlines()[1].startswith("REQ-F-001,functional,REQ-F-001,confirmed,OBJ-001,US-001,REQ-F-001.AC1 Works")
