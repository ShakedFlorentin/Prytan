---
name: code-review
description: Review code for bugs, security issues, and maintainability
argument-hint: "[file path, diff, or 'staged']"
allowed-tools:
  - Read
  - Bash
  - Glob
  - Grep
---

# /code-review

Review the code specified in `$ARGUMENTS` (a file path, glob, or "staged" for `git diff --staged`).

## What to check

**Bugs & correctness**
- Off-by-one errors, null/undefined handling, error paths that swallow exceptions
- Race conditions, uninitialized state, incorrect comparisons

**Security**
- User input reaching SQL/shell/template without sanitization
- Credentials or secrets hardcoded or logged
- Missing auth/authz checks on routes or object access (IDOR)

**Maintainability**
- Functions longer than ~40 lines — suggest splitting
- Names that don't describe what the thing does
- Missing tests for non-trivial logic

**Performance** (flag only obvious problems)
- N+1 queries, loading full datasets when a count or single record would do

## Output format

```
## Code Review — <file or scope> — <date>

### 🔴 Must fix
- [file:line] — <issue> — <recommended fix>

### 🟡 Should fix
- [file:line] — <issue> — <recommendation>

### 🟢 Suggestions
- [file:line] — <optional improvement>

### ✅ Looks good
- <what was reviewed and passed>
```

If `$ARGUMENTS` is empty, review `git diff --staged`.
