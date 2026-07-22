#!/usr/bin/env node
// Fetches the pinned portolan-sdi extension schemas listed in
// portolan-extensions.json into .schema-cache/ so the test suite can apply
// them without the published site being live. Each fetched schema's $id must
// match its canonical https://schemas.portolan-sdi.org/<name>/<version>/schema.json
// URI. Pins are immutable refs, so an existing cache entry is reused; pass
// --force to refetch.
'use strict';

const fs = require('fs');
const path = require('path');
const https = require('https');

const root = path.join(__dirname, '..');
const manifest = require('../portolan-extensions.json');
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

(async () => {
  for (const [name, ext] of Object.entries(manifest)) {
    if (name.startsWith('$')) continue;
    for (const [version, ref] of Object.entries(ext.versions)) {
      const dest = path.join(root, '.schema-cache', name, version, 'schema.json');
      if (fs.existsSync(dest) && !force) {
        console.log(`✓ ${name} ${version} (cached)`);
        continue;
      }
      const url = `https://raw.githubusercontent.com/${ext.repo}/${ref}/${ext.path}`;
      const body = await get(url);
      const schema = JSON.parse(body);
      const canonical = `https://schemas.portolan-sdi.org/${name}/${version}/schema.json`;
      const id = String(schema.$id || '').replace(/#$/, '');
      if (id !== canonical) {
        throw new Error(`${name} ${version}: fetched $id ${schema.$id} does not match ${canonical}`);
      }
      fs.mkdirSync(path.dirname(dest), { recursive: true });
      fs.writeFileSync(dest, body);
      console.log(`✓ ${name} ${version} fetched from ${ext.repo}@${ref}`);
    }
  }
})().catch((e) => {
  console.error(`✗ ${e.message}`);
  process.exit(1);
});
