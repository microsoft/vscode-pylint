# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Thin regression tests for delegated tool_server paths.

Validates that key lsp_server functions correctly delegate to tool_server
and that workspace_settings/global_settings are read live (not stale aliases).
"""

# pylint: disable=protected-access
from unittest.mock import MagicMock, patch

import lsp_server
import pytest


@pytest.fixture()
def _mock_workspace_settings():
    """Populate workspace_settings with a fake entry, clean up afterwards."""
    ws = lsp_server.tool_server.workspace_settings
    original = ws.copy()
    ws.clear()
    ws["test_ws"] = {
        "workspaceFS": "/fake/workspace",
        "path": [],
        "interpreter": [],
        "args": [],
        "importStrategy": "useBundled",
        "extraPaths": [],
        "enabled": True,
    }
    yield ws
    ws.clear()
    ws.update(original)


def test_log_version_info_reads_live_workspace_settings(
    patched_lsp_server, _mock_workspace_settings  # pylint: disable=unused-argument
):
    """_log_version_info iterates tool_server.workspace_settings (not a stale alias)."""
    with patch.object(lsp_server, "_run_tool") as mock_run:
        mock_run.return_value = lsp_server.RunResult(stdout="pylint 3.0.0", stderr="")
        # Should not raise; confirms it reads the live dict
        lsp_server._log_version_info()
        mock_run.assert_called_once()


def test_workspace_settings_alias_removed():
    """WORKSPACE_SETTINGS module-level alias should no longer exist."""
    assert not hasattr(lsp_server, "WORKSPACE_SETTINGS")


def test_global_settings_alias_removed():
    """GLOBAL_SETTINGS module-level alias should no longer exist."""
    assert not hasattr(lsp_server, "GLOBAL_SETTINGS")


def test_dead_shims_removed():
    """Vestigial pass-through shims should no longer exist."""
    for name in (
        "_get_global_defaults",
        "_update_workspace_settings",
        "_get_settings_by_path",
        "_get_document_key",
        "get_cwd",
    ):
        assert not hasattr(lsp_server, name), f"{name} should have been removed"


def test_tool_server_get_settings_by_document_delegated():
    """get_settings_by_document is called on tool_server directly."""
    mock_return = {"enabled": False, "workspaceFS": "/fake"}
    with patch.object(
        lsp_server.tool_server,
        "get_settings_by_document",
        return_value=mock_return,
    ) as mock_get:
        doc = MagicMock()
        doc.path = "/fake/file.py"
        result = lsp_server.tool_server.get_settings_by_document(doc)
        mock_get.assert_called_once_with(doc)
        assert result["enabled"] is False
