#!/usr/bin/env node
'use strict';
// PostToolUse(Edit|Write): enforce layering with import-linter contracts declared in pyproject.toml
// (api > services > repositories > models > domain, pure domain, no HTTP below controllers, ...).
const { readInput, projectRoot, runGate, relativeToProject } = require('./lib/gate');

const input = readInput();
const file = (input && input.tool_input && input.tool_input.file_path) || '';
if (!file.endsWith('.py')) process.exit(0);

const project = projectRoot();
if (relativeToProject(file, project).startsWith('app/')) {
  runGate('ARCHITECTURE', 'uv', ['run', 'lint-imports'], { cwd: project, timeout: 60000 });
}
process.exit(0);
