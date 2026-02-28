"""Tests for FilterRule and FilterBuilder components."""

from vector_inspector.ui.components.filter_builder import FilterBuilder, FilterRule

# ---------------------------------------------------------------------------
# FilterRule tests
# ---------------------------------------------------------------------------


def test_filter_rule_instantiates(qtbot):
    rule = FilterRule()
    qtbot.addWidget(rule)
    assert rule is not None
    assert hasattr(rule, "field_input")
    assert hasattr(rule, "operator_combo")
    assert hasattr(rule, "value_input")


def test_filter_rule_get_filter_dict_empty(qtbot):
    rule = FilterRule()
    qtbot.addWidget(rule)
    # No field or value set → returns None
    assert rule.get_filter_dict() is None


def test_filter_rule_get_filter_dict_eq(qtbot):
    rule = FilterRule()
    qtbot.addWidget(rule)
    rule.field_input.setEditText("age")
    rule.operator_combo.setCurrentText("=")
    rule.value_input.setText("30")
    result = rule.get_filter_dict()
    assert result == {"age": {"$eq": 30}}


def test_filter_rule_get_filter_dict_ne(qtbot):
    rule = FilterRule()
    qtbot.addWidget(rule)
    rule.field_input.setEditText("status")
    rule.operator_combo.setCurrentText("!=")
    rule.value_input.setText("inactive")
    result = rule.get_filter_dict()
    assert result == {"status": {"$ne": "inactive"}}


def test_filter_rule_get_filter_dict_gt(qtbot):
    rule = FilterRule()
    qtbot.addWidget(rule)
    rule.field_input.setEditText("score")
    rule.operator_combo.setCurrentText(">")
    rule.value_input.setText("0.5")
    result = rule.get_filter_dict()
    assert result == {"score": {"$gt": 0.5}}


def test_filter_rule_get_filter_dict_gte(qtbot):
    rule = FilterRule()
    qtbot.addWidget(rule)
    rule.field_input.setEditText("count")
    rule.operator_combo.setCurrentText(">=")
    rule.value_input.setText("10")
    result = rule.get_filter_dict()
    assert result == {"count": {"$gte": 10}}


def test_filter_rule_get_filter_dict_lt(qtbot):
    rule = FilterRule()
    qtbot.addWidget(rule)
    rule.field_input.setEditText("n")
    rule.operator_combo.setCurrentText("<")
    rule.value_input.setText("100")
    result = rule.get_filter_dict()
    assert result == {"n": {"$lt": 100}}


def test_filter_rule_get_filter_dict_lte(qtbot):
    rule = FilterRule()
    qtbot.addWidget(rule)
    rule.field_input.setEditText("n")
    rule.operator_combo.setCurrentText("<=")
    rule.value_input.setText("5")
    result = rule.get_filter_dict()
    assert result == {"n": {"$lte": 5}}


def test_filter_rule_get_filter_dict_in(qtbot):
    rule = FilterRule()
    qtbot.addWidget(rule)
    rule.field_input.setEditText("tag")
    rule.operator_combo.setCurrentText("in")
    rule.value_input.setText("a, b, c")
    result = rule.get_filter_dict()
    assert result == {"tag": {"$in": ["a", "b", "c"]}}


def test_filter_rule_get_filter_dict_not_in(qtbot):
    rule = FilterRule()
    qtbot.addWidget(rule)
    rule.field_input.setEditText("tag")
    rule.operator_combo.setCurrentText("not in")
    rule.value_input.setText("x, y")
    result = rule.get_filter_dict()
    assert result == {"tag": {"$nin": ["x", "y"]}}


def test_filter_rule_get_filter_dict_contains_client_side(qtbot):
    rule = FilterRule()
    qtbot.addWidget(rule)
    rule.field_input.setEditText("description")
    rule.operator_combo.setCurrentText("contains (client-side)")
    rule.value_input.setText("hello")
    result = rule.get_filter_dict()
    assert result is not None
    assert result.get("__client_side__") is True
    assert result.get("op") == "contains"


def test_filter_rule_get_filter_dict_not_contains_client_side(qtbot):
    rule = FilterRule()
    qtbot.addWidget(rule)
    rule.field_input.setEditText("description")
    rule.operator_combo.setCurrentText("not contains (client-side)")
    rule.value_input.setText("bye")
    result = rule.get_filter_dict()
    assert result is not None
    assert result.get("op") == "not_contains"


def test_filter_rule_parse_value_bool_true(qtbot):
    rule = FilterRule()
    qtbot.addWidget(rule)
    assert rule._parse_value("true") is True
    assert rule._parse_value("True") is True


def test_filter_rule_parse_value_bool_false(qtbot):
    rule = FilterRule()
    qtbot.addWidget(rule)
    assert rule._parse_value("false") is False


def test_filter_rule_set_operators(qtbot):
    rule = FilterRule()
    qtbot.addWidget(rule)
    operators = [
        {"name": "=", "server_side": True},
        {"name": "contains", "server_side": False},
    ]
    rule.set_operators(operators)
    labels = [rule.operator_combo.itemText(i) for i in range(rule.operator_combo.count())]
    assert "=" in labels
    assert "contains (client-side)" in labels


def test_filter_rule_set_available_fields(qtbot):
    rule = FilterRule()
    qtbot.addWidget(rule)
    rule.set_available_fields(["name", "age", "score"])
    items = [rule.field_input.itemText(i) for i in range(rule.field_input.count())]
    assert "name" in items
    assert "age" in items


