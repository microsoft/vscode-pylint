# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Test for linting over LSP.
"""

import sys
from threading import Event

from hamcrest import assert_that, greater_than, is_

from .lsp_test_client import constants, session, utils

file_path = constants.TEST_DATA / "sample1" / "sample.py"
uri = utils.as_uri(file_path)
linter = utils.get_linter_defaults()


def test_publish_diagnostics_on_open():
    """Test to ensure linting on file open."""
    contents = file_path.read_text()

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
                    "uri": uri,
                    "languageId": "python",
                    "version": 1,
                    "text": contents,
                }
            }
        )

        # wait for a second to receive all notifications
        done.wait(1)

    expected = {
        "uri": uri,
        "diagnostics": [
            {
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 0},
                },
                "message": "Missing module docstring",
                "severity": 3,
                "code": "C0114:missing-module-docstring",
                "source": linter["name"],
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
                "source": linter["name"],
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
                "source": linter["name"],
            },
        ],
    }

    assert_that(actual, is_(expected))


def test_publish_diagnostics_on_save():
    """Test to ensure linting on file save."""
    contents = file_path.read_text()

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
                    "uri": uri,
                    "languageId": "python",
                    "version": 1,
                    "text": contents,
                }
            }
        )

        # wait for a second to receive all notifications
        done.wait(1)

    expected = {
        "uri": uri,
        "diagnostics": [
            {
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 0},
                },
                "message": "Missing module docstring",
                "severity": 3,
                "code": "C0114:missing-module-docstring",
                "source": linter["name"],
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
                "source": linter["name"],
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
                "source": linter["name"],
            },
        ],
    }

    assert_that(actual, is_(expected))


def test_publish_diagnostics_on_close():
    """Test to ensure diagnostic clean-up on file close."""
    contents = file_path.read_text()

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
                    "uri": uri,
                    "languageId": "python",
                    "version": 1,
                    "text": contents,
                }
            }
        )

        # wait for a second to receive all notifications
        done.wait(1)

        # We should receive some diagnostics
        assert_that(len(actual), is_(greater_than(0)))

        # reset waiting
        done.clear()

        ls_session.notify_did_close(
            {
                "textDocument": {
                    "uri": uri,
                    "languageId": "python",
                    "version": 1,
                }
            }
        )

        # wait for a second to receive all notifications
        done.wait(1)

    # On close should clearout everything
    expected = {
        "uri": uri,
        "diagnostics": [],
    }
    assert_that(actual, is_(expected))
