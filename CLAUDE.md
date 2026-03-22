# Claude Code Notes

Use [AGENTS.md](AGENTS.md) as the primary workflow guide for this repository.

## Recommended Behavior

- prefer executing the repository scripts over rewriting the workflow from scratch
- keep the target page loaded in the user's CDP-enabled Chrome session
- treat runtime chunk data as the source of truth for completeness
- separate content completeness from visual parity in status updates

## Suggested Prompt

Ask Claude Code to:

```text
Use the workflow in AGENTS.md to export this Feishu document into a local HTML package with localized images and a completeness audit.
```

If folded sections are important, include:

```text
Verify these headings after export: Heading One, Heading Two
```
