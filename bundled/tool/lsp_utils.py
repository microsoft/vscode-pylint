# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Utility functions and classes for use with running tools over LSP.

Thin wrapper: delegates to vscode-common-python-lsp shared package,
providing backward-compatible names used by lsp_server.py and tests.
"""

from __future__ import annotations

from vscode_common_python_lsp import (
    SERVER_CWD,
    change_cwd,
    classify_python_file,
)

# Pylint-specific message category mapping
CATEGORIES = {
    "F": "fatal",
    "E": "error",
    "W": "warning",
    "C": "convention",
    "R": "refactor",
    "I": "information",
}


def get_message_category(code: str) -> str | None:
    """Get the full name of the message category."""
    return CATEGORIES.get(code[0].upper())


def is_stdlib_file(file_path: str) -> bool:
    """Return True if the file belongs to a non-user Python path."""
    return classify_python_file(file_path) is not None


__all__ = [
    "CATEGORIES",
    "SERVER_CWD",
    "change_cwd",
    "get_message_category",
    "is_stdlib_file",
]
