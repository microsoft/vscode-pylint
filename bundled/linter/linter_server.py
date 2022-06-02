# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Implementation of linting support over LSP.
"""

import json
import os
import pathlib
import sys
from typing import Dict, Sequence, Union

# Ensure that we can import LSP libraries, and other bundled linter libraries
sys.path.append(str(pathlib.Path(__file__).parent.parent / "libs"))

# pylint: disable=wrong-import-position,import-error
import utils
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
    col_offset = 0

    messages = json.loads(content)
    for data in messages:
        start = types.Position(
            line=int(data["line"]) - line_offset,
            character=int(data["column"]) - col_offset,
        )

        if "endLine" in data and data["endLine"] is not None:
            end = types.Position(
                line=int(data["endLine"]) - line_offset,
                character=int(data["endColumn"]) - col_offset,
            )
        else:
            end = start

        diagnostic = types.Diagnostic(
            range=types.Range(
                start=start,
                end=end,
            ),
            message=data["message"],
            severity=_get_severity(
                data["symbol"], data["message-id"], data["type"], severity
            ),
            code=f"{data['message-id']}:{ data['symbol']}",
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

    settings = _get_settings_by_document(document)

    module = LINTER["module"]
    cwd = settings["workspaceFS"]

    if len(settings["path"]) > 0:
        # 'path' setting takes priority over everything.
        use_path = True
        argv = settings["path"]
    elif len(settings["interpreter"]) > 0 and not utils.is_current_interpreter(
        settings["interpreter"][0]
    ):
        # If there is a different interpreter set use that interpreter.
        argv = settings["interpreter"] + [str(RUNNER), module]
        use_path = True
    else:
        # if the interpreter is same as the interpreter running this
        # process then run as module.
        argv = [LINTER["module"]]
        use_path = False

    argv += LINTER["args"] + settings["args"]
    argv += ["--from-stdin", document.path]

    LSP_SERVER.show_message_log(" ".join(argv))
    LSP_SERVER.show_message_log(f"CWD Linter: {cwd}")

    if use_path:
        result = utils.run_path(
            argv=argv,
            use_stdin=True,
            cwd=cwd,
            source=document.source.replace("\r\n", "\n"),
        )
    else:
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

    diagnostics = _parse_output(result.stdout, settings["severity"])
    LSP_SERVER.publish_diagnostics(document.uri, diagnostics)


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


if __name__ == "__main__":
    LSP_SERVER.start_io()
