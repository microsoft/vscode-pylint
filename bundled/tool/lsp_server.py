# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Implementation of tool support over LSP."""

# pylint: disable=too-many-lines

from __future__ import annotations

import copy
import json
import os
import pathlib
import re
import sys
import threading
import traceback
import types
from typing import Any, Callable, Dict, List, Optional, Sequence, Union
from urllib.parse import urlparse, urlunparse


# **********************************************************
# Update sys.path before importing any bundled libraries.
# **********************************************************
def update_sys_path(path_to_add: str, strategy: str) -> None:
    """Add given path to `sys.path`."""
    if path_to_add not in sys.path and os.path.isdir(path_to_add):
        if strategy == "useBundled":
            sys.path.insert(0, path_to_add)
        else:
            sys.path.append(path_to_add)


# Ensure that we can import LSP libraries, and other bundled libraries.
BUNDLE_DIR = pathlib.Path(__file__).parent.parent
# Always use bundled server files.
update_sys_path(os.fspath(BUNDLE_DIR / "tool"), "useBundled")
update_sys_path(
    os.fspath(BUNDLE_DIR / "libs"),
    os.getenv("LS_IMPORT_STRATEGY", "useBundled"),
)

# **********************************************************
# Imports needed for the language server goes below this.
# **********************************************************
# pylint: disable=wrong-import-position,import-error
import lsp_notebook as notebook
import lsp_utils as utils
from lsprotocol import types as lsp
from pygls import uris
from pygls.lsp.server import LanguageServer
from pygls.workspace import TextDocument
from vscode_common_python_lsp import (
    QuickFixRegistrationError,
    RunResult,
    ToolServer,
    ToolServerConfig,
    is_current_interpreter,
    is_match,
    update_environ_path,
)

update_environ_path()

RUNNER = pathlib.Path(__file__).parent / "runner.py"

MAX_WORKERS = 5
_STDERR_ERROR_KEYWORDS = ("error", "traceback", "exception", "fatal")

# Track lint request versions per URI to discard stale results from superseded runs.
_lint_versions: Dict[str, int] = {}
_lint_versions_lock = threading.Lock()

LSP_SERVER = LanguageServer(
    name="pylint-server",
    version="v0.1.0",
    max_workers=MAX_WORKERS,
    notebook_document_sync=notebook.NOTEBOOK_SYNC_OPTIONS,
)

PYLINT_CONFIG = ToolServerConfig(
    tool_module="pylint",
    tool_display="Pylint",
    tool_args=["--reports=n", "--output-format=json2"],
    min_version="2.14.0",
    runner_script=str(RUNNER),
    default_settings={
        "enabled": True,
        "severity": {
            "convention": "Information",
            "error": "Error",
            "fatal": "Error",
            "refactor": "Hint",
            "warning": "Warning",
            "info": "Information",
        },
        "ignorePatterns": [],
        "extraPaths": [],
    },
)

tool_server = ToolServer(PYLINT_CONFIG, server=LSP_SERVER)

WORKSPACE_SETTINGS = tool_server.workspace_settings
GLOBAL_SETTINGS = tool_server.global_settings


def _get_document_path(document: str) -> str:
    """Returns the filesystem path for a document.

    Examples:
        file:///path/to/file.py -> /path/to/file.py
        vscode-notebook-cell:/path/to/notebook.ipynb#C00001 -> /path/to/notebook.ipynb
    """
    if not document.startswith("file:"):
        parsed = urlparse(document)
        file_uri = urlunparse(
            (
                "file",
                parsed.netloc,
                parsed.path,
                parsed.params,
                parsed.query,
                "",
            )
        )
        if result := uris.to_fs_path(file_uri):
            return result
    return uris.to_fs_path(document) or document


# **********************************************************
# Tool specific code goes below this.
# **********************************************************
TOOL_MODULE = PYLINT_CONFIG.tool_module
TOOL_DISPLAY = PYLINT_CONFIG.tool_display
DOCUMENTATION_HOME = "https://pylint.readthedocs.io/en/latest/user_guide/messages"

# Default arguments always passed to pylint.
TOOL_ARGS = PYLINT_CONFIG.tool_args

