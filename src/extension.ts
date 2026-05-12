// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import * as vscode from 'vscode';
import {
    createToolContext,
    deactivateServer,
    getConfiguration,
    loadServerDefaults,
    onDidChangeConfiguration,
    PythonEnvironmentsProvider,
    registerCommonSubscriptions,
    registerLogger,
    ToolExtensionContext,
} from '@vscode/common-python-lsp';
import { EXTENSION_ROOT_DIR, PYLINT_TOOL_CONFIG } from './common/constants';
import { logLegacySettings } from './common/settings';
import { registerScoreStatusBar, updateScore, updateStatusBarVisibility } from './common/status';

let toolContext: ToolExtensionContext | undefined;

function registerScoreNotifications(ctx: ToolExtensionContext): void {
    if (!ctx.lsClient) {
        return;
    }
    ctx.lsClient.onNotification('pylint/score', (params: { uri: string; score: number }) => {
        updateScore(params.uri, params.score);
    });
    ctx.lsClient.onNotification('pylint/lintingStarted', (params: { uri: string }) => {
        updateScore(params.uri, undefined);
    });
    ctx.lsClient.onNotification('pylint/lintingFailed', (params: { uri: string }) => {
        updateScore(params.uri, -1);
    });
}

export async function activate(context: vscode.ExtensionContext): Promise<void> {
    const serverInfo = loadServerDefaults(EXTENSION_ROOT_DIR);
    const outputChannel = vscode.window.createOutputChannel(serverInfo.name, { log: true });
    context.subscriptions.push(outputChannel, registerLogger(outputChannel));

    const pythonProvider = new PythonEnvironmentsProvider(PYLINT_TOOL_CONFIG);
    context.subscriptions.push(pythonProvider);

    toolContext = createToolContext({ serverInfo, outputChannel, toolConfig: PYLINT_TOOL_CONFIG, pythonProvider });
    context.subscriptions.push({ dispose: () => toolContext?.dispose() });

    // HACK: Override runServer to (1) set the lintOnChange env var dynamically so
    // toggling the setting takes effect without a full window reload, and (2) register
    // pylint-specific score notification handlers after each server restart.
    // Replace with a proper post-start hook when the shared package supports one.
    const originalRunServer = toolContext.runServer.bind(toolContext);
    toolContext.runServer = async () => {
        // Re-evaluate lintOnChange on each restart so runtime config changes take effect
        if (getConfiguration('pylint').get<boolean>('lintOnChange', false)) {
            process.env['VSCODE_PYLINT_LINT_ON_CHANGE'] = '1';
        } else {
            delete process.env['VSCODE_PYLINT_LINT_ON_CHANGE'];
        }
        await originalRunServer();
        registerScoreNotifications(toolContext!);
    };

    registerCommonSubscriptions(context, {
        serverInfo,
        outputChannel,
        toolConfig: PYLINT_TOOL_CONFIG,
        toolContext,
        pythonProvider,
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

    setImmediate(() => toolContext!.initialize(context.subscriptions));
}

export async function deactivate(): Promise<void> {
    await deactivateServer(toolContext);
}
