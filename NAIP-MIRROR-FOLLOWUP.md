# Metadata-only mirror follow-up

What the `naip-mosaic` example catalog exposed about the spec, and what to do about it.

Written 2026-07-30 against commit `eba25f4`. Every number here was measured, and every rule ID and quotation was checked against the file it comes from. Section 10 lists what failed that check and was dropped.

The catalog publishes 924 Microsoft Planetary Computer NAIP scenes as metadata. The imagery stays upstream. It is the first Portolan catalog in this repo that does not host the bytes it describes, and that single difference is what surfaced everything below.

---

## 1. The custody gap, unfiled and the main subject

`PORTO-CORE-028` makes `file:checksum` a MUST on every asset. `PORTO-CORE-030` then says how the value is produced.

```
Assets MUST carry `file:size` and `file:checksum` from the [file
extension](https://github.com/stac-extensions/file).

These embedded values MUST be regenerated at publish time, in the same
operation that uploads the files, so they always match what is in the bucket.
```

The second sentence presumes the publisher uploads the files. This catalog uploads none of them, so there is no such operation and no bucket of its own to match. `file:size` survives the difference because a HEAD returns it. The checksum does not, because nothing short of reading every byte produces it.

**The arithmetic, which is not what a reader would guess.** Each Item carries two assets without a checksum, the scene COG under the `image` key and the referenced upstream thumbnail under `thumbnail`. `PTL-AST-003` is reported per asset, so it fires 1848 times. `PTL-SCH-001` is reported per file, so it fires 924 times, once per `item.json`, however many of that Item's assets are short the property. The gate reports 2772 errors, all of them baselined in `examples/expected-findings/naip-mosaic.json`.

```console
$ python3 -c "
import json, glob, collections
missing = collections.Counter(); items = 0
for f in glob.glob('examples/catalog/naip-mosaic/**/item.json', recursive=True):
    d = json.load(open(f)); items += 1
    for k, a in d['assets'].items():
        if 'file:checksum' not in a: missing[k] += 1
print(items, 'items;', dict(missing), 'sum', sum(missing.values()))"
924 items; {'image': 924, 'thumbnail': 924} sum 1848
```

Computing the checksums honestly means reading every scene. The published `file:size` values sum to it exactly.

```console
$ python3 -c "
import json, glob
t = sum(json.load(open(f))['assets']['image']['file:size']
        for f in glob.glob('examples/catalog/naip-mosaic/**/item.json', recursive=True))
print(t, 'bytes =', round(t/1e12, 3), 'TB, mean', round(t/924/1e9, 2), 'GB')"
1859248614649 bytes = 1.859 TB, mean 2.01 GB
```

1.86 TB read on every publish, to produce a value that describes bytes this project does not control and cannot keep from changing. Synthesizing the checksums would be a false claim about data nobody here has hashed. Omitting them is the only honest option, which is why the baseline exists rather than a workaround.

**Note the upstream `file` extension makes `file:checksum` optional.** Portolan raises it to a MUST. That is a deliberate Portolan choice, not inherited from STAC, so it is Portolan's to scope.

### The neighbouring issues, and why neither covers this

