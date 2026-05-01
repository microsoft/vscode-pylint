# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Utility functions and classes for use with running tools over LSP.

Thin wrapper: delegates to vscode-common-python-lsp shared package,
providing backward-compatible names used by lsp_server.py.
"""

from __future__ import annotations

from typing import Optional

from vscode_common_python_lsp import (
    CWD_LOCK,
    SERVER_CWD,
    CustomIO,
    QuickFixRegistrationError,
    RunResult,
    as_list,
    change_cwd,
    classify_python_file,
    is_current_interpreter,
    is_match,
    is_same_path,
    normalize_path,
    redirect_io,
    run_api,
    run_module,
    run_path,
    substitute_attr,
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


def get_message_category(code: str) -> Optional[str]:
    """Get the full name of the message category."""
    return CATEGORIES.get(code[0].upper())


def is_stdlib_file(file_path: str) -> bool:
    """Return True if the file belongs to a non-user Python path."""
    return classify_python_file(file_path) is not None


__all__ = [
    "SERVER_CWD",
    "CWD_LOCK",
    "CATEGORIES",
    "get_message_category",
    "as_list",
    "normalize_path",
    "is_same_path",
    "is_current_interpreter",
    "is_stdlib_file",
    "is_match",
    "RunResult",
    "CustomIO",
    "substitute_attr",
    "redirect_io",
    "change_cwd",
    "run_module",
    "run_path",
    "run_api",
    "QuickFixRegistrationError",
]
