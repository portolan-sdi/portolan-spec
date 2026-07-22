#!/usr/bin/env node
// The package.json version is the single source of truth for the profile
// version, and https://schemas.portolan-sdi.org/portolan/v<version>/schema.json is the
// single canonical schema URI. The schema for the current version must exist
// under json-schema/, and every Portolan schema URI — in the schema itself,
// the profile README, the examples, and the spec documents — must match the
// canonical one exactly, host included.
'use strict';

const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const repo = path.join(root, '..');
const version = require('../package.json').version;
const canonical = `https://schemas.portolan-sdi.org/portolan/v${version}/schema.json`;
// Any URL that mentions portolan and ends in a versioned schema.json is a
// Portolan schema URI candidate — this catches stale hosts (github.io, the
// apex domain) as well as stale versions. Extension schema URIs pinned in
// portolan-extensions.json also match (schemas.portolan-sdi.org contains
// "portolan"), so the pinned canonical URIs are exempted; anything else —
// a stale extension version or host — still fails.
const pattern = /https:\/\/[^\s"'`<>()\[\]]*portolan[^\s"'`<>()\[\]]*\/v\d+\.\d+\.\d+\/schema\.json/g;

const extensions = require('../portolan-extensions.json');
const pinned = new Set();
for (const [name, ext] of Object.entries(extensions)) {
  if (name.startsWith('$')) continue;
  for (const ver of Object.keys(ext.versions)) {
    pinned.add(`https://schemas.portolan-sdi.org/${name}/${ver}/schema.json`);
  }
}

let failed = false;
const fail = (msg) => { failed = true; console.error(`✗ ${msg}`); };

const schemaPath = path.join(root, 'json-schema', `v${version}`, 'schema.json');
if (!fs.existsSync(schemaPath)) {
  fail(`json-schema/v${version}/schema.json not found (package.json version is ${version})`);
}

const files = [
  schemaPath,
  path.join(root, 'README.md'),
  path.join(repo, 'README.md'),
  path.join(repo, 'specs', 'portolan', 'core.md'),
  path.join(repo, 'specs', 'portolan', 'formats.md'),
  ...fs.readdirSync(path.join(root, 'examples'))
    .filter((f) => f.endsWith('.json'))
    .map((f) => path.join(root, 'examples', f)),
];

for (const file of files) {
  if (!fs.existsSync(file)) continue;
  const rel = path.relative(repo, file);
  const text = fs.readFileSync(file, 'utf8');
  for (const match of text.matchAll(pattern)) {
    if (pinned.has(match[0])) continue;
    if (match[0] !== canonical) {
      const line = text.slice(0, match.index).split('\n').length;
      fail(`${rel}:${line} references ${match[0]}, expected ${canonical}`);
    }
  }
}

if (!failed) console.log(`✓ all Portolan schema URI references match ${canonical}`);
process.exit(failed ? 1 : 0);
