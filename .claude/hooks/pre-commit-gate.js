#!/usr/bin/env node
'use strict';
// PreToolUse(Bash) on `git commit`: block commits that break the import-linter architecture contracts
// or the append-only migration manifest.
const { readInput, projectRoot, runGate } = require('./lib/gate');

const input = readInput();
const command = (input && input.tool_input && input.tool_input.command) || '';
if (!/\bgit\s+commit\b/.test(command)) process.exit(0);

const project = projectRoot();
runGate('ARCHITECTURE', 'uv', ['run', 'lint-imports'], { cwd: project, timeout: 60000 });
runGate('MIGRATION_IMMUTABILITY', 'uv', ['run', 'python', '-m', 'scripts.migration_manifest', 'check'], { cwd: project, timeout: 60000 });
process.exit(0);