# Minimum version of pylint supported.
MIN_VERSION = PYLINT_CONFIG.min_version

# **********************************************************
# Linting features start here
# **********************************************************


# Captures version of `pylint` in various workspaces.
VERSION_TABLE: Dict[str, (int, int, int)] = {}


@LSP_SERVER.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
def did_open(params: lsp.DidOpenTextDocumentParams) -> None:
    """LSP handler for textDocument/didOpen request."""
    document = LSP_SERVER.workspace.get_text_document(params.text_document.uri)
    diagnostics: list[lsp.Diagnostic] = _linting_helper(document)
    LSP_SERVER.text_document_publish_diagnostics(
        lsp.PublishDiagnosticsParams(uri=document.uri, diagnostics=diagnostics)
    )


@LSP_SERVER.feature(lsp.TEXT_DOCUMENT_DID_SAVE)
def did_save(params: lsp.DidSaveTextDocumentParams) -> None:
    """LSP handler for textDocument/didSave request."""
    document = LSP_SERVER.workspace.get_text_document(params.text_document.uri)
    diagnostics: list[lsp.Diagnostic] = _linting_helper(document)
    LSP_SERVER.text_document_publish_diagnostics(
        lsp.PublishDiagnosticsParams(uri=document.uri, diagnostics=diagnostics)
    )


@LSP_SERVER.feature(lsp.TEXT_DOCUMENT_DID_CLOSE)
def did_close(params: lsp.DidCloseTextDocumentParams) -> None:
    """LSP handler for textDocument/didClose request."""
    document = LSP_SERVER.workspace.get_text_document(params.text_document.uri)
    # Publishing empty diagnostics to clear the entries for this file.
    LSP_SERVER.text_document_publish_diagnostics(
        lsp.PublishDiagnosticsParams(uri=document.uri, diagnostics=[])
    )


if os.getenv("VSCODE_PYLINT_LINT_ON_CHANGE"):

    @LSP_SERVER.feature(lsp.TEXT_DOCUMENT_DID_CHANGE)
    def did_change(params: lsp.DidChangeTextDocumentParams) -> None:
        """LSP handler for textDocument/didChange request."""
        document = LSP_SERVER.workspace.get_text_document(params.text_document.uri)
        diagnostics: list[lsp.Diagnostic] = _linting_helper(document)
        LSP_SERVER.text_document_publish_diagnostics(
            lsp.PublishDiagnosticsParams(uri=document.uri, diagnostics=diagnostics)
        )


@LSP_SERVER.feature(lsp.NOTEBOOK_DOCUMENT_DID_OPEN)
def notebook_did_open(params: lsp.DidOpenNotebookDocumentParams) -> None:
    """Run diagnostics on all code cells when a notebook is opened."""
    _linting_helper_notebook(params.notebook_document.uri)


@LSP_SERVER.feature(lsp.NOTEBOOK_DOCUMENT_DID_CHANGE)
def notebook_did_change(params: lsp.DidChangeNotebookDocumentParams) -> None:
    """Re-lint all cells when any cell changes (for cross-cell context)."""
    if params.change is not None and params.change.cells is not None:
        structure = params.change.cells.structure
        if structure and structure.did_close:
            for cell_document in structure.did_close:
                _clear_notebook_cell_diagnostics(cell_document.uri)
    _linting_helper_notebook(params.notebook_document.uri)


@LSP_SERVER.feature(lsp.NOTEBOOK_DOCUMENT_DID_SAVE)
def notebook_did_save(params: lsp.DidSaveNotebookDocumentParams) -> None:
    """Re-lint all cells when a notebook is saved."""
    _linting_helper_notebook(params.notebook_document.uri)


@LSP_SERVER.feature(lsp.NOTEBOOK_DOCUMENT_DID_CLOSE)
def notebook_did_close(params: lsp.DidCloseNotebookDocumentParams) -> None:
    """Clear diagnostics for all cells when the notebook is closed."""
    for cell_doc in params.cell_text_documents:
        _clear_notebook_cell_diagnostics(cell_doc.uri)


