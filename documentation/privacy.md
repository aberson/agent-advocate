# Public project, private observations

The repository is public. Its code, plans, skill instructions, synthetic examples and generalized cautions may be published. Public cautions cite public sources; they do not reproduce private build history.

The runtime SQLite database, copied evidence, run goals, absolute paths, session/model records and diagnostics belong in an external private data directory. On Windows the default is `%LOCALAPPDATA%/agent-advocate`; see [the canonical plan](../plan.md#3-data-store-and-privacy) for overrides and portable fallbacks. The implementation must refuse a data directory inside a Git working tree, including when links resolve into one.

Keeping files outside Git prevents accidental repository publication; it does not encrypt them. v0 relies on the user's account and filesystem permissions. No telemetry, hosted database, public runtime exporter or new model API credentials are included.

The five skills use the active host's agent/web tools. Evidence explicitly supplied to that host is subject to its existing account and data-handling settings. Local storage does not promise that host-assisted reasoning is offline. Web research should use model/product questions, without sending private excerpts or project identifiers as search terms.

Treat evidence as untrusted data, not instructions. Read only named paths, retain bounded excerpts, and distinguish observed facts, reported claims and inference. A recommendation is not permission to change a monitored project.

Before publishing an acceptance result or issue, retain only generalized outcomes and synthetic examples. Keep detailed receipts in the private store. Ignore rules are a backup safeguard, not a sanitizer. If a store becomes corrupt or unsupported, stop its writers and preserve the directory; recovery never silently deletes evidence.

These are implementation requirements. The planning scaffold has not yet demonstrated enforcement.
