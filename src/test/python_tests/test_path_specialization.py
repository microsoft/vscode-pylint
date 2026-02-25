"""
Test for path and interpreter settings.
"""

import pathlib
import tempfile
from threading import Event
from typing import Dict

import pytest
from hamcrest import assert_that, is_

from .lsp_test_client import constants, defaults, session, utils

# Path to bundled tool for direct testing
BUNDLED_TOOL_PATH = (
    pathlib.Path(__file__).parent.parent.parent.parent / "bundled" / "tool"
)


@pytest.fixture(autouse=True)
def _prepend_bundled_tool_to_sys_path(monkeypatch):
    """Prepend bundled tool path to sys.path for each test in this module."""
    monkeypatch.syspath_prepend(str(BUNDLED_TOOL_PATH))

TEST_FILE_PATH = constants.TEST_DATA / "sample1" / "sample.py"
TEST_FILE_URI = utils.as_uri(str(TEST_FILE_PATH))
TIMEOUT = 10  # 10 seconds


class CallbackObject:
    """Object that holds results for WINDOW_LOG_MESSAGE to capture argv"""

    def __init__(self):
        self.result = False

    def check_result(self):
        """returns Boolean result"""
        return self.result

    def check_for_argv_duplication(self, argv: Dict[str, str]):
        """checks if argv duplication exists and sets result boolean"""
        if argv["type"] == 4 and argv["message"].find("--from-stdin") >= 0:
            parts = argv["message"].split()
            count = len([x for x in parts if x.startswith("--from-stdin")])
            self.result = count > 1


def test_path():
    """Test linting using pylint bin path set."""

    default_init = defaults.vscode_initialize_defaults()
    default_init["initializationOptions"]["settings"][0]["path"] = ["pylint"]

    argv_callback_object = CallbackObject()
    contents = TEST_FILE_PATH.read_text(encoding="utf-8")

    actual = True
    with session.LspSession() as ls_session:
        ls_session.set_notification_callback(
            session.WINDOW_LOG_MESSAGE,
            argv_callback_object.check_for_argv_duplication,
        )

        done = Event()

        def _handler(_params):
            done.set()

        ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)

        ls_session.initialize(default_init)
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
        done.clear()

        # Call this second time to detect arg duplication.
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

        actual = argv_callback_object.check_result()

    assert_that(actual, is_(False))


def test_interpreter():
    """Test linting using specific python path."""
    default_init = defaults.vscode_initialize_defaults()
    default_init["initializationOptions"]["settings"][0]["interpreter"] = ["python"]

    argv_callback_object = CallbackObject()
    contents = TEST_FILE_PATH.read_text(encoding="utf-8")

    actual = True
    with session.LspSession() as ls_session:
        ls_session.set_notification_callback(
            session.WINDOW_LOG_MESSAGE,
            argv_callback_object.check_for_argv_duplication,
        )

        done = Event()

        def _handler(_params):
            done.set()

        ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)

        ls_session.initialize(default_init)
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
        done.clear()

        # Call this second time to detect arg duplication.
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

        actual = argv_callback_object.check_result()

    assert_that(actual, is_(False))


def test_document_key_resolution_with_symlinks():
    """Test that _get_document_key correctly resolves symlinked paths.

    This is a regression test for symlink path resolution issues where
    workspace-level settings were ignored when document paths contained symlinks.
    See: vscode-flake8#340, vscode-mypy#396
    """
    from unittest.mock import Mock

    import lsp_server
    import lsp_utils

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create the real workspace directory
        real_workspace = pathlib.Path(tmpdir) / "real_workspace"
        real_workspace.mkdir()

        # Create a Python file
        test_file = real_workspace / "test.py"
        test_file.write_text("print('test')")

        # Create a symlink to the workspace
        symlink_workspace = pathlib.Path(tmpdir) / "symlinked_workspace"
        try:
            symlink_workspace.symlink_to(real_workspace, target_is_directory=True)
        except OSError as e:
            pytest.skip(f"Symlinks not supported in this environment: {e}")

        # File path accessed through the symlink
        symlinked_file = symlink_workspace / "test.py"

        # Set up workspace settings with the real workspace path
        real_workspace_key = lsp_utils.normalize_path(str(real_workspace))
        lsp_server.WORKSPACE_SETTINGS.clear()
        lsp_server.WORKSPACE_SETTINGS[real_workspace_key] = {
            "workspaceFS": real_workspace_key,
            "args": ["--max-line-length=120"],
        }

        # Create a mock document with the symlinked path
        mock_document = Mock()
        mock_document.path = str(symlinked_file)

        # Test that _get_document_key finds the workspace despite the symlink
        document_key = lsp_server._get_document_key(mock_document)

        # The document key should match the real workspace key
        assert document_key == real_workspace_key, (
            f"Expected document key '{real_workspace_key}' but got '{document_key}'. "
            "Symlinked paths should resolve to match workspace settings."
        )

        # Verify we can retrieve the correct settings
        settings = lsp_server._get_settings_by_document(mock_document)
        assert settings is not None, "Should retrieve workspace settings"
        assert settings.get("args") == [
            "--max-line-length=120"
        ], "Should get workspace-specific args, not fall back to global settings"


def test_is_same_path_with_symlinks():
    """Test that is_same_path correctly identifies paths through symlinks as equal."""
    import lsp_utils

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create real directory structure
        real_dir = pathlib.Path(tmpdir) / "real_dir"
        real_dir.mkdir()

        # Create a test file
        test_file = real_dir / "test_file.py"
        test_file.write_text("# test file", encoding="utf-8")

        # Create a symlink to the real directory
        symlink_dir = pathlib.Path(tmpdir) / "symlink_dir"
        try:
            symlink_dir.symlink_to(real_dir, target_is_directory=True)
        except OSError as e:
            pytest.skip(f"Symlinks not supported in this environment: {e}")

        # Real path
        real_file_path = str(real_dir / "test_file.py")
        # Path through symlink
        symlink_file_path = str(symlink_dir / "test_file.py")

        # The string paths are different
        assert real_file_path != symlink_file_path

        # But is_same_path should identify them as the same file
        assert_that(
            lsp_utils.is_same_path(real_file_path, symlink_file_path), is_(True)
        )
        assert_that(
            lsp_utils.is_same_path(symlink_file_path, real_file_path), is_(True)
        )