def _get_extra_args(document: TextDocument | None) -> list[str]:
    """Return extra pylint CLI args based on the pylint version for the workspace."""
    code_workspace = _get_settings_by_document(document)["workspaceFS"]
    if VERSION_TABLE.get(code_workspace, None):
        major, minor, _ = VERSION_TABLE[code_workspace]
        if (major, minor) >= (2, 16):
            return ["--clear-cache-post-run=y"]
    return []


def _linting_helper_notebook(notebook_uri: str) -> None:
    """Lint all code cells together and publish per-cell diagnostics."""
    try:
        nb = LSP_SERVER.workspace.get_notebook_document(notebook_uri=notebook_uri)
        if nb is None:
            return

        combined_source, cell_map = notebook.build_notebook_source(
            nb.cells, LSP_SERVER.workspace.get_text_document
        )
        if not cell_map:
            for cell in nb.cells:
                if cell.kind == lsp.NotebookCellKind.Code and cell.document:
                    LSP_SERVER.text_document_publish_diagnostics(
                        lsp.PublishDiagnosticsParams(uri=cell.document, diagnostics=[])
                    )
            return

        # Build a synthetic document pointing at the notebook's .ipynb path so
        # that settings resolution and pylint invocation work correctly.
        # NOTE: SimpleNamespace is used here as a lightweight stand-in for
        # workspace.TextDocument. If _run_tool_on_document or
        # _get_settings_by_document begin accessing additional attributes,
        # consider replacing this with a Protocol or TypedDict.
        nb_path = _get_document_path(notebook_uri)
        combined_doc = types.SimpleNamespace(
            uri=notebook_uri,
            path=nb_path,
            source=combined_source,
            language_id="python",
            version=0,
        )

        # Debounce: key on the notebook URI.
        with _lint_versions_lock:
            version = _lint_versions.get(notebook_uri, 0) + 1
            _lint_versions[notebook_uri] = version

        LSP_SERVER.protocol.notify(
            "pylint/lintingStarted",
            {"uri": notebook_uri},
        )

        result = _run_tool_on_document(
            combined_doc, use_stdin=True, extra_args=_get_extra_args(combined_doc)
        )

        # Discard stale results if a newer request has arrived.
        with _lint_versions_lock:
            if _lint_versions.get(notebook_uri, 0) != version:
                log_to_output(
                    f"Discarding stale lint results for {notebook_uri} "
                    f"(version {version} superseded by {_lint_versions[notebook_uri]})"
                )
                return

        combined_diagnostics: Sequence[lsp.Diagnostic] = []
        if result and result.stdout:
            log_to_output(f"{notebook_uri} :\r\n{result.stdout}")
            settings = copy.deepcopy(_get_settings_by_document(combined_doc))
            combined_diagnostics, _ = _parse_output(
                result.stdout, severity=settings["severity"]
            )

        per_cell = notebook.remap_diagnostics_to_cells(combined_diagnostics, cell_map)

        # Publish per-cell diagnostics; cells with no issues get an empty list
        # so that stale diagnostics from a previous run are cleared.
        for cell_uri, diags in per_cell.items():
            LSP_SERVER.text_document_publish_diagnostics(
                lsp.PublishDiagnosticsParams(uri=cell_uri, diagnostics=diags)
            )

        # Clear diagnostics for empty code cells that were skipped by
        # build_notebook_source so stale diagnostics don't persist.
        for cell in nb.cells:
            if (
                cell.kind == lsp.NotebookCellKind.Code
                and cell.document
                and cell.document not in per_cell
            ):
                LSP_SERVER.text_document_publish_diagnostics(
                    lsp.PublishDiagnosticsParams(uri=cell.document, diagnostics=[])
                )
    except Exception:  # pylint: disable=broad-except
        log_error(f"Notebook linting failed with error:\r\n{traceback.format_exc()}")
        LSP_SERVER.protocol.notify(
            "pylint/lintingFailed",
            {"uri": notebook_uri},
        )


def _clear_notebook_cell_diagnostics(cell_uri: str) -> None:
    """Clear diagnostics for a single notebook cell."""
    LSP_SERVER.text_document_publish_diagnostics(
        lsp.PublishDiagnosticsParams(uri=cell_uri, diagnostics=[])
    )


