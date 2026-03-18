# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Tests for Jupyter notebook cell support over LSP.

These are template-style example tests that demonstrate how to validate notebook
cell diagnostics. Adapt the expected diagnostics to match your tool's output.
"""

import json
from threading import Event
from typing import Any, Dict, List, Tuple

from .lsp_test_client import constants, defaults, session, utils

TIMEOUT = 10  # seconds

SAMPLE_NOTEBOOK = constants.TEST_DATA / "sample1" / "sample_notebook.ipynb"
LINTER = utils.get_server_info_defaults()


def _make_notebook_uri(notebook_path: str) -> str:
    """Returns a 'file:' URI for a notebook path."""
    return utils.as_uri(notebook_path)


def _make_cell_uri(notebook_path: str, cell_id: str) -> str:
    """Returns a 'vscode-notebook-cell:' URI for a notebook cell.

    Args:
        notebook_path: Absolute path to the .ipynb file.
        cell_id: Fragment identifier for the cell (e.g. 'W0sZmlsZQ%3D%3D0').
    """
    nb_uri = utils.as_uri(notebook_path)
    # Replace 'file:' scheme with 'vscode-notebook-cell:'
    cell_uri = nb_uri.replace("file:", "vscode-notebook-cell:", 1)
    return f"{cell_uri}#{cell_id}"


def _load_notebook(
    notebook_path: str,
) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Load an .ipynb file and return LSP-ready cell structures.

    Returns:
        A tuple of (notebook_uri, cells, cell_text_documents) where
        *cells* is the list for ``notebookDocument.cells`` and
        *cell_text_documents* is the list for ``cellTextDocuments``.
    """
    nb_uri = _make_notebook_uri(notebook_path)

    with open(notebook_path, "r", encoding="utf-8") as f:
        nb_json = json.load(f)

    _CELL_KIND = {"code": 2, "markdown": 1}
    _LANG_ID = {"code": "python", "markdown": "markdown"}

    cells = []
    cell_text_documents = []
    for cell in nb_json["cells"]:
        cell_id = cell["id"]
        cell_type = cell["cell_type"]
        cell_uri = _make_cell_uri(notebook_path, cell_id)
        source = "".join(cell["source"])

        cells.append(
            {
                "kind": _CELL_KIND[cell_type],
                "document": cell_uri,
                "metadata": {},
                "executionSummary": None,
            }
        )
        cell_text_documents.append(
            {
                "uri": cell_uri,
                "languageId": _LANG_ID[cell_type],
                "version": 1,
                "text": source,
            }
        )

    return nb_uri, cells, cell_text_documents


def test_notebook_did_open():
    """Diagnostics are published for each code cell when a notebook is opened.

    This test sends a notebookDocument/didOpen notification for a notebook with
    code cells and verifies that a publishDiagnostics notification is received
    for the first code cell's URI.
    """
    nb_path = str(SAMPLE_NOTEBOOK)
    nb_uri, cells, cell_text_documents = _load_notebook(nb_path)
    code_cell_uri = cell_text_documents[0]["uri"]  # first code cell

    with session.LspSession() as ls_session:
        ls_session.initialize(defaults.vscode_initialize_defaults())

        done = Event()
        received = []

        def _handler(params):
            received.append(params)
            if params.get("uri") == code_cell_uri:
                done.set()

        ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)

        ls_session.notify_notebook_did_open(
            {
                "notebookDocument": {
                    "uri": nb_uri,
                    "notebookType": "jupyter-notebook",
                    "version": 1,
                    "metadata": {},
                    "cells": cells,
                },
                "cellTextDocuments": cell_text_documents,
            }
        )

        assert done.wait(TIMEOUT)
        assert any(
            r.get("uri") == code_cell_uri for r in received
        ), f"Expected diagnostics for {code_cell_uri!r}, got: {received}"


def test_notebook_did_change_text_content():
    """Diagnostics update when the text content of a cell changes."""
    nb_path = str(SAMPLE_NOTEBOOK)
    nb_uri, cells, cell_text_documents = _load_notebook(nb_path)
    code_cell_uri = cell_text_documents[0]["uri"]

    # Count how many code cells will produce diagnostics on open.
    expected_open_count = sum(
        1 for d in cell_text_documents if d["languageId"] == "python"
    )

    with session.LspSession() as ls_session:
        ls_session.initialize(defaults.vscode_initialize_defaults())

        # Open notebook and drain initial diagnostics
        open_done = Event()
        open_received = []

        def _open_handler(params):
            open_received.append(params)
            if len(open_received) >= expected_open_count:
                open_done.set()

        ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _open_handler)

        ls_session.notify_notebook_did_open(
            {
                "notebookDocument": {
                    "uri": nb_uri,
                    "notebookType": "jupyter-notebook",
                    "version": 1,
                    "metadata": {},
                    "cells": cells,
                },
                "cellTextDocuments": cell_text_documents,
            }
        )

        assert open_done.wait(
            TIMEOUT
        ), "Timed out waiting for initial notebook diagnostics"

        # Set up fresh callback for the change notification
        done = Event()
        received = []

        def _change_handler(params):
            received.append(params)
            if params.get("uri") == code_cell_uri:
                done.set()

        ls_session.set_notification_callback(
            session.PUBLISH_DIAGNOSTICS, _change_handler
        )

        # Send a change with updated text content
        ls_session.notify_notebook_did_change(
            {
                "notebookDocument": {
                    "uri": nb_uri,
                    "version": 2,
                },
                "change": {
                    "metadata": None,
                    "cells": {
                        "structure": None,
                        "data": None,
                        "textContent": [
                            {
                                "document": {"uri": code_cell_uri, "version": 2},
                                "changes": [
                                    {
                                        "text": "z = 99\n",
                                    }
                                ],
                            }
                        ],
                    },
                },
            }
        )

        assert done.wait(TIMEOUT)
        assert any(
            r.get("uri") == code_cell_uri for r in received
        ), f"Expected diagnostics for {code_cell_uri!r}, got: {received}"


