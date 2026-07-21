#!/usr/bin/env node
// The package.json version is the single source of truth for the profile
// version. The schema for the current version must exist under json-schema/,
// and every reference to a versioned Portolan schema URI — in the schema
// itself, the profile README, the examples, and the spec documents — must
// match it.
'use strict';

const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const repo = path.join(root, '..');
const version = require('../package.json').version;
const expected = `v${version}`;
const pattern = /portolan\/(v\d+\.\d+\.\d+)\/schema\.json/g;

let failed = false;
const fail = (msg) => { failed = true; console.error(`✗ ${msg}`); };

const schemaPath = path.join(root, 'json-schema', expected, 'schema.json');
if (!fs.existsSync(schemaPath)) {
  fail(`json-schema/${expected}/schema.json not found (package.json version is ${version})`);
}

const files = [
  schemaPath,
  path.join(root, 'README.md'),
  path.join(repo, 'README.md'),
  path.join(repo, 'specs', 'portolan', 'core.md'),
  ...fs.readdirSync(path.join(root, 'examples'))
    .filter((f) => f.endsWith('.json'))
    .map((f) => path.join(root, 'examples', f)),
];

for (const file of files) {
  if (!fs.existsSync(file)) continue;
  const rel = path.relative(repo, file);
  const text = fs.readFileSync(file, 'utf8');
  for (const match of text.matchAll(pattern)) {
    if (match[1] !== expected) {
      const line = text.slice(0, match.index).split('\n').length;
      fail(`${rel}:${line} references ${match[1]}, expected ${expected}`);
    }
  }
}

if (!failed) console.log(`✓ all Portolan schema URI references match ${expected}`);
process.exit(failed ? 1 : 0);
