// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const { readFileSync } = require('node:fs');
const { createRequire } = require('node:module');
const path = require('node:path');
const { test } = require('node:test');
const { fileURLToPath } = require('node:url');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const sharedEntry = '../external/vscode-common-python-lsp/typescript/dist';

function load(file, bindings, globals = {}) {
    const filename = path.join(root, file);
    const module = { exports: {} };
    const nativeRequire = createRequire(filename);
    vm.runInNewContext(
        readFileSync(filename, 'utf8'),
        {
            module,
            exports: module.exports,
            require: (name) => (Object.hasOwn(bindings, name) ? bindings[name] : nativeRequire(name)),
            __dirname: path.dirname(filename),
            ...globals,
        },
        { filename },
    );
    return module.exports;
}

function launchedEnvironment(client, inherited) {
    return JSON.parse(
        execFileSync(process.execPath, ['-e', 'process.stdout.write(JSON.stringify(process.env))'], {
            env: { ...inherited, ...client.serverOptions.options.env },
            encoding: 'utf8',
        }),
    );
}

async function fixture({
    failRegistration,
    failStart = false,
    failTrace = false,
    inherited = { VSCODE_PYLINT_LINT_ON_CHANGE: 'inherited', KEEP: 'unchanged' },
    platform = process.platform,
} = {}) {
    const environment = { ...inherited };
    const scores = [];
    const clients = [];
    const configCalls = [];
    const subscriptions = [];
    let lintOnChange = false;
    let envFileVars = {};
    let activation;
    let visibilityListener;
    let legacyCalls = 0;
    let visibilityCalls = 0;
    let deactivations = 0;
    const ui = { dispose() {} };
    const configuration = { dispose() {} };
    const toolConfig = load(
        'out/common/constants.js',
        { '../../external/vscode-common-python-lsp/typescript/dist': { resolveExtensionRoot: () => root } },
        { __dirname: path.join(root, 'out', 'common') },
    ).PYLINT_TOOL_CONFIG;
    const extension = load(
        'out/extension.js',
        {
            vscode: {},
            [sharedEntry]: {
                loadServerDefaults: () => ({ name: 'Pylint', module: 'pylint' }),
                activateToolExtension: (context, options) => {
                    assert.equal(context.subscriptions, subscriptions);
                    assert.equal(options.toolConfig.workspaceEnablementSetting, 'enabled');
                    activation = options;
                    return {
                        async deactivate() {
                            deactivations++;
                        },
                    };
                },
                getConfiguration: (...args) => {
                    configCalls.push(args);
                    return {
                        get(key, fallback) {
                            assert.equal(key, 'lintOnChange');
                            assert.equal(fallback, false);
                            return lintOnChange;
                        },
                    };
                },
                onDidChangeConfiguration: (listener) => {
                    visibilityListener = listener;
                    return configuration;
                },
            },
            './common/constants': { EXTENSION_ROOT_DIR: root, PYLINT_TOOL_CONFIG: toolConfig },
            './common/settings': {
                logLegacySettings() {
                    legacyCalls++;
                },
            },
            './common/status': {
                registerScoreStatusBar: () => ui,
                updateScore: (...args) => scores.push(args),
                updateStatusBarVisibility() {
                    visibilityCalls++;
                },
            },
        },
        { process: { env: environment, platform } },
    );
    await extension.activate({ subscriptions });
    assert.equal(legacyCalls, 1);
    assert.deepEqual(subscriptions, [ui, configuration]);
    await visibilityListener({ affectsConfiguration: (key) => key === 'pylint.showScoreInStatusBar' });
    assert.equal(visibilityCalls, 1);

    // Exercise the built pinned server lifecycle with only VS Code/transport boundaries mocked.
    class Client {
        constructor(_id, _name, serverOptions, clientOptions) {
            this.serverOptions = serverOptions;
            this.clientOptions = clientOptions;
            this.handlers = new Map();
            this.registrations = [];
            this.state = 1;
            clients.push(this);
        }
        onNotification(method, handler) {
            assert.equal(this.started, undefined, 'notifications must be registered before start');
            if (this.registrations.length + 1 === failRegistration) {
                throw new Error('registration failed');
            }
            this.handlers.set(method, handler);
            const registration = {
                disposals: 0,
                dispose: () => {
                    registration.disposals++;
                    this.handlers.delete(method);
                },
            };
            this.registrations.push(registration);
            return registration;
        }
        async start() {
            this.started = true;
            this.handlers.get('pylint/lintingStarted')({ uri: 'file:///active.py' });
            this.handlers.get('pylint/score')({ uri: 'file:///active.py', score: 8.5 });
            this.handlers.get('pylint/lintingFailed')({ uri: 'file:///active.py' });
            if (failStart) {
                throw new Error('start failed');
            }
            this.state = 2;
        }
        async setTrace() {
            if (failTrace) {
                throw new Error('trace failed');
            }
        }
        onDidChangeState() {
            return { dispose() {} };
        }
        async stop() {
            this.state = 1;
        }
        async dispose() {
            this.disposed = true;
        }
    }

    const server = load(
        'external/vscode-common-python-lsp/typescript/dist/server.js',
        {
            vscode: {
                env: { logLevel: 1 },
                l10n: { t: (message) => message },
                LanguageStatusSeverity: { Information: 1, Error: 3 },
                Uri: {
                    file: (fsPath) => ({ fsPath }),
                    parse: (uri) => ({ fsPath: fileURLToPath(uri) }),
                },
            },
            'vscode-languageclient': { State: { Stopped: 1, Running: 2 } },
            'vscode-languageclient/node': { LanguageClient: Client, RevealOutputChannelOn: { Never: 0 } },
            './envFile': { getEnvFileVars: async () => envFileVars },
            './logging': { traceInfo() {}, traceError() {}, traceVerbose() {} },
            './settings': { getGlobalSettings: async () => ({ futureWireField: 'preserved' }) },
            './status': { updateStatus() {} },
            './utilities': { getDocumentSelector: () => [], getLSClientTraceLevel: () => 0 },
            './vscodeapi': { getWorkspaceFolder: () => ({ uri: { fsPath: root } }) },
        },
        { process: { env: environment, platform } },
    );
    const settings = {
        workspace: new URL('file:///C:/workspace').href,
        cwd: root,
        interpreter: ['python'],
        importStrategy: 'useBundled',
        showNotifications: 'off',
        // Deliberately different from the unscoped configuration.
        lintOnChange: true,
    };
    const options = {
        settings,
        extensionSettings: [settings],
        serverId: 'pylint',
        serverName: 'Pylint',
        outputChannel: { logLevel: 1 },
        toolConfig: activation.toolConfig,
        hooks: activation.hooks,
        pythonProvider: { getInterpreterDetails() {}, async getDebuggerPath() {} },
    };
    return {
        extension,
        server,
        options,
        scores,
        clients,
        configCalls,
        environment,
        setLintOnChange(value) {
            lintOnChange = value;
        },
        setEnvFile(value) {
            envFileVars = value;
        },
        get deactivations() {
            return deactivations;
        },
    };
}

