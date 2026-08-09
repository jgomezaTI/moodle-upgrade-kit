from pathlib import Path

from moodle_upgrade.plugins import RISK_PATTERNS, _scan_path


def test_php_only_rules_do_not_flag_javascript_split_or_each(tmp_path: Path):
    root = tmp_path / "custom"
    root.mkdir()
    (root / "app.js").write_text(
        "const parts = value.split(',');\nitems.each(function () {});\n",
        encoding="utf-8",
    )
    (root / "legacy.php").write_text(
        "<?php\n$parts = split(',', $value);\nwhile (list($key, $value) = each($items)) {}\n",
        encoding="utf-8",
    )

    hits, summary = _scan_path(root, root, "4.1", 100, 100000, RISK_PATTERNS)

    assert summary["scanned_files"] == 2
    assert [(hit["id"], hit["path"]) for hit in hits] == [
        ("php_split_removed", "legacy.php"),
        ("php_each_removed", "legacy.php"),
    ]


def test_php_only_rules_ignore_embedded_javascript_in_php_files(tmp_path: Path):
    root = tmp_path / "custom"
    root.mkdir()
    (root / "page.php").write_text(
        "<?php\n$title = 'Example';\n?>\n"
        "<script>\n"
        "function split(value) { return value.split(','); }\n"
        "const parts = split('a,b');\n"
        "items.each(function () {});\n"
        "</script>\n",
        encoding="utf-8",
    )

    hits, _ = _scan_path(root, root, "4.1", 100, 100000, RISK_PATTERNS)

    assert not [hit for hit in hits if hit["id"].startswith("php_")]


def test_php_only_rules_ignore_php_comments_and_string_literals(tmp_path: Path):
    root = tmp_path / "custom"
    root.mkdir()
    (root / "comments.php").write_text(
        "<?php\n"
        "// ereg() is deprecated.\n"
        "/* split(',', $value); */\n"
        "$message = \"each($items) is legacy\";\n"
        "$template = <<<'TEXT'\n"
        "create_function('', 'return true;');\n"
        "TEXT;\n"
        "$parts = split(',', $value);\n",
        encoding="utf-8",
    )

    hits, _ = _scan_path(root, root, "4.1", 100, 100000, RISK_PATTERNS)

    assert [(hit["id"], hit["line"]) for hit in hits if hit["id"].startswith("php_")] == [
        ("php_split_removed", 8),
    ]


def test_ereg_and_split_are_reported_with_distinct_stable_ids(tmp_path: Path):
    root = tmp_path / "custom"
    root.mkdir()
    (root / "legacy.php").write_text(
        "<?php\nif (ereg('x', $value)) {}\n$parts = spliti(',', $value);\n",
        encoding="utf-8",
    )

    hits, _ = _scan_path(root, root, "4.1", 100, 100000, RISK_PATTERNS)

    assert [(hit["id"], hit["line"]) for hit in hits] == [
        ("php_ereg_removed", 2),
        ("php_split_removed", 3),
    ]


def test_sql_aware_rules_still_scan_php_strings_and_sql_files(tmp_path: Path):
    root = tmp_path / "custom"
    root.mkdir()
    (root / "check.sql").write_text(
        "SELECT u.yahoo FROM mdl_user u;\n",
        encoding="utf-8",
    )
    (root / "query.php").write_text(
        '<?php\n$sql = "SELECT u.yahoo FROM mdl_user u";\n',
        encoding="utf-8",
    )

    hits, _ = _scan_path(root, root, "4.1", 100, 100000, RISK_PATTERNS)
    findings = {(hit["id"], hit["path"]) for hit in hits}

    assert findings == {
        ("hardcoded_mdl_prefix", "check.sql"),
        ("hardcoded_mdl_prefix", "query.php"),
        ("legacy_user_contact_column", "check.sql"),
        ("legacy_user_contact_column", "query.php"),
    }
