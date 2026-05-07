# Privacy

`mirror-mirror` is designed for local operator experiments. Readout logs can contain private context even when the protocol looks harmless.

## What may leak

Readouts may include:

- project names,
- prompt fragments,
- architectural decisions,
- operator preferences,
- session IDs,
- private uncertainty or escalation notes,
- enough context to reconstruct what the agent was working on.

Do not publish raw `readouts.jsonl` files unless they are intentionally anonymized.

## Defaults

The MCP server writes readouts to:

```text
~/.mirror-mirror/readouts.jsonl
```

You can override this with:

```bash
MIRROR_MIRROR_LOG=/path/to/private/readouts.jsonl
```

## Safe Sharing Checklist

Before sharing logs, examples, or issues:

1. Remove private project names and file paths.
2. Remove secrets, tokens, customer data, and private prompts.
3. Replace exact session IDs if they identify a real workflow.
4. Keep the functional-state pattern and operator recommendation.
5. Mark the example as synthetic or anonymized.

## Public Examples

The examples in this repository are synthetic. They show the shape of the protocol, not real sessions.

## Operator Rule

Treat readout logs like agent transcripts: useful for debugging, risky if pasted blindly.