def test_notebook_did_save():
    """All code cells are re-linted when a notebook is saved."""
    nb_path = str(SAMPLE_NOTEBOOK)
    nb_uri, cells, cell_text_documents = _load_notebook(nb_path)
    code_cell_uri = cell_text_documents[0]["uri"]

    # Count how many code cells will produce diagnostics on open.
    expected_open_count = sum(
        1 for d in cell_text_documents if d["languageId"] == "python"
    )

    with session.LspSession() as ls_session:
        ls_session.initialize(defaults.vscode_initialize_defaults())

        # Open notebook and drain initial diagnostics
        open_done = Event()
        open_received = []

        def _open_handler(params):
            open_received.append(params)
            if len(open_received) >= expected_open_count:
                open_done.set()

        ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _open_handler)

        ls_session.notify_notebook_did_open(
            {
                "notebookDocument": {
                    "uri": nb_uri,
                    "notebookType": "jupyter-notebook",
                    "version": 1,
                    "metadata": {},
                    "cells": cells,
                },
                "cellTextDocuments": cell_text_documents,
            }
        )

        assert open_done.wait(
            TIMEOUT
        ), "Timed out waiting for initial notebook diagnostics"

        # Set up fresh callback for the save notification
        done = Event()
        received = []

        def _save_handler(params):
            received.append(params)
            if params.get("uri") == code_cell_uri:
                done.set()

        ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _save_handler)

        ls_session.notify_notebook_did_save(
            {
                "notebookDocument": {
                    "uri": nb_uri,
                    "version": 1,
                }
            }
        )

        assert done.wait(TIMEOUT)
        assert any(
            r.get("uri") == code_cell_uri for r in received
        ), f"Expected diagnostics for {code_cell_uri!r}, got: {received}"


def test_notebook_did_change_new_cell_kind_filter():
    """Diagnostics are only published for newly added code cells, not markdown cells.

    When a notebook change adds both a code cell and a markdown cell via
    structure.did_open, only the code cell should receive diagnostics.
    """
    # pylint: disable=too-many-locals
    nb_path = str(SAMPLE_NOTEBOOK)
    nb_uri, cells, cell_text_documents = _load_notebook(nb_path)

    # Identify the code and markdown cells from the loaded notebook.
    code_docs = [d for d in cell_text_documents if d["languageId"] == "python"]
    md_docs = [d for d in cell_text_documents if d["languageId"] == "markdown"]
    assert code_docs, "Notebook must have at least one code cell"
    assert md_docs, "Notebook must have at least one markdown cell"

    # Use the second code cell and the markdown cell as the newly-added cells.
    new_code_doc = code_docs[-1]
    new_md_doc = md_docs[0]
    new_code_cell_uri = new_code_doc["uri"]
    new_md_cell_uri = new_md_doc["uri"]

    with session.LspSession() as ls_session:
        ls_session.initialize(defaults.vscode_initialize_defaults())

        # Open an initially empty notebook
        ls_session.notify_notebook_did_open(
            {
                "notebookDocument": {
                    "uri": nb_uri,
                    "notebookType": "jupyter-notebook",
                    "version": 1,
                    "metadata": {},
                    "cells": [],
                },
                "cellTextDocuments": [],
            }
        )

        received = []
        done = Event()

        def _handler(params):
            received.append(params)
            done.set()

        ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)

        # Build structure cells from the notebook data for the two new cells
        new_cells = [
            c for c in cells if c["document"] in (new_code_cell_uri, new_md_cell_uri)
        ]

        ls_session.notify_notebook_did_change(
            {
                "notebookDocument": {
                    "uri": nb_uri,
                    "version": 2,
                },
                "change": {
                    "metadata": None,
                    "cells": {
                        "structure": {
                            "array": {
                                "start": 0,
                                "deleteCount": 0,
                                "cells": new_cells,
                            },
                            "didOpen": [new_code_doc, new_md_doc],
                            "didClose": None,
                        },
                        "data": None,
                        "textContent": None,
                    },
                },
            }
        )

        assert done.wait(TIMEOUT)

        # The code cell should receive diagnostics; the markdown cell must not.
        uris_with_diagnostics = {r.get("uri") for r in received}
        assert (
            new_code_cell_uri in uris_with_diagnostics
        ), f"Expected diagnostics for code cell {new_code_cell_uri!r}, got: {received}"
        assert (
            new_md_cell_uri not in uris_with_diagnostics
        ), f"Markdown cell {new_md_cell_uri!r} should not receive diagnostics, got: {received}"


