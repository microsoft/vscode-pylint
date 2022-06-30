# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Implementation of linting support over LSP.
"""

import copy
import json
import os
import pathlib
import sys
import traceback
from typing import Any, Dict, List, Sequence, Union

# Ensure that we can import LSP libraries, and other bundled linter libraries
sys.path.append(str(pathlib.Path(__file__).parent.parent / "libs"))

# pylint: disable=wrong-import-position,import-error
import jsonrpc
import utils
from packaging.version import parse as parse_version
from pygls import lsp, protocol, server, uris, workspace
from pygls.lsp import types

LINTER = {
    "name": "Pylint",
    "module": "pylint",
    "args": ["--reports=n", "--output-format=json"],
}
WORKSPACE_SETTINGS = {}
RUNNER = pathlib.Path(__file__).parent / "runner.py"

MAX_WORKERS = 5
LSP_SERVER = server.LanguageServer(max_workers=MAX_WORKERS)


def _get_severity(
    symbol: str, code: str, code_type: str, severity: Dict[str, str]
) -> types.DiagnosticSeverity:
    """Converts severity provided by linter to LSP specific value."""
    value = (
        severity.get(symbol, None)
        or severity.get(code, None)
        or severity.get(code_type, "Error")
    )
    try:
        return types.DiagnosticSeverity[value]
    except KeyError:
        pass

    return types.DiagnosticSeverity.Error


def _parse_output(
    content: str,
    severity: Dict[str, str],
) -> Sequence[types.Diagnostic]:
    """Parses linter messages and return LSP diagnostic object for each message."""
    diagnostics = []
    line_offset = 1

    messages: List[Dict[str, Any]] = json.loads(content)
    for data in messages:
        start = types.Position(
            line=int(data.get("line")) - line_offset,
            character=int(data.get("column")),
        )

        if data.get("endLine") is not None:
            end = types.Position(
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

        diagnostic = types.Diagnostic(
            range=types.Range(start=start, end=end),
            message=data.get("message"),
            severity=_get_severity(
                data.get("symbol"), data.get("message-id"), data.get("type"), severity
            ),
            code=f"{data.get('message-id')}:{data.get('symbol')}",
            source=LINTER["name"],
        )

        diagnostics.append(diagnostic)

    return diagnostics


def _update_workspace_settings(settings):
    for setting in settings:
        key = uris.to_fs_path(setting["workspace"])
        WORKSPACE_SETTINGS[key] = {
            **setting,
            "workspaceFS": key,
        }


def _get_settings_by_document(document: workspace.Document):
    if len(WORKSPACE_SETTINGS) == 1 or document.path is None:
        return list(WORKSPACE_SETTINGS.values())[0]

    document_workspace = pathlib.Path(document.path)
    workspaces = [s["workspaceFS"] for s in WORKSPACE_SETTINGS.values()]

    while document_workspace != document_workspace.parent:
        if str(document_workspace) in workspaces:
            break
        document_workspace = document_workspace.parent

    return WORKSPACE_SETTINGS[str(document_workspace)]


def _log_version_info() -> None:
    for value in WORKSPACE_SETTINGS.values():
        try:
            settings = copy.deepcopy(value)
            code_workspace = settings["workspaceFS"]
            module = LINTER["module"]
            if len(settings["path"]) > 0:
                result = utils.run_path(
                    [*settings["path"], "--version"], False, code_workspace
                )
            elif len(settings["interpreter"]) > 0 and not utils.is_current_interpreter(
                settings["interpreter"][0]
            ):
                result = jsonrpc.run_over_json_rpc(
                    workspace=code_workspace,
                    interpreter=settings["interpreter"],
                    module=module,
                    argv=[module, "--version"],
                    use_stdin=False,
                    cwd=code_workspace,
                )
            else:
                result = utils.run_module(
                    module, [module, "--version"], False, code_workspace
                )
            LSP_SERVER.show_message_log(
                f"Version info for linter running for {code_workspace}:\r\n{result.stdout}"
            )

            # minimum version of pylint supported.
            min_version = "2.12.2"

            # This is text we get from running `pylint --version`
            # pylint 2.12.2 <--- This is the version we want.
            # astroid 2.9.3
            first_line = result.stdout.splitlines(keepends=False)[0]
            actual_version = first_line.split(" ")[1]

            version = parse_version(actual_version)
            min_version = parse_version(min_version)

            if version < min_version:
                LSP_SERVER.show_message_log(
                    f"Version of linter running for {code_workspace} is NOT supported:\r\n"
                    f"SUPPORTED {module}>={min_version}\r\nFOUND {module}=={actual_version}\r\n"
                )
            else:
                LSP_SERVER.show_message_log(
                    f"SUPPORTED {module}>={min_version}\r\nFOUND {module}=={actual_version}\r\n"
                )
        except:  # pylint: disable=bare-except
            pass


def _lint_and_publish_diagnostics(
    params: Union[types.DidOpenTextDocumentParams, types.DidSaveTextDocumentParams]
) -> None:
    """Runs linter, processes the output, and publishes the diagnostics over LSP."""
    document = LSP_SERVER.workspace.get_document(params.text_document.uri)

    if str(document.uri).startswith("vscode-notebook-cell") or utils.is_stdlib_file(
        document.path
    ):
        # Don't lint standard library python files.
        # Publishing empty diagnostics clears the entry.
        LSP_SERVER.publish_diagnostics(document.uri, [])
        return

    settings = copy.deepcopy(_get_settings_by_document(document))

    module = LINTER["module"]
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
        argv = [LINTER["module"]]
        use_rpc = True
    else:
        # if the interpreter is same as the interpreter running this
        # process then run as module.
        argv = [LINTER["module"]]

    argv += LINTER["args"] + settings["args"]
    argv += ["--from-stdin", document.path]

    if use_path:
        # This mode is used when running pylint.exe
        LSP_SERVER.show_message_log(" ".join(argv))
        LSP_SERVER.show_message_log(f"CWD Linter: {cwd}")
        result = utils.run_path(
            argv=argv,
            use_stdin=True,
            cwd=cwd,
            source=document.source.replace("\r\n", "\n"),
        )
    elif use_rpc:
        # This mode is used if the interpreter running this server is different from
        # the interpreter used for linting.
        LSP_SERVER.show_message_log(" ".join(settings["interpreter"] + ["-m"] + argv))
        LSP_SERVER.show_message_log(f"CWD Linter: {cwd}")
        result = jsonrpc.run_over_json_rpc(
            workspace=code_workspace,
            interpreter=settings["interpreter"],
            module=module,
            argv=argv,
            use_stdin=True,
            cwd=cwd,
            source=document.source,
        )
    else:
        # In this mode pylint is run as a module in the same process as the language server.
        LSP_SERVER.show_message_log(" ".join([sys.executable, "-m"] + argv))
        LSP_SERVER.show_message_log(f"CWD Linter: {cwd}")
        # This is needed to preserve sys.path, pylint modifies
        # sys.path and that might not work for this scenario
        # next time around.
        with utils.substitute_attr(sys, "path", sys.path[:]):
            result = utils.run_module(
                module=module,
                argv=argv,
                use_stdin=True,
                cwd=cwd,
                source=document.source,
            )

    if result.stderr:
        LSP_SERVER.show_message_log(result.stderr, msg_type=lsp.MessageType.Error)
    LSP_SERVER.show_message_log(f"{document.uri} :\r\n{result.stdout}")

    try:
        diagnostics = _parse_output(result.stdout, settings["severity"])
        LSP_SERVER.publish_diagnostics(document.uri, diagnostics)
    except Exception:  # pylint: disable=broad-except
        LSP_SERVER.show_message_log(
            f"Error while parsing output:\r\n{traceback.format_exc()}"
        )


@LSP_SERVER.feature(lsp.INITIALIZE)
def initialize(params: types.InitializeParams):
    """LSP handler for initialize request."""
    LSP_SERVER.show_message_log(f"CWD Linter Server: {os.getcwd()}")

    paths = "\r\n   ".join(sys.path)
    LSP_SERVER.show_message_log(f"sys.path used to run Linter:\r\n   {paths}")

    settings = params.initialization_options["settings"]
    _update_workspace_settings(settings)
    LSP_SERVER.show_message_log(
        f"Settings used to run Linter:\r\n{json.dumps(settings, indent=4, ensure_ascii=False)}\r\n"
    )

    if isinstance(LSP_SERVER.lsp, protocol.LanguageServerProtocol):
        trace = lsp.Trace.Off
        for setting in settings:
            if setting["trace"] == "debug":
                trace = lsp.Trace.Verbose
                break
            if setting["trace"] == "off":
                continue
            trace = lsp.Trace.Messages
        LSP_SERVER.lsp.trace = trace

    _log_version_info()


@LSP_SERVER.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
def did_open(_server: server.LanguageServer, params: types.DidOpenTextDocumentParams):
    """LSP handler for textDocument/didOpen request."""
    _lint_and_publish_diagnostics(params)


@LSP_SERVER.feature(lsp.TEXT_DOCUMENT_DID_SAVE)
def did_save(_server: server.LanguageServer, params: types.DidSaveTextDocumentParams):
    """LSP handler for textDocument/didSave request."""
    _lint_and_publish_diagnostics(params)


@LSP_SERVER.feature(lsp.TEXT_DOCUMENT_DID_CLOSE)
def did_close(_server: server.LanguageServer, params: types.DidCloseTextDocumentParams):
    """LSP handler for textDocument/didClose request."""
    # Publishing empty diagnostics to clear the entries for this file.
    text_document = LSP_SERVER.workspace.get_document(params.text_document.uri)
    LSP_SERVER.publish_diagnostics(text_document.uri, [])


@LSP_SERVER.feature(lsp.EXIT)
def on_exit():
    """Handle clean up on exit."""
    jsonrpc.shutdown_json_rpc()


if __name__ == "__main__":
    LSP_SERVER.start_io()
