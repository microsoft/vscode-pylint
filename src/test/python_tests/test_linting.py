# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Test for linting over LSP.
"""

import sys
from threading import Event

import pytest
from hamcrest import assert_that, greater_than, is_

from .lsp_test_client import constants, defaults, session, utils

TEST_FILE_PATH = constants.TEST_DATA / "sample1" / "sample.py"
TEST_FILE_URI = utils.as_uri(str(TEST_FILE_PATH))
LINTER = utils.get_server_info_defaults()
TIMEOUT = 10  # 10 seconds
DOCUMENTATION_HOME = "https://pylint.readthedocs.io/en/latest/user_guide/messages"


def test_publish_diagnostics_on_open():
    """Test to ensure linting on file open."""
    contents = TEST_FILE_PATH.read_text(encoding="utf-8")

    actual = []
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
                    "uri": TEST_FILE_URI,
                    "languageId": "python",
                    "version": 1,
                    "text": contents,
                }
            }
        )

        # wait for some time to receive all notifications
        done.wait(TIMEOUT)

    expected = {
        "uri": TEST_FILE_URI,
        "diagnostics": [
            {
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 0},
                },
                "message": "Missing module docstring",
                "severity": 3,
                "code": "C0114:missing-module-docstring",
                "codeDescription": {
                    "href": f"{DOCUMENTATION_HOME}/convention/missing-module-docstring.html"
                },
                "source": LINTER["name"],
            },
            {
                "range": {
                    "start": {"line": 2, "character": 6},
                    "end": {
                        "line": 2,
                        "character": 7 if sys.version_info >= (3, 8) else 6,
                    },
                },
                "message": "Undefined variable 'x'",
                "severity": 1,
                "code": "E0602:undefined-variable",
                "codeDescription": {
                    "href": f"{DOCUMENTATION_HOME}/error/undefined-variable.html"
                },
                "source": LINTER["name"],
            },
            {
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {
                        "line": 0,
                        "character": 10 if sys.version_info >= (3, 8) else 0,
                    },
                },
                "message": "Unused import sys",
                "severity": 2,
                "code": "W0611:unused-import",
                "codeDescription": {
                    "href": f"{DOCUMENTATION_HOME}/warning/unused-import.html"
                },
                "source": LINTER["name"],
            },
        ],
    }

    assert_that(actual, is_(expected))


def test_publish_diagnostics_on_save():
    """Test to ensure linting on file save."""
    contents = TEST_FILE_PATH.read_text(encoding="utf-8")

    actual = []
    with session.LspSession() as ls_session:
        ls_session.initialize()

        done = Event()

        def _handler(params):
            nonlocal actual
            actual = params
            done.set()

        ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)

        ls_session.notify_did_save(
            {
                "textDocument": {
                    "uri": TEST_FILE_URI,
                    "languageId": "python",
                    "version": 1,
                    "text": contents,
                }
            }
        )

        # wait for some time to receive all notifications
        done.wait(TIMEOUT)

    expected = {
        "uri": TEST_FILE_URI,
        "diagnostics": [
            {
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 0},
                },
                "message": "Missing module docstring",
                "severity": 3,
                "code": "C0114:missing-module-docstring",
                "codeDescription": {
                    "href": f"{DOCUMENTATION_HOME}/convention/missing-module-docstring.html"
                },
                "source": LINTER["name"],
            },
            {
                "range": {
                    "start": {"line": 2, "character": 6},
                    "end": {
                        "line": 2,
                        "character": 7 if sys.version_info >= (3, 8) else 6,
                    },
                },
                "message": "Undefined variable 'x'",
                "severity": 1,
                "code": "E0602:undefined-variable",
                "codeDescription": {
                    "href": f"{DOCUMENTATION_HOME}/error/undefined-variable.html"
                },
                "source": LINTER["name"],
            },
            {
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {
                        "line": 0,
                        "character": 10 if sys.version_info >= (3, 8) else 0,
                    },
                },
                "message": "Unused import sys",
                "severity": 2,
                "code": "W0611:unused-import",
                "codeDescription": {
                    "href": f"{DOCUMENTATION_HOME}/warning/unused-import.html"
                },
                "source": LINTER["name"],
            },
        ],
    }

    assert_that(actual, is_(expected))


def test_publish_diagnostics_on_close():
    """Test to ensure diagnostic clean-up on file close."""
    contents = TEST_FILE_PATH.read_text(encoding="utf-8")

    actual = []
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
                    "uri": TEST_FILE_URI,
                    "languageId": "python",
                    "version": 1,
                    "text": contents,
                }
            }
        )

        # wait for some time to receive all notifications
        done.wait(TIMEOUT)

        # We should receive some diagnostics
        assert_that(len(actual), is_(greater_than(0)))

        # reset waiting
        done.clear()

        ls_session.notify_did_close(
            {
                "textDocument": {
                    "uri": TEST_FILE_URI,
                    "languageId": "python",
                    "version": 1,
                }
            }
        )

        # wait for some time to receive all notifications
        done.wait(TIMEOUT)

    # On close should clearout everything
    expected = {
        "uri": TEST_FILE_URI,
        "diagnostics": [],
    }
    assert_that(actual, is_(expected))


@pytest.mark.parametrize("lint_code", ["W0611", "unused-import", "warning"])
def test_severity_setting(lint_code):
    """Test to ensure linting on file open."""
    contents = TEST_FILE_PATH.read_text(encoding="utf-8")

    actual = []
    with session.LspSession() as ls_session:
        init_options = defaults.VSCODE_DEFAULT_INITIALIZE["initializationOptions"]
        init_options["settings"][0]["severity"][lint_code] = "Error"
        ls_session.initialize(defaults.VSCODE_DEFAULT_INITIALIZE)

        done = Event()

        def _handler(params):
            nonlocal actual
            actual = params
            done.set()

        ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)

        ls_session.notify_did_open(
            {
                "textDocument": {
                    "uri": TEST_FILE_URI,
                    "languageId": "python",
                    "version": 1,
                    "text": contents,
                }
            }
        )

        # wait for some time to receive all notifications
        done.wait(TIMEOUT)

    expected = {
        "uri": TEST_FILE_URI,
        "diagnostics": [
            {
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 0},
                },
                "message": "Missing module docstring",
                "severity": 3,
                "code": "C0114:missing-module-docstring",
                "codeDescription": {
                    "href": f"{DOCUMENTATION_HOME}/convention/missing-module-docstring.html"
                },
                "source": LINTER["name"],
            },
            {
                "range": {
                    "start": {"line": 2, "character": 6},
                    "end": {
                        "line": 2,
                        "character": 7 if sys.version_info >= (3, 8) else 6,
                    },
                },
                "message": "Undefined variable 'x'",
                "severity": 1,
                "code": "E0602:undefined-variable",
                "codeDescription": {
                    "href": f"{DOCUMENTATION_HOME}/error/undefined-variable.html"
                },
                "source": LINTER["name"],
            },
            {
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {
                        "line": 0,
                        "character": 10 if sys.version_info >= (3, 8) else 0,
                    },
                },
                "message": "Unused import sys",
                "severity": 1,
                "code": "W0611:unused-import",
                "codeDescription": {
                    "href": f"{DOCUMENTATION_HOME}/warning/unused-import.html"
                },
                "source": LINTER["name"],
            },
        ],
    }

    assert_that(actual, is_(expected))