def test_notebook_did_close():
    """Diagnostics are cleared for all cells when a notebook is closed."""
    nb_path = str(SAMPLE_NOTEBOOK)
    nb_uri, cells, cell_text_documents = _load_notebook(nb_path)
    code_cell_uri = cell_text_documents[0]["uri"]

    # Count how many code cells will produce diagnostics on open.
    expected_open_count = sum(
        1 for d in cell_text_documents if d["languageId"] == "python"
    )

    with session.LspSession() as ls_session:
        ls_session.initialize(defaults.vscode_initialize_defaults())

        # Open notebook and wait for ALL code-cell diagnostics to arrive
        open_done = Event()
        open_received = []

        def _open_handler(params):
            open_received.append(params)
            if len(open_received) >= expected_open_count:
                open_done.set()

        ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _open_handler)

        ls_session.notify_notebook_did_open(
            {
                "notebookDocument": {
                    "uri": nb_uri,
                    "notebookType": "jupyter-notebook",
                    "version": 1,
                    "metadata": {},
                    "cells": cells,
                },
                "cellTextDocuments": cell_text_documents,
            }
        )

        assert open_done.wait(
            TIMEOUT
        ), "Timed out waiting for initial notebook diagnostics"

        # Now set up a fresh callback for the close notification
        done = Event()
        received = []

        def _close_handler(params):
            received.append(params)
            done.set()

        ls_session.set_notification_callback(
            session.PUBLISH_DIAGNOSTICS, _close_handler
        )

        ls_session.notify_notebook_did_close(
            {
                "notebookDocument": {
                    "uri": nb_uri,
                    "version": 1,
                },
                "cellTextDocuments": [{"uri": code_cell_uri}],
            }
        )

        assert done.wait(TIMEOUT)

        # Diagnostics should be cleared (empty list) for the cell URI
        assert any(
            r.get("uri") == code_cell_uri and r.get("diagnostics") == []
            for r in received
        ), f"Expected empty diagnostics for {code_cell_uri!r}, got: {received}"


SAMPLE_NOTEBOOK_ERR = constants.TEST_DATA / "sample1" / "sample_notebook_err.ipynb"


def test_notebook_cell_reports_specific_error():
    """Diagnostics for a notebook cell contain the expected pylint error details.

    When a notebook is opened with a cell containing a known pylint violation
    (W0611 – unused import), the published diagnostic must include the correct
    error code, message, source, and range.
    """
    nb_path = str(SAMPLE_NOTEBOOK_ERR)
    nb_uri, cells, cell_text_documents = _load_notebook(nb_path)
    code_cell_uri = cell_text_documents[0]["uri"]  # first code cell has `import os`

    with session.LspSession() as ls_session:
        ls_session.initialize(defaults.vscode_initialize_defaults())

        done = Event()
        received = []

        def _handler(params):
            received.append(params)
            if params.get("uri") == code_cell_uri and params.get("diagnostics"):
                done.set()

        ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)

        ls_session.notify_notebook_did_open(
            {
                "notebookDocument": {
                    "uri": nb_uri,
                    "notebookType": "jupyter-notebook",
                    "version": 1,
                    "metadata": {},
                    "cells": cells,
                },
                "cellTextDocuments": cell_text_documents,
            }
        )

        assert done.wait(TIMEOUT)

        # Find the diagnostics for the target cell
        cell_results = [r for r in received if r.get("uri") == code_cell_uri]
        assert cell_results, f"No diagnostics received for {code_cell_uri!r}"

        # Use the last diagnostic notification (most up-to-date)
        diagnostics = cell_results[-1]["diagnostics"]
        assert diagnostics, f"Expected at least one diagnostic, got: {diagnostics}"

        # Find the unused-import diagnostic among the results
        unused_import = [d for d in diagnostics if "unused-import" in d.get("code", "")]
        assert (
            unused_import
        ), f"Expected W0611:unused-import diagnostic, got: {diagnostics}"

        diag = unused_import[0]
        assert (
            diag["code"] == "W0611:unused-import"
        ), f"Expected code 'W0611:unused-import', got {diag['code']!r}"
        assert (
            "Unused import os" in diag["message"]
        ), f"Unexpected message: {diag['message']!r}"
        assert (
            diag["severity"] == 2
        ), f"Expected severity 2 (Warning), got {diag['severity']}"
        assert (
            diag["source"] == LINTER["name"]
        ), f"Expected source {LINTER['name']!r}, got {diag['source']!r}"
        assert (
            diag["range"]["start"]["line"] == 0
        ), f"Expected error on line 0, got {diag['range']}"
        assert (
            diag["range"]["start"]["character"] == 0
        ), f"Expected error at character 0, got {diag['range']}"
