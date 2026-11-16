# Incubating — GeoTIFF Statistics Headers

**Status: encoding detail for a normative requirement.**

The requirement that COGs carry embedded per-band statistics is normative and lives
in [`formats.md` → Raster statistics](../portolan/formats.md#raster-statistics),
with the table of required statistics and their severities. This document specifies
the exact on-disk encoding. It is incubating because there is no official standard (Portolan follows the de-facto GDAL convention) and the encoding may be refined.

## Encoding

Statistics are stored in the TIFF `GDAL_METADATA` tag (code 42112) as an XML
document with one `<Item>` per statistic per band, where `sample` is the zero-based
band index:

```xml
<GDALMetadata>
  <Item name="STATISTICS_MINIMUM" sample="0">12.5</Item>
  <Item name="STATISTICS_MAXIMUM" sample="0">340.25</Item>
  <Item name="STATISTICS_MEAN" sample="0">88.4</Item>
  <Item name="STATISTICS_STDDEV" sample="0">42.1</Item>
</GDALMetadata>
```

## Rules

- Values are plain ASCII decimals in the band's native value space and MUST exclude
  nodata pixels, except that approximate statistics (`STATISTICS_APPROXIMATE = YES`)
  MAY be computed from a sample, which need not perfectly exclude nodata.
- Bands with a nodata value SHOULD also set the `GDAL_NODATA` tag (code 42113).
- Statistics MUST be embedded in the file — an external `.aux.xml` (PAM) sidecar
  does not satisfy the requirement — and MUST reside in the file's leading header
  block so they arrive in a reader's first range request.
- Compliance is defined by the tag contents, not by use of GDAL. Any tool that
  writes an equivalent `GDAL_METADATA` tag conforms.
- One command that writes these statistics at creation time is
  `gdal_translate -of COG -stats`.

## Nodata

For a non-finite nodata value, use the corresponding string in the band's
`nodata` field: `"nan"`, `"inf"`, or `"-inf"`. These strings are specified in
[STAC 1.1.0 common metadata](https://github.com/radiantearth/stac-spec/blob/v1.1.0/commons/common-metadata.md#bands).
Do not use `null` or an unquoted `NaN` in this field.

A valid-percent statistic is required even when the nodata value is non-finite.
