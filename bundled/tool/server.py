# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Implementation of tool support over LSP."""
from __future__ import annotations

import copy
import json
import os
import pathlib
import sys
import traceback
from typing import Any, Dict, List, Sequence


# **********************************************************
# Update sys.path before importing any bundled libraries.
# **********************************************************
def update_sys_path(path_to_add: str, append: bool = True) -> None:
    """Add given path to `sys.path`."""
    if path_to_add not in sys.path and os.path.isdir(path_to_add):
        if append:
            sys.path.append(path_to_add)
        else:
            sys.path.insert(0, path_to_add)


# Ensure that we can import LSP libraries, and other bundled libraries.
update_sys_path(os.fspath(pathlib.Path(__file__).parent.parent / "libs"))

# **********************************************************
# Imports needed for the language server goes below this.
# **********************************************************
# pylint: disable=wrong-import-position,import-error
import jsonrpc
import utils
from packaging.version import parse as parse_version
from pygls import lsp, protocol, server, uris, workspace

WORKSPACE_SETTINGS = {}
RUNNER = pathlib.Path(__file__).parent / "runner.py"

MAX_WORKERS = 5
LSP_SERVER = server.LanguageServer(max_workers=MAX_WORKERS)


# **********************************************************
# Tool specific code goes below this.
# **********************************************************
TOOL_MODULE = "pylint"
TOOL_DISPLAY = "Pylint"

# Default arguments always passed to pylint.
TOOL_ARGS = ["--reports=n", "--output-format=json"]

# Minimum version of pylint supported.
MIN_VERSION = "2.12.2"

# **********************************************************
# Linting features start here
# **********************************************************


@LSP_SERVER.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
def did_open(params: lsp.DidOpenTextDocumentParams) -> None:
    """LSP handler for textDocument/didOpen request."""
    document = LSP_SERVER.workspace.get_document(params.text_document.uri)
    diagnostics: list[lsp.Diagnostic] = _linting_helper(document)
    LSP_SERVER.publish_diagnostics(document.uri, diagnostics)


@LSP_SERVER.feature(lsp.TEXT_DOCUMENT_DID_SAVE)
def did_save(params: lsp.DidSaveTextDocumentParams) -> None:
    """LSP handler for textDocument/didSave request."""
    document = LSP_SERVER.workspace.get_document(params.text_document.uri)
    diagnostics: list[lsp.Diagnostic] = _linting_helper(document)
    LSP_SERVER.publish_diagnostics(document.uri, diagnostics)


@LSP_SERVER.feature(lsp.TEXT_DOCUMENT_DID_CLOSE)
def did_close(params: lsp.DidCloseTextDocumentParams) -> None:
    """LSP handler for textDocument/didClose request."""
    document = LSP_SERVER.workspace.get_document(params.text_document.uri)
    # Publishing empty diagnostics to clear the entries for this file.
    LSP_SERVER.publish_diagnostics(document.uri, [])