def _linting_helper(document: TextDocument) -> list[lsp.Diagnostic]:
    try:
        # Skip notebook cells — they are linted via _linting_helper_notebook
        # which concatenates all cells before passing to pylint.
        if str(document.uri).startswith("vscode-notebook-cell"):
            return []

        # Bump the version for this URI so any concurrent or queued lint for
        # the same document can detect that it has been superseded.
        with _lint_versions_lock:
            version = _lint_versions.get(document.uri, 0) + 1
            _lint_versions[document.uri] = version

        # Notify the client that linting has started for this document.
        LSP_SERVER.protocol.notify(
            "pylint/lintingStarted",
            {
                "uri": document.uri,
            },
        )
        result = _run_tool_on_document(
            document, use_stdin=True, extra_args=_get_extra_args(document)
        )

        # If a newer lint request arrived while we were running, discard
        # these stale results — the newer request will publish its own.
        with _lint_versions_lock:
            if _lint_versions.get(document.uri, 0) != version:
                log_to_output(
                    f"Discarding stale lint results for {document.uri} "
                    f"(version {version} superseded by {_lint_versions[document.uri]})"
                )
                return []

        if result and result.stdout:
            log_to_output(f"{document.uri} :\r\n{result.stdout}")

            # deep copy here to prevent accidentally updating global settings.
            settings = copy.deepcopy(_get_settings_by_document(document))
            diagnostics, score = _parse_output(
                result.stdout, severity=settings["severity"]
            )
            LSP_SERVER.protocol.notify(
                "pylint/score",
                {
                    "uri": document.uri,
                    "score": score if score is not None else 0.0,
                },
            )
            return list(diagnostics)
    except Exception:  # pylint: disable=broad-except
        log_error(f"Linting failed with error:\r\n{traceback.format_exc()}")
        LSP_SERVER.protocol.notify(
            "pylint/lintingFailed",
            {"uri": document.uri},
        )
    return []


def _get_severity(
    symbol: str, code: str, code_type: str, severity: Dict[str, str]
) -> lsp.DiagnosticSeverity:
    """Converts severity provided by linter to LSP specific value."""
    value = (
        severity.get(symbol, None)
        or severity.get(code, None)
        or severity.get(code_type, "Error")
    )
    try:
        return lsp.DiagnosticSeverity[value]
    except KeyError:
        pass

    return lsp.DiagnosticSeverity.Error


def _build_message_doc_url(code: str) -> str:
    """Build the URL to the documentation for this diagnostic message."""
    msg_id, message = code.split(":")
    category = utils.get_message_category(msg_id)
    uri = f"{category}/{message}.html" if category else DOCUMENTATION_HOME
    return f"{DOCUMENTATION_HOME}/{uri}"


def _parse_output(
    content: str,
    severity: Dict[str, str],
) -> tuple[Sequence[lsp.Diagnostic], float | None]:
    """Parses linter messages and return LSP diagnostic object for each message."""
    diagnostics = []
    line_offset = 1

    json_content = json.loads(content)
    messages: List[Dict[str, Any]] = json_content.get("messages", [])
    score: float | None = json_content.get("statistics", {}).get("score", None)
    for data in messages:
        start = lsp.Position(
            line=int(data.get("line")) - line_offset,
            character=int(data.get("column")),
        )

        if data.get("endLine") is not None:
            end = lsp.Position(
                line=int(data.get("endLine")) - line_offset,
                character=int(data.get("endColumn", 0)),
            )
        else:
            # If there is no endLine we can use `start` for end position.
            # According to LSP range will include the character at `start`
            # but will exclude character at `end`. The LSP client in this
            # case can decide the actual range based on th token this
            # points to.
            end = start

        msg_id = data.get("messageId")
        code = f"{msg_id}:{data.get('symbol')}"
        documentation_url = _build_message_doc_url(code)

        diagnostic = lsp.Diagnostic(
            range=lsp.Range(start=start, end=end),
            message=data.get("message"),
            severity=_get_severity(
                data.get("symbol"), msg_id, data.get("type"), severity
            ),
            code=f"{msg_id}:{data.get('symbol')}",
            code_description=lsp.CodeDescription(href=documentation_url),
            source=TOOL_DISPLAY,
        )

        diagnostics.append(diagnostic)

    return diagnostics, score


