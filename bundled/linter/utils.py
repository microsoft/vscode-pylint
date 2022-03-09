# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Utility functions and classes for use with linting over LSP.
"""


import contextlib
import importlib
import io
import os.path
import runpy
import site
import subprocess
import sys
from typing import List, Sequence
from packaging.version import parse


def as_list(content):
    """Ensures we always get a list"""
    if isinstance(content, (list, tuple)):
        return content
    return [content]


# pylint: disable-next=consider-using-generator
_site_paths = tuple(
    [
        os.path.normcase(os.path.normpath(p))
        for p in (as_list(site.getsitepackages()) + as_list(site.getusersitepackages()))
    ]
)


def is_stdlib_file(file_path):
    """Return True if the file belongs to standard library."""
    return os.path.normcase(os.path.normpath(file_path)).startswith(_site_paths)


def _get_linter_version_by_path(settings_path: List[str]) -> str:
    """Extract version number when using path to run linter."""
    try:
        args = settings_path + ["--version"]
        result = subprocess.run(
            args,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
    except SystemExit:
        pass

    # This is to just get the version number:
    # > pylint --version
    # pylint 2.12.2  <--- this is all we want
    # astroid 2.9.3
    # Python 3.10.2 (tags/v3.10.2:a58ebcc, Jan 17 2022, 14:12:15) [MSC v.1929 64 bit (AMD64)]
    first_line = result.stdout.splitlines(keepends=False)[0]
    return first_line.split(" ")[1]


def _get_linter_version_by_module(module):
    """Extracts linter version when using the module to lint."""
    imported = importlib.import_module(module)
    return imported.__getattr__("__version__")


def get_linter_options_by_version(raw_options, linter_path):
    """Gets the settings based on the version of the linter."""
    name = raw_options["name"]
    module = raw_options["module"]

    default = {
        "name": name,
        "module": module,
        "columnStartsAt1": raw_options["patterns"]["default"]["columnStartsAt1"],
        "lineStartsAt1": raw_options["patterns"]["default"]["lineStartsAt1"],
        "args": raw_options["patterns"]["default"]["args"],
        "regex": raw_options["patterns"]["default"]["regex"],
        "useStdin": raw_options["patterns"]["default"]["useStdin"],
    }

    options = default

    if len(raw_options["patterns"]) == 1:
        return options

    try:
        version = parse(
            _get_linter_version_by_path(linter_path)
            if len(linter_path) > 0
            else _get_linter_version_by_module(module)
        )
    except Exception:  # pylint: disable=broad-except
        return options

    for ver in filter(lambda k: not k == "default", raw_options["patterns"].keys()):
        if version >= parse(ver):
            options = {
                "name": name,
                "module": module,
                "columnStartsAt1": raw_options["patterns"][ver]["columnStartsAt1"],
                "lineStartsAt1": raw_options["patterns"][ver]["lineStartsAt1"],
                "args": raw_options["patterns"][ver]["args"],
                "regex": raw_options["patterns"][ver]["regex"],
                "useStdin": raw_options["patterns"][ver]["useStdin"],
            }

    return options


class RedirectIO(contextlib.AbstractContextManager):
    """Redirect stdio streams to a custom stream."""

    def __init__(self, stream, new_target):
        self._stream = stream
        self._new_target = new_target
        # We use a list of old targets to make this CM re-entrant
        self._old_targets = []

    def __enter__(self):
        self._old_targets.append(getattr(sys, self._stream))
        setattr(sys, self._stream, self._new_target)
        return self._new_target

    def __exit__(self, exctype, excinst, exctb):
        setattr(sys, self._stream, self._old_targets.pop())


# pylint: disable-next=too-few-public-methods
class LinterResult:
    """Object to hold result from running linter."""

    def __init__(self, stdout, stderr):
        self.stdout = stdout
        self.stderr = stderr


class CustomIO(io.TextIOWrapper):
    """Custom stream object to replace stdio."""

    name = None

    def __init__(self, name, encoding="utf-8", newline=None):
        super().__init__(io.BytesIO(), encoding=encoding, newline=newline)
        self.name = name

    def close(self):
        """Provide this close method which is used by some linters."""


class SubstituteSysArgv:
    """Manage sys.argv context when using runpy.run_module()."""

    def __init__(self, new_args):
        self.original_argv = []
        self.new_args = new_args

    def __enter__(self):
        self.original_argv = sys.argv[:]
        setattr(sys, "argv", self.new_args)
        return self

    def __exit__(self, exctype, excinst, exctb):
        setattr(sys, "argv", self.original_argv)


def run_module(
    module: str, argv: Sequence[str], use_stdin: bool, source: str = None
) -> LinterResult:
    """Runs linter as a module."""
    str_output = CustomIO("<stdout>", encoding=sys.stdout.encoding)
    str_error = CustomIO("<stderr>", encoding=sys.stderr.encoding)

    try:
        with SubstituteSysArgv(argv), RedirectIO("stdout", str_output), RedirectIO(
            "stderr", str_error
        ):
            if use_stdin and source:
                str_input = CustomIO(
                    "<stdin>",
                    encoding=sys.stdin.encoding,
                    newline="\n",
                )
                with RedirectIO("stdin", str_input):
                    str_input.write(source)
                    str_input.seek(0)
                    runpy.run_module(module, run_name="__main__")
            else:
                runpy.run_module(module, run_name="__main__")
    except SystemExit:
        pass

    str_error.seek(0)
    str_output.seek(0)
    return LinterResult(str_output.read(), str_error.read())


def run_path(argv: Sequence[str], use_stdin: bool, source: str = None) -> LinterResult:
    """Runs linter as an executable."""
    if use_stdin:
        with subprocess.Popen(
            argv,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
        ) as process:
            return LinterResult(*process.communicate(input=source))
    else:
        result = subprocess.run(
            argv,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return LinterResult(result.stdout, result.stderr)
