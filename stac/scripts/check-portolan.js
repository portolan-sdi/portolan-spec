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

const schemaPath = path.join(__dirname, '..', 'json-schema', 'schema.json');
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

// Classes sit on the asset for a single-band raster and on the band for a
// multiband raster (PORTO-FMT-050). The classification v2.0.0 schema checks
// classes on the asset and under raster:bands. It does not check STAC 1.1
// bands, so this script applies the class schema to bands. This script also
// applies the Portolan class rules (PORTO-FMT-052, PORTO-FMT-057,
// PORTO-FMT-060) in both places.
const classificationUri = 'https://stac-extensions.github.io/classification/v2.0.0/schema.json';
const classificationCache = path.join(
  __dirname, '..', '.schema-cache', 'stac-extensions', 'classification', 'v2.0.0', 'schema.json',
);
let validateClassFields = null;
if (fs.existsSync(classificationCache)) {
  ajv.addSchema(JSON.parse(fs.readFileSync(classificationCache, 'utf8')));
  validateClassFields = ajv.getSchema(`${classificationUri}#/definitions/fields`);
}

// `holder` is the asset or band object that carries the class list.
function classRuleErrors(holder, where) {
  const errors = [];
  const classes = holder['classification:classes'];
  if (!Array.isArray(classes)) return errors;
  classes.forEach((cls, j) => {
    const at = `${where}/classification:classes/${j}`;
    if (typeof cls.title !== 'string' || !cls.title) {
      errors.push(`${at}: class has no title (PORTO-FMT-052)`);
    }
    if (cls.nodata === true && cls.value !== holder.nodata) {
      errors.push(`${at}: nodata class value ${cls.value} is not the nodata ${holder.nodata} of its holder (PORTO-FMT-057)`);
    }
    if (holder.nodata !== undefined && cls.value === holder.nodata && cls.nodata !== true) {
      errors.push(`${at}: class at the nodata value ${holder.nodata} is not marked nodata (PORTO-FMT-060)`);
    }
  });
  return errors;
}

function classErrors(doc) {
  const errors = [];
  const groups = { assets: doc.assets || {}, item_assets: doc.item_assets || {} };
  for (const [group, assets] of Object.entries(groups)) {
    for (const [key, asset] of Object.entries(assets)) {
      const where = `${group}/${key}`;
      const bands = Array.isArray(asset.bands) ? asset.bands : [];
      if (asset['classification:classes'] !== undefined && bands.length > 1) {
        errors.push(`${where}: multiband raster has its classes on the asset, not on the band (PORTO-FMT-050)`);
      }
      errors.push(...classRuleErrors(asset, where));
      bands.forEach((band, i) => {
        const bandWhere = `${where}/bands/${i}`;
        if (band['classification:classes'] === undefined) return;
        if (bands.length === 1) {
          errors.push(`${bandWhere}: single-band raster has its classes on the band, not on the asset (PORTO-FMT-050)`);
        }
        if (!validateClassFields) {
          errors.push(`${bandWhere}: classification schema not cached, run \`node scripts/fetch-extension-schemas.js\``);
          return;
        }
        if (!validateClassFields(band)) {
          errors.push(...validateClassFields.errors.map((e) => `[classification] ${bandWhere}${e.instancePath} ${e.message}`));
        }
        errors.push(...classRuleErrors(band, bandWhere));
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

  errors.push(...classErrors(doc));

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
