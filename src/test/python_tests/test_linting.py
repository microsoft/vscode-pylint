import os
from threading import Event
from hamcrest import assert_that, greater_than, is_

from .lsp_test_client import session, utils, constants

file_path = os.path.join(constants.TEST_DATA, "sample1", "sample.py")
uri = utils.as_uri(file_path)
linter = utils.get_linter_defaults()


def test_publish_diagnostics_on_open():
    with open(file_path, "r") as f:
        contents = f.read()

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
        done.wait(1000)

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
                    "end": {"line": 2, "character": 7},
                },
                "message": "Undefined variable 'x'",
                "severity": 1,
                "code": "E0602:undefined-variable",
                "source": linter["name"],
            },
            {
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 10},
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
    with open(file_path, "r") as f:
        contents = f.read()

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
                    "end": {"line": 2, "character": 7},
                },
                "message": "Undefined variable 'x'",
                "severity": 1,
                "code": "E0602:undefined-variable",
                "source": linter["name"],
            },
            {
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 10},
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
    with open(file_path, "r") as f:
        contents = f.read()

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
        done.wait(100)

    # On close should clearout everything
    expected = {
        "uri": uri,
        "diagnostics": [],
    }
    assert_that(actual, is_(expected))
