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

            actual_code_actions = ls_session.text_document_code_action(
                {
                    "textDocument": {"uri": uri},
                    "range": {
                        "start": {"line": 0, "character": 0},
                        "end": {"line": 1, "character": 0},
                    },
                    "context": {"diagnostics": diagnostics},
                }
            )

            expected = [
                {
                    "title": command["title"],
                    "kind": "quickfix",
                    "diagnostics": [d],
                    "command": command,
                }
                for d in diagnostics
            ]

        assert_that(actual_code_actions, is_(expected))


@pytest.mark.parametrize(
    ("code", "contents", "new_text"),
    [
        (
            "C0113:unneeded-not",
            """
if not not True:
    pass""",
            """if True:
""",
        ),
        (
            "C0121:singleton-comparison",
            """
foo = True
if foo == True:
    pass""",
            """if foo:
""",
        ),
        (
            "C0121:singleton-comparison",
            """
foo = True
if foo != False:
    pass""",
            """if foo:
""",
        ),
        (
            "C0121:singleton-comparison",
            """
foo = True
if True == foo:
    pass""",
            """if foo:
""",
        ),
        (
            "C0121:singleton-comparison",
            """
foo = True
if False != foo:
    pass""",
            """if foo:
""",
        ),
        (
            "C0121:singleton-comparison",
            """
foo = True
if foo == False:
    pass""",
            """if not foo:
""",
        ),
        (
            "C0121:singleton-comparison",
            """
foo = True
if foo != True:
    pass""",
            """if not foo:
""",
        ),
        (
            "C0121:singleton-comparison",
            """
foo = True
if False == foo:
    pass""",
            """if not foo:
""",
        ),
        (
            "C0121:singleton-comparison",
            """
foo = True
if True != foo:
    pass""",
            """if not foo:
""",
        ),
        (
            "C0123:unidiomatic-typecheck",
            """
test_score = {"Biology": 95, "History": 80}
if type(test_score) is dict:
    pass""",
            """if isinstance(test_score, dict):
""",
        ),
        (
            "R0205:useless-object-inheritance",
            """
class Banana(object):
    pass""",
            """class Banana:
""",
        ),
        (
            "R1721:unnecessary-comprehension",
            """
NUMBERS = [1, 1, 2, 2, 3, 3]

UNIQUE_NUMBERS = {number for number in NUMBERS}
""",
            """UNIQUE_NUMBERS = set(NUMBERS)
""",
        ),
        (
            "E1141:dict-iter-missing-items",
            """
data = {'Paris': 2_165_423, 'New York City': 8_804_190, 'Tokyo': 13_988_129}
for city, population in data:
    print(f"{city} has population {population}.")
""",
            """for city, population in data.items():
""",
        ),
    ],
)
def test_edit_code_action(code, contents, new_text):
    """Tests for code actions which run a command."""
    with utils.python_file(contents, TEST_FILE_PATH.parent) as temp_file:
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

            actual_code_actions = ls_session.text_document_code_action(
                {
                    "textDocument": {"uri": uri},
                    "range": {
                        "start": {"line": 0, "character": 0},
                        "end": {"line": 1, "character": 0},
                    },
                    "context": {"diagnostics": diagnostics},
                }
            )
            text_document = actual_code_actions[0]["edit"]["documentChanges"][0][
                "textDocument"
            ]
            text_range = actual_code_actions[0]["edit"]["documentChanges"][0]["edits"][
                0
            ]["range"]
            expected = [
                {
                    "title": f"{LINTER}: Run autofix code action",
                    "kind": "quickfix",
                    "diagnostics": [d],
                    "edit": {
                        "documentChanges": [
                            {
                                "textDocument": text_document,
                                "edits": [
                                    {
                                        "range": text_range,
                                        "newText": new_text,
                                    }
                                ],
                            }
                        ]
                    },
                }
                for d in diagnostics
            ]

        assert_that(
            actual_code_actions[0]["edit"]["documentChanges"],
            is_(expected[0]["edit"]["documentChanges"]),
        )
