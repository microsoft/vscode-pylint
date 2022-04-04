# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Implementation of linting support over LSP.
"""

import json
import pathlib
import sys
from typing import Dict, Sequence, Union

# Ensure that will can import LSP libraries, and other bundled linter libraries
sys.path.append(str(pathlib.Path(__file__).parent.parent / "libs"))

# pylint: disable=wrong-import-position,import-error
import utils
from pygls import lsp, protocol, server
from pygls.lsp import types

all_configurations = {
    "name": "Pylint",
    "module": "pylint",
    "patterns": {
        "default": {
            "regex": "",
            "args": ["--reports=n", "--output-format=json"],
            "lineStartsAt1": True,
            "columnStartsAt1": False,
            "useStdin": True,
        }
    },
}

SETTINGS = {}
LINTER = {}

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
    line_at_1: bool,
    column_at_1: bool,
    severity: Dict[str, str],
    additional_offset: int = 0,
) -> Sequence[types.Diagnostic]:
    """Parses linter messages and return LSP diagnostic object for each message."""
    diagnostics = []

    line_offset = (1 if line_at_1 else 0) + additional_offset
    col_offset = 1 if column_at_1 else 0

    messages = json.loads(content)
    for data in messages:
        start = types.Position(
            line=int(data["line"]) - line_offset,
            character=int(data["column"]) - col_offset,
        )

        if data["endLine"] is not None:
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

    module = LINTER["module"]
    use_stdin = LINTER["useStdin"]
    use_path = len(SETTINGS["path"]) > 0

    argv = SETTINGS["path"] if use_path else [module]
    argv += LINTER["args"] + SETTINGS["args"]
    argv += ["--from-stdin", document.path] if use_stdin else [document.path]

    if use_path:
        result = utils.run_path(argv, use_stdin, document.source)
    else:
        # This is needed to preserve sys.path, pylint modifies
        # sys.path and that might not work for this scenario
        # next time around.
        with utils.SubstituteAttr(sys, "path", sys.path[:]):
            result = utils.run_module(module, argv, use_stdin, document.source)

    if result.stderr:
        LSP_SERVER.show_message_log(result.stderr)

    LSP_SERVER.show_message_log(f"{document.uri} :\r\n{result.stdout}")

    diagnostics = _parse_output(
        result.stdout,
        LINTER["lineStartsAt1"],
        LINTER["columnStartsAt1"],
        SETTINGS["severity"],
    )

    LSP_SERVER.publish_diagnostics(document.uri, diagnostics)


@LSP_SERVER.feature(lsp.INITIALIZE)
def initialize(params: types.InitializeParams):
    """LSP handler for initialize request."""
    paths = "\r\n".join(sys.path)
    LSP_SERVER.show_message_log(f"sys.path used to run Linter:\r\n{paths}")
    # First get workspace settings to know if we are using linter
    # module or binary.
    global SETTINGS  # pylint: disable=global-statement
    SETTINGS = params.initialization_options["settings"]

    global LINTER  # pylint: disable=global-statement
    LINTER = utils.get_linter_options_by_version(
        all_configurations,
        SETTINGS["path"] if len(SETTINGS["path"]) > 0 else None,
    )

    if isinstance(LSP_SERVER.lsp, protocol.LanguageServerProtocol):
        if SETTINGS['trace'] == 'debug':
            LSP_SERVER.lsp.trace = lsp.Trace.Verbose
        elif SETTINGS['trace'] == 'info':
            LSP_SERVER.lsp.trace = lsp.Trace.Messages
        else:
            LSP_SERVER.lsp.trace = 'off'


@LSP_SERVER.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
def did_open(_server: server.LanguageServer, params: types.DidOpenTextDocumentParams):
    """LSP handler for textDocument/didOpen request."""
    _lint_and_publish_diagnostics(params)


@LSP_SERVER.feature(lsp.TEXT_DOCUMENT_DID_SAVE)
def did_save(_server: server.LanguageServer, params: types.DidSaveTextDocumentParams):
    """LSP handler for textDocument/didOpen request."""
    _lint_and_publish_diagnostics(params)


@LSP_SERVER.feature(lsp.TEXT_DOCUMENT_DID_CLOSE)
def did_close(_server: server.LanguageServer, params: types.DidCloseTextDocumentParams):
    """LSP handler for textDocument/didClose request."""
    # Publishing empty diagnostics to clear the entries for this file.
    text_document = LSP_SERVER.workspace.get_document(params.text_document.uri)
    LSP_SERVER.publish_diagnostics(text_document.uri, [])


if __name__ == "__main__":
    LSP_SERVER.start_io()
