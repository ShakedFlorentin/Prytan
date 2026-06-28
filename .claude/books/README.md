# .claude/books/ — Reference Documentation Index

Place any markdown documentation here and codegrapher will index it into the
knowledge graph — so agents can find it with `python3 codegrapher.py query "<topic>"`
instead of reading whole files.

## Frontmatter format

Every page you want indexed needs YAML frontmatter:

```markdown
---
id: unique-id-for-this-page
type: page          # or "book" for the root index file
chapter: chapter-slug
book: book-slug
keywords: keyword1, keyword2, keyword3
explains: module.function, ClassName.method
---

# Page Title

Your content here...
```

| Field | Required | Description |
|---|---|---|
| `id` | Yes | Unique slug (no spaces) |
| `type` | Yes | `book` (root file) or `page` (content) |
| `chapter` | For pages | Groups pages within a book |
| `book` | For pages | Which book this page belongs to |
| `keywords` | Recommended | Comma-separated terms for search |
| `explains` | Optional | Code symbols this page documents |

## Example structure

```
.claude/books/
  architecture/
    _book.md         # type: book, id: architecture
    overview.md      # type: page, book: architecture, chapter: intro
    auth-design.md   # type: page, book: architecture, chapter: security
  api-reference/
    _book.md
    endpoints.md
    errors.md
```

## After adding pages

Re-scan to update the graph:

```bash
python3 codegrapher.py scan .
```

Agents can then find your docs:

```bash
python3 codegrapher.py query "authentication flow"
# → returns page:auth-design with file path — read ONLY that page
```

## Protocol (token-saving rule)

**Never read a whole book.** Query the graph → get the page node → read only that file.
This is enforced by `codegrapher_hook.py` which fires before every Read/Grep/Glob call.
