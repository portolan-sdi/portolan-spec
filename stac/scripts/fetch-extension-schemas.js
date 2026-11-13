#!/usr/bin/env node
// Fetches pinned extension schemas into .schema-cache/ so the test suite can
// apply them without the published sites being live. Each fetched schema's $id
// must match its canonical URI. Pins are immutable refs, so an existing cache
// entry is reused; pass --force to refetch.
'use strict';

const fs = require('fs');
const path = require('path');
const https = require('https');

const root = path.join(__dirname, '..');
const manifest = require('../portolan-extensions.json');
const testExtensions = require('../test-extension-schemas.json');
const force = process.argv.includes('--force');

function get(url, redirects = 5) {
  return new Promise((resolve, reject) => {
    https.get(url, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location && redirects > 0) {
        res.resume();
        return resolve(get(res.headers.location, redirects - 1));
      }
      if (res.statusCode !== 200) {
        res.resume();
        return reject(new Error(`HTTP ${res.statusCode} fetching ${url}`));
      }
      let body = '';
      res.on('data', (d) => { body += d; });
      res.on('end', () => resolve(body));
    }).on('error', reject);
  });
}

async function cacheSchema({ canonical, dest, label, path: schemaPath, ref, repo }) {
  if (fs.existsSync(dest) && !force) {
    console.log(`✓ ${label} (cached)`);
    return;
  }

  const url = `https://raw.githubusercontent.com/${repo}/${ref}/${schemaPath}`;
  const body = await get(url);
  const schema = JSON.parse(body);
  const id = String(schema.$id || '').replace(/#$/, '');
  if (id !== canonical) {
    throw new Error(`${label}: fetched $id ${schema.$id} does not match ${canonical}`);
  }
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.writeFileSync(dest, body);
  console.log(`✓ ${label} fetched from ${repo}@${ref}`);
}

(async () => {
  for (const [name, ext] of Object.entries(manifest)) {
    if (name.startsWith('$')) continue;
    for (const [version, ref] of Object.entries(ext.versions)) {
      await cacheSchema({
        canonical: `https://schemas.portolan-sdi.org/${name}/${version}/schema.json`,
        dest: path.join(root, '.schema-cache', name, version, 'schema.json'),
        label: `${name} ${version}`,
        path: ext.path,
        ref,
        repo: ext.repo,
      });
    }
  }

  for (const [canonical, ext] of Object.entries(testExtensions)) {
    if (canonical.startsWith('$')) continue;
    await cacheSchema({
      canonical,
      dest: path.join(root, '.schema-cache', 'stac-extensions', ext.name, ext.version, 'schema.json'),
      label: `${ext.name} ${ext.version}`,
      path: ext.path,
      ref: ext.ref,
      repo: ext.repo,
    });
  }
})().catch((e) => {
  console.error(`✗ ${e.message}`);
  process.exit(1);
});
