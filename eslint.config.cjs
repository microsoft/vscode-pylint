const tsParser = require("@typescript-eslint/parser");
const tsPlugin = require("@typescript-eslint/eslint-plugin");

module.exports = [
    {
        files: ["src/**/*.ts"],
        ignores: ["out", "dist", "**/*.d.ts"],
        languageOptions: {
            ecmaVersion: 6,
            sourceType: "module",
            parser: tsParser,
        },
        plugins: {
            "@typescript-eslint": tsPlugin,
        },
        linterOptions: {
            reportUnusedDisableDirectives: "warn",
        },
        rules: {
            "@typescript-eslint/naming-convention": "warn",
            curly: "warn",
            eqeqeq: "warn",
            "no-throw-literal": "warn",
            semi: "warn",
        },
    },
    {
        files: ['build/setup*.js', 'build/normalize-package-lock*.js'],
        languageOptions: {
            ecmaVersion: 2022,
            sourceType: 'commonjs',
            globals: {
                __dirname: 'readonly',
                console: 'readonly',
                process: 'readonly',
            },
        },
        rules: {
            'no-unused-vars': 'error',
            'no-undef': 'error',
        },
    },
];
