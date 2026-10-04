#!/usr/bin/env node
'use strict';
// TaskCompleted: a task may only be marked complete when the MarketScope architecture contracts hold.
// Understands the real layout (backend `app/`, frontend `frontend/src/`) and fails closed: if the
// expected hierarchy is missing, or the gate cannot run, completion is blocked rather than waved through.
const fs = require('fs');
const path = require('path');
const { readInput, projectRoot, runGate, fail } = require('./lib/gate');

readInput();
const project = projectRoot();
for (const required of ['app', 'frontend/src']) {
  if (!fs.existsSync(path.join(project, required))) {
    fail(`TASK_COMPLETION_BLOCKED: expected source directory \`${required}\` is missing, so the architecture check cannot run.`);
  }
}
runGate('ARCHITECTURE', 'uv', ['run', 'lint-imports'], { cwd: project, timeout: 60000 });
process.stdout.write('Architecture check: PASS (import-linter contracts for app/ kept)\n');
process.exit(0);
