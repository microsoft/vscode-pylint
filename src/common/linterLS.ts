// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import { OutputChannel } from 'vscode';
import {
    LanguageClient,
    LanguageClientOptions,
    RevealOutputChannelOn,
    ServerOptions,
} from 'vscode-languageclient/node';
import { LINTER_SCRIPT_PATH } from './constants';
import { traceInfo } from './logging';
import { ISettings } from './settings';
import { traceLevelToLSTrace } from './utilities';
import { isVirtualWorkspace } from './vscodeapi';

export type ILinterInitOptions = { settings: ISettings };

export async function createLinterServer(
    interpreter: string,
    serverName: string,
    trace: OutputChannel,
    initializationOptions: ILinterInitOptions,
): Promise<LanguageClient> {
    const serverOptions: ServerOptions = {
        command: interpreter,
        args: [LINTER_SCRIPT_PATH],
    };

    // Options to control the language client
    const clientOptions: LanguageClientOptions = {
        // Register the server for python documents
        documentSelector: isVirtualWorkspace()
            ? [{ language: 'python' }]
            : [
                  { scheme: 'file', language: 'python' },
                  { scheme: 'untitled', language: 'python' },
                  { scheme: 'vscode-notebook', language: 'python' },
                  { scheme: 'vscode-notebook-cell', language: 'python' },
                  { scheme: 'vscode-interactive-input', language: 'python' },
              ],
        outputChannel: trace,
        revealOutputChannelOn: RevealOutputChannelOn.Error,
        outputChannelName: trace.name,
        traceOutputChannel: trace,
        initializationOptions,
    };

    return new LanguageClient(serverName, serverName, serverOptions, clientOptions);
}

export async function restartLinterServer(
    interpreter: string,
    serverName: string,
    trace: OutputChannel,
    initializationOptions: ILinterInitOptions,
    lsClient?: LanguageClient,
): Promise<LanguageClient> {
    if (lsClient) {
        traceInfo(`Stopping linter server`);
        lsClient.stop();
    }
    const newLSClient = await createLinterServer(interpreter, serverName, trace, initializationOptions);
    newLSClient.trace = traceLevelToLSTrace(initializationOptions.settings.trace);
    newLSClient.start();
    traceInfo(`Starting linter server`);
    return newLSClient;
}
