#!/usr/bin/env node
'use strict';
// PostToolUse(Edit|Write): type-check / build after an edit. Failures block the agent (exit 2).
const path = require('path');
const { readInput, projectRoot, runGate, relativeToProject } = require('./lib/gate');

const input = readInput();
const file = (input && input.tool_input && input.tool_input.file_path) || '';
if (!file) process.exit(0);

const project = projectRoot();
const relative = relativeToProject(file, project);
const ext = path.extname(relative).toLowerCase();

if (ext === '.py' && relative.startsWith('app/')) {
  runGate('TYPECHECK', 'uv', ['run', 'mypy', 'app'], { cwd: project });
} else if ((ext === '.ts' || ext === '.tsx') && relative.startsWith('frontend/src/')) {
  runGate('TYPECHECK', 'npm', ['--prefix', 'frontend', 'run', 'build'], { cwd: project, timeout: 180000 });
}
process.exit(0);
