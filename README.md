# Pylint extension for Visual Studio Code

A Visual Studio Code extension with support for the `pylint` linter. The extension ships with `pylint=2.16.2`.

Note:

-   This extension is supported for all [actively supported versions](https://devguide.python.org/#status-of-python-branches) of the `python` language (i.e., python >= 3.7).
-   The bundled `pylint` is only used if there is no installed version of `pylint` found in the selected `python` environment.
-   Minimum supported version of `pylint` is `2.12.2`.

## Usage

Once installed in Visual Studio Code, pylint will be automatically executed when you open a Python file.

If you want to disable pylint, you can [disable this extension](https://code.visualstudio.com/docs/editor/extension-marketplace#_disable-an-extension) per workspace in Visual Studio Code.

## Settings

| Settings                | Default                                                                                                                                | Description                                                                                                                                                                                                                                                                                                              |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| pylint.args             | `[]`                                                                                                                                   | Custom arguments passed to `pylint`. E.g `"pylint.args" = ["--rcfile=<file>"]`                                                                                                                                                                                                                                           |
| pylint.severity         | `{ "convention": "Information", "error": "Error", "fatal": "Error", "refactor": "Hint", "warning": "Warning", "info": "Information" }` | Controls mapping of severity from `pylint` to VS Code severity when displaying in the problems window. You can override specific `pylint` error codes `{ "convention": "Information", "error": "Error", "fatal": "Error", "refactor": "Hint", "warning": "Warning", "W0611": "Error", "undefined-variable": "Warning" }` |
| pylint.path             | `[]`                                                                                                                                   | Setting to provide custom `pylint` executable. This will slow down linting, since we will have to run `pylint` executable every time or file save or open. Example 1: `["~/global_env/pylint"]` Example 2: `["conda", "run", "-n", "lint_env", "python", "-m", "pylint"]`                                                |
| pylint.interpreter      | `[]`                                                                                                                                   | Path to a python interpreter to use to run the linter server.                                                                                                                                                                                                                                                            |
| pylint.importStrategy   | `useBundled`                                                                                                                           | Setting to choose where to load `pylint` from. `useBundled` picks pylint bundled with the extension. `fromEnvironment` uses `pylint` available in the environment.                                                                                                                                                       |
| pylint.showNotification | `off`                                                                                                                                  | Setting to control when a notification is shown.                                                                                                                                                                                                                                                                         |

## Commands

| Command                | Description                       |
| ---------------------- | --------------------------------- |
| Pylint: Restart Server | Force re-start the linter server. |

## Logging

From the command palette (View > Command Palette ...), run the `Developer: Set Log Level...` command. From the quick pick menu, select `Pylint` extension from the `Extension logs` group. Then select the log level you want to set.
