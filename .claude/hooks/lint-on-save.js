#!/usr/bin/env node
'use strict';
// PostToolUse(Edit|Write): lint the edited file. Non-zero exit blocks the agent (exit 2) with the failing command.
const path = require('path');
const { readInput, projectRoot, runGate, relativeToProject } = require('./lib/gate');

const input = readInput();
const file = (input && input.tool_input && input.tool_input.file_path) || '';
if (!file) process.exit(0);

const project = projectRoot();
const relative = relativeToProject(file, project);
const ext = path.extname(relative).toLowerCase();
const pythonScopes = ['app/', 'tests/', 'scripts/', 'migrations/'];

if (ext === '.py' && pythonScopes.some((scope) => relative.startsWith(scope))) {
  runGate('LINT', 'uv', ['run', 'ruff', 'check', relative], { cwd: project });
} else if ((ext === '.ts' || ext === '.tsx') && relative.startsWith('frontend/')) {
  runGate('LINT', 'npm', ['--prefix', 'frontend', 'run', 'lint', '--', relative.replace(/^frontend\//, '')], { cwd: project });
}
process.exit(0);
