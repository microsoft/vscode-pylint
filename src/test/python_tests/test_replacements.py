# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Unit tests for the quick-fix text rewrites in lsp_server."""

import pytest
from lsp_server import _fix_unspecified_encoding
from lsprotocol import types as lsp


@pytest.mark.parametrize(
    ("marked", "expected"),
    [
        # The argument list starts at the matching parenthesis, so nested calls,
        # subscripts and parentheses or spaces inside the path do not start it.
        ("open(path)|\n", "open(path, encoding='utf-8')\n"),
        ("open(get_path())|\n", "open(get_path(), encoding='utf-8')\n"),
        ("open(paths[0])|\n", "open(paths[0], encoding='utf-8')\n"),
        (
            "open(os.path.join(base, 'a (1).txt'), 'r')|\n",
            "open(os.path.join(base, 'a (1).txt'), 'r', encoding='utf-8')\n",
        ),
        (
            "with open('my file.txt')| as f:\n",
            "with open('my file.txt', encoding='utf-8') as f:\n",
        ),
        # Only the call the diagnostic ends at is touched: a nested call of the
        # same name is somebody else's function, and another call on the line
        # has a diagnostic and an edit of its own.
        ("open(read_text())|\n", "open(read_text(), encoding='utf-8')\n"),
        (
            "a, b = open('a.txt')|, open('b.txt')\n",
            "a, b = open('a.txt', encoding='utf-8'), open('b.txt')\n",
        ),
        (
            "a, b = open('a.txt'), open('b.txt')|\n",
            "a, b = open('a.txt'), open('b.txt', encoding='utf-8')\n",
        ),
        # The keyword goes after the positional arguments and before any other
        # keyword, and an encoding that is already there is left alone.
        ("open('f.txt', 'wt+')|\n", "open('f.txt', 'wt+', encoding='utf-8')\n"),
        ("open(path, encoding='latin-1')|\n", "open(path, encoding='latin-1')\n"),
        (
            "open(path, 'r', newline='\\n')|\n",
            "open(path, 'r', encoding='utf-8', newline='\\n')\n",
        ),
        # A call with no arguments needs no separator, a trailing comma is one.
        ("open('f.txt',)|\n", "open('f.txt', encoding='utf-8',)\n"),
        ("Path(p).read_text()|\n", "Path(p).read_text(encoding='utf-8')\n"),
        ("Path(p).write_text(text)|\n", "Path(p).write_text(text, encoding='utf-8')\n"),
        # A call split over several lines keeps its layout: the argument joins
        # the last line that holds one.
        (
            "open(\n    path,\n    'r'\n)|\n",
            "open(\n    path,\n    'r', encoding='utf-8'\n)\n",
        ),
        (
            "open(\n    path,\n    'r',\n    newline='\\n',\n)|\n",
            "open(\n    path,\n    'r',\n    encoding='utf-8', newline='\\n',\n)\n",
        ),
        (
            "open(\n    path,  # the file\n)|\n",
            "open(\n    path, encoding='utf-8',  # the file\n)\n",
        ),
        # The statement around the call can run past it in either direction.
        (
            "RESULT = wrap(open(\n    'f.txt'\n)|, 1,\n    2)\n",
            "RESULT = wrap(open(\n    'f.txt', encoding='utf-8'\n), 1,\n    2)\n",
        ),
        (
            "HANDLE = open('g.txt')| \\\n    if flag else None\n",
            "HANDLE = open('g.txt', encoding='utf-8') \\\n    if flag else None\n",
        ),
        (
            "def read():\n    return open('f.txt')|\n",
            "def read():\n    return open('f.txt', encoding='utf-8')\n",
        ),
        # An unfinished statement elsewhere in the document does not hide a
        # call that is finished.
        (
            "HANDLE = open('f.txt')|\nLATER = [1,\n",
            "HANDLE = open('f.txt', encoding='utf-8')\nLATER = [1,\n",
        ),
        (
            "EARLIER = [1,\nHANDLE = open('f.txt')|\n",
            "EARLIER = [1,\nHANDLE = open('f.txt', encoding='utf-8')\n",
        ),
        # Nothing to anchor to: a range that does not reach the closing
        # parenthesis leaves the text alone rather than guessing at a call.
        ("open|(path)\n", "open(path)\n"),
        ("with open(\n|", "with open(\n"),
    ],
)
def test_fix_unspecified_encoding(marked, expected):
    """Tests the W1514 quick fix over the call a diagnostic flags."""
    assert _fixed(marked) == expected


def _fixed(marked: str) -> str:
    """Applies the fix, with ``|`` marking where the diagnostic ends."""
    before, _, after = marked.partition("|")
    text = before + after
    end = lsp.Position(
        line=before.count("\n"), character=len(before) - before.rfind("\n") - 1
    )
    edit = _fix_unspecified_encoding(
        text.splitlines(keepends=True),
        lsp.Diagnostic(range=lsp.Range(start=end, end=end), message=""),
    )

    if edit is None:
        return text

    lines = text.splitlines(keepends=True)
    at = sum(len(line) for line in lines[: edit.range.start.line])
    at += edit.range.start.character

    return f"{text[:at]}{edit.new_text}{text[at:]}"
