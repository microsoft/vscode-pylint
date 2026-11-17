// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import * as vscode from 'vscode';
import {
    activateToolExtension,
    getConfiguration,
    loadServerDefaults,
    onDidChangeConfiguration,
    ToolExtensionRuntime,
} from '../external/vscode-common-python-lsp/typescript/dist';
import { EXTENSION_ROOT_DIR, PYLINT_TOOL_CONFIG } from './common/constants';
import { logLegacySettings } from './common/settings';
import { registerScoreStatusBar, updateScore, updateStatusBarVisibility } from './common/status';

let runtime: ToolExtensionRuntime | undefined;

export async function activate(context: vscode.ExtensionContext): Promise<void> {
    const serverInfo = loadServerDefaults(EXTENSION_ROOT_DIR);
    runtime = activateToolExtension(context, {
        serverInfo,
        toolConfig: PYLINT_TOOL_CONFIG,
        hooks: {
            getLaunchEnvironment: () => ({
                // Preserve the unscoped machine setting, not a workspace's bootstrap settings.
                // eslint-disable-next-line @typescript-eslint/naming-convention
                VSCODE_PYLINT_LINT_ON_CHANGE: getConfiguration('pylint').get<boolean>('lintOnChange', false)
                    ? '1'
                    : undefined,
            }),
            configureClient: ({ client, registerDisposable }) => {
                registerDisposable(
                    client.onNotification('pylint/score', (params: { uri: string; score: number }) => {
                        updateScore(params.uri, params.score);
                    }),
                );
                registerDisposable(
                    client.onNotification('pylint/lintingStarted', (params: { uri: string }) => {
                        updateScore(params.uri, undefined);
                    }),
                );
                registerDisposable(
                    client.onNotification('pylint/lintingFailed', (params: { uri: string }) => {
                        updateScore(params.uri, -1);
                    }),
                );
            },
        },
    });

    // Pylint-specific: score status bar (separate from the shared LanguageStatusItem)
    context.subscriptions.push(registerScoreStatusBar(PYLINT_TOOL_CONFIG.toolId, serverInfo.name));

    // Pylint-specific: update status bar visibility on config change
    context.subscriptions.push(
        onDidChangeConfiguration(async (e: vscode.ConfigurationChangeEvent) => {
            if (e.affectsConfiguration('pylint.showScoreInStatusBar')) {
                updateStatusBarVisibility();
            }
        }),
    );

    logLegacySettings();
}

export async function deactivate(): Promise<void> {
    await runtime?.deactivate();
    runtime = undefined;
}