| Issue | State | What it covers | Why it is not this |
|---|---|---|---|
| [#90](https://github.com/portolan-sdi/portolan-spec/issues/90) | open | Defines the `source` role normatively, and names the question of whether source-role assets may omit `file:size` and `file:checksum` | Scoped to the optional `source` role. Says nothing about a `data` asset |
| [#80](https://github.com/portolan-sdi/portolan-spec/issues/80) | closed | An upstream drifted away from a published checksum | Diagnosis, not remedy |
| [PR #85](https://github.com/portolan-sdi/portolan-spec/pull/85) | merged 2026-07-27 | Dropped source assets for live-endpoint upstreams | The precedent removes a rotting pin by dropping the asset. That works only because `source` is optional. A mirror cannot drop its `data` asset |

`PORTO-CORE-027` scopes the `data` role to the primary GeoParquet, COG, or Parquet and says nothing about who holds the bytes, so a mirror's remote COG takes the `data` role and with it every custody requirement.

### Custody requirements a metadata-only mirror cannot satisfy

| Rule | Severity | Problem |
|---|---|---|
| `PORTO-CORE-028` | MUST, validator | Couples `file:size` and `file:checksum` with no separability. `file:size` is obtainable by HEAD, the checksum is not, which is exactly why this catalog carries one and not the other |
| `PORTO-CORE-030` | MUST, process | Publish-time regeneration presumes an upload that never happens |
| `PORTO-CORE-043` | MUST, validator | A server MUST that binds a server the publisher does not run. See section 2 |
| `PORTO-CORE-045` | MUST, validator | Same. See section 2 |
| `PORTO-CORE-047` | MUST, validator | Exactly one `host` provider. See section 9 |

### A taxonomy question, not a proposal

`core.md` derives Official versus Mirror from the providers and defines a Mirror as "a cloud-native copy that complements a source maintained elsewhere". This catalog copies nothing. Whether that wants a third term, or whether Mirror should simply stop implying copied bytes, is a question for whoever picks the custody work up. Filing a name before the requirements are scoped would be backwards.

### No prior art found, with one gap in the search

A web search across `stac-spec`, the `stac-extensions/file` repository, OGC Testbed reports, the Cloud-Native Geo forum and DCAT-AP turned up nothing on this argument. `stac-extensions/file` has seven issues in its whole history and none touches custody. `radiantearth/stac-spec` has nine issues mentioning checksums and none asks who holds the bytes. So the argument appears novel rather than a restatement of a known debate.

The Cloud-Native Geo Slack is not web-searchable, so the search cannot rule out the question having been raised there. Worth asking before filing.

---

## 2. Evidence for #89, measured

[#89](https://github.com/portolan-sdi/portolan-spec/issues/89) is open and already proposes scoping the Data Storage MUSTs to servers hosting the catalog's own assets. This catalog is the strongest case for it, because the upstream host is not merely uncontrolled, it is partly non-conformant. Measured 2026-07-30 against a real scene href.

```console
$ U="https://naipeuwest.blob.core.windows.net/naip/v002/co/2023/co_030cm_2023/38104/m_3810401_ne_13_030_20231010_20240104.tif"
$ curl -sI "$U" | tr -d '\r'
HTTP/1.1 200 OK
Content-Length: 2071927303
Content-Type: image/tiff
ETag: 0x8DD3391120D79A4
Server: Windows-Azure-Blob/1.0 Microsoft-HTTPAPI/2.0
Access-Control-Expose-Headers: x-ms-request-id,Server,x-ms-version,Content-Type,ETag,Last-Modified,x-ms-lease-status,x-ms-blob-type,Content-Length,Date,Transfer-Encoding
Access-Control-Allow-Origin: *

$ curl -s -o /dev/null -D - -H 'Range: bytes=0-99' "$U" | tr -d '\r' | head -4
HTTP/1.1 206 Partial Content
Content-Length: 100
Content-Type: image/tiff
Content-Range: bytes 0-99/2071927303
```

| Requirement | Result |
|---|---|
| Honor `Range`, return `206 Partial Content` | Pass |
| Advertise `Accept-Ranges: bytes` | **Absent on both HEAD and the 206** |
| HEAD returns an accurate `Content-Length` | Pass. 2071927303 matches the published `file:size` |
| `Access-Control-Allow-Origin: *` | Pass |
| Allowed methods including `GET` and `HEAD`, request header `Range` | Pass. A preflight echoes each |
| Exposed headers including `Content-Range` and `Accept-Ranges` | **Both absent from `Access-Control-Expose-Headers`** |

So a browser client can range-read this COG but cannot read back the `Content-Range` it got, and no client can discover range support from the advertised headers. `PORTO-CORE-043` and `PORTO-CORE-045` are both MUSTs enforced by the validator, and both bind a server the publisher does not run. Nothing the generator can do reaches them.

---

## 3. #40 closed without considering a mirrored COG

[#40](https://github.com/portolan-sdi/portolan-spec/issues/40) asked for embedded GDAL band statistics and was closed as resolved by #54. Its whole discussion assumes the publisher writes the COG. The ratified text in `formats.md` closes the only route a mirror has.

```
**Raster statistics.** COGs MUST carry pixel statistics for rendering. Every band
MUST carry an embedded minimum, maximum, mean, and standard deviation so a renderer
can scale any data type without reading pixels. Statistics MUST be embedded in the
file — an external `.aux.xml` (PAM) sidecar does not satisfy this — and MUST be
written at creation time (e.g. `gdal_translate -of COG -stats`), residing in the
file's leading header block so they arrive in a reader's first range request.
```

That is `PORTO-FMT-026` through `PORTO-FMT-029`. A mirror creates no file, so `PORTO-FMT-029` is unreachable by definition, and `PORTO-FMT-028` forecloses the sidecar that would otherwise let a mirror supply what upstream omitted.

This catalog reads each scene's coarsest internal overview and publishes the result in STAC 1.1 core `bands[].statistics`, flagged `"approximate": true`. `PORTO-FMT-032` requires that flag in the GDAL tag when statistics are estimated and is silent about the STAC field, so the honesty marker has no defined meaning where this catalog puts it.

Upstream carries nothing to inherit, checked directly.

```console
$ GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR uv run --with "rasterio>=1.5" python -c "
import rasterio
u='https://naipeuwest.blob.core.windows.net/naip/v002/co/2023/co_030cm_2023/38104/m_3810401_ne_13_030_20231010_20240104.tif'
with rasterio.open(u) as d:
    print('bands', d.count, d.dtypes[0], 'overviews', d.overviews(1))
    for b in range(1, d.count+1):
        print('band', b, {k: v for k, v in d.tags(b).items() if k.startswith('STATISTICS_')} or 'NONE')"
bands 4 uint8 overviews [2, 4, 8, 16, 32, 64]
band 1 NONE
band 2 NONE
band 3 NONE
band 4 NONE
```

**Worth knowing that no configured gate sees this.** rashid checks embedded COG statistics in its data pass, and the data pass is off for this catalog (section 5). The baseline therefore does not list a statistics rule, because none fires. The gap is real and undetected rather than accepted, and recording that plainly here is more honest than adding an accepted entry that can never match.

---

## 4. A correction for #98 and #100

[#98](https://github.com/portolan-sdi/portolan-spec/issues/98) and [#100](https://github.com/portolan-sdi/portolan-spec/issues/100) both rest on rashid#66, the finding that `PTL-DAT-006` passes vacuously on a single row group. That issue is now **closed as completed**, and the pinned `rashid[data]>=0.1.3,<0.2.0` rejects a plain unsorted single-row-group mirror.

```
the file is a single row group of 924 rows whose rows do not cluster spatially
```

Measured during the Task 5 spike over a 924-item fixture, and reproduced independently by the reviewer. A shuffled multi-row-group file fires the other branch, `row groups overlap heavily and lack locality`. Two further facts from the same spike are worth carrying into #98 and #100.

- rashid cannot measure `PTL-DAT-006` below 200 rows, the product of its internal `_ORDERING_CHUNKS` and `_MIN_CHUNK_ROWS`. A small fixture goes green vacuously however badly ordered.
- `pyarrow.parquet.write_table` drops the `geo` key, after which rashid reads the file as plain Parquet and skips `PTL-DAT-006`, `007`, `008` and `012` entirely. That is a pass for the wrong reason and it is easy to ship by accident.

The committed mirror clears the rule on its own bytes.

```console
$ uv run --with "pyarrow>=25" python -c "
import pyarrow.parquet as pq, os
p='examples/catalog/naip-mosaic/imagery/colorado-2023/items.parquet'
f=pq.ParquetFile(p); m=f.metadata
print(m.num_rows,'rows,',m.num_row_groups,'row groups,',os.path.getsize(p),'bytes')
print([m.row_group(i).num_rows for i in range(m.num_row_groups)])
print(sorted(k.decode() for k in f.schema_arrow.metadata))"
924 rows, 8 row groups, 306771 bytes
[128, 128, 128, 128, 128, 128, 128, 28]
['geo', 'stac-geoparquet']
```

---

## 5. rashid scalability, filed

[rashid#86](https://github.com/portolan-sdi/rashid/issues/86) is open. The data pass streams every asset in full, even when there is no checksum to hash, because size is a byte counter and format detection reads the leading bytes. Timed at 5 m 56 s for 2 scenes during design, which extrapolates to roughly 45 hours for 924, alongside the 1.86 TB from section 1.

```console
$ python3 -c "print(f'{(356 / 2) * 924 / 3600:.1f} hours')"
45.7 hours
```

Read that as a single-threaded extrapolation from two scenes rather than a prediction. Either way it is not a CI job, so `examples/expected-findings/naip-mosaic.json` sets `data_pass` to false and `check_catalogs.py` passes `--no-data` for this catalog.

That skips the two checks a mirror most needs, `PTL-DAT-006` ordering and `PTL-DAT-016` row-per-item parity, on the Collection's own local `items.parquet`. `examples/tools/tests/check_items_parquet.py` covers them offline instead. Note precisely what it covers. It exercises `write_items_parquet` over a synthetic 300-item fixture and asserts row-per-item parity, several row groups, the 150,000-row cap, and that Hilbert order clusters neighbours more tightly than input order. It does not read the committed `items.parquet` and it does not run rashid, so it proves the writer rather than the artifact.

---

## 6. Access durability, a risk and not a conformance gap

Unsigned reads against the upstream container succeed today, measured in section 2. But the Planetary Computer runs a token endpoint for this exact container, and it issues a short-lived credential on request.

```console
$ curl -s "https://planetarycomputer.microsoft.com/api/sas/v1/token/naipeuwest/naip" \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['msft:expiry'])"
2026-07-30T02:03:16Z
```

So the service's designed access path is a signed one, and the unsigned access this catalog depends on is a property of the container's current public ACL rather than something the publisher has committed to. If that ACL changes, every asset href in this catalog stops resolving and there is nothing in the metadata to fall back to. That is a durability risk a metadata-only mirror carries, and it is worth stating in the Collection documentation. It is not a spec gap.

---

## 7. The license reading

The Collection declares `license: other` with a `rel=license` link, which `PORTO-CORE-059` allows when no SPDX identifier fits. Three findings sit behind that choice.

**Upstream is non-conformant on the exact value the spec forbids.** `PORTO-CORE-060` says the deprecated STAC 1.1 value `proprietary` MUST NOT be used.

```console
$ curl -s "https://planetarycomputer.microsoft.com/api/stac/v1/collections/naip" \
    | python3 -c "
import json,sys; d=json.load(sys.stdin)
print('license', repr(d['license']))
print([(l['rel'], l['href'], l.get('title')) for l in d['links'] if l['rel']=='license'])"
license 'proprietary'
[('license', 'https://www.fsa.usda.gov/help/policies-and-links/', 'Public Domain')]
```

Upstream declares `proprietary` and links a generic FSA site policy page that never names NAIP, while titling that link "Public Domain". The spec says nothing about a mirror whose upstream metadata is itself non-conformant, which is a small gap in its own right. This catalog does not inherit the value, which is right.

**No SPDX identifier fits.** Checked against the SPDX license list at version `e4c1f27`, 733 identifiers. There is no identifier for United States federal public domain. The US public-domain entries are agency-specific software notices, `NIST-PD`, `NCBI-PD` and `NTIA-PD`, and `CC-PDM-1.0` is Creative Commons' Public Domain Mark rather than a government instrument. So `other` is the conformant value.

**The public domain status checks out, but the citation in the manifest is weak.** FSA Notice AP-26 says verbatim, "Since the start of NAIP in 2003, all acquired imagery has been placed in public domain allowing unrestricted use and sharing of the data." Read the rest of the notice before leaning on it. AP-26 is dated 11-27-17 with a disposal date of March 1, 2018, and its actual purpose was a survey exploring whether to move NAIP to a licensed data model. It is expired, and its own subject is the possible end of the status it records.

**A better citation is inside the data.** Every scene's TIFF carries the grant in `TIFFTAG_IMAGEDESCRIPTION`.

```console
$ GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR uv run --with "rasterio>=1.5" python -c "
import rasterio
u='https://naipeuwest.blob.core.windows.net/naip/v002/co/2023/co_030cm_2023/38104/m_3810401_ne_13_030_20231010_20240104.tif'
with rasterio.open(u) as d: print(d.tags()['TIFFTAG_IMAGEDESCRIPTION'])"
Image courtesy of USDA Farm Service Agency's National Agriculture Imagery Program (NAIP) under FPAC-Geo, Farm Production and Conservation contract 12FPC222A0007. Imagery has been placed in the public domain and may be used and reproduced without permission or fee. Please credit 'NAIP imagery provided by USDA Farm Service Agency' on any use.
```

That is current, per scene, written by the producer's contractor, and it independently confirms the `attribution` string this Collection publishes, which is the same sentence. Worth using in place of AP-26 in the manifest comment, and worth considering as the `rel=license` target given the finding below.

### A defect found while writing this, not a spec gap

The committed `rel=license` href no longer serves license text.

```console
$ curl -s "https://www.usa.gov/publicdomain/label/1.0/" -o /dev/null -w "%{http_code}\n"
200
$ curl -s "https://www.usa.gov/publicdomain/label/1.0/" | python3 -c "
import sys,re,html
t=re.sub(r'<[^>]+>',' ',sys.stdin.read()); print(re.sub(r'\s+',' ',html.unescape(t)).strip())"
Redirecting to https://www.usa.gov/government-copyright Redirecting to https://www.usa.gov/government-copyright .
```

It answers 200 with a client-side redirect stub, and the target is a general explainer titled "Learn about copyright and federal government materials" rather than an instrument. `PORTO-CORE-059` asks the link to point "to the license text", and this does not. Commit `ee88086` chose this URL over the FSA page for good reasons that still hold, but the URL has stopped working as license text. Needs a replacement.

---

## 8. What worked and needed no spec change

**The `canonical` link.** `PORTO-CORE-054` requires it when the upstream publishes its own STAC. This is the first Collection in the repo to carry one.

```console
$ python3 -c "
import json, glob
for f in sorted(glob.glob('examples/catalog/**/collection.json', recursive=True)):
    d = json.load(open(f)); rels = [l['rel'] for l in d['links']]
    print(f\"{d['id']:42s} canonical={'canonical' in rels}\")"
imagery/colorado-2023                      canonical=True
boundaries/boston-open-space               canonical=False
boundaries/netherlands-provinces           canonical=False
boundaries/us-counties                     canonical=False
mirror/san-francisco-addresses             canonical=False
raster/sample-cog                          canonical=False
reference/natural-earth-countries          canonical=False
reference/natural-earth-populated-places   canonical=False
tabular/eurostat-electricity-prices        canonical=False
```

None of the other eight has a STAC-publishing upstream, which is why all eight report `PTL-PRO-002` as info and why the requirement had never been exercised. It was satisfied by the generator from a `provenance.canonical` manifest field with no special handling, and the target resolves. A conditional MUST that had shipped untested now has a working example.

**Absolute `https` asset hrefs.** `core.md` requires an absolute href to use `https` and says nothing about who serves it. That silence is what makes this catalog legal at all, and it needed no change.

**The item mirror.** `PORTO-FMT-040` through `043` bind `items.parquet` to the GeoParquet storage rules. A 924-row mirror satisfies all of them, measured in section 4.

---

## 9. Other spec-conflict findings that survived checking

**`PORTO-CORE-047`, exactly one host provider.**

```
The list MUST include at least one provider with the `producer` role, the
organization that originally captured or created the data, and exactly one
provider with the `host` role, listed as the last element.
```

This catalog serves the metadata and Microsoft serves every byte of imagery. There is no way to record that. The built Collection lists Portolan SDI as `host` and Microsoft as `processor`, which understates what Microsoft does, and the alternative would name as host an organization that does not maintain this copy of the catalog. `core.md` already anticipates the near case, a catalog on S3 lists the city GIS office rather than AWS, but that is one party operating a copy on rented storage. Split hosting is a different shape and the cardinality forbids expressing it.

**`PORTO-CORE-065` and `PORTO-CORE-067`, no render path for a 924-scene raster Collection.** Both branches of `PORTO-CORE-065` are written for one data asset. Rendering from source turns on whether "the data asset is small and simple enough for clients to draw directly", singular, and the derivative branch names PMTiles as the recommended format, which is vector. Meanwhile `core.md` requires the opposite arrangement for exactly this case.

```
A collection holding multiple raster scenes MUST model each scene as an item
carrying its COG as an item-level asset; scene COGs MUST NOT be listed as
collection-level assets.
```

So a multi-scene raster Collection is forbidden from having the collection-level data asset that both render branches presume. This is why `minimal.json` exists, a compact bbox-and-href index registered with the `metadata` role so a client-side mosaic can load every footprint in one request. It is invention, not conformance. `PORTO-CORE-067` then requires styles as standalone assets except for a self-rendering path, and whether 924 four-band uint8 COGs count as self-rendering is undecided.

Existing issues nearby, none of which is this. [#41](https://github.com/portolan-sdi/portolan-spec/issues/41) and [#55](https://github.com/portolan-sdi/portolan-spec/issues/55) are raster styling and colormaps. [#73](https://github.com/portolan-sdi/portolan-spec/issues/73) is closed and settled how multi-scene raster is modelled, which is the rule quoted above. [#44](https://github.com/portolan-sdi/portolan-spec/issues/44) is a root-level GeoParquet for Collection search and is unrelated, despite what `mosaic.write_minimal_json`'s docstring says. This wants a new issue.

**`PORTO-CORE-059` and `PORTO-CORE-060`.** The spec is silent on a mirror whose upstream metadata is non-conformant. Covered in section 7.

**`PORTO-FMT-032`.** Approximate statistics are permitted in the GDAL tag and spec-silent in STAC `bands[].statistics`. Covered in section 3.

---

## 10. Claims that did not survive checking, and were dropped

Kept here so nobody re-derives them.

| Claim | Verdict |
|---|---|
| The `canonical` link is missing from the built Collection | **Wrong.** It is present and its target resolves. See section 8 |
| `PORTO-CORE-055`'s premise, that STAC publication cannot be determined from the mirror's metadata alone, is false for a mirror derived from a STAC search | **Dropped.** The premise concerns what a validator can see. Nothing in the built Item or Collection reveals that the upstream publishes STAC apart from the `canonical` link the requirement is about. The publisher knowing at build time is a different matter from the metadata showing it, and the spec's info-only severity follows correctly from the premise as written |
| Microsoft's documentation states that data assets require a token, and the terms state access will require a valid token | **Dropped.** Both pages are JavaScript-only and serve no text to any fetch, including the Wayback Machine, so no sentence could be quoted. Replaced in section 6 with the token endpoint's own measured response, which supports the same conclusion |
| The Planetary Computer is a preview service | **Dropped.** Could not be verified from any fetchable source, and nothing in section 6 needs it |
| 924 scenes total 1.7 TB at 1.85 GB each | **Imprecise.** The published `file:size` values sum to 1.859 TB at a 2.01 GB mean. 1.7 is the TiB figure. The estimate is still carried in the `naip-mosaic.json` baseline text and the manifest header comment, both of which predate the build |
| The embedded-statistics failure is baselined | **Wrong.** It is undetected. No statistics rule fires because the data pass is off. `mosaic.read_overview`'s docstring says baselined and is inaccurate |
| The Hilbert curve rotation was a corrected defect | **Not a defect.** The two rotation forms are algebraically equivalent, confirmed at orders 2 through 6 and over 20,000 random order-16 cells. The committed form is a readability fix. Do not cite it as a spec or code gap |

---

## 11. What to file, and where

Drafts written and held for human review, not posted. Nothing in this document has been filed.

| Draft | Target | Absorbs |
|---|---|---|
| Checksum and custody | new issue, `portolan-sdi/portolan-spec` | Sections 1 and 9, `PORTO-CORE-027`, `028`, `030`, the taxonomy question |
| Measured host headers | comment on [#89](https://github.com/portolan-sdi/portolan-spec/issues/89) | Section 2 |
| Host provider cardinality | new issue | `PORTO-CORE-047`, section 9 |
| Multi-scene raster render path | new issue | `PORTO-CORE-065` and `067`, section 9 |

Held for a separate decision, not drafted. The statistics question from section 3, the license reading and the broken license URL from section 7.

Already filed, no action needed. [rashid#86](https://github.com/portolan-sdi/rashid/issues/86) for the data-pass scalability finding.
