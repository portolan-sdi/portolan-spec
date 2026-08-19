# Best Practices — Multilingual Catalogs

A multilingual catalog publishes a separate metadata tree for each language. The
catalog uses one tree as its source and derives the other trees from it. `alternate`
links connect equivalent catalogs and collections across the trees.

Use the STAC [Language](https://github.com/stac-extensions/language) extension on each
translated catalog and collection. It identifies the document's language and gives
clients the information they need for a language selector.

The examples below use Romanian as the source language, with Russian and English
translations. Core defines the required structure in [Alternate-Language
Trees](../portolan/core.md#alternate-language-trees).

## The Basic Layout

Keep the source-language catalog at the root. Put each translation in a directory
named with its [RFC 5646](https://www.rfc-editor.org/rfc/rfc5646) language tag:

```text
national-geodata/
├── catalog.json              # Romanian source
├── README.md
├── AGENTS.md
├── cadastru/
│   ├── collection.json
│   ├── README.md
│   └── AGENTS.md
├── en/
│   ├── catalog.json
│   ├── README.md
│   ├── AGENTS.md             # may stay in the source language
│   └── cadastru/
│       ├── collection.json
│       ├── README.md
│       └── AGENTS.md
└── ru/
    └── ...
```

Use the same IDs and directory names in every tree. The file
`en/cadastru/collection.json` is the English version of
`cadastru/collection.json`, not a new collection with a new ID.

Only the metadata is duplicated. Data assets remain in the source tree, and translated
metadata refers to them with relative hrefs.

## Language Fields

Every translated catalog and collection declares the Language extension and its own
language:

```json
{
  "stac_extensions": [
    "https://schemas.portolan-sdi.org/portolan/v0.1.1/schema.json",
    "https://stac-extensions.github.io/language/v1.0.0/schema.json"
  ],
  "language": { "code": "ro", "name": "Română", "alternate": "Romanian" },
  "languages": [
    { "code": "ru", "name": "Русский", "alternate": "Russian" },
    { "code": "en", "name": "English" }
  ]
}
```

`language` describes the current document. `languages` lists the other available
languages and must not repeat the current one.

Use an RFC 5646 tag for `code`. Write `name` in the language it names, such as
`Română` or `Русский`. The optional `alternate` field gives a familiar name in
another language. For a right-to-left language, add `"dir": "rtl"`.

## Links Between Trees

Each root catalog links to every other root catalog:

```json
{
  "rel": "alternate",
  "href": "./en/catalog.json",
  "type": "application/json",
  "title": "Engleză",
  "hreflang": "en"
}
```

The `type` matters because an `alternate` link can also point to HTML or another media
type. The `hreflang` identifies the target language. The `title` names that language
for the current reader, so a Romanian document uses `Engleză` and an English document
uses `Romanian`.

Keep these hrefs relative. From the English root, the Romanian root is
`../catalog.json` and the Russian root is `../ru/catalog.json`.

Add the same links to equivalent collections. This lets a reader switch languages
without losing their place in the catalog.

Do not use `child` to link a translated root. The translation represents the same
catalog; it is not a subcatalog.

## Links to Untranslated Content

A language tree does not need to reproduce every item. A translated collection can
link to an item in the source tree and identify its language with `hreflang`:

```json
{
  "rel": "item",
  "href": "../../cadastru/parcele/parcele.json",
  "type": "application/geo+json",
  "title": "Cadastral parcels, 2024",
  "hreflang": "ro"
}
```

Translate the link title even when the target item remains in the source language.
Clients can show the title without fetching the item.

Use `hreflang` on the `describedby` and `agents` links too. Both point at files in
the same directory. The value names the language of the file it points at.

## What to Translate

Translate the root catalog, the collections, and their `README.md` files. These
carry the descriptions that people use to understand and find the data. The
`AGENTS.md` files may stay in the source language, see
[Agent Guidance](#agent-guidance).

Translate the column descriptions under `table:columns` as well. A client shows
them beside the column names, so they read as prose to the user. Keep the column
names themselves unchanged.

Translate items only when their prose warrants it. Items often contain identifiers,
geometries, times, and asset hrefs, so duplicating thousands of them may add little
value.

Keep these values identical in every language:

- Collection IDs, item IDs, and asset keys
- Data column names
- Style layer IDs
- CRS identifiers
- License identifiers

They are identifiers or properties of shared data. Stable values also let clients
match equivalent objects across trees.

## Agent Guidance

Every catalog and collection MUST carry an `AGENTS.md`, and the `agents` link MUST
point at the sibling file. Core states this under
[AGENTS.md](../portolan/core.md#agentsmd). A translated node is a catalog or a
collection, so it carries the file too. `rashid check` reports `PTL-FIL-001` and
`PTL-FIL-002` when it does not.

The language of that file is a separate choice. Technical guidance describes the
data rather than the prose, so it may stay in the source language. Mark the link
with the language of the file, not the language of the tree:

```json
{
  "rel": "agents",
  "href": "./AGENTS.md",
  "type": "text/markdown",
  "title": "Guidance for AI agents",
  "hreflang": "ro"
}
```

Translate `AGENTS.md` when the guidance itself is about the language. The term
glossary below is one example, because a translating agent reads it.

## One Source Language

Choose one source language and treat every other tree as derived. Use a language that
the publisher can check against the upstream material. In this example, the publisher
chooses Romanian because the upstream material is in Romanian.

Apply corrections to the source tree first, then regenerate the affected translations.
A direct edit to a derived tree will disappear during the next regeneration.

Record the source language and the regeneration command in the root `AGENTS.md`.

## A Glossary for Important Terms

General translation tools often choose reasonable but inconsistent words. A short
glossary prevents that drift and protects distinctions that matter in the data.
Keep it in the root `AGENTS.md`:

````markdown
## Translation

Source language: Romanian (`ro`). Edit `catalog.json`, `collection.json`,
`README.md`, and `AGENTS.md` in the root tree. Regenerate `en/` and `ru/`.

Use these terms. Do not substitute a synonym.

| Concept          | ro                   | ru                  | en               |
| ---------------- | -------------------- | ------------------- | ---------------- |
| cadastral parcel | parcelă cadastrală   | кадастровый участок | cadastral parcel |
| land cover       | acoperirea terenului | земельный покров    | land cover       |
| geodetic network | rețea geodezică      | геодезическая сеть  | geodetic network |

Keep the agency names and abbreviations AGCC and INGEOCAD unchanged.
````

Include terms that affect search or meaning. For example, Spanish uses `riesgo` for
risk and `peligro` for hazard. Those terms are related, but they are not interchangeable
in flood metadata.

## Keep Translations Current

Use the source-tree diff to decide what to regenerate. If one collection description
changes, update that collection in each translated tree. There is no need to translate
the whole catalog again.

CI can catch omissions. Fail the check when a source metadata file changes without a
corresponding change in every translated tree.

## Check the Result

Run `rashid check` on the catalog. It validates each language tree and the links
between them.

Some warnings use English-language heuristics. `PTL-FIL-005` looks for license and
provenance text in a collection `README.md`. `PTL-TTL-002` checks whether a title looks
like prose. Review these warnings instead of assuming they apply equally to every
language.

Finally, open the catalog in
[STAC Browser](https://radiantearth.github.io/stac-browser/). Check that every language
appears in the selector and opens the equivalent catalog or collection.
