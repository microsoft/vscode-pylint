# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Thin regression tests for delegated tool_server paths.

Validates that key lsp_server functions correctly delegate to tool_server
and that workspace_settings/global_settings are read live (not stale aliases).
"""

# pylint: disable=protected-access
import types
from unittest.mock import Mock, patch

import lsp_server
import pytest

from .lsp_test_client import utils


@pytest.fixture(name="participation_settings")
def _participation_settings(tmp_path, monkeypatch):
    """Use real shared routing with retained mixed and nested settings."""
    roots = [tmp_path, tmp_path / "disabled", tmp_path / "disabled" / "nested"]
    settings = []
    for root, enabled in zip(roots, (True, False, True)):
        root.mkdir(parents=True, exist_ok=True)
        value = utils.get_initialization_options()["settings"][0]
        value.update(workspace=root.as_uri(), cwd=str(root), _toolEnabled=enabled)
        settings.append(value)
    global_settings = utils.get_initialization_options()["globalSettings"]
    global_settings["_toolEnabled"] = False
    server = lsp_server.ToolServer(lsp_server.PYLINT_CONFIG)
    server.apply_settings(
        types.SimpleNamespace(
            initialization_options={
                "settings": settings,
                "globalSettings": global_settings,
            }
        )
    )
    monkeypatch.setattr(lsp_server, "tool_server", server)
    monkeypatch.setattr(lsp_server, "_lint_versions", {})
    return roots


def test_participation_routing_keeps_disabled_and_nested_roots(participation_settings):
    """The most-specific root wins; outside files use global participation."""
    enabled, disabled, nested = participation_settings
    for root, expected in (
        (enabled, True),
        (disabled, False),
        (nested, True),
        (enabled.parent / "outside", False),
    ):
        document = types.SimpleNamespace(path=str(root / "probe.py"))
        assert lsp_server._is_document_enabled(document) is expected


def test_disabled_lint_and_startup_skip_tool_work(participation_settings, monkeypatch):
    """Do not execute the linter or publish a loading score for disabled files."""
    _, disabled, _ = participation_settings
    document = types.SimpleNamespace(
        uri=(disabled / "probe.py").as_uri(), path=str(disabled / "probe.py")
    )
    notify = Mock()
    monkeypatch.setattr(
        lsp_server.LSP_SERVER,
        "protocol",
        types.SimpleNamespace(notify=notify),
        raising=False,
    )
    with patch.object(lsp_server, "_run_tool_on_document") as run_document:
        assert lsp_server._linting_helper(document) == []
        run_document.assert_not_called()
        notify.assert_not_called()
    with (
        patch.object(lsp_server.tool_server, "execute_tool") as execute,
        patch.object(lsp_server, "log_warning"),
    ):
        assert lsp_server._run_tool_on_document(document) is None
        execute.assert_not_called()
    with patch.object(lsp_server, "_run_tool") as run:
        run.return_value = lsp_server.RunResult(stdout="pylint 4.0.9", stderr="")
        lsp_server._log_version_info()
        assert run.call_count == 2
        assert all(call.args[1]["_toolEnabled"] for call in run.call_args_list)


def test_disabled_notebook_clears_cells_without_linting(
    participation_settings, monkeypatch
):
    """Route by the notebook path, invalidate old work, and clear stale cells."""
    _, disabled, _ = participation_settings
    monkeypatch.setattr(lsp_server.lsp.NotebookCellKind, "Code", 2, raising=False)
    notebook_uri = (disabled / "probe.ipynb").as_uri()
    cell_uri = notebook_uri.replace("file:", "vscode-notebook-cell:", 1) + "#cell"
    notebook = types.SimpleNamespace(
        cells=[
            types.SimpleNamespace(
                kind=lsp_server.lsp.NotebookCellKind.Code, document=cell_uri
            )
        ]
    )
    monkeypatch.setattr(
        lsp_server.LSP_SERVER,
        "workspace",
        types.SimpleNamespace(get_notebook_document=lambda **_: notebook),
        raising=False,
    )
    lsp_server._lint_versions[notebook_uri] = 1
    with (
        patch.object(lsp_server, "_run_tool_on_document") as run,
        patch.object(lsp_server, "_clear_notebook_cell_diagnostics") as clear,
    ):
        lsp_server._linting_helper_notebook(notebook_uri)
        run.assert_not_called()
        clear.assert_called_once_with(cell_uri)
        assert lsp_server._lint_versions[notebook_uri] == 2


@pytest.mark.parametrize("notebook_cell", (False, True))
def test_disabled_actions_and_resolve_do_not_edit(
    participation_settings, monkeypatch, notebook_cell
):
    """No quick fixes or previously requested edits may escape participation."""
    _, disabled, _ = participation_settings
    path = disabled / ("probe.ipynb" if notebook_cell else "probe.py")
    uri = path.as_uri()
    if notebook_cell:
        uri = uri.replace("file:", "vscode-notebook-cell:", 1) + "#cell"
    document = types.SimpleNamespace(uri=uri, path=str(disabled.parent / "wrong.py"))
    if not notebook_cell:
        document.path = str(path)
    monkeypatch.setattr(
        lsp_server.LSP_SERVER,
        "workspace",
        types.SimpleNamespace(get_text_document=lambda _: document),
        raising=False,
    )
    params = types.SimpleNamespace(text_document=types.SimpleNamespace(uri=uri))
    assert lsp_server.code_action(params) == []
    action = types.SimpleNamespace(data=uri, edit=object())
    with patch.object(lsp_server, "_create_workspace_edits") as edits:
        assert lsp_server.code_action_resolve(action).edit is None
        edits.assert_not_called()


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


def test_get_extra_args_uses_tool_server_get_settings_by_document():
    """_get_extra_args uses tool_server.get_settings_by_document."""
    with patch.object(
        lsp_server.tool_server,
        "get_settings_by_document",
        return_value={"workspaceFS": "ws"},
    ) as mock_get:
        assert lsp_server._get_extra_args(None) == []
        mock_get.assert_called_once_with(None)
