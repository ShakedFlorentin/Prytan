# Reference Library (`books/`)

Curated, authoritative reference pages that ground the agents so they cite
standards and hallucinate less. Indexed into the code graph as
`book → chapter → page` nodes, with `page —explains→ code` edges.

## Layout

```
books/
└── <book-name>/
    └── <page>.md
```

## Page format

Each page is markdown with YAML frontmatter:

```markdown
---
title: Input Validation
chapter: security
explains:
  - sanitize_input      # optional: code symbols this page explains
---
Body of the reference page…
```

- `title` — page name (shown in graph queries).
- `chapter` — groups pages within a book.
- `explains` — optional list of code symbols; creates `page —explains→ code` edges.

## Per-role shelves

Map a book to the agents that should consult it, in `config.yaml`:

```yaml
books:
  security: [owasp]      # the security role reasons from the owasp book
  qa: [testing]
```

## Licensing — hard gate

**Only add books you are licensed to use.** Never commit copyrighted texts to a
public fork. The shipped starter library (if any) is original / openly-licensed
(CC-BY / MIT) only; domain references are bring-your-own. This is the same hard
licensing gate the framework applies to everything it bundles.

## Authoring

Reference-page distillation is bulk content work — generate it on a low-cost
model tier (the content role), never a premium model. Authoring a library with a
top-tier model would violate the framework's own cost principle.
