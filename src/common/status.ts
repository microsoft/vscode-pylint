// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import { LanguageStatusItem, Disposable, l10n, LanguageStatusSeverity, StatusBarItem, window } from 'vscode';
import {
    createLanguageStatusItem,
    createStatusBarItem,
    getConfiguration,
    onDidChangeActiveTextEditor,
} from './vscodeapi';
import { Command } from 'vscode-languageclient';
import { getDocumentSelector } from './utilities';

let _status: LanguageStatusItem | undefined;
let _statusBarItem: StatusBarItem | undefined;
let _disposables: Disposable[] = [];
const _scoresByUri = new Map<string, number>();

export function registerLanguageStatusItem(id: string, name: string, command: string): Disposable {
    _status = createLanguageStatusItem(id, getDocumentSelector());
    _status.name = name;
    _status.text = name;
    _status.command = Command.create(l10n.t('Open logs'), command);

    _statusBarItem = createStatusBarItem(`${id}.score`);
    _statusBarItem.name = name;
    _statusBarItem.text = '$(checklist) Pylint';
    updateStatusBarVisibility();

    _disposables.push(
        onDidChangeActiveTextEditor(() => {
            updateDisplayedScore();
        }),
    );

    return {
        dispose: () => {
            _status?.dispose();
            _status = undefined;
            _statusBarItem?.dispose();
            _statusBarItem = undefined;
            _disposables.forEach((d) => d.dispose());
            _disposables = [];
            _scoresByUri.clear();
        },
    };
}

export function updateStatusBarVisibility(): void {
    const showInStatusBar = getConfiguration('pylint').get<boolean>('showScoreInStatusBar', true);
    if (showInStatusBar) {
        _statusBarItem?.show();
    } else {
        _statusBarItem?.hide();
    }
}

function updateDisplayedScore(): void {
    const activeUri = window.activeTextEditor?.document.uri.toString();
    const score = _scoresByUri.get(activeUri ?? '');

    const scoreText = score !== undefined ? `Pylint: ${score.toFixed(2)}/10` : 'Pylint';
    const statusBarText = score !== undefined ? `$(checklist) ${scoreText}` : '$(checklist) Pylint';

    if (_status) {
        _status.text = scoreText;
        _status.detail = score !== undefined ? scoreText : undefined;
    }

    if (_statusBarItem) {
        _statusBarItem.text = statusBarText;
        _statusBarItem.tooltip = scoreText;
    }
}

export function updateScore(uri: string, score: number | undefined): void {
    if (score !== undefined) {
        _scoresByUri.set(uri, score);
        const activeUri = window.activeTextEditor?.document.uri.toString();
        if (activeUri === uri) {
            updateDisplayedScore();
        }
    }
}

export function updateStatus(
    status: string | undefined,
    severity: LanguageStatusSeverity,
    busy?: boolean,
    detail?: string,
): void {
    if (_status) {
        _status.text = status && status.length > 0 ? `${_status.name}: ${status}` : `${_status.name}`;
        _status.severity = severity;
        _status.busy = busy ?? false;
        _status.detail = detail;
    }
}
