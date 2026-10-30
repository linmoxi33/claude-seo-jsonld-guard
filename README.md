# claude-seo-jsonld-guard

An offline JSON-LD validator for schema.org markup that keeps checking when a node declares **multiple `@type` values** — the exact case where claude-seo's bundled hook crashes and silently reports success. Why now: agent plugins increasingly ship their own "validators", and a validator that dies on valid JSON-LD is worse than none, because the agent believes the page was checked.

Upstream: https://github.com/AgriciDaniel/claude-seo

## Upstream and the gap

[claude-seo](https://github.com/AgriciDaniel/claude-seo) runs `hooks/validate-schema.py` as a PostToolUse hook on every edit that touches JSON-LD. That hook reads `@type` at line 221 and immediately uses it as a dictionary key at lines 231 and 239, without normalising a list. Schema.org explicitly allows `"@type": ["Organization", "LocalBusiness"]`, so on valid multi-typed markup the hook raises `TypeError: cannot use 'list' as a dict key` and the schema is never validated.

Reported and still open, independently, three times:

- [#382 — validate-schema.py raises TypeError when @type holds an array](https://github.com/AgriciDaniel/claude-seo/issues/382)
- [#357 — validate-schema.py hook crashes with TypeError when JSON-LD "@type" is an array](https://github.com/AgriciDaniel/claude-seo/issues/357)
- [#394 — schema_ecommerce_validate.py: priceSpecification array crashes the loyalty check](https://github.com/AgriciDaniel/claude-seo/issues/394) (same array-vs-scalar class in a sibling validator)

The one-line statement: it validates JSON-LD on every edit, but nobody can validate a node whose `@type` is an array — the hook throws and the edit passes unchecked.

## What this tool does / does not do

**Does:** extract every `application/ld+json` block from HTML (or read `.json` files), parse it, normalise `@type` string-or-array, walk `@graph` and nested nodes, and report: missing `@type`, non-string types, missing required properties for 19 common schema.org types, duplicate `@id` values, malformed JSON, and missing `@context` (warning only).

**Does not:** fetch URLs, crawl sites, call Google's Rich Results API, or grade SEO quality. It never executes page JavaScript and never phones home.

## Install

No dependencies, Python 3.8+:

```bash
git clone git@github-linmoxi33:linmoxi33/claude-seo-jsonld-guard.git
cd claude-seo-jsonld-guard
python3 bin/jsonld-guard examples/in/broken.html
```

## Usage

```bash
python3 bin/jsonld-guard page.html                 # one file
python3 bin/jsonld-guard examples/in               # directory, recursive
python3 bin/jsonld-guard --json examples/in/broken.html
```

Text output, one line per issue:

```
examples/in/broken.html:1:$.@graph[0] error missing-required: Product is missing required property 'name'
examples/in/broken.html:2:$.@graph[0] error missing-required: Article is missing required property 'author'
examples/in/broken.html:3:$ error invalid-json: JSON parse error: Expecting property name ...
3 file(s), 3 block(s), 3 node(s), 3 error(s), 0 warning(s)
```

`--json` output (see `examples/out/report.json`):

```json
{
  "tool": "jsonld-guard",
  "version": "1.0.0",
  "summary": {"files": 1, "blocks": 3, "nodes": 2, "errors": 3, "warnings": 0},
  "issues": [
    {"file": "examples/in/broken.html", "block": 1, "path": "$.@graph[0]",
     "code": "missing-required", "severity": "error",
     "message": "Product is missing required property 'name'"}
  ]
}
```

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | No errors (warnings may exist) |
| `1` | At least one validation error was found |
| `2` | Usage error, missing path, or unreadable input |

## Tests

```bash
python3 -m unittest discover -s tests -v
```

15 tests, 7 of them end-to-end behaviour tests that assert stdout and exit codes.

## Differences from existing tools

`gh search repos "json-ld validator"` (2026-10-30) surfaced only small projects: `probeo-io/jsonld` (1 star), `nadar/php-schemaorg-jsonld-validator` (0), `jrynks/schema-lint` (0). None is a mature (>500 stars) tool covering this space, and none is built around the multi-`@type` regression. This tool deliberately stays narrow: offline, stdlib-only, exit-code contract, no crawl.

## Limitations

- Required-property rules cover 19 common types, not the full schema.org ontology; unknown types are accepted as long as `@type` is well-formed.
- HTML is parsed with a regular expression for `<script type="application/ld+json">` blocks, not a DOM parser.
- It validates shape, not truth: it cannot know whether the address or price is real.
- The upstream hook may be fixed later; this tool remains useful as an independent, dependency-free check.

## License

MIT
