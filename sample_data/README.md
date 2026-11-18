# Demo fixtures

The JSON files contain the offline CloudDesk demo records. The startup bootstrap
loads profiles, customers, subscriptions, workspaces, products, incidents, tickets,
and their initial messages into an empty database when `DEMO_MODE=true`.

The fixture set has eight customers and the thirteen `CD-1001`–`CD-1013` scenarios
defined in `CLAUDE.md`. `previous_resolutions.json` is a retrieval fixture for the
knowledge/similar-case pipeline; it is not inserted into a domain table.

Keep UUIDs stable across files and preserve parent-before-child references. Do not
put real customer information, credentials, or other secrets in these fixtures.

`knowledge_base/` contains 15 Markdown support articles used by the offline RAG
pipeline. Each article has YAML front matter for `title`, `category`, `tags`, and
`summary`, followed by Markdown headings and support guidance. Article files are
fixtures and must not contain secrets or real customer data.