# **********************************************************
# Linting features end here
# **********************************************************


# **********************************************************
# Code Action features start here
# **********************************************************
class QuickFixSolutions:
    """Manages quick fixes registered using the quick fix decorator."""

    def __init__(self):
        self._solutions: Dict[
            str,
            Callable[[TextDocument, List[lsp.Diagnostic]], List[lsp.CodeAction]],
        ] = {}

    def quick_fix(self, codes: Union[str, List[str]]):
        """Decorator used for registering quick fixes."""

        def decorator(
            func: Callable[[TextDocument, List[lsp.Diagnostic]], List[lsp.CodeAction]],
        ):
            if isinstance(codes, str):
                if codes in self._solutions:
                    raise QuickFixRegistrationError(codes)
                self._solutions[codes] = func
            else:
                for code in codes:
                    if code in self._solutions:
                        raise QuickFixRegistrationError(code)
                    self._solutions[code] = func

        return decorator

    def solutions(
        self, code: str
    ) -> Optional[Callable[[TextDocument, List[lsp.Diagnostic]], List[lsp.CodeAction]]]:
        """Given a pylint error code returns a function, if available, that provides
        quick fix code actions."""
        return self._solutions.get(code, None)


QUICK_FIXES = QuickFixSolutions()


@LSP_SERVER.feature(
    lsp.TEXT_DOCUMENT_CODE_ACTION,
    lsp.CodeActionOptions(
        code_action_kinds=[lsp.CodeActionKind.QuickFix], resolve_provider=True
    ),
)
def code_action(params: lsp.CodeActionParams) -> List[lsp.CodeAction]:
    """LSP handler for textDocument/codeAction request."""

    document = LSP_SERVER.workspace.get_text_document(params.text_document.uri)
    settings = copy.deepcopy(_get_settings_by_document(document))
    code_actions = []
    if not settings["enabled"]:
        return code_actions

    diagnostics = (d for d in params.context.diagnostics if d.source == TOOL_DISPLAY)

    for diagnostic in diagnostics:
        func = QUICK_FIXES.solutions(diagnostic.code)
        if func:
            code_actions.extend(func(document, [diagnostic]))
    return code_actions


@QUICK_FIXES.quick_fix(
    codes=[
        "C0301:line-too-long",
        "C0303:trailing-whitespace",
        "C0304:missing-final-newline",
        "C0305:trailing-newlines",
        "C0321:multiple-statements",
    ]
)
def fix_format(
    _document: TextDocument, diagnostics: List[lsp.Diagnostic]
) -> List[lsp.CodeAction]:
    """Provides quick fixes which involve formatting document."""
    return [
        _command_quick_fix(
            diagnostics=diagnostics,
            title=f"{TOOL_DISPLAY}: Run document formatting",
            command="editor.action.formatDocument",
        )
    ]


@QUICK_FIXES.quick_fix(
    codes=[
        "C0410:multiple-imports",
        "C0411:wrong-import-order",
        "C0412:ungrouped-imports",
    ]
)
def organize_imports(
    _document: TextDocument, diagnostics: List[lsp.Diagnostic]
) -> List[lsp.CodeAction]:
    """Provides quick fixes which involve organizing imports."""
    return [
        _command_quick_fix(
            diagnostics=diagnostics,
            title=f"{TOOL_DISPLAY}: Run organize imports",
            command="editor.action.organizeImports",
        )
    ]


