#!/usr/bin/env node
'use strict';
// PreToolUse(Write|Edit|MultiEdit|Bash): merged Alembic migrations are append-only (NFR-05).
const fs = require('fs');
const path = require('path');
const { readInput, projectRoot, fail, relativeToProject } = require('./lib/gate');

const input = readInput();
if (!input || !input.tool_input) process.exit(0);
const project = projectRoot();

function registered() {
  try {
    return fs.readFileSync(path.join(project, 'migrations', 'MANIFEST.sha256'), 'utf8')
      .split('\n').filter((l) => l && !l.startsWith('#')).map((l) => l.split(/\s+/)[1]);
  } catch (_) { return []; }
}

const file = input.tool_input.file_path;
if (file) {
  const relative = relativeToProject(file, project);
  if (relative === 'migrations/MANIFEST.sha256') {
    fail('MIGRATION_IMMUTABILITY: do not edit the manifest by hand; run `uv run python -m scripts.migration_manifest append` after adding a new migration.');
  }
  const match = /^migrations\/(versions\/[^/]+\.py)$/.exec(relative);
  if (match && registered().includes(match[1])) {
    fail(`MIGRATION_IMMUTABILITY: ${relative} is a merged migration and is append-only. Add a NEW migration instead of editing it.`);
  }
  process.exit(0);
}

const command = input.tool_input.command || '';
const touchesVersions = /migrations\/(versions\/)?[^\s]*/.test(command) && /migrations\/versions/.test(command);
const mutating = /(^|[\s;&|])(rm|mv|sed\s+-i|truncate|git\s+rm|git\s+mv|git\s+checkout\s+--)\b/.test(command) || />\s*migrations\/versions/.test(command);
if (touchesVersions && mutating) {
  const names = registered().filter((name) => command.includes(path.basename(name)) || /migrations\/versions\/\*/.test(command));
  if (names.length) fail(`MIGRATION_IMMUTABILITY: this command would modify merged migrations (${names.join(', ')}). Migrations are append-only.`);
}
process.exit(0);
