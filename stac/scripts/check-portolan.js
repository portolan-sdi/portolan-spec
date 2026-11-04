#!/usr/bin/env node
// Validates every example directly against the Portolan schema. Items never
// declare the schema URI in stac_extensions (they inherit conformance from
// their collection), so stac-node-validator's schemaMap never applies the
// schema's item branch to them — this script applies the schema to every
// example regardless of declaration, the way the Portolan validator does.
// It also applies the pinned portolan-sdi extension schemas (fetched into
// .schema-cache/ by fetch-extension-schemas.js) to every example that
// declares them.
'use strict';

const fs = require('fs');
const path = require('path');
const Ajv = require('ajv');

const version = require('../package.json').version;
const schemaPath = path.join(__dirname, '..', 'json-schema', `v${version}`, 'schema.json');
const examplesDir = path.join(__dirname, '..', 'examples');

const ajv = new Ajv({ allErrors: true, strict: false });
const validate = ajv.compile(JSON.parse(fs.readFileSync(schemaPath, 'utf8')));

const extensions = require('../portolan-extensions.json');
const extValidators = {};
for (const [name, ext] of Object.entries(extensions)) {
  if (name.startsWith('$')) continue;
  for (const ver of Object.keys(ext.versions)) {
    const uri = `https://schemas.portolan-sdi.org/${name}/${ver}/schema.json`;
    const cached = path.join(__dirname, '..', '.schema-cache', name, ver, 'schema.json');
    if (!fs.existsSync(cached)) {
      console.error(`✗ ${name} ${ver}: schema not cached — run \`node scripts/fetch-extension-schemas.js\``);
      process.exit(1);
    }
    extValidators[uri] = {
      label: `${name} ${ver}`,
      validate: ajv.compile(JSON.parse(fs.readFileSync(cached, 'utf8'))),
    };
  }
}

// The classification v2.0.0 schema checks classes only under raster:bands,
// never under STAC 1.1 bands, so apply its class fields here, plus the
// Portolan class rules (PORTO-FMT-052, PORTO-FMT-057).
const classificationUri = 'https://stac-extensions.github.io/classification/v2.0.0/schema.json';
const classificationCache = path.join(
  __dirname, '..', '.schema-cache', 'stac-extensions', 'classification', 'v2.0.0', 'schema.json',
);
let validateClassFields = null;
if (fs.existsSync(classificationCache)) {
  ajv.addSchema(JSON.parse(fs.readFileSync(classificationCache, 'utf8')));
  validateClassFields = ajv.getSchema(`${classificationUri}#/definitions/fields`);
}

function bandClassErrors(doc) {
  const errors = [];
  const groups = { assets: doc.assets || {}, item_assets: doc.item_assets || {} };
  for (const [group, assets] of Object.entries(groups)) {
    for (const [key, asset] of Object.entries(assets)) {
      (asset.bands || []).forEach((band, i) => {
        const where = `${group}/${key}/bands/${i}`;
        const classes = band['classification:classes'];
        if (classes === undefined) return;
        if (!validateClassFields) {
          errors.push(`${where}: classification schema not cached, run \`node scripts/fetch-extension-schemas.js\``);
          return;
        }
        if (!validateClassFields(band)) {
          errors.push(...validateClassFields.errors.map((e) => `[classification] ${where}${e.instancePath} ${e.message}`));
        }
        if (!Array.isArray(classes)) return;
        classes.forEach((cls, j) => {
          if (typeof cls.title !== 'string' || !cls.title) {
            errors.push(`${where}/classification:classes/${j}: class has no title (PORTO-FMT-052)`);
          }
          if (cls.nodata === true && cls.value !== band.nodata) {
            errors.push(`${where}/classification:classes/${j}: nodata class value ${cls.value} is not the band nodata ${band.nodata} (PORTO-FMT-057)`);
          }
        });
      });
    }
  }
  return errors;
}

let failed = false;

const names = fs.readdirSync(examplesDir).filter((f) => f.endsWith('.json')).sort();
for (const name of names) {
  const doc = JSON.parse(fs.readFileSync(path.join(examplesDir, name), 'utf8'));
  const errors = [];

  if (!validate(doc)) {
    errors.push(...validate.errors.map((e) => `${e.instancePath || '/'} ${e.message}`));
  }

  for (const uri of doc.stac_extensions || []) {
    const ext = extValidators[uri];
    if (ext && !ext.validate(doc)) {
      errors.push(...ext.validate.errors.map((e) => `[${ext.label}] ${e.instancePath || '/'} ${e.message}`));
    }
  }

  errors.push(...bandClassErrors(doc));

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
