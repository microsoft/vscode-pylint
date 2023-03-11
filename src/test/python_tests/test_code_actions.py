# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Test for code actions over LSP.
"""

import os
from threading import Event

import pytest
from hamcrest import assert_that, greater_than, is_

from .lsp_test_client import constants, session, utils

TEST_FILE_PATH = constants.TEST_DATA / "sample1" / "sample.py"
TEST_FILE_URI = utils.as_uri(str(TEST_FILE_PATH))
LINTER = utils.get_server_info_defaults()["name"]
TIMEOUT = 10  # 10 seconds


def _expected_format_command():
    return {
        "title": f"{LINTER}: Run document formatting",
        "command": "editor.action.formatDocument",
    }


def _expected_organize_imports_command():
    return {
        "title": f"{LINTER}: Run organize imports",
        "command": "editor.action.organizeImports",
    }


@pytest.mark.parametrize(
    ("code", "contents", "command"),
    [
        (
            "C0301:line-too-long",
            # pylint: disable=line-too-long
            "FRUIT = ['apricot', 'blackcurrant', 'cantaloupe', 'dragon fruit', 'elderberry', 'fig', 'grapefruit', 'honeydew melon', 'jackfruit', 'kiwi', 'lemon', 'mango', 'nectarine', 'orange', 'papaya', 'quince', 'raspberry', 'strawberry', 'tangerine', 'watermelon']\n",
            _expected_format_command(),
        ),
        (
            "C0303:trailing-whitespace",
            "x =  1    \ny = 1\n",
            _expected_format_command(),
        ),
        (
            "C0304:missing-final-newline",
            "print('hello')",
            _expected_format_command(),
        ),
        (
            "C0305:trailing-newlines",
            "VEGGIE = ['carrot', 'radish', 'cucumber', 'potato']\n\n\n",
            _expected_format_command(),
        ),
        (
            "C0321:multiple-statements",
            "import sys; print(sys.executable)\n",
            _expected_format_command(),
        ),
        (
            "C0410:multiple-imports",
            "import os, sys\n",
            _expected_organize_imports_command(),
        ),
        (
            "C0411:wrong-import-order",
            "import os\nfrom . import utils\nimport pylint\nimport sys\n",
            _expected_organize_imports_command(),
        ),
        (
            "C0412:ungrouped-imports",
            # pylint: disable=line-too-long
            "import logging\nimport os\nimport sys\nimport logging.config\nfrom logging.handlers import WatchedFileHandler\n",
            _expected_organize_imports_command(),
        ),
    ],
)
def test_command_code_action(code, contents, command):
    """Tests for code actions which run a command."""
    with utils.python_file(contents, TEST_FILE_PATH.parent) as temp_file:
        diagnostics, actual_code_actions = _get_diagnostics_and_code_actions_for_file(
            temp_file, contents, code
        )

        actual_code_specific_actions = _remove_generic_actions(actual_code_actions)

        expected = [
            {
                "title": command["title"],
                "kind": "quickfix",
                "diagnostics": [d],
                "command": command,
            }
            for d in diagnostics
        ]

        assert_that(actual_code_specific_actions, is_(expected))


@pytest.mark.parametrize(
    ("code", "contents", "uri"),
    [
        (
            "E1300:bad-format-character",
            "print('%s %z' % ('hello', 'world'))",
            "error/bad-format-character.html",
        ),
        (
            "W0129:assert-on-string-literal",
            "assert 'foo'",
            "warning/assert-on-string-literal.html",
        ),
        (
            "C0303:trailing-whitespace",
            "x =  1    \ny = 1\n",
            "convention/trailing-whitespace.html",
        ),
    ],
)
def test_documentation_action(code, contents, uri):
    """Tests that for messages a code action linking to the online documentation exists"""
    with utils.python_file(contents, TEST_FILE_PATH.parent) as temp_file:
        diagnostics, actual_code_actions = _get_diagnostics_and_code_actions_for_file(
            temp_file, contents, code
        )

        command = {
            "title": f"Pylint: Open documentation for {code}",
            "command": "simpleBrowser.show",
            "arguments": [
                f"https://pylint.readthedocs.io/en/latest/user_guide/messages/{uri}"
            ],
        }

        expected = [
            {
                "title": command["title"],
                "kind": "quickfix",
                "diagnostics": [d],
                "command": command,
            }
            for d in diagnostics
        ]

        assert_that(all(e in actual_code_actions) for e in expected)


def _get_diagnostics_and_code_actions_for_file(temp_file, contents, code):
    uri = utils.as_uri(os.fspath(temp_file))

    actual = {}
    with session.LspSession() as ls_session:
        ls_session.initialize()

        done = Event()

        def _handler(params):
            nonlocal actual
            actual = params
            done.set()

        ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)

        ls_session.notify_did_open(
            {
                "textDocument": {
                    "uri": uri,
                    "languageId": "python",
                    "version": 1,
                    "text": contents,
                }
            }
        )

        # wait for some time to receive all notifications
        done.wait(TIMEOUT)

        diagnostics = [d for d in actual["diagnostics"] if d["code"] == code]

        assert_that(len(diagnostics), is_(greater_than(0)))

        code_actions = ls_session.text_document_code_action(
            {
                "textDocument": {"uri": uri},
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 1, "character": 0},
                },
                "context": {"diagnostics": diagnostics},
            }
        )

        return diagnostics, code_actions


def _remove_generic_actions(code_actions):
    """Remove all code actions that are not specific to a single message."""
    return [
        action for action in code_actions if "Open documentation" not in action["title"]
    ]
