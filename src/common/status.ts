// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import { LanguageStatusItem, Disposable, l10n, LanguageStatusSeverity, StatusBarItem } from 'vscode';
import { createLanguageStatusItem, createStatusBarItem, getConfiguration } from './vscodeapi';
import { Command } from 'vscode-languageclient';
import { getDocumentSelector } from './utilities';

let _status: LanguageStatusItem | undefined;
let _statusBarItem: StatusBarItem | undefined;
let _currentScore: number | undefined;

export function registerLanguageStatusItem(id: string, name: string, command: string): Disposable {
    _status = createLanguageStatusItem(id, getDocumentSelector());
    _status.name = name;
    _status.text = name;
    _status.command = Command.create(l10n.t('Open logs'), command);

    _statusBarItem = createStatusBarItem(`${id}.score`);
    _statusBarItem.name = name;
    _statusBarItem.text = '$(checklist) Pylint';
    updateStatusBarVisibility();

    return {
        dispose: () => {
            _status?.dispose();
            _status = undefined;
            _statusBarItem?.dispose();
            _statusBarItem = undefined;
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

export function updateScore(score: number | undefined): void {
    if (score !== undefined && score !== _currentScore) {
        _currentScore = score;
        const scoreText = `Pylint: ${score.toFixed(2)}/10`;
        if (_status) {
            _status.text = scoreText;
            _status.detail = scoreText;
        }
        if (_statusBarItem) {
            _statusBarItem.text = `$(checklist) ${scoreText}`;
            _statusBarItem.tooltip = scoreText;
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
