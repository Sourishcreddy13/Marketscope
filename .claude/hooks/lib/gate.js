'use strict';
// Shared helpers for blocking hooks. Claude Code treats exit code 2 as "block and show stderr to the agent".
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

function readInput() {
  try { return JSON.parse(fs.readFileSync(0, 'utf8')); } catch (_) { return null; }
}

function projectRoot(start = __dirname) {
  let current = path.resolve(start);
  for (;;) {
    if (fs.existsSync(path.join(current, '.claude')) && fs.existsSync(path.join(current, 'pyproject.toml'))) return current;
    const parent = path.dirname(current);
    if (parent === current) return process.cwd();
    current = parent;
  }
}

function fail(message) {
  process.stderr.write(`${message}\n`);
  process.exit(2);
}

/**
 * Run a gate command. A non-zero exit, a timeout, or a command that cannot be started all BLOCK
 * (fail closed): an unavailable quality gate must never read as a passing one.
 */
function runGate(label, command, args, options = {}) {
  const rendered = [command, ...args].join(' ');
  const result = spawnSync(command, args, {
    cwd: options.cwd, encoding: 'utf8', timeout: options.timeout || 120000, env: process.env,
  });
  if (result.error) {
    fail(`${label}_GATE_UNAVAILABLE: could not run \`${rendered}\`: ${result.error.message}. Install the tool or fix PATH; the gate fails closed.`);
  }
  if (result.status !== 0) {
    const output = `${result.stdout || ''}${result.stderr || ''}`.trim().split('\n').slice(-40).join('\n');
    fail(`${label}_GATE_FAILED: \`${rendered}\` exited with status ${result.status}.\n${output}`);
  }
}

function relativeToProject(file, project) {
  return path.relative(project, path.resolve(project, file)).split(path.sep).join('/');
}

module.exports = { readInput, projectRoot, fail, runGate, relativeToProject };