def _linting_helper(document: workspace.Document) -> list[lsp.Diagnostic]:
    try:
        result = _run_tool_on_document(document, use_stdin=True)
        if result and result.stdout:
            # deep copy here to prevent accidentally updating global settings.
            settings = copy.deepcopy(_get_settings_by_document(document))
            return _parse_output(result.stdout, severity=settings["severity"])
    except Exception:  # pylint: disable=broad-except
        LSP_SERVER.show_message_log(
            f"Linting failed with error:\r\n{traceback.format_exc()}",
            lsp.MessageType.Error,
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


def _parse_output(
    content: str,
    severity: Dict[str, str],
) -> Sequence[lsp.Diagnostic]:
    """Parses linter messages and return LSP diagnostic object for each message."""
    diagnostics = []
    line_offset = 1

    messages: List[Dict[str, Any]] = json.loads(content)
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

        diagnostic = lsp.Diagnostic(
            range=lsp.Range(start=start, end=end),
            message=data.get("message"),
            severity=_get_severity(
                data.get("symbol"), data.get("message-id"), data.get("type"), severity
            ),
            code=f"{data.get('message-id')}:{data.get('symbol')}",
            source=TOOL_DISPLAY,
        )

        diagnostics.append(diagnostic)

    return diagnostics


# **********************************************************
# Linting features end here
# **********************************************************

# **********************************************************
# Required Language Server Initialization and Exit handlers.
# **********************************************************
@LSP_SERVER.feature(lsp.INITIALIZE)
def initialize(params: lsp.InitializeParams) -> None:
    """LSP handler for initialize request."""
    LSP_SERVER.show_message_log(f"CWD Server: {os.getcwd()}")

    paths = "\r\n   ".join(sys.path)
    LSP_SERVER.show_message_log(f"sys.path used to run Server:\r\n   {paths}")

    settings = params.initialization_options["settings"]
    _update_workspace_settings(settings)
    LSP_SERVER.show_message_log(
        f"Settings used to run Server:\r\n{json.dumps(settings, indent=4, ensure_ascii=False)}\r\n"
    )

    if isinstance(LSP_SERVER.lsp, protocol.LanguageServerProtocol):
        if any(setting["logLevel"] == "debug" for setting in settings):
            LSP_SERVER.lsp.trace = lsp.Trace.Verbose
        elif any(
            setting["logLevel"] in ["error", "warn", "info"] for setting in settings
        ):
            LSP_SERVER.lsp.trace = lsp.Trace.Messages
        else:
            LSP_SERVER.lsp.trace = lsp.Trace.Off
    _log_version_info()


@LSP_SERVER.feature(lsp.EXIT)
def on_exit():
    """Handle clean up on exit."""
    jsonrpc.shutdown_json_rpc()


def _log_version_info() -> None:
    for value in WORKSPACE_SETTINGS.values():
        try:
            settings = copy.deepcopy(value)
            result = _run_tool(["--version"], settings)
            code_workspace = settings["workspaceFS"]
            LSP_SERVER.show_message_log(
                f"Version info for linter running for {code_workspace}:\r\n{result.stdout}"
            )

            # This is text we get from running `pylint --version`
            # pylint 2.12.2 <--- This is the version we want.
            # astroid 2.9.3
            first_line = result.stdout.splitlines(keepends=False)[0]
            actual_version = first_line.split(" ")[1]

            version = parse_version(actual_version)
            min_version = parse_version(MIN_VERSION)

            if version < min_version:
                LSP_SERVER.show_message_log(
                    f"Version of linter running for {code_workspace} is NOT supported:\r\n"
                    f"SUPPORTED {TOOL_MODULE}>={min_version}\r\n"
                    f"FOUND {TOOL_MODULE}=={actual_version}\r\n"
                )
            else:
                LSP_SERVER.show_message_log(
                    f"SUPPORTED {TOOL_MODULE}>={min_version}\r\n"
                    f"FOUND {TOOL_MODULE}=={actual_version}\r\n"
                )
        except:  # pylint: disable=bare-except
            pass


# *****************************************************
# Internal functional and settings management APIs.
# *****************************************************
def _update_workspace_settings(settings):
    for setting in settings:
        key = uris.to_fs_path(setting["workspace"])
        WORKSPACE_SETTINGS[key] = {
            **setting,
            "workspaceFS": key,
        }


def _get_settings_by_document(document: workspace.Document | None):
    if len(WORKSPACE_SETTINGS) == 1 or document is None or document.path is None:
        return list(WORKSPACE_SETTINGS.values())[0]

    document_workspace = pathlib.Path(document.path)
    workspaces = {s["workspaceFS"] for s in WORKSPACE_SETTINGS.values()}

    # COMMENT: about non workspace files
    while document_workspace != document_workspace.parent:
        if str(document_workspace) in workspaces:
            break
        document_workspace = document_workspace.parent

    return WORKSPACE_SETTINGS[str(document_workspace)]


# *****************************************************
# Internal execution APIs.
# *****************************************************
def _run_tool_on_document(
    document: workspace.Document,
    use_stdin: bool = False,
) -> utils.RunResult | None:
    """Runs tool on the given document.

    if use_stdin is true then contents of the document is passed to the
    tool via stdin.
    """
    if str(document.uri).startswith("vscode-notebook-cell"):
        return None

    if utils.is_stdlib_file(document.path):
        return None

    # deep copy here to prevent accidentally updating global settings.
    settings = copy.deepcopy(_get_settings_by_document(document))

    code_workspace = settings["workspaceFS"]
    cwd = settings["workspaceFS"]

    use_path = False
    use_rpc = False
    if settings["path"]:
        # 'path' setting takes priority over everything.
        use_path = True
        argv = settings["path"]
    elif settings["interpreter"] and not utils.is_current_interpreter(
        settings["interpreter"][0]
    ):
        # If there is a different interpreter set use JSON-RPC to the subprocess
        # running under that interpreter.
        argv = [TOOL_MODULE]
        use_rpc = True
    else:
        # if the interpreter is same as the interpreter running this
        # process then run as module.
        argv = [TOOL_MODULE]

    argv += TOOL_ARGS + settings["args"]

    if use_stdin:
        argv += ["--from-stdin", document.path]
    else:
        argv += [document.path]

    if use_path:
        # This mode is used when running executables.
        LSP_SERVER.show_message_log(" ".join(argv))
        LSP_SERVER.show_message_log(f"CWD Server: {cwd}")
        result = utils.run_path(
            argv=argv,
            use_stdin=use_stdin,
            cwd=cwd,
            source=document.source.replace("\r\n", "\n"),
        )
    elif use_rpc:
        # This mode is used if the interpreter running this server is different from
        # the interpreter used for running this server.
        LSP_SERVER.show_message_log(" ".join(settings["interpreter"] + ["-m"] + argv))
        LSP_SERVER.show_message_log(f"CWD Linter: {cwd}")
        result = jsonrpc.run_over_json_rpc(
            workspace=code_workspace,
            interpreter=settings["interpreter"],
            module=TOOL_MODULE,
            argv=argv,
            use_stdin=use_stdin,
            cwd=cwd,
            source=document.source,
        )
    else:
        # In this mode the tool is run as a module in the same process as the language server.
        LSP_SERVER.show_message_log(" ".join([sys.executable, "-m"] + argv))
        LSP_SERVER.show_message_log(f"CWD Linter: {cwd}")
        # This is needed to preserve sys.path, in cases where the tool modifies
        # sys.path and that might not work for this scenario next time around.
        with utils.substitute_attr(sys, "path", sys.path[:]):
            result = utils.run_module(
                module=TOOL_MODULE,
                argv=argv,
                use_stdin=use_stdin,
                cwd=cwd,
                source=document.source,
            )

    if result.stderr:
        LSP_SERVER.show_message_log(result.stderr, msg_type=lsp.MessageType.Error)
    LSP_SERVER.show_message_log(f"{document.uri} :\r\n{result.stdout}")
    return result


def _run_tool(extra_args: Sequence[str], settings: Dict[str, Any]) -> utils.RunResult:
    """Runs tool."""
    code_workspace = settings["workspaceFS"]
    cwd = settings["workspaceFS"]

    use_path = False
    use_rpc = False
    if len(settings["path"]) > 0:
        # 'path' setting takes priority over everything.
        use_path = True
        argv = settings["path"]
    elif len(settings["interpreter"]) > 0 and not utils.is_current_interpreter(
        settings["interpreter"][0]
    ):
        # If there is a different interpreter set use JSON-RPC to the subprocess
        # running under that interpreter.
        argv = [TOOL_MODULE]
        use_rpc = True
    else:
        # if the interpreter is same as the interpreter running this
        # process then run as module.
        argv = [TOOL_MODULE]

    argv += extra_args

    if use_path:
        # This mode is used when running executables.
        LSP_SERVER.show_message_log(" ".join(argv))
        LSP_SERVER.show_message_log(f"CWD Server: {cwd}")
        result = utils.run_path(argv=argv, use_stdin=True, cwd=cwd)
    elif use_rpc:
        # This mode is used if the interpreter running this server is different from
        # the interpreter used for running this server.
        LSP_SERVER.show_message_log(" ".join(settings["interpreter"] + ["-m"] + argv))
        LSP_SERVER.show_message_log(f"CWD Linter: {cwd}")
        result = jsonrpc.run_over_json_rpc(
            workspace=code_workspace,
            interpreter=settings["interpreter"],
            module=TOOL_MODULE,
            argv=argv,
            use_stdin=True,
            cwd=cwd,
        )
    else:
        # In this mode the tool is run as a module in the same process as the language server.
        LSP_SERVER.show_message_log(" ".join([sys.executable, "-m"] + argv))
        LSP_SERVER.show_message_log(f"CWD Linter: {cwd}")
        # This is needed to preserve sys.path, in cases where the tool modifies
        # sys.path and that might not work for this scenario next time around.
        with utils.substitute_attr(sys, "path", sys.path[:]):
            result = utils.run_module(
                module=TOOL_MODULE, argv=argv, use_stdin=True, cwd=cwd
            )

    if result.stderr:
        LSP_SERVER.show_message_log(result.stderr, msg_type=lsp.MessageType.Error)
    LSP_SERVER.show_message_log(f"\r\n{result.stdout}\r\n")
    return result


if __name__ == "__main__":
    LSP_SERVER.start_io()
