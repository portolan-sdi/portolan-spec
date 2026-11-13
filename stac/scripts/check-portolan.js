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
// PORTO-FMT-060) in both places. A class list in the legacy raster:bands
// array is in the wrong place. An asset with the source role is an upstream
// original, and the format rules do not apply to it (PORTO-FMT-045). The
// profile schema makes the same placement, title, and source decisions. The
// drift cases at the end of this script fail the run if the two disagree.
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
      const roles = Array.isArray(asset.roles) ? asset.roles : [];
      if (roles.includes('source')) continue;
      const bands = Array.isArray(asset.bands) ? asset.bands : [];
      const legacyBands = Array.isArray(asset['raster:bands']) ? asset['raster:bands'] : [];
      legacyBands.forEach((band, i) => {
        if (band && band['classification:classes'] !== undefined) {
          errors.push(`${where}/raster:bands/${i}: classes belong in the STAC 1.1 bands array, not raster:bands (PORTO-FMT-050)`);
        }
      });
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

// Drift cases. Each case changes the classified example in one way. The
// profile schema and the class rules above must both give the expected
// result, so a change to one without the other fails the run.
const classified = JSON.parse(
  fs.readFileSync(path.join(examplesDir, 'raster-classified-collection.json'), 'utf8'),
);
const untitled = [{ value: 1, name: 'water' }];
const titled = [{ value: 1, name: 'water', title: 'Water' }];
const driftCases = [
  {
    name: 'a source asset with misplaced and untitled classes passes',
    valid: true,
    change: (doc) => {
      doc.assets.upstream = {
        href: 'https://upstream.example.org/flood.tif',
        type: 'image/tiff',
        roles: ['source'],
        bands: [{}, {}],
        'classification:classes': untitled,
        'raster:bands': [{ 'classification:classes': untitled }],
      };
    },
  },
  {
    name: 'a class list in raster:bands of an asset fails',
    valid: false,
    change: (doc) => {
      doc.assets.data['raster:bands'] = [{ 'classification:classes': titled }];
    },
  },
  {
    name: 'a class list in raster:bands of item_assets fails',
    valid: false,
    change: (doc) => {
      doc.item_assets = {
        data: {
          type: doc.assets.data.type,
          roles: ['data'],
          'raster:bands': [{ 'classification:classes': titled }],
        },
      };
    },
  },
  {
    name: 'a class list on the asset of a multiband raster fails',
    valid: false,
    change: (doc) => {
      doc.assets.data.bands = [{}, {}];
    },
  },
  {
    name: 'a class with no title fails',
    valid: false,
    change: (doc) => {
      delete doc.assets.data['classification:classes'][1].title;
    },
  },
];
for (const testCase of driftCases) {
  const doc = JSON.parse(JSON.stringify(classified));
  testCase.change(doc);
  const bySchema = validate(doc);
  const byScript = classErrors(doc).length === 0;
  if (bySchema === testCase.valid && byScript === testCase.valid) {
    console.log(`✓ drift: ${testCase.name}`);
  } else {
    failed = true;
    console.error(`✗ drift: ${testCase.name}: schema says ${bySchema}, class rules say ${byScript}, expected ${testCase.valid}`);
  }
}

process.exit(failed ? 1 : 0);
