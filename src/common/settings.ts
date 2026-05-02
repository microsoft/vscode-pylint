// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import { ConfigurationChangeEvent, WorkspaceFolder } from 'vscode';
import {
    IBaseSettings,
    checkIfConfigurationChanged as _checkIfConfigurationChanged,
    getGlobalSettings as _getGlobalSettings,
    getWorkspaceSettings as _getWorkspaceSettings,
    resolveVariables,
} from '@vscode/common-python-lsp';
import { PYLINT_TOOL_CONFIG } from './constants';
import { getInterpreterDetails } from './python';
import { getConfiguration, getWorkspaceFolders } from './vscodeapi';
import { traceWarn } from './logging';

export interface ISettings extends IBaseSettings {
    enabled: boolean;
    severity: Record<string, string>;
    path: string[];
    ignorePatterns: string[];
    lintOnChange: boolean;
}

export function getExtensionSettings(namespace: string, includeInterpreter?: boolean): Promise<ISettings[]> {
    return Promise.all(getWorkspaceFolders().map((w) => getWorkspaceSettings(namespace, w, includeInterpreter)));
}

export async function getWorkspaceSettings(
    namespace: string,
    workspace: WorkspaceFolder,
    includeInterpreter?: boolean,
): Promise<ISettings> {
    const resolveInterpreter = includeInterpreter ? getInterpreterDetails : undefined;
    const settings = (await _getWorkspaceSettings(
        namespace,
        workspace,
        PYLINT_TOOL_CONFIG,
        resolveInterpreter,
    )) as ISettings;

    if (settings.ignorePatterns?.length > 0) {
        settings.ignorePatterns = resolveVariables(settings.ignorePatterns, workspace);
    }

    return settings;
}

export async function getGlobalSettings(namespace: string, includeInterpreter?: boolean): Promise<ISettings> {
    const resolveInterpreter = includeInterpreter ? getInterpreterDetails : undefined;
    return (await _getGlobalSettings(namespace, PYLINT_TOOL_CONFIG, resolveInterpreter)) as ISettings;
}

export function isLintOnChangeEnabled(namespace: string): boolean {
    const config = getConfiguration(namespace);
    return config.get<boolean>('lintOnChange', false);
}

export function getTrackedSettings(namespace: string): string[] {
    return [...PYLINT_TOOL_CONFIG.trackedSettings.map((s) => `${namespace}.${s}`), 'python.analysis.extraPaths'];
}

export function checkIfConfigurationChanged(e: ConfigurationChangeEvent, namespace: string): boolean {
    return (
        _checkIfConfigurationChanged(e, namespace, PYLINT_TOOL_CONFIG.trackedSettings) ||
        e.affectsConfiguration('python.analysis.extraPaths')
    );
}

export function logLegacySettings(): void {
    getWorkspaceFolders().forEach((workspace) => {
        try {
            const legacyConfig = getConfiguration('python', workspace.uri);

            const legacyPylintEnabled = legacyConfig.get<boolean>('linting.pylintEnabled', false);
            if (legacyPylintEnabled) {
                traceWarn(`"python.linting.pylintEnabled" is deprecated. You can remove that setting.`);
                traceWarn(
                    'The pylint extension is always enabled. However, you can disable it per workspace using the extensions view.',
                );
                traceWarn('You can exclude files and folders using the `python.linting.ignorePatterns` setting.');
                traceWarn(
                    `"python.linting.pylintEnabled" value for workspace ${workspace.uri.fsPath}: ${legacyPylintEnabled}`,
                );
            }

            const legacyCwd = legacyConfig.get<string>('linting.cwd');
            if (legacyCwd) {
                traceWarn(`"python.linting.cwd" is deprecated. Use "pylint.cwd" instead.`);
                traceWarn(`"python.linting.cwd" value for workspace ${workspace.uri.fsPath}: ${legacyCwd}`);
            }

            const legacyArgs = legacyConfig.get<string[]>('linting.pylintArgs', []);
            if (legacyArgs.length > 0) {
                traceWarn(`"python.linting.pylintArgs" is deprecated. Use "pylint.args" instead.`);
                traceWarn(`"python.linting.pylintArgs" value for workspace ${workspace.uri.fsPath}:`);
                traceWarn(`\n${JSON.stringify(legacyArgs, null, 4)}`);
            }

            const legacyPath = legacyConfig.get<string>('linting.pylintPath', '');
            if (legacyPath.length > 0 && legacyPath !== 'pylint') {
                traceWarn(`"python.linting.pylintPath" is deprecated. Use "pylint.path" instead.`);
                traceWarn(`"python.linting.pylintPath" value for workspace ${workspace.uri.fsPath}:`);
                traceWarn(`\n${JSON.stringify(legacyPath, null, 4)}`);
            }
        } catch (err) {
            traceWarn(`Error while logging legacy settings: ${err}`);
        }
    });
}
