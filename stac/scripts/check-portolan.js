#!/usr/bin/env node
// Validates every example directly against the Portolan schema. Items never
// declare the schema URI in stac_extensions (they inherit conformance from
// their collection), so stac-node-validator's schemaMap never applies the
// schema's item branch to them — this script applies the schema to every
// example regardless of declaration, the way the Portolan validator does.
'use strict';

const fs = require('fs');
const path = require('path');
const Ajv = require('ajv');

const version = require('../package.json').version;
const schemaPath = path.join(__dirname, '..', 'json-schema', `v${version}`, 'schema.json');
const examplesDir = path.join(__dirname, '..', 'examples');

const ajv = new Ajv({ allErrors: true, strict: false });
const validate = ajv.compile(JSON.parse(fs.readFileSync(schemaPath, 'utf8')));

let failed = false;

const names = fs.readdirSync(examplesDir).filter((f) => f.endsWith('.json')).sort();
for (const name of names) {
  const doc = JSON.parse(fs.readFileSync(path.join(examplesDir, name), 'utf8'));
  const errors = [];

  if (!validate(doc)) {
    errors.push(...validate.errors.map((e) => `${e.instancePath || '/'} ${e.message}`));
  }

  // The schema deliberately delegates multihash validity to tooling; the
  // examples must still be valid exemplars, so enforce well-formed sha2-256
  // multihashes here.
  for (const [key, asset] of Object.entries(doc.assets || {})) {
    const checksum = asset['file:checksum'];
    if (typeof checksum === 'string' && !/^1220[0-9a-f]{64}$/.test(checksum)) {
      errors.push(`assets/${key}: file:checksum is not a well-formed sha2-256 multihash (1220 + 64 hex chars)`);
    }
  }

  if (errors.length) {
    failed = true;
    console.error(`✗ ${name}`);
    for (const e of errors) console.error(`    ${e}`);
  } else {
    console.log(`✓ ${name}`);
  }
}

process.exit(failed ? 1 : 0);