REPLACEMENTS: Dict[str, re.Pattern] = {
    "C0117:unnecessary-negation": [
        {
            "pattern": re.compile(r"\snot\s+not"),
            "repl": r"",
        }
    ],
    "C0121:singleton-comparison": [
        {
            "pattern": re.compile(
                r"(\w+)\s+(?:==\s+True|!=\s+False)|(?:True\s+==|False\s+!=)\s+(\w+)"
            ),
            "repl": r"\1\2",
        },
        {
            "pattern": re.compile(
                r"(\w+)\s+(?:!=\s+True|==\s+False)|(?:True\s+!=|False\s+==)\s+(\w+)"
            ),
            "repl": r"not \1\2",
        },
    ],
    "C0123:unidiomatic-typecheck": [
        {
            "pattern": re.compile(r"type\((\w+)\)\s+is\s+(\w+)"),
            "repl": r"isinstance(\1, \2)",
        }
    ],
    "R0205:useless-object-inheritance": [
        {
            "pattern": re.compile(r"class (\w+)\(object\):"),
            "repl": r"class \1:",
        }
    ],
    "R1721:unnecessary-comprehension": [
        {
            "pattern": re.compile(r"\{([\w\s,]+) for [\w\s,]+ in ([\w\s,]+)\}"),
            "repl": r"set(\2)",
        }
    ],
    "E1141:dict-iter-missing-items": [
        {
            "pattern": re.compile(r"for\s+(\w+),\s+(\w+)\s+in\s+(\w+)\s*:"),
            "repl": r"for \1, \2 in \3.items():",
        }
    ],
}


def _get_replacement_edit(diagnostic: lsp.Diagnostic, lines: List[str]) -> lsp.TextEdit:
    new_line = lines[diagnostic.range.start.line]
    for replacement in REPLACEMENTS[diagnostic.code]:
        new_line = re.sub(
            replacement["pattern"],
            replacement["repl"],
            new_line,
        )
    return lsp.TextEdit(
        lsp.Range(
            start=lsp.Position(line=diagnostic.range.start.line, character=0),
            end=lsp.Position(line=diagnostic.range.start.line + 1, character=0),
        ),
        new_line,
    )


@QUICK_FIXES.quick_fix(
    codes=list(REPLACEMENTS.keys()),
)
def fix_with_replacement(
    document: TextDocument, diagnostics: List[lsp.Diagnostic]
) -> List[lsp.CodeAction]:
    """Provides quick fixes which basic string replacements."""
    return [
        lsp.CodeAction(
            title=f"{TOOL_DISPLAY}: Run autofix code action",
            kind=lsp.CodeActionKind.QuickFix,
            diagnostics=diagnostics,
            edit=None,
            data=document.uri,
        )
    ]


@LSP_SERVER.feature(lsp.CODE_ACTION_RESOLVE)
def code_action_resolve(params: lsp.CodeAction) -> lsp.CodeAction:
    """LSP handler for codeAction/resolve request."""
    if params.data:
        document = LSP_SERVER.workspace.get_text_document(params.data)
        params.edit = _create_workspace_edits(
            document,
            [
                _get_replacement_edit(diagnostic, document.lines)
                for diagnostic in params.diagnostics
                if diagnostic.source == TOOL_DISPLAY and diagnostic.code in REPLACEMENTS
            ],
        )
    return params


def _command_quick_fix(
    diagnostics: List[lsp.Diagnostic],
    title: str,
    command: str,
    args: Optional[List[Any]] = None,
) -> lsp.CodeAction:
    return lsp.CodeAction(
        title=title,
        kind=lsp.CodeActionKind.QuickFix,
        diagnostics=diagnostics,
        command=lsp.Command(title=title, command=command, arguments=args),
    )


def _create_workspace_edits(
    document: TextDocument, results: Optional[List[lsp.TextEdit]]
):
    return lsp.WorkspaceEdit(
        document_changes=[
            lsp.TextDocumentEdit(
                text_document=lsp.OptionalVersionedTextDocumentIdentifier(
                    uri=document.uri,
                    version=document.version if document.version else 0,
                ),
                edits=results,
            )
        ],
    )


# **********************************************************
# Code Action features end here
# **********************************************************


# **********************************************************
# Required Language Server Initialization and Exit handlers.
# **********************************************************
@LSP_SERVER.feature(lsp.INITIALIZE)
def initialize(params: lsp.InitializeParams) -> None:
    """LSP handler for initialize request."""
    tool_server.apply_settings(params)
    settings = (params.initialization_options or {}).get("settings")

    import_strategy = os.getenv("LS_IMPORT_STRATEGY", "useBundled")
    update_sys_path(os.getcwd(), import_strategy)

    # Add extra paths to sys.path
    setting = tool_server.get_settings_by_path(pathlib.Path(os.getcwd()))
    for extra in setting.get("extraPaths", []):
        update_sys_path(extra, import_strategy)

    tool_server.log_startup_info(settings)
    _log_version_info()


