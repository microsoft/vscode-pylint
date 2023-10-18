# Pylint extension for Visual Studio Code

A Visual Studio Code extension with support for the `pylint` linter. The extension ships with `pylint=3.0.1`.

Note:

-   This extension is supported for all [actively supported versions](https://devguide.python.org/#status-of-python-branches) of the `python` language (i.e., python >= 3.8).
-   By default, this extension uses the shipped `pylint` version. However, you can use `pylint` from your environment by setting `pylint.importStrategy` to `fromEnvironment`. Alternatively, you can use a custom `pylint` executable by setting `pylint.path`.
-   Minimum supported version of `pylint` is `2.12.2`.

## Usage

Once installed in Visual Studio Code, pylint will be automatically executed when you open a Python file.

If you want to disable pylint, you can [disable this extension](https://code.visualstudio.com/docs/editor/extension-marketplace#_disable-an-extension) per workspace in Visual Studio Code.

## Settings

| Settings                | Default                                                                                                                                | Description                                                                                                                                                                                                                                                                                                              |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| pylint.args             | `[]`                                                                                                                                   | Custom arguments passed to `pylint`. E.g `"pylint.args" = ["--rcfile=<file>"]`                                                                                                                                                                                                                                           |
| pylint.cwd              | `${workspaceFolder}`                                                                                                                   | This setting specifies the working directory for `pylint`. By default, it uses the root directory of the workspace `${workspaceFolder}`. If you want pylint to operate within the directory of the file currently being linted, you can set this to `${fileDirname}`.                                                    |
| pylint.severity         | `{ "convention": "Information", "error": "Error", "fatal": "Error", "refactor": "Hint", "warning": "Warning", "info": "Information" }` | Controls mapping of severity from `pylint` to VS Code severity when displaying in the problems window. You can override specific `pylint` error codes `{ "convention": "Information", "error": "Error", "fatal": "Error", "refactor": "Hint", "warning": "Warning", "W0611": "Error", "undefined-variable": "Warning" }` |
| pylint.path             | `[]`                                                                                                                                   | Setting to provide custom `pylint` executable. This will slow down linting, since we will have to run `pylint` executable every time or file save or open. Example 1: `["~/global_env/pylint"]` Example 2: `["conda", "run", "-n", "lint_env", "python", "-m", "pylint"]`                                                |
| pylint.interpreter      | `[]`                                                                                                                                   | Path to a python interpreter to use to run the linter server. When set to `[]`, it will use the Python extension's selected interpreter. If it is set to a path, it will use that value as the interpreter.                                                                                                              |
| pylint.importStrategy   | `useBundled`                                                                                                                           | Setting to choose where to load `pylint` from. `useBundled` picks pylint bundled with the extension. `fromEnvironment` uses `pylint` available in the environment.                                                                                                                                                       |
| pylint.showNotification | `off`                                                                                                                                  | Setting to control when a notification is shown.                                                                                                                                                                                                                                                                         |
| pylint.lintOnChange     | `false`                                                                                                                                | (experimental) Setting to control linting on change feature.                                                                                                                                                                                                                                                             |
| pylint.ignorePatterns   | `[]`                                                                                                                                   | Glob patterns used to exclude files and directories from being linted.                                                                                                                                                                                                                                                   |
| pylint.includeStdLib    | `false`                                                                                                                                | Controls whether to perform linting on Python's standard library files or directories.                                                                                                                                                                                                                                   |

## Commands

| Command                | Description                       |
| ---------------------- | --------------------------------- |
| Pylint: Restart Server | Force re-start the linter server. |

## Logging

From the command palette (View > Command Palette ...), run the `Developer: Set Log Level...` command. From the quick pick menu, select `Pylint` extension from the `Extension logs` group. Then select the log level you want to set.
