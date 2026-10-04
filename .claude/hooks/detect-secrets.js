#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');

// Secret patterns: [label, RegExp] — all use the global flag for matchAll
const patterns = [
  ['AWS Access Key',     /AKIA[0-9A-Z]{16}/g],
  ['GitHub Token',       /gh[pousr]_[^\s"'`]{1,}/g],
  ['Anthropic Key',      /sk-ant-[^\s"'`]{1,}/g],
  ['OpenAI Key',         /sk-[a-zA-Z0-9]{20,}/g],
  ['Slack Token',        /xox[baprs]-[^\s"'`]{1,}/g],
  ['Private Key Block',  /-----BEGIN .* PRIVATE KEY-----/g],
  ['Connection String',  /:\/\/[^:]+:[^@]+@/g],
  ['SSN',                /\b\d{3}-\d{2}-\d{4}\b/g],
];

function redact(value) {
  if (value.length <= 10) {
    return value.substring(0, 4) + '...';
  }
  return value.substring(0, 10) + '...';
}

try {
  const input = JSON.parse(fs.readFileSync('/dev/stdin', 'utf8'));
  const filePath = input.tool_input && input.tool_input.file_path;

  if (!filePath) {
    process.exit(0);
  }

  const resolvedFilePath = path.resolve(filePath);

  // Markdown is scanned too: agent instructions, skills and CLAUDE.md are a prime place for pasted credentials.
  // Skip .env.example
  const basename = path.basename(filePath);
  if (basename === '.env.example') {
    process.exit(0);
  }

  // Skip files in hooks/, evals/, or templates/ directories
  const normalised = resolvedFilePath.replace(/\\/g, '/');
  if (
    normalised.includes('/hooks/') ||
    normalised.includes('/evals/') ||
    normalised.includes('/templates/')
  ) {
    process.exit(0);
  }

  // Scan what is about to be written (PreToolUse) as well as what is already on disk (PostToolUse).
  const toolInput = input.tool_input || {};
  const incoming = [toolInput.content, toolInput.new_string]
    .concat(Array.isArray(toolInput.edits) ? toolInput.edits.map((e) => e && e.new_string) : [])
    .filter((v) => typeof v === 'string')
    .join('\n');
  let onDisk = '';
  try {
    onDisk = fs.readFileSync(resolvedFilePath, 'utf8');
  } catch (_) {
    // File does not exist yet: the incoming text is all there is to scan.
  }
  const content = `${onDisk}\n${incoming}`;

  const findings = [];

  for (const [label, pattern] of patterns) {
    const matches = Array.from(content.matchAll(pattern));
    for (const match of matches) {
      findings.push({ label, value: redact(match[0]) });
    }
  }

  if (findings.length > 0) {
    const lines = [`BLOCKED: Potential secrets detected in ${filePath}:`];
    for (const { label, value } of findings) {
      lines.push(`  - ${label}: ${value}`);
    }
    lines.push('Fix: Move secrets to .env and reference via os.environ.get(). Never hardcode credentials.');
    process.stdout.write(lines.join('\n') + '\n');
    process.exit(2);
  }
} catch (_) {
  // Silent exit — stderr output triggers "hook error" in Claude Code
}

process.exit(0);
