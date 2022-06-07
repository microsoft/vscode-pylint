# Pylint extension for Visual Studio Code

A Visual Studio Code extension with support for the `pylint` linter. The extension ships with `pylint=2.14.1`.

Note:

-   This extension is supported for all [actively supported versions](https://devguide.python.org/#status-of-python-branches) of the `python` language (i.e., python >= 3.7).
-   The bundled `pylint` is only used if there is no installed version of `pylint` found in the selected `python` environment.
-   Minimum supported version of `pylint` is `2.12.2`.

## Usage

Once installed in Visual Studio Code, pylint will be automatically executed when you open a Python file.

If you want to disable pylint, you can [disable this extension](https://code.visualstudio.com/docs/editor/extension-marketplace#_disable-an-extension) per workspace in Visual Studio Code.

## Settings

| Settings        | Default                                                                                                                                | Description                                                                                                                                                                                                                                                                                                              |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| pylint.args     | `[]`                                                                                                                                   | Custom arguments passed to `pylint`. E.g `"pylint.args" = ["--rcfile=<file>"]`                                                                                                                                                                                                                                           |
| pylint.severity | `{ "convention": "Information", "error": "Error", "fatal": "Error", "refactor": "Hint", "warning": "Warning", "info": "Information" }` | Controls mapping of severity from `pylint` to VS Code severity when displaying in the problems window. You can override specific `pylint` error codes `{ "convention": "Information", "error": "Error", "fatal": "Error", "refactor": "Hint", "warning": "Warning", "W0611": "Error", "undefined-variable": "Warning" }` |
| pylint.trace    | `error`                                                                                                                                | Sets the tracing level for the extension.                                                                                                                                                                                                                                                                                |
| pylint.path     | `[]`                                                                                                                                   | Setting to provide custom `pylint` executable. This will slow down linting, since we will have to run `pylint` executable every time or file save or open. Example 1: `["~/global_env/pylint"]` Example 2: `["conda", "run", "-n", "lint_env", "python", "-m", "pylint"]`                                                |

## Commands

| Command                | Description                       |
| ---------------------- | --------------------------------- |
| Pylint: Restart Linter | Force re-start the linter server. |
