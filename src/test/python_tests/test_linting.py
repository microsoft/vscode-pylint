# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Test for linting over LSP.
"""

import sys
from threading import Event

from hamcrest import assert_that, greater_than, is_

from .lsp_test_client import constants, session, utils

TEST_FILE_PATH = constants.TEST_DATA / "sample1" / "sample.py"
TEST_FILE_URI = utils.as_uri(str(TEST_FILE_PATH))
LINTER = utils.get_linter_defaults()
TIMEOUT = 10  # 10 seconds


def test_publish_diagnostics_on_open():
    """Test to ensure linting on file open."""
    contents = TEST_FILE_PATH.read_text()

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
                "source": LINTER["name"],
            },
        ],
    }

    assert_that(actual, is_(expected))


def test_publish_diagnostics_on_save():
    """Test to ensure linting on file save."""
    contents = TEST_FILE_PATH.read_text()

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
                "source": LINTER["name"],
            },
        ],
    }

    assert_that(actual, is_(expected))


def test_publish_diagnostics_on_close():
    """Test to ensure diagnostic clean-up on file close."""
    contents = TEST_FILE_PATH.read_text()

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
