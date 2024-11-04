// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import * as path from 'path';
import { ConfigurationChangeEvent, ConfigurationScope, WorkspaceConfiguration, WorkspaceFolder } from 'vscode';
import { traceLog, traceWarn } from './logging';
import { getInterpreterDetails } from './python';
import { getConfiguration, getWorkspaceFolders } from './vscodeapi';

const DEFAULT_SEVERITY: Record<string, string> = {
    convention: 'Information',
    error: 'Error',
    fatal: 'Error',
    refactor: 'Hint',
    warning: 'Warning',
    info: 'Information',
};
export interface ISettings {
    cwd: string;
    enabled: boolean;
    workspace: string;
    args: string[];
    severity: Record<string, string>;
    path: string[];
    ignorePatterns: string[];
    interpreter: string[];
    importStrategy: string;
    showNotifications: string;
    extraPaths: string[];
}

export function getExtensionSettings(namespace: string, includeInterpreter?: boolean): Promise<ISettings[]> {
    return Promise.all(getWorkspaceFolders().map((w) => getWorkspaceSettings(namespace, w, includeInterpreter)));
}

function resolveVariables(
    value: string[],
    workspace?: WorkspaceFolder,
    interpreter?: string[],
    env?: NodeJS.ProcessEnv,
): string[] {
    const substitutions = new Map<string, string>();
    const home = process.env.HOME || process.env.USERPROFILE;
    if (home) {
        substitutions.set('${userHome}', home);
        substitutions.set(`~/`, `${home}/`);
        substitutions.set(`~\\`, `${home}\\`); // Adding both path seps '/' and '\\' explicitly handle and preserve the path separators.
    }
    if (workspace) {
        substitutions.set('${workspaceFolder}', workspace.uri.fsPath);
    }

    substitutions.set('${cwd}', process.cwd());
    getWorkspaceFolders().forEach((w) => {
        substitutions.set('${workspaceFolder:' + w.name + '}', w.uri.fsPath);
    });

    env = env || process.env;
    if (env) {
        for (const [key, value] of Object.entries(env)) {
            if (value) {
                substitutions.set('${env:' + key + '}', value);
            }
        }
    }

    const modifiedValue = [];
    for (const v of value) {
        if (interpreter && v === '${interpreter}') {
            modifiedValue.push(...interpreter);
        } else {
            modifiedValue.push(v);
        }
    }

    return modifiedValue.map((s) => {
        for (const [key, value] of substitutions) {
            s = s.replace(key, value);
        }
        return s;
    });
}

function getCwd(config: WorkspaceConfiguration, workspace: WorkspaceFolder): string {
    const cwd = config.get<string>('cwd', workspace.uri.fsPath);
    return resolveVariables([cwd], workspace)[0];
}

function getExtraPaths(_namespace: string, workspace: WorkspaceFolder): string[] {
    const legacyConfig = getConfiguration('python', workspace.uri);
    const legacyExtraPaths = legacyConfig.get<string[]>('analysis.extraPaths', []);

    if (legacyExtraPaths.length > 0) {
        traceLog('Using cwd from `python.analysis.extraPaths`.');
    }
    return legacyExtraPaths;
}

export function getInterpreterFromSetting(namespace: string, scope?: ConfigurationScope) {
    const config = getConfiguration(namespace, scope);
    return config.get<string[]>('interpreter');
}