@LSP_SERVER.feature(lsp.EXIT)
def on_exit(_params: Optional[Any] = None) -> None:
    """Handle clean up on exit."""
    tool_server.handle_exit()


@LSP_SERVER.feature(lsp.SHUTDOWN)
def on_shutdown(_params: Optional[Any] = None) -> None:
    """Handle clean up on shutdown."""
    tool_server.handle_shutdown()


def _log_version_info() -> None:
    for value in WORKSPACE_SETTINGS.values():
        try:
            from packaging.version import parse as parse_version

            settings = copy.deepcopy(value)
            result = _run_tool(["--version"], settings)
            code_workspace = settings["workspaceFS"]
            log_to_output(
                f"Version info for linter running for {code_workspace}:\r\n{result.stdout}"
            )

            # This is text we get from running `pylint --version`
            # pylint 2.12.2 <--- This is the version we want.
            # astroid 2.9.3
            first_line = result.stdout.splitlines(keepends=False)[0]
            actual_version = first_line.split(" ")[1]

            version = parse_version(actual_version)
            min_version = parse_version(MIN_VERSION)
            VERSION_TABLE[code_workspace] = (
                version.major,
                version.minor,
                version.micro,
            )

            if version < min_version:
                log_error(
                    f"Version of linter running for {code_workspace} is NOT supported:\r\n"
                    f"SUPPORTED {TOOL_MODULE}>={min_version}\r\n"
                    f"FOUND {TOOL_MODULE}=={actual_version}\r\n"
                )
            else:
                log_to_output(
                    f"SUPPORTED {TOOL_MODULE}>={min_version}\r\n"
                    f"FOUND {TOOL_MODULE}=={actual_version}\r\n"
                )
        except:  # pylint: disable=bare-except
            log_warning(
                f"Error while detecting pylint version:\r\n{traceback.format_exc()}"
            )


# *****************************************************
# Internal functional and settings management APIs.
# *****************************************************
def _get_global_defaults():
    defaults = tool_server.get_global_defaults()
    # ignorePatterns is always hardcoded to [] — the client resolves it
    # before sending per-workspace settings, so the global default must
    # never reflect user-supplied values.
    defaults["ignorePatterns"] = []
    return defaults


def _update_workspace_settings(settings):
    tool_server.update_workspace_settings(settings)


def _get_settings_by_path(file_path: pathlib.Path):
    return tool_server.get_settings_by_path(file_path)


def _get_document_key(document: TextDocument):
    return tool_server.get_document_key(document)


def _get_settings_by_document(document: TextDocument | None):
    return tool_server.get_settings_by_document(document)


# *****************************************************
# Internal execution APIs.
# *****************************************************
def get_cwd(settings: Dict[str, Any], document: Optional[TextDocument]) -> str:
    """Returns the working directory for running the tool."""
    return tool_server.get_cwd(settings, document)