def test_filter_rule_remove_signal(qtbot):
    rule = FilterRule()
    qtbot.addWidget(rule)
    removed = []
    rule.remove_requested.connect(lambda r: removed.append(r))

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QPushButton

    # Find and click the actual remove button
    remove_btns = [b for b in rule.findChildren(QPushButton) if b.text() == "\u2715"]
    assert len(remove_btns) == 1
    qtbot.mouseClick(remove_btns[0], Qt.MouseButton.LeftButton)
    assert removed == [rule]


# ---------------------------------------------------------------------------
# FilterBuilder tests
# ---------------------------------------------------------------------------


def test_filter_builder_instantiates(qtbot):
    fb = FilterBuilder()
    qtbot.addWidget(fb)
    assert fb is not None
    assert fb.rules == []


def test_filter_builder_initially_no_filters(qtbot):
    fb = FilterBuilder()
    qtbot.addWidget(fb)
    assert fb.has_filters() is False
    assert fb.get_filter() is None


def test_filter_builder_add_rule(qtbot):
    fb = FilterBuilder()
    qtbot.addWidget(fb)
    fb._add_rule()
    assert len(fb.rules) == 1
    assert fb.has_filters() is True


def test_filter_builder_clear_all(qtbot):
    fb = FilterBuilder()
    qtbot.addWidget(fb)
    fb._add_rule()
    fb._add_rule()
    assert len(fb.rules) == 2
    fb._clear_all()
    assert len(fb.rules) == 0
    assert fb.has_filters() is False


def test_filter_builder_remove_rule(qtbot):
    fb = FilterBuilder()
    qtbot.addWidget(fb)
    fb._add_rule()
    rule = fb.rules[0]
    fb._remove_rule(rule)
    assert len(fb.rules) == 0


def test_filter_builder_get_filter_single_rule(qtbot):
    fb = FilterBuilder()
    qtbot.addWidget(fb)
    fb._add_rule()
    rule = fb.rules[0]
    rule.field_input.setEditText("name")
    rule.operator_combo.setCurrentText("=")
    rule.value_input.setText("alice")
    result = fb.get_filter()
    assert result == {"name": {"$eq": "alice"}}


def test_filter_builder_get_filter_two_rules_and(qtbot):
    fb = FilterBuilder()
    qtbot.addWidget(fb)
    fb._add_rule()
    fb._add_rule()
    r1, r2 = fb.rules[0], fb.rules[1]
    r1.field_input.setEditText("age")
    r1.operator_combo.setCurrentText(">")
    r1.value_input.setText("18")
    r2.field_input.setEditText("active")
    r2.operator_combo.setCurrentText("=")
    r2.value_input.setText("true")
    fb.logic_combo.setCurrentText("AND")
    result = fb.get_filter()
    assert "$and" in result
    assert len(result["$and"]) == 2


def test_filter_builder_get_filter_two_rules_or(qtbot):
    fb = FilterBuilder()
    qtbot.addWidget(fb)
    fb._add_rule()
    fb._add_rule()
    r1, r2 = fb.rules[0], fb.rules[1]
    r1.field_input.setEditText("tag")
    r1.operator_combo.setCurrentText("=")
    r1.value_input.setText("alpha")
    r2.field_input.setEditText("tag")
    r2.operator_combo.setCurrentText("=")
    r2.value_input.setText("beta")
    fb.logic_combo.setCurrentText("OR")
    result = fb.get_filter()
    assert "$or" in result


def test_filter_builder_get_filters_split(qtbot):
    fb = FilterBuilder()
    qtbot.addWidget(fb)
    fb._add_rule()
    fb._add_rule()
    r1, r2 = fb.rules[0], fb.rules[1]
    # Server-side rule
    r1.field_input.setEditText("age")
    r1.operator_combo.setCurrentText(">")
    r1.value_input.setText("18")
    # Client-side rule
    r2.field_input.setEditText("bio")
    r2.operator_combo.setCurrentText("contains (client-side)")
    r2.value_input.setText("dev")

    server, client = fb.get_filters_split()
    assert server == {"age": {"$gt": 18}}
    assert len(client) == 1
    assert client[0].get("__client_side__") is True


def test_filter_builder_set_available_fields(qtbot):
    fb = FilterBuilder()
    qtbot.addWidget(fb)
    fb._add_rule()
    fb.set_available_fields(["x", "y", "z"])
    rule = fb.rules[0]
    items = [rule.field_input.itemText(i) for i in range(rule.field_input.count())]
    assert "x" in items


def test_filter_builder_set_operators(qtbot):
    fb = FilterBuilder()
    qtbot.addWidget(fb)
    fb._add_rule()
    fb.set_operators([{"name": "eq", "server_side": True}])
    rule = fb.rules[0]
    items = [rule.operator_combo.itemText(i) for i in range(rule.operator_combo.count())]
    assert "eq" in items


def test_filter_builder_get_filter_summary_no_filters(qtbot):
    fb = FilterBuilder()
    qtbot.addWidget(fb)
    assert fb.get_filter_summary() == "No filters"


def test_filter_builder_get_filter_summary_one_rule(qtbot):
    fb = FilterBuilder()
    qtbot.addWidget(fb)
    fb._add_rule()
    rule = fb.rules[0]
    rule.field_input.setEditText("status")
    rule.operator_combo.setCurrentText("=")
    rule.value_input.setText("active")
    summary = fb.get_filter_summary()
    assert "status" in summary
    assert "active" in summary


def test_filter_builder_filter_changed_signal(qtbot):
    fb = FilterBuilder()
    qtbot.addWidget(fb)
    changes = []
    fb.filter_changed.connect(lambda: changes.append(1))
    fb._add_rule()
    assert changes  # Adding a rule should emit filter_changed
