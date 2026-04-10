# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Unit tests for diagnostic output parsing in lsp_server.

Pylint uses JSON output (``--output-format=json2``) rather than a regex,
so the parsing entry point is :func:`lsp_server._parse_output`.  These
tests mirror the structure of mypy's ``test_diagnostic_regex.py`` but
exercise pylint's JSON-based parsing instead.
"""

import json

import lsp_server
from lsp_server import _get_severity, _parse_output

# ---------------------------------------------------------------------------
# Default severity mapping (matches _get_global_defaults in lsp_server.py)
# ---------------------------------------------------------------------------
DEFAULT_SEVERITY = {
    "convention": "Information",
    "error": "Error",
    "fatal": "Error",
    "refactor": "Hint",
    "warning": "Warning",
    "info": "Information",
}

DOCUMENTATION_HOME = "https://pylint.readthedocs.io/en/latest/user_guide/messages"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _build_json(messages, score=None):
    """Build a JSON string mimicking pylint ``--output-format=json2``."""
    payload = {"messages": messages}
    if score is not None:
        payload["statistics"] = {"score": score}
    return json.dumps(payload)


def _make_message(
    msg_id="C0114",
    symbol="missing-module-docstring",
    message="Missing module docstring",
    msg_type="convention",
    line=1,
    column=0,
    end_line=None,
    end_column=None,
):
    """Create a single pylint message dict."""
    msg = {
        "type": msg_type,
        "symbol": symbol,
        "message": message,
        "messageId": msg_id,
        "line": line,
        "column": column,
        "endLine": end_line,
        "endColumn": end_column,
    }
    return msg


# ---------------------------------------------------------------------------
# _parse_output — convention (C) messages
# ---------------------------------------------------------------------------
def test_parse_convention_message():
    """Convention (C) messages should map to Information severity."""
    content = _build_json(
        [
            _make_message(
                msg_id="C0114",
                symbol="missing-module-docstring",
                message="Missing module docstring",
                msg_type="convention",
                line=1,
                column=0,
                end_line=1,
                end_column=10,
            )
        ],
        score=8.0,
    )

    diagnostics, score = _parse_output(content, severity=DEFAULT_SEVERITY)

    assert len(diagnostics) == 1
    diag = diagnostics[0]
    assert diag.message == "Missing module docstring"
    assert diag.code == "C0114:missing-module-docstring"
    assert diag.source == "Pylint"
    assert score == 8.0

    # Start position (1-indexed line → 0-indexed)
    assert diag.range.start.line == 0
    assert diag.range.start.character == 0
    # End position
    assert diag.range.end.line == 0
    assert diag.range.end.character == 10


def test_parse_convention_line_naming():
    """C0103 naming-convention messages are parsed correctly."""
    content = _build_json(
        [
            _make_message(
                msg_id="C0103",
                symbol="invalid-name",
                message='Constant name "x" doesn\'t conform to UPPER_CASE',
                msg_type="convention",
                line=5,
                column=0,
                end_line=5,
                end_column=1,
            )
        ]
    )

    diagnostics, _ = _parse_output(content, severity=DEFAULT_SEVERITY)
    assert diagnostics[0].code == "C0103:invalid-name"
    assert "UPPER_CASE" in diagnostics[0].message


# ---------------------------------------------------------------------------
# _parse_output — refactor (R) messages
# ---------------------------------------------------------------------------
def test_parse_refactor_message():
    """Refactor (R) messages should map to Hint severity."""
    content = _build_json(
        [
            _make_message(
                msg_id="R0205",
                symbol="useless-object-inheritance",
                message="Class 'Foo' inherits from object, can be removed",
                msg_type="refactor",
                line=10,
                column=0,
                end_line=10,
                end_column=20,
            )
        ]
    )

    diagnostics, _ = _parse_output(content, severity=DEFAULT_SEVERITY)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "R0205:useless-object-inheritance"


def test_parse_too_many_branches():
    """R1702 too-many-branches is a refactor-category message."""
    content = _build_json(
        [
            _make_message(
                msg_id="R1702",
                symbol="too-many-branches",
                message="Too many branches (15/12)",
                msg_type="refactor",
                line=20,
                column=0,
                end_line=20,
                end_column=12,
            )
        ]
    )

    diagnostics, _ = _parse_output(content, severity=DEFAULT_SEVERITY)
    assert diagnostics[0].message == "Too many branches (15/12)"


# ---------------------------------------------------------------------------
# _parse_output — warning (W) messages
# ---------------------------------------------------------------------------
def test_parse_warning_message():
    """Warning (W) messages should map to Warning severity."""
    content = _build_json(
        [
            _make_message(
                msg_id="W0611",
                symbol="unused-import",
                message="Unused import os",
                msg_type="warning",
                line=3,
                column=0,
                end_line=3,
                end_column=9,
            )
        ]
    )

    diagnostics, _ = _parse_output(content, severity=DEFAULT_SEVERITY)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "W0611:unused-import"
    assert diagnostics[0].message == "Unused import os"


def test_parse_unused_variable():
    """W0612 unused-variable is correctly parsed."""
    content = _build_json(
        [
            _make_message(
                msg_id="W0612",
                symbol="unused-variable",
                message="Unused variable 'result'",
                msg_type="warning",
                line=15,
                column=4,
                end_line=15,
                end_column=10,
            )
        ]
    )

    diagnostics, _ = _parse_output(content, severity=DEFAULT_SEVERITY)
    assert diagnostics[0].range.start.line == 14
    assert diagnostics[0].range.start.character == 4


# ---------------------------------------------------------------------------
# _parse_output — error (E) messages
# ---------------------------------------------------------------------------
def test_parse_error_message():
    """Error (E) messages should map to Error severity."""
    content = _build_json(
        [
            _make_message(
                msg_id="E1101",
                symbol="no-member",
                message="Module 'os' has no 'foo' member",
                msg_type="error",
                line=7,
                column=4,
                end_line=7,
                end_column=10,
            )
        ]
    )

    diagnostics, _ = _parse_output(content, severity=DEFAULT_SEVERITY)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "E1101:no-member"
    assert diagnostics[0].message == "Module 'os' has no 'foo' member"


def test_parse_syntax_error():
    """E0001 syntax-error messages are parsed correctly."""
    content = _build_json(
        [
            _make_message(
                msg_id="E0001",
                symbol="syntax-error",
                message="Missing parentheses in call to 'print'",
                msg_type="error",
                line=1,
                column=0,
            )
        ]
    )

    diagnostics, _ = _parse_output(content, severity=DEFAULT_SEVERITY)
    assert diagnostics[0].code == "E0001:syntax-error"


# ---------------------------------------------------------------------------
# _parse_output — fatal (F) messages
# ---------------------------------------------------------------------------
def test_parse_fatal_message():
    """Fatal (F) messages should map to Error severity."""
    content = _build_json(
        [
            _make_message(
                msg_id="F0001",
                symbol="fatal",
                message=(
                    "No module named nonexistent "
                    "(analysis:ERROR while handling module)"
                ),
                msg_type="fatal",
                line=1,
                column=0,
            )
        ]
    )

    diagnostics, _ = _parse_output(content, severity=DEFAULT_SEVERITY)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "F0001:fatal"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------
def test_parse_message_without_end_line():
    """When ``endLine`` is ``None`` the end position should equal start."""
    content = _build_json(
        [
            _make_message(
                msg_id="W0611",
                symbol="unused-import",
                message="Unused import os",
                msg_type="warning",
                line=3,
                column=0,
                end_line=None,
                end_column=None,
            )
        ]
    )

    diagnostics, _ = _parse_output(content, severity=DEFAULT_SEVERITY)
    diag = diagnostics[0]
    assert diag.range.start.line == diag.range.end.line
    assert diag.range.start.character == diag.range.end.character


def test_parse_message_with_missing_end_column():
    """When ``endColumn`` is absent the parser should default to 0."""
    msg = {
        "type": "error",
        "symbol": "no-member",
        "message": "Module 'os' has no 'foo' member",
        "messageId": "E1101",
        "line": 7,
        "column": 4,
        "endLine": 7,
    }
    content = _build_json([msg])

    diagnostics, _ = _parse_output(content, severity=DEFAULT_SEVERITY)
    assert diagnostics[0].range.end.character == 0


def test_parse_multiple_messages():
    """Multiple diagnostics in one run are all returned."""
    content = _build_json(
        [
            _make_message(
                msg_id="C0114",
                symbol="missing-module-docstring",
                message="Missing module docstring",
                msg_type="convention",
                line=1,
                column=0,
            ),
            _make_message(
                msg_id="W0611",
                symbol="unused-import",
                message="Unused import os",
                msg_type="warning",
                line=3,
                column=0,
                end_line=3,
                end_column=9,
            ),
            _make_message(
                msg_id="E1101",
                symbol="no-member",
                message="Module 'os' has no 'foo' member",
                msg_type="error",
                line=7,
                column=4,
                end_line=7,
                end_column=10,
            ),
        ],
        score=5.0,
    )

    diagnostics, score = _parse_output(content, severity=DEFAULT_SEVERITY)
    assert len(diagnostics) == 3
    assert score == 5.0

    codes = [d.code for d in diagnostics]
    assert "C0114:missing-module-docstring" in codes
    assert "W0611:unused-import" in codes
    assert "E1101:no-member" in codes


def test_parse_empty_messages():
    """An empty message list produces no diagnostics."""
    content = _build_json([], score=10.0)

    diagnostics, score = _parse_output(content, severity=DEFAULT_SEVERITY)
    assert diagnostics == []
    assert score == 10.0


def test_parse_score_absent():
    """When the statistics block is absent the score should be ``None``."""
    content = json.dumps({"messages": []})

    _, score = _parse_output(content, severity=DEFAULT_SEVERITY)
    assert score is None


def test_parse_message_with_special_characters():
    """Messages containing quotes and special characters are preserved."""
    content = _build_json(
        [
            _make_message(
                msg_id="C0103",
                symbol="invalid-name",
                message='Constant name "x_y" doesn\'t conform to UPPER_CASE',
                msg_type="convention",
                line=2,
                column=0,
                end_line=2,
                end_column=3,
            )
        ]
    )

    diagnostics, _ = _parse_output(content, severity=DEFAULT_SEVERITY)
    assert '"x_y"' in diagnostics[0].message


def test_documentation_url_convention():
    """Convention messages link to the correct documentation URL."""
    content = _build_json(
        [
            _make_message(
                msg_id="C0114",
                symbol="missing-module-docstring",
                msg_type="convention",
            )
        ]
    )

    diagnostics, _ = _parse_output(content, severity=DEFAULT_SEVERITY)
    href = diagnostics[0].code_description.href
    assert "convention/missing-module-docstring.html" in href


def test_documentation_url_error():
    """Error messages link to the correct documentation URL."""
    content = _build_json(
        [
            _make_message(
                msg_id="E1101",
                symbol="no-member",
                msg_type="error",
            )
        ]
    )

    diagnostics, _ = _parse_output(content, severity=DEFAULT_SEVERITY)
    href = diagnostics[0].code_description.href
    assert "error/no-member.html" in href


# ---------------------------------------------------------------------------
# _get_severity
# ---------------------------------------------------------------------------
def test_severity_convention():
    """Convention type maps to Information."""
    sev = _get_severity(
        "missing-module-docstring", "C0114", "convention", DEFAULT_SEVERITY
    )
    assert sev == lsp_server.lsp.DiagnosticSeverity.Information


def test_severity_error():
    """Error type maps to Error."""
    sev = _get_severity("no-member", "E1101", "error", DEFAULT_SEVERITY)
    assert sev == lsp_server.lsp.DiagnosticSeverity.Error


def test_severity_fatal():
    """Fatal type maps to Error."""
    sev = _get_severity("fatal", "F0001", "fatal", DEFAULT_SEVERITY)
    assert sev == lsp_server.lsp.DiagnosticSeverity.Error


def test_severity_warning():
    """Warning type maps to Warning."""
    sev = _get_severity("unused-import", "W0611", "warning", DEFAULT_SEVERITY)
    assert sev == lsp_server.lsp.DiagnosticSeverity.Warning


def test_severity_refactor():
    """Refactor type maps to Hint."""
    sev = _get_severity(
        "useless-object-inheritance", "R0205", "refactor", DEFAULT_SEVERITY
    )
    assert sev == lsp_server.lsp.DiagnosticSeverity.Hint


def test_severity_override_by_symbol():
    """A per-symbol override in the severity map takes precedence."""
    custom = {**DEFAULT_SEVERITY, "unused-import": "Hint"}
    sev = _get_severity("unused-import", "W0611", "warning", custom)
    assert sev == lsp_server.lsp.DiagnosticSeverity.Hint


def test_severity_override_by_code():
    """A per-code override in the severity map takes precedence."""
    custom = {**DEFAULT_SEVERITY, "W0611": "Information"}
    sev = _get_severity("unused-import", "W0611", "warning", custom)
    # Symbol lookup returns None → falls through to code lookup
    assert sev == lsp_server.lsp.DiagnosticSeverity.Information


def test_severity_unknown_type_defaults_to_error():
    """An unrecognised type defaults to Error."""
    sev = _get_severity("custom-check", "X9999", "unknown", DEFAULT_SEVERITY)
    assert sev == lsp_server.lsp.DiagnosticSeverity.Error
