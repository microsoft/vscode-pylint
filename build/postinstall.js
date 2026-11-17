// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

const { existsSync } = require('node:fs');
const { execFileSync } = require('node:child_process');
const path = require('node:path');

const pkgDir = path.resolve(__dirname, '..', 'external', 'vscode-common-python-lsp', 'typescript');
if (!existsSync(path.join(pkgDir, 'package.json'))) {
    throw new Error('Shared submodule missing. Run git submodule update --init --recursive before building.');
}
if (!process.env.npm_execpath) {
    throw new Error('Run this build using npm run build:shared.');
}

function npm(args) {
    execFileSync(process.execPath, [process.env.npm_execpath, ...args], { cwd: pkgDir, stdio: 'inherit' });
}

if (!existsSync(path.join(pkgDir, 'node_modules', 'typescript'))) {
    npm(['ci', '--include=dev']);
}

// Always rebuild: an existing dist directory may belong to a different gitlink.
npm(['run', 'build']);