# pylint: disable=too-many-branches,too-many-statements
def _run_tool_on_document(
    document: TextDocument,
    use_stdin: bool = False,
    extra_args: Optional[Sequence[str]] = None,
) -> RunResult | None:
    """Runs tool on the given document.

    if use_stdin is true then contents of the document is passed to the
    tool via stdin.
    """
    if extra_args is None:
        extra_args = []

    # deep copy here to prevent accidentally updating global settings.
    settings = copy.deepcopy(_get_settings_by_document(document))

    if not settings["enabled"]:
        log_warning(f"Skipping file [Linting Disabled]: {document.path}")
        log_warning("See `pylint.enabled` in settings.json to enabling linting.")
        return None

    if utils.is_stdlib_file(document.path):
        log_warning(
            f"Skipping standard library file (stdlib excluded): {document.path}"
        )

        return None

    if is_match(settings["ignorePatterns"], document.path):
        log_warning(
            f"Skipping file due to `pylint.ignorePatterns` match: {document.path}"
        )
        return None

    code_workspace = settings["workspaceFS"]
    cwd = tool_server.get_cwd(settings, document)

    if settings["path"]:
        mode = "path"
        argv = list(settings["path"])
    elif settings["interpreter"] and not is_current_interpreter(
        settings["interpreter"][0]
    ):
        mode = "rpc"
        argv = [TOOL_MODULE]
    else:
        mode = "module"
        argv = [TOOL_MODULE]

    argv += TOOL_ARGS + settings["args"] + list(extra_args)

    # pygls normalizes the path to lowercase on windows, but we need to resolve the
    # correct capitalization to avoid https://github.com/pylint-dev/pylint/issues/10137
    resolved_path = str(pathlib.Path(document.path).resolve())

    if use_stdin:
        argv += ["--from-stdin", resolved_path]
    else:
        argv += [resolved_path]

    env = None
    if mode in ("path", "rpc"):
        # for path and rpc modes we need to set PYTHONPATH, for module or API mode
        # we would have already set the extra paths in the initialize handler.
        env = _get_updated_env(settings)

    source = document.source
    if mode == "path" and use_stdin:
        source = source.replace("\r\n", "\n")

    result = tool_server.execute_tool(
        argv=argv,
        mode=mode,
        settings=settings,
        use_stdin=use_stdin,
        cwd=cwd,
        workspace=code_workspace,
        source=source,
        env=env,
    )

    if result.stderr and any(
        kw in result.stderr.lower() for kw in _STDERR_ERROR_KEYWORDS
    ):
        tool_server.log_warning(result.stderr)

    return result


def _run_tool(extra_args: Sequence[str], settings: Dict[str, Any]) -> RunResult:
    """Runs tool."""
    code_workspace = settings["workspaceFS"]
    cwd = tool_server.get_cwd(settings, None)

    if len(settings["path"]) > 0:
        mode = "path"
        argv = list(settings["path"])
    elif len(settings["interpreter"]) > 0 and not is_current_interpreter(
        settings["interpreter"][0]
    ):
        mode = "rpc"
        argv = [TOOL_MODULE]
    else:
        mode = "module"
        argv = [TOOL_MODULE]

    argv += list(extra_args)

    env = None
    if mode in ("path", "rpc"):
        # for path and rpc modes we need to set PYTHONPATH, for module or API mode
        # we would have already set the extra paths in the initialize handler.
        env = _get_updated_env(settings)

    result = tool_server.execute_tool(
        argv=argv,
        mode=mode,
        settings=settings,
        use_stdin=True,
        cwd=cwd,
        workspace=code_workspace,
        env=env,
    )

    if result.stderr and any(
        kw in result.stderr.lower() for kw in _STDERR_ERROR_KEYWORDS
    ):
        tool_server.log_warning(result.stderr)

    log_to_output(f"\r\n{result.stdout}\r\n")
    return result


def _get_updated_env(settings: Dict[str, Any]) -> str:
    """Returns the updated environment variables."""
    extra_paths = settings.get("extraPaths", [])
    paths = os.environ.get("PYTHONPATH", "").split(os.pathsep) + extra_paths
    python_paths = os.pathsep.join([p for p in paths if len(p) > 0])

    env = {
        "LS_IMPORT_STRATEGY": settings["importStrategy"],
        "PYTHONUTF8": "1",
    }
    if python_paths:
        env["PYTHONPATH"] = python_paths
    return env


def log_to_output(
    message: str, msg_type: lsp.MessageType = lsp.MessageType.Log
) -> None:
    """Logs messages to Output > Pylint channel only."""
    tool_server.log_to_output(message, msg_type)


def log_error(message: str) -> None:
    """Logs messages with notification on error."""
    tool_server.log_error(message)


def log_warning(message: str) -> None:
    """Logs messages with notification on warning."""
    tool_server.log_warning(message)


def log_always(message: str) -> None:
    """Logs messages with notification."""
    tool_server.log_always(message)


# *****************************************************
# Start the server.
# *****************************************************
if __name__ == "__main__":
    LSP_SERVER.start_io()
