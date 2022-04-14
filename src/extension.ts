// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import * as vscode from 'vscode';
import { LanguageClient } from 'vscode-languageclient/node';
import { restartLinterServer } from './common/linterLS';
import { initializeFileLogging, registerLogger, setLoggingLevel, traceLog, traceVerbose } from './common/logging';
import { OutputChannelLogger } from './common/outputChannelLogger';
import { getInterpreterDetails, initializePython, onDidChangePythonInterpreter } from './common/python';
import { checkIfConfigurationChanged, getLinterExtensionSettings, ISettings } from './common/settings';
import { loadLinterDefaults } from './common/setup';
import { createOutputChannel, onDidChangeConfiguration, registerCommand } from './common/vscodeapi';

function setupLogging(settings: ISettings[], outputChannel: vscode.OutputChannel, disposables: vscode.Disposable[]) {
    // let error: unknown;
    if (settings.length > 0) {
        setLoggingLevel(settings[0].trace);

        // if (settings.logPath && settings.logPath.length > 0) {
        //     error = initializeFileLogging(settings.logPath, disposables);
        // }
    }

    disposables.push(registerLogger(new OutputChannelLogger(outputChannel)));

    // if (error) {
    //     // Capture and show log file creation error in the output channel
    //     traceLog(`Failed to create log file: ${settings.logPath} \r\n`, error);
    // }
}

let lsClient: LanguageClient | undefined;
export async function activate(context: vscode.ExtensionContext): Promise<void> {
    // This is required to get linter name and module. This should be
    // the first thing that we do in this extension.
    const linter = loadLinterDefaults();

    const settings = await getLinterExtensionSettings(linter.module);

    // Setup logging
    const outputChannel = createOutputChannel(linter.name);
    context.subscriptions.push(outputChannel);
    setupLogging(settings, outputChannel, context.subscriptions);

    traceLog(`Linter Name: ${linter.name}`);
    traceLog(`Linter Module: ${linter.module}`);
    traceVerbose(`Linter configuration: ${JSON.stringify(linter)}`);

    const runServer = async () => {
        const interpreter = await getInterpreterDetails();
        if (interpreter.path) {
            lsClient = await restartLinterServer(
                interpreter.path,
                linter.name,
                outputChannel,
                {
                    settings: await getLinterExtensionSettings(linter.module, true),
                },
                lsClient,
            );
        }
    };

    context.subscriptions.push(
        onDidChangePythonInterpreter(async () => {
            await runServer();
        }),
    );

    context.subscriptions.push(
        registerCommand(`${linter.module}.restart`, async () => {
            await runServer();
        }),
    );

    context.subscriptions.push(
        onDidChangeConfiguration(async (e: vscode.ConfigurationChangeEvent) => {
            if (checkIfConfigurationChanged(e, linter.module)) {
                const newSettings = await getLinterExtensionSettings(linter.module);
                setLoggingLevel(newSettings[0].trace);

                await runServer();
            }
        }),
    );

    setImmediate(async () => {
        traceVerbose(`Python extension loading`);
        await initializePython(context.subscriptions);
        traceVerbose(`Python extension loaded`);
    });
}
