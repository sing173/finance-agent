# Triage labels

The `triage` skill applies the following GitHub labels to move issues through its state machine:

| Role | Label | Meaning |
|------|-------|---------|
| Needs evaluation | `needs-triage` | Maintainer must review before any further action |
| Needs info | `needs-info` | Waiting for the reporter to supply more details |
| Ready for agent | `ready-for-agent` | Fully specified; an AFK agent can pick this up without human context |
| Ready for human | `ready-for-human` | Requires a person to implement; no agent should be assigned |
| Won't fix | `wontfix` | Intentionally not being actioned |

All five labels use their default names — no custom mapping is configured.
