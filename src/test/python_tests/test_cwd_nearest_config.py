# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Test for cwd with ${nearestConfig} setting.
"""

import os
import pathlib
import tempfile
from threading import Event
from typing import List

from hamcrest import assert_that, greater_than, is_

from .lsp_test_client import constants, defaults, session, utils

TEST_FILE_PATH = constants.TEST_DATA / "sample1" / "sample.py"
TEST_FILE_URI = utils.as_uri(str(TEST_FILE_PATH))
LINTER = utils.get_server_info_defaults()
TIMEOUT = 10  # 10 seconds


def test_nearest_config_with_pylintrc():
    """Test linting with cwd set to ${nearestConfig} when .pylintrc exists."""
    contents = TEST_FILE_PATH.read_text(encoding="utf-8")

    actual = []
    with session.LspSession() as ls_session:
        default_init = defaults.vscode_initialize_defaults()
        init_options = default_init["initializationOptions"]
        init_options["settings"][0]["cwd"] = "${nearestConfig}"
        ls_session.initialize(default_init)

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

    # Should still produce diagnostics when using ${nearestConfig}
    assert_that(len(actual["diagnostics"]), is_(greater_than(0)))


def test_nearest_config_falls_back_to_workspace():
    """Test that ${nearestConfig} falls back to workspace root when no config found."""
    # Create a temp directory with a Python file but no pylint config files
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = pathlib.Path(tmp_dir)
        sample_file = tmp_path / "test_sample.py"
        sample_file.write_text("import sys\n\nprint(x)\n", encoding="utf-8")
        sample_uri = utils.as_uri(str(sample_file))

        actual = []
        with session.LspSession() as ls_session:
            default_init = defaults.vscode_initialize_defaults()
            init_options = default_init["initializationOptions"]
            init_options["settings"][0]["cwd"] = "${nearestConfig}"
            init_options["settings"][0]["workspace"] = utils.as_uri(str(tmp_path))
            init_options["settings"][0]["workspaceFS"] = str(tmp_path)
            default_init["rootUri"] = utils.as_uri(str(tmp_path))
            default_init["rootPath"] = str(tmp_path)
            default_init["workspaceFolders"] = [
                {"uri": utils.as_uri(str(tmp_path)), "name": "tmp_project"}
            ]
            ls_session.initialize(default_init)

            done = Event()

            def _handler(params):
                nonlocal actual
                actual = params
                done.set()

            ls_session.set_notification_callback(
                session.PUBLISH_DIAGNOSTICS, _handler
            )

            ls_session.notify_did_open(
                {
                    "textDocument": {
                        "uri": sample_uri,
                        "languageId": "python",
                        "version": 1,
                        "text": sample_file.read_text(encoding="utf-8"),
                    }
                }
            )

            # wait for some time to receive all notifications
            done.wait(TIMEOUT)

        # Should still produce diagnostics even without config file (falls back to workspace root)
        assert_that(len(actual["diagnostics"]), is_(greater_than(0)))


def test_nearest_config_with_pyproject_toml():
    """Test that ${nearestConfig} finds pyproject.toml in parent directory."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = pathlib.Path(tmp_dir)

        # Create a pyproject.toml in the root
        (tmp_path / "pyproject.toml").write_text(
            "[tool.pylint]\n", encoding="utf-8"
        )

        # Create a subdirectory with a Python file
        sub_dir = tmp_path / "subpackage"
        sub_dir.mkdir()
        sample_file = sub_dir / "test_sample.py"
        sample_file.write_text("import sys\n\nprint(x)\n", encoding="utf-8")
        sample_uri = utils.as_uri(str(sample_file))

        actual = []
        with session.LspSession() as ls_session:
            default_init = defaults.vscode_initialize_defaults()
            init_options = default_init["initializationOptions"]
            init_options["settings"][0]["cwd"] = "${nearestConfig}"
            init_options["settings"][0]["workspace"] = utils.as_uri(str(tmp_path))
            init_options["settings"][0]["workspaceFS"] = str(tmp_path)
            default_init["rootUri"] = utils.as_uri(str(tmp_path))
            default_init["rootPath"] = str(tmp_path)
            default_init["workspaceFolders"] = [
                {"uri": utils.as_uri(str(tmp_path)), "name": "tmp_project"}
            ]
            ls_session.initialize(default_init)

            done = Event()

            def _handler(params):
                nonlocal actual
                actual = params
                done.set()

            ls_session.set_notification_callback(
                session.PUBLISH_DIAGNOSTICS, _handler
            )

            ls_session.notify_did_open(
                {
                    "textDocument": {
                        "uri": sample_uri,
                        "languageId": "python",
                        "version": 1,
                        "text": sample_file.read_text(encoding="utf-8"),
                    }
                }
            )

            # wait for some time to receive all notifications
            done.wait(TIMEOUT)

        # Should still produce diagnostics when pyproject.toml found
        assert_that(len(actual["diagnostics"]), is_(greater_than(0)))
