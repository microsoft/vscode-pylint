# Pylint extension for Visual Studio Code

A Visual Studio Code extension with support for the Pylint linter. This extension ships with `pylint=3.0.2`.

> **Note**: The minimum version of Pylint this extension supports is `2.12.2`.

This extension supports all [actively supported versions](https://devguide.python.org/#status-of-python-branches) of the `Python` language (i.e., Python >= 3.8).

For more information on Pylint, see https://pylint.readthedocs.io/

## Usage and Features

The Pylint extension provides a series of features to help your productivity while working with Python code in Visual Studio Code. Check out the [Settings section](#settings) below for more details on how to customize the extension.

-   **Integrated Linting**: Once this extension is installed in Visual Studio Code, Pylint is automatically executed when you open a Python file, providing immediate feedback on your code quality.
-   **Customizable Pylint Version**: By default, this extension uses the version of Pylint that is shipped with the extension. However, you can configure it to use a different binary installed in your environment through the `pylint.importStrategy` setting, or set it to a custom Pylint executable through the `pylint.path` settings.
-   **Immediate Feedback**: By default, Pylint will update the diagnostics in the editor once you save the file. But you can get immediate feedback on your code quality as you type by enabling the `pylint.lintOnChange` setting.
-   **Mono repo support**: If you are working with a mono repo, you can configure the extension to lint Python files in subfolders of the workspace root folder by setting the `pylint.cwd` setting to `${fileDirname}`. You can also set it to ignore/skip linting for certain files or folder paths by specifying a glob pattern to the `pylint.ignorePatterns` setting.
-   **Customizable Linting Rules**: You can customize the severity of specific Pylint error codes through the `pylint.severity` setting.

### Disabling Pylint

You can skip linting with Pylint for specific files or directories by setting the `pylint.ignorePatterns` setting.

But if you wish to disable linting with Pylint for your entire workspace or globally, you can [disable this extension](https://code.visualstudio.com/docs/editor/extension-marketplace#_disable-an-extension) in Visual Studio Code.

## Settings

There are several settings you can configure to customize the behavior of this extension.

| Settings                | Default                                                                                                                                | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| pylint.args             | `[]`                                                                                                                                   | Arguments passed to Pylint for linting Python files. Each argument should be provided as a separate string in the array. <br> Examples: <br>- `"pylint.args": ["--rcfile=<file>"]` <br> - `"pylint.args": ["--disable=C0111", "--max-line-length=120"]`                                                                                                                                                                                                                                                                                                                                                                           |
| pylint.cwd              | `${workspaceFolder}`                                                                                                                   | Sets the current working directory used to lint Python files with Pylint. By default, it uses the root directory of the workspace `${workspaceFolder}`. You can set it to `${fileDirname}` to use the parent folder of the file being linted as the working directory for Pylint.                                                                                                                                                                                                                                                                                                                                                 |
| pylint.severity         | `{ "convention": "Information", "error": "Error", "fatal": "Error", "refactor": "Hint", "warning": "Warning", "info": "Information" }` | Mapping of Pylint's message types to VS Code's diagnostic severity levels as displayed in the Problems window. You can also use it to override specific Pylint error codes. E.g. `{ "convention": "Information", "error": "Error", "fatal": "Error", "refactor": "Hint", "warning": "Warning", "W0611": "Error", "undefined-variable": "Warning" }`                                                                                                                                                                                                                                                                               |
| pylint.path             | `[]`                                                                                                                                   | "Path or command to be used by the extension to lint Python files with Pylint. Accepts an array of a single or multiple strings. If passing a command, each argument should be provided as a separate string in the array. If set to `["pylint"]`, it will use the version of Pylint available in the `PATH` environment variable. Note: Using this option may slowdown linting. <br>Examples: <br>- `"pylint.path" : ["~/global_env/pylint"]` <br>- `"pylint.path" : ["conda", "run", "-n", "lint_env", "python", "-m", "pylint"]` <br>- `"pylint.path" : ["pylint"]` <br>- `"pylint.path" : ["${interpreter}", "-m", "pylint"]` |
| pylint.interpreter      | `[]`                                                                                                                                   | Path to a Python executable or a command that will be used to launch the Pylint server and any subprocess. Accepts an array of a single or multiple strings. When set to `[]`, the extension will use the path to the selected Python interpreter. If passing a command, each argument should be provided as a separate string in the array.                                                                                                                                                                                                                                                                                      |
| pylint.importStrategy   | `useBundled`                                                                                                                           | Defines which Pylint binary to be used to lint Python files. When set to `useBundled`, the extension will use the Pylint binary that is shipped with the extension. When set to `fromEnvironment`, the extension will attempt to use the Pylint binary and all dependencies that are available in the currently selected environment. Note: If the extension can't find a valid Pylint binary in the selected environment, it will fallback to using the Pylint binary that is shipped with the extension. This setting will be overriden if `pylint.path` is set.                                                                |
| pylint.showNotification | `off`                                                                                                                                  | Controls when notifications are shown by this extension. Accepted values are `onError`, `onWarning`, `always` and `off`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| pylint.lintOnChange     | `false`                                                                                                                                | Enable linting Python files with Pylint as you type.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| pylint.ignorePatterns   | `[]`                                                                                                                                   | Configure [glob patterns](https://docs.python.org/3/library/fnmatch.html) as supported by the fnmatch Python library to exclude files or folders from being linted with Pylint.                                                                                                                                                                                      |

The following variables are supported for substitution in the `pylint.args`, `pylint.cwd`, `pylint.path`, `pylint.interpreter` and `pylint.ignorePatterns` settings:

-   `${workspaceFolder}`
-   `${workspaceFolder:FolderName}`
-   `${userHome}`
-   `${env:EnvVarName}`

The `pylint.path` setting also supports the `${interpreter}` variable as one of the entries of the array. This variable is subtituted based on the value of the `pylint.interpreter` setting.

## Commands

| Command                | Description                       |
| ---------------------- | --------------------------------- |
| Pylint: Restart Server | Force re-start the linter server. |

## Logging

From the Command Palette (**View** > **Command Palette ...**), run the **Developer: Set Log Level...** command. Select **Pylint** from the **Extension logs** group. Then select the log level you want to set.

Alternatively, you can set the `pylint.trace.server` setting to `verbose` to get more detailed logs from the Pylint server. This can be helpful when filing bug reports.

To open the logs, click on the language status icon (`{}`) on the bottom right of the Status bar, next to the Python language mode. Locate the **Pylint** entry and select **Open logs**.

## Troubleshooting

In this section, you will find some common issues you might encounter and how to resolve them. If you are experiencing any issues that are not covered here, please [file an issue](https://github.com/microsoft/vscode-pylint/issues).

-   If the `pylint.importStrategy` setting is set to `fromEnvironment` but Pylint is not found in the selected environment, this extension will fallback to using the Pylint binary that is shipped with the extension. However, if there are dependencies installed in the environment, those dependencies will be used along with the shipped Pylint binary. This can lead to problems if the dependencies are not compatible with the shipped Pylint binary.

    To resolve this issue, you can:

    -   Set the `pylint.importStrategy` setting to `useBundled` and the `pylint.path` setting to point to the custom binary of Pylint you want to use; or
    -   Install Pylint in the selected environment.