export async function getWorkspaceSettings(
    namespace: string,
    workspace: WorkspaceFolder,
    includeInterpreter?: boolean,
): Promise<ISettings> {
    const config = getConfiguration(namespace, workspace);

    let interpreter: string[] = [];
    if (includeInterpreter) {
        interpreter = getInterpreterFromSetting(namespace, workspace) ?? [];
        if (interpreter.length === 0) {
            traceLog(`No interpreter found from setting ${namespace}.interpreter`);
            traceLog(`Getting interpreter from ms-python.python extension for workspace ${workspace.uri.fsPath}`);
            interpreter = (await getInterpreterDetails(workspace.uri)).path ?? [];
            if (interpreter.length > 0) {
                traceLog(
                    `Interpreter from ms-python.python extension for ${workspace.uri.fsPath}:`,
                    `${interpreter.join(' ')}`,
                );
            }
        } else {
            traceLog(`Interpreter from setting ${namespace}.interpreter: ${interpreter.join(' ')}`);
        }

        if (interpreter.length === 0) {
            traceLog(`No interpreter found for ${workspace.uri.fsPath} in settings or from ms-python.python extension`);
        }
    }

    const extraPaths = getExtraPaths(namespace, workspace);
    const workspaceSetting = {
        enabled: config.get<boolean>('enabled', true),
        cwd: getCwd(config, workspace),
        workspace: workspace.uri.toString(),
        args: resolveVariables(config.get<string[]>('args', []), workspace),
        severity: config.get<Record<string, string>>('severity', DEFAULT_SEVERITY),
        path: resolveVariables(config.get<string[]>('path', []), workspace, interpreter),
        ignorePatterns: resolveVariables(config.get<string[]>('ignorePatterns', []), workspace),
        interpreter: resolveVariables(interpreter, workspace),
        importStrategy: config.get<string>('importStrategy', 'useBundled'),
        showNotifications: config.get<string>('showNotifications', 'off'),
        extraPaths: resolveVariables(extraPaths, workspace),
    };
    return workspaceSetting;
}

function getGlobalValue<T>(config: WorkspaceConfiguration, key: string, defaultValue: T): T {
    const inspect = config.inspect<T>(key);
    return inspect?.globalValue ?? inspect?.defaultValue ?? defaultValue;
}

export async function getGlobalSettings(namespace: string, includeInterpreter?: boolean): Promise<ISettings> {
    const config = getConfiguration(namespace);

    let interpreter: string[] = [];
    if (includeInterpreter) {
        interpreter = getGlobalValue<string[]>(config, 'interpreter', []);
        if (interpreter === undefined || interpreter.length === 0) {
            interpreter = (await getInterpreterDetails()).path ?? [];
        }
    }

    const setting = {
        cwd: getGlobalValue<string>(config, 'cwd', process.cwd()),
        enabled: getGlobalValue<boolean>(config, 'enabled', true),
        workspace: process.cwd(),
        args: getGlobalValue<string[]>(config, 'args', []),
        severity: getGlobalValue<Record<string, string>>(config, 'severity', DEFAULT_SEVERITY),
        path: getGlobalValue<string[]>(config, 'path', []),
        ignorePatterns: getGlobalValue<string[]>(config, 'ignorePatterns', []),
        interpreter: interpreter ?? [],
        importStrategy: getGlobalValue<string>(config, 'importStrategy', 'fromEnvironment'),
        showNotifications: getGlobalValue<string>(config, 'showNotifications', 'off'),
        extraPaths: getGlobalValue<string[]>(config, 'extraPaths', []),
    };
    return setting;
}

export function isLintOnChangeEnabled(namespace: string): boolean {
    const config = getConfiguration(namespace);
    return config.get<boolean>('lintOnChange', false);
}

export function checkIfConfigurationChanged(e: ConfigurationChangeEvent, namespace: string): boolean {
    const settings = [
        `${namespace}.args`,
        `${namespace}.cwd`,
        `${namespace}.enabled`,
        `${namespace}.severity`,
        `${namespace}.path`,
        `${namespace}.interpreter`,
        `${namespace}.importStrategy`,
        `${namespace}.showNotifications`,
        `${namespace}.ignorePatterns`,
        `${namespace}.lintOnChange`,
        'python.analysis.extraPaths',
    ];
    const changed = settings.map((s) => e.affectsConfiguration(s));
    return changed.includes(true);
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
