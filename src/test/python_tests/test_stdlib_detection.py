# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Unit tests for stdlib/managed-path file detection in lsp_utils.

Tests the ``is_stdlib_file`` helper which determines whether a file belongs
to a Python-managed path (stdlib, site-packages, or VS Code extensions dir).

Note: pylint's ``is_stdlib_file`` checks against *all* known Python paths
(including site-packages), unlike some other extensions that exclude
site-packages.
"""

import os
import sys
import tempfile
from pathlib import Path

# Add bundled tool to path (also done by conftest, but kept for standalone use)
_BUNDLED_PATH = str(Path(__file__).parent.parent.parent.parent / "bundled" / "tool")
if _BUNDLED_PATH not in sys.path:
    sys.path.insert(0, _BUNDLED_PATH)

from lsp_utils import is_stdlib_file  # pylint: disable=wrong-import-position


def test_stdlib_file_detection():
    """Actual stdlib files (e.g. os module) are correctly identified."""
    os_file = os.__file__
    assert is_stdlib_file(
        os_file
    ), f"os module file {os_file} should be detected as stdlib"

    if hasattr(sys, "__file__"):
        sys_file = sys.__file__
        assert is_stdlib_file(
            sys_file
        ), f"sys module file {sys_file} should be detected as stdlib"


def test_random_file_not_stdlib():
    """Random user files are NOT identified as stdlib."""
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        result = is_stdlib_file(tmp_path)
        assert not result, f"Temporary file {tmp_path} should NOT be detected as stdlib"
    finally:
        os.unlink(tmp_path)


def test_user_project_file_not_stdlib():
    """A file in a user project directory is not detected as stdlib."""
    test_file = os.path.join(os.sep, "home", "user", "my-project", "src", "main.py")
    result = is_stdlib_file(test_file)
    assert not result, f"User project file {test_file} should NOT be detected as stdlib"


if __name__ == "__main__":
    test_stdlib_file_detection()
    test_random_file_not_stdlib()
    test_user_project_file_not_stdlib()
    print("All tests passed!")