test('facade activation retains extension-owned UI and delegates deactivation', async () => {
    const f = await fixture();
    await f.extension.deactivate();
    await f.extension.deactivate();
    assert.equal(f.deactivations, 1);
});

test('each launch re-reads the unscoped setting without mutating inherited env; .env still wins', async () => {
    const f = await fixture();
    const first = await f.server.createServer({ ...f.options, initializationOptions: {} });
    assert.equal(Object.hasOwn(launchedEnvironment(first, f.environment), 'VSCODE_PYLINT_LINT_ON_CHANGE'), false);
    f.setLintOnChange(true);
    const second = await f.server.createServer({ ...f.options, initializationOptions: {} });
    assert.equal(second.serverOptions.options.env.VSCODE_PYLINT_LINT_ON_CHANGE, '1');
    f.setLintOnChange(false);
    f.setEnvFile({ VSCODE_PYLINT_LINT_ON_CHANGE: 'from-env-file' });
    const third = await f.server.createServer({ ...f.options, initializationOptions: {} });
    assert.equal(third.serverOptions.options.env.VSCODE_PYLINT_LINT_ON_CHANGE, 'from-env-file');
    f.setEnvFile({ VSCODE_PYLINT_LINT_ON_CHANGE: '' });
    const fourth = await f.server.createServer({ ...f.options, initializationOptions: {} });
    assert.equal(fourth.serverOptions.options.env.VSCODE_PYLINT_LINT_ON_CHANGE, '');
    assert.notEqual(first.serverOptions.options.env, second.serverOptions.options.env);
    assert.deepEqual(f.environment, { VSCODE_PYLINT_LINT_ON_CHANGE: 'inherited', KEEP: 'unchanged' });
    assert.deepEqual(
        f.configCalls.map((args) => Array.from(args)),
        Array(4).fill(['pylint']),
    );
});

