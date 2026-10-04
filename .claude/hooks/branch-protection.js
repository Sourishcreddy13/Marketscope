#!/usr/bin/env node
'use strict';
// PreToolUse(Bash): technical enforcement of the PR-Only Merge Rule.
// Agents may commit and push FEATURE branches. They may not commit on, push to, force-push, or merge
// into a protected branch, and may not bypass hooks. Merges to main happen in the PR UI (or by a human
// with `git merge --no-ff`). Set PROTECTED_BRANCHES (comma separated) to extend the default main,master.
const { spawnSync } = require('child_process');
const { readInput, projectRoot, fail } = require('./lib/gate');

const input = readInput();
const command = (input && input.tool_input && input.tool_input.command) || '';
if (!/\bgit\b/.test(command)) process.exit(0);

const protectedBranches = new Set(['main', 'master', ...(process.env.PROTECTED_BRANCHES || '').split(',').map((s) => s.trim()).filter(Boolean)]);
const project = projectRoot();

function currentBranch() {
  const result = spawnSync('git', ['rev-parse', '--abbrev-ref', 'HEAD'], { cwd: project, encoding: 'utf8' });
  return result.status === 0 ? result.stdout.trim() : null;
}

const isProtectedRef = (token) => {
  const ref = token.replace(/^\+/, '').replace(/^refs\/heads\//, '');
  const parts = ref.split(':');
  return parts.some((part) => protectedBranches.has(part.replace(/^origin\//, '').replace(/^refs\/heads\//, '')));
};

const segments = command.split(/&&|\|\||;|\n|\|/).map((s) => s.trim()).filter(Boolean);
let branch = currentBranch();
let reason = null;

for (const segment of segments) {
  const tokens = segment.split(/\s+/);
  const gitIndex = tokens.indexOf('git');
  if (gitIndex === -1) continue;
  const sub = tokens[gitIndex + 1];
  const args = tokens.slice(gitIndex + 2);

  if ((sub === 'checkout' || sub === 'switch') && args.length) {
    const target = args.filter((a) => !a.startsWith('-')).pop();
    if (target) branch = target;
    continue;
  }
  if (args.includes('--no-verify') || (sub === 'commit' && args.includes('-n'))) {
    reason = `\`git ${sub}\` with --no-verify bypasses the quality gates.`; break;
  }
  if (sub === 'push') {
    const flags = args.filter((a) => a.startsWith('-'));
    const refs = args.filter((a) => !a.startsWith('-'));
    if (flags.some((f) => /^(-f|--force|--force-with-lease.*|--mirror|--delete|-d)$/.test(f))) { reason = 'force/delete pushes are not allowed.'; break; }
    if (refs.some(isProtectedRef)) { reason = `pushing to a protected branch is not allowed; push a feature branch and open a PR.`; break; }
    if (refs.length <= 1 && branch && protectedBranches.has(branch)) { reason = `the current branch "${branch}" is protected; create a feature branch and open a PR.`; break; }
  }
  if (['commit', 'merge', 'rebase', 'cherry-pick', 'revert'].includes(sub) && branch && protectedBranches.has(branch)) {
    reason = `direct \`git ${sub}\` on protected branch "${branch}" is not allowed; work on a feature branch and open a PR.`; break;
  }
  if (sub === 'reset' && args.includes('--hard') && branch && protectedBranches.has(branch)) {
    reason = `\`git reset --hard\` on protected branch "${branch}" is not allowed.`; break;
  }
}

if (reason) fail(`PR_ONLY_MERGE_RULE: blocked. ${reason}`);
process.exit(0);
