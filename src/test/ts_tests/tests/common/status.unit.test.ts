// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import { assert } from 'chai';
import * as sinon from 'sinon';
import { window } from 'vscode';
import { registerLanguageStatusItem, updateScore } from '../../../../common/status';
import * as vscodeapi from '../../../../common/vscodeapi';
import * as utilities from '../../../../common/utilities';

suite('Status Bar Score Display Tests', () => {
    let mockStatusBarItem: {
        text: string;
        tooltip: string | undefined;
        name: string | undefined;
        show: sinon.SinonStub;
        hide: sinon.SinonStub;
        dispose: sinon.SinonStub;
    };
    let disposable: { dispose: () => void };

    setup(() => {
        mockStatusBarItem = {
            text: '',
            tooltip: undefined,
            name: undefined,
            show: sinon.stub(),
            hide: sinon.stub(),
            dispose: sinon.stub(),
        };

        const mockLanguageStatusItem = {
            text: '',
            name: '',
            command: undefined,
            severity: 0,
            busy: false,
            detail: undefined,
            dispose: sinon.stub(),
            selector: [],
        };

        sinon.stub(vscodeapi, 'createStatusBarItem').returns(mockStatusBarItem as any);
        sinon.stub(vscodeapi, 'createLanguageStatusItem').returns(mockLanguageStatusItem as any);
        sinon.stub(vscodeapi, 'getConfiguration').returns({
            get: sinon.stub().returns(true),
        } as any);
        sinon.stub(vscodeapi, 'onDidChangeActiveTextEditor').returns({ dispose: sinon.stub() } as any);
        sinon.stub(utilities, 'getDocumentSelector').returns([]);

        disposable = registerLanguageStatusItem('pylint', 'Pylint', 'pylint.showLogs');
    });

    teardown(() => {
        disposable.dispose();
        sinon.restore();
    });

    test('updateScore with numeric score updates status bar text', () => {
        const testUri = 'file:///test/file.py';
        sinon.replaceGetter(
            window,
            'activeTextEditor',
            () =>
                ({
                    document: { uri: { toString: () => testUri } },
                }) as any,
        );

        updateScore(testUri, 8.5);

        assert.strictEqual(mockStatusBarItem.text, '$(checklist) Pylint: 8.50/10');
        assert.strictEqual(mockStatusBarItem.tooltip, 'Pylint: 8.50/10');
    });

    test('updateScore with undefined shows loading state for active document', () => {
        const testUri = 'file:///test/file.py';
        sinon.replaceGetter(
            window,
            'activeTextEditor',
            () =>
                ({
                    document: { uri: { toString: () => testUri } },
                }) as any,
        );

        updateScore(testUri, undefined);

        assert.strictEqual(mockStatusBarItem.text, '$(sync~spin) Pylint');
        assert.isString(mockStatusBarItem.tooltip);
        assert.include(mockStatusBarItem.tooltip as string, 'progress');
    });

    test('updateScore with -1 shows error state', () => {
        const testUri = 'file:///test/file.py';
        sinon.replaceGetter(
            window,
            'activeTextEditor',
            () =>
                ({
                    document: { uri: { toString: () => testUri } },
                }) as any,
        );

        updateScore(testUri, -1);

        assert.strictEqual(mockStatusBarItem.text, '$(error) Pylint');
        assert.isString(mockStatusBarItem.tooltip);
        assert.include(mockStatusBarItem.tooltip as string, 'failed');
    });

    test('updateScore does not show loading for non-active document', () => {
        const activeUri = 'file:///test/active.py';
        const otherUri = 'file:///test/other.py';
        sinon.replaceGetter(
            window,
            'activeTextEditor',
            () =>
                ({
                    document: { uri: { toString: () => activeUri } },
                }) as any,
        );

        // Set initial state
        updateScore(activeUri, 7.0);
        const textBefore = mockStatusBarItem.text;

        // Update a different document with undefined (loading) — should not change display
        updateScore(otherUri, undefined);

        assert.strictEqual(mockStatusBarItem.text, textBefore);
    });

    test('updateScore with zero score displays correctly', () => {
        const testUri = 'file:///test/file.py';
        sinon.replaceGetter(
            window,
            'activeTextEditor',
            () =>
                ({
                    document: { uri: { toString: () => testUri } },
                }) as any,
        );

        updateScore(testUri, 0.0);

        assert.strictEqual(mockStatusBarItem.text, '$(checklist) Pylint: 0.00/10');
        assert.strictEqual(mockStatusBarItem.tooltip, 'Pylint: 0.00/10');
    });
});
