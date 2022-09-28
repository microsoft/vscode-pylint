# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Test for code actions over LSP.
"""

import os

import pytest
from hamcrest import assert_that, is_

from .lsp_test_client import constants, session, utils

TEST_FILE_PATH = constants.TEST_DATA / "sample1" / "sample.py"
TEST_FILE_URI = utils.as_uri(str(TEST_FILE_PATH))
LINTER = utils.get_server_info_defaults()["name"]


@pytest.mark.parametrize(
    ("code", "contents", "command"),
    [
        (
            "C0301:line-too-long", 
            # # pylint: disable=line-too-long
            "FRUIT = ['apricot', 'blackcurrant', 'cantaloupe', 'dragon fruit', 'elderberry', 'fig', 'grapefruit']",
            {
                "title": f"{LINTER}: Run document formatting",
                "command": "editor.action.formatDocument",
                "arguments": None,
            },
        ),
        (
            "C0305:trailing-newlines",
            # # pylint: disable=trailing-newlines
            "VEGGIE = ['carrot\n', 'radish\n', 'cucumber\n', 'potato\n', '\n']",
            {
                "title": f"{LINTER}: Run document formatting",
                "command": "editor.action.formatDocument",
                "arguments": None,
            },
        )
    ],
)
def test_command_code_action(code, contents, command):
    """Tests for code actions which run a command."""
    with utils.python_file(contents, TEST_FILE_PATH.parent) as temp_file:
        uri = utils.as_uri(os.fspath(temp_file))
        with session.LspSession() as ls_session:
            ls_session.initialize()

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

            diagnostics = [
                {
                    "range": {
                        "start": {"line": 0, "character": 0},
                        "end": {"line": 1, "character": 0},
                    },
                    "message": "",
                    "severity": 1,
                    "code": code,
                    "source": LINTER,
                }
            ]

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

            expected = {
                "title": command["title"],
                "kind": "quickfix",
                "diagnostics": diagnostics,
                "command": command,
            }

        assert_that(actual_code_actions, is_([expected]))
