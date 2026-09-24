# MCP Governance

This document defines which MCP servers are approved for use in the agent org,
which are rejected, and the process for adding new ones. Keep it up to date
any time an MCP is added or removed.

---

## Approved MCPs

| MCP | Purpose | Notes |
| --- | --- | --- |
| *(project-specific — document here)* | | |

---

## Rejected MCPs

The following MCPs were evaluated and explicitly rejected. Do not add them
without revisiting the stated rationale.

| MCP | Reason |
| --- | --- |
| **filesystem (full-write)** | Grants agents write access to the entire filesystem. Prytan enforces scoped-write boundaries via `perms_file` instead; a full-write MCP would bypass that safety layer. |
| **git** | Allows agents to commit, push, and create branches autonomously. All merges require explicit human approval; an autonomous git MCP removes that gate. |
| **shell / bash (unrestricted)** | Arbitrary shell execution from agents creates uncontrolled side effects. Bash is only permitted for the `security` agent and scoped to grep/scan commands. |
| **browser-control (headless)** | Headless browser MCPs can exfiltrate data or be used to access authenticated sessions. Use read-only fetch or Claude-in-Chrome with explicit user approval instead. |
| **email / calendar (send)** | Agents that can send email or book meetings can cause unintended external communication. Drafting is fine; sending always requires human confirmation. |

---

## Process for adding a new MCP

1. **Propose** — Open a ticket or write a short proposal in `.handoffs/` with:
   - What the MCP does
   - Which agent(s) would use it and for what tasks
   - What access it requires (read / write / network / etc.)
2. **Review** — governance + security must both sign off before installation.
3. **Scope** — Configure the MCP with the minimum required permissions. If it
   grants write access, ensure it is limited to the same comm dirs that
   `write_perms_file()` enforces (`.inbox`, `.handoffs`, `.proposals`, `.logs`).
4. **Document** — Add it to the Approved MCPs table above with a clear purpose
   and any scope restrictions.
5. **Test** — Run at least one full gsd-plan / gsd-execute / gsd-verify cycle
   with the MCP active before marking it production-ready.

---

## General principles

- **Least privilege.** Grant agents the narrowest access that satisfies the
  use case. Expand later if needed rather than granting broad access upfront.
- **No autonomous external side-effects.** Agents should not send messages,
  push code, or charge money without explicit human confirmation.
- **Auditability.** Every MCP action that modifies state outside the project
  directory should be logged. Use the usage ledger in `.logs/usage.tsv` as a
  reference model.
- **Reversibility.** Prefer MCPs whose actions can be undone (drafts over
  sends, branches over direct commits, proposals over live edits).
