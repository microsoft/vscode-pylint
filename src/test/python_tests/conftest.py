# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Shared test fixtures for lsp_server unit tests.

Provides mock LSP dependencies so that ``import lsp_server`` succeeds
without the full VS Code extension environment, and exposes reusable
fixtures for patching the LSP_SERVER singleton.
"""

import os
import pathlib
import sys
import types
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Module-level mock injection
# ---------------------------------------------------------------------------
_INJECTED_MODULES = []
_INJECTED_PATHS = []


def _create_pygls_mocks():
    """Create mock ``pygls`` modules and return them as a dict."""

    class _MockLS:  # pylint: disable=missing-function-docstring
        def __init__(self, *_args, **_kwargs):
            pass

        def feature(self, *_args, **_kwargs):
            return lambda f: f

        def command(self, *_args, **_kwargs):
            return lambda f: f

        def window_log_message(self, *_args, **_kwargs):
            pass

        def window_show_message(self, *_args, **_kwargs):
            pass

    mock_server = types.ModuleType("pygls.server")
    mock_server.LanguageServer = _MockLS

    mock_lsp_server_mod = types.ModuleType("pygls.lsp.server")
    mock_lsp_server_mod.LanguageServer = _MockLS

    mock_lsp_mod = types.ModuleType("pygls.lsp")
    mock_lsp_mod.server = mock_lsp_server_mod

    doc_cls = type("TextDocument", (), {"path": None})
    mock_workspace = types.ModuleType("pygls.workspace")
    mock_workspace.Document = doc_cls
    mock_workspace.TextDocument = doc_cls

    mock_uris = types.ModuleType("pygls.uris")

    def _from_fs_path(path):
        return pathlib.Path(path).as_uri()

    def _to_fs_path(uri):
        if uri.startswith("file:///"):
            path = uri[len("file:///") :]
            if len(path) >= 2 and path[1] == ":":
                return path
            return "/" + path
        return uri

    mock_uris.from_fs_path = _from_fs_path
    mock_uris.to_fs_path = _to_fs_path

    mock_pygls = types.ModuleType("pygls")
    mock_pygls.__path__ = []
    mock_pygls.lsp = mock_lsp_mod
    mock_pygls.workspace = mock_workspace
    mock_pygls.uris = mock_uris

    mock_lsp_mod.__path__ = []

    return {
        "pygls": mock_pygls,
        "pygls.server": mock_server,
        "pygls.lsp": mock_lsp_mod,
        "pygls.lsp.server": mock_lsp_server_mod,
        "pygls.workspace": mock_workspace,
        "pygls.uris": mock_uris,
    }


def _create_lsprotocol_mocks():
    """Create mock ``lsprotocol`` modules and return them as a dict."""
    mock_lsp = types.ModuleType("lsprotocol.types")
    for _name in [
        "TEXT_DOCUMENT_DID_OPEN",
        "TEXT_DOCUMENT_DID_SAVE",
        "TEXT_DOCUMENT_DID_CLOSE",
        "TEXT_DOCUMENT_DID_CHANGE",
        "TEXT_DOCUMENT_FORMATTING",
        "TEXT_DOCUMENT_CODE_ACTION",
        "CODE_ACTION_RESOLVE",
        "INITIALIZE",
        "EXIT",
        "SHUTDOWN",
        "NOTEBOOK_DOCUMENT_DID_OPEN",
        "NOTEBOOK_DOCUMENT_DID_CHANGE",
        "NOTEBOOK_DOCUMENT_DID_SAVE",
        "NOTEBOOK_DOCUMENT_DID_CLOSE",
    ]:
        setattr(mock_lsp, _name, _name)

    mock_lsp.CodeActionKind = types.SimpleNamespace(QuickFix="quickfix")

    class _FlexClass:
        """Accepts arbitrary positional/keyword args (stores kwargs as attributes)."""

        def __init__(self, *_args, **_kwargs):
            for key, value in _kwargs.items():
                setattr(self, key, value)

    class _DiagSevMeta(type):
        _MAP = {"Error": 1, "Warning": 2, "Information": 3, "Hint": 4}

        def __getitem__(cls, key):
            return cls._MAP[key]

    class _MockDiagnosticSeverity(metaclass=_DiagSevMeta):
        Error = 1
        Warning = 2
        Information = 3
        Hint = 4

    mock_lsp.DiagnosticSeverity = _MockDiagnosticSeverity

    for _name in [
        "CodeDescription",
        "Diagnostic",
        "DidCloseTextDocumentParams",
        "DidOpenTextDocumentParams",
        "DidSaveTextDocumentParams",
        "DidChangeTextDocumentParams",
        "DidChangeNotebookDocumentParams",
        "DidCloseNotebookDocumentParams",
        "DidOpenNotebookDocumentParams",
        "DidSaveNotebookDocumentParams",
        "DocumentFormattingParams",
        "InitializeParams",
        "NotebookCellKind",
        "NotebookCellLanguage",
        "NotebookDocumentFilterWithNotebook",
        "NotebookDocumentSyncOptions",
        "Position",
        "Range",
        "TextEdit",
        "CodeAction",
        "CodeActionParams",
        "CodeActionOptions",
        "Command",
        "WorkspaceEdit",
        "TextDocumentEdit",
        "OptionalVersionedTextDocumentIdentifier",
        "LogMessageParams",
        "ShowMessageParams",
        "PublishDiagnosticsParams",
    ]:
        setattr(mock_lsp, _name, _FlexClass)

    mock_lsp.MessageType = types.SimpleNamespace(Log=4, Error=1, Warning=2, Info=3)

    mock_lsprotocol = types.ModuleType("lsprotocol")
    mock_lsprotocol.__path__ = []
    mock_lsprotocol.types = mock_lsp

    return {
        "lsprotocol": mock_lsprotocol,
        "lsprotocol.types": mock_lsp,
    }


def setup_lsp_mocks():
    """Inject mock LSP dependencies into ``sys.modules`` and ``sys.path``.

    Tracks what is injected so :func:`_lsp_mock_teardown` can undo it.
    """
    all_mocks = {}
    all_mocks.update(_create_pygls_mocks())
    all_mocks.update(_create_lsprotocol_mocks())

    for _mod_name, _mod in all_mocks.items():
        try:
            __import__(_mod_name)
        except ImportError:
            sys.modules[_mod_name] = _mod
            _INJECTED_MODULES.append(_mod_name)

    _project_root = pathlib.Path(__file__).parents[3]
    tool_dir = str(_project_root / "bundled" / "tool")
    libs_dir = str(_project_root / "bundled" / "libs")
    if libs_dir not in sys.path and os.path.isdir(libs_dir):
        sys.path.insert(0, libs_dir)
        _INJECTED_PATHS.append(libs_dir)
    if tool_dir not in sys.path:
        sys.path.insert(0, tool_dir)
        _INJECTED_PATHS.append(tool_dir)

    # Pre-import real bundled modules so that existing test files whose
    # _setup_mocks() guards (``if _mod_name not in sys.modules``) would
    # otherwise inject empty stubs cannot shadow them.
    import lsp_jsonrpc  # noqa: F401  # pylint: disable=unused-import
    import lsp_utils  # noqa: F401  # pylint: disable=unused-import


# Run at import time so test modules can ``import lsp_server`` at the top level.
setup_lsp_mocks()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _lsp_mock_teardown():
    """Remove injected mock modules and sys.path entries after the session."""
    yield
    for mod_name in _INJECTED_MODULES:
        sys.modules.pop(mod_name, None)
    _INJECTED_MODULES.clear()
    for p in _INJECTED_PATHS:
        if p in sys.path:
            sys.path.remove(p)
    _INJECTED_PATHS.clear()


@pytest.fixture()
def patched_lsp_server():
    """Patch ``LSP_SERVER.window_log_message`` and ``window_show_message``
    with ``MagicMock`` instances that are automatically restored after the test.
    """
    import lsp_server

    with patch.object(
        lsp_server.LSP_SERVER, "window_log_message"
    ) as log_mock, patch.object(
        lsp_server.LSP_SERVER, "window_show_message"
    ) as show_mock:
        yield log_mock, show_mock