test('Windows launches remove inherited casing aliases and retain later env-file overrides', async () => {
    const inherited = {
        vscode_pylint_lint_on_change: 'lower',
        Vscode_Pylint_Lint_On_Change: 'mixed',
        KEEP: 'unchanged',
    };
    const f = await fixture({ inherited, platform: 'win32' });
    const values = (client) =>
        Object.entries(launchedEnvironment(client, f.environment))
            .filter(([key]) => key.toLowerCase() === 'vscode_pylint_lint_on_change')
            .map(([, value]) => value);

    const disabled = await f.server.createServer({ ...f.options, initializationOptions: {} });
    assert.deepEqual(values(disabled), []);
    f.setLintOnChange(true);
    const enabled = await f.server.createServer({ ...f.options, initializationOptions: {} });
    assert.ok(values(enabled).length > 0);
    assert.ok(values(enabled).every((value) => value === '1'));
    f.setLintOnChange(false);
    f.setEnvFile({ VSCODE_PYLINT_LINT_ON_CHANGE: 'env-file' });
    const overridden = await f.server.createServer({ ...f.options, initializationOptions: {} });
    assert.ok(values(overridden).length > 0);
    assert.ok(values(overridden).every((value) => value === 'env-file'));
    f.setEnvFile({ VSCODE_PYLINT_LINT_ON_CHANGE: '' });
    const empty = await f.server.createServer({ ...f.options, initializationOptions: {} });
    assert.ok(values(empty).length > 0);
    assert.ok(values(empty).every((value) => value === ''));
    assert.deepEqual(f.environment, inherited);
});

test('new clients receive initial score/status notifications and retire registrations on replacement/shutdown', async () => {
    const f = await fixture();
    const first = await f.server.restartServer(f.options);
    assert.equal(first.client, f.clients[0]);
    assert.deepEqual(f.scores, [
        ['file:///active.py', undefined],
        ['file:///active.py', 8.5],
        ['file:///active.py', -1],
    ]);
    assert.equal(first.client.clientOptions.initializationOptions.settings[0], f.options.settings);
    const controller = new AbortController();
    const second = await f.server.restartServer(
        {
            ...f.options,
            signal: controller.signal,
            onOldClientStopped: () => first.disposables.forEach((disposable) => disposable.dispose()),
        },
        first.client,
    );
    assert.notEqual(second.client, first.client);
    assert.equal(first.client.handlers.size, 0);
    assert.equal(second.client.handlers.size, 3);
    assert.equal(f.scores.length, 6);
    controller.abort();
    second.disposables.forEach((disposable) => disposable.dispose());
    assert.equal(second.client.handlers.size, 0);
    for (const client of f.clients) {
        assert.deepEqual(
            client.registrations.map((registration) => registration.disposals),
            [1, 1, 1],
        );
    }
});

for (const failure of [{ failRegistration: 2 }, { failStart: true }, { failTrace: true }]) {
    test(`failed setup/start/trace releases every Pylint registration: ${JSON.stringify(failure)}`, async () => {
        const f = await fixture(failure);
        const result = await f.server.restartServer(f.options);
        assert.equal(result.client, undefined);
        assert.equal(f.clients[0].disposed, true);
        assert.equal(f.clients[0].handlers.size, 0);
        assert.ok(f.clients[0].registrations.every((registration) => registration.disposals === 1));
    });
}

for (const hasToolchain of [false, true]) {
    test(`shared build always rebuilds existing dist (toolchain present: ${hasToolchain})`, () => {
        const calls = [];
        const npmCli = path.join(root, 'npm with spaces', 'npm-cli.js');
        load(
            'build/postinstall.js',
            {
                'node:fs': { existsSync: (file) => !file.endsWith('typescript') || hasToolchain },
                'node:child_process': {
                    execFileSync: (command, args, options) => calls.push({ command, args: Array.from(args), options }),
                },
            },
            { process: { execPath: process.execPath, env: { npm_execpath: npmCli } } },
        );
        assert.deepEqual(
            calls.map((call) => call.args.slice(1)),
            hasToolchain
                ? [['run', 'build']]
                : [
                      ['ci', '--include=dev'],
                      ['run', 'build'],
                  ],
        );
        for (const call of calls) {
            assert.equal(call.command, process.execPath);
            assert.equal(call.args[0], npmCli);
            assert.equal(call.options.cwd, path.join(root, 'external', 'vscode-common-python-lsp', 'typescript'));
        }
    });
}
