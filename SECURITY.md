# Security

AetherGuard is a synthetic refund prototype. Keep access limited to trusted collaborators and run the development services on loopback.

- A single bearer token protects the HTTP API except health. It gives access to policy changes, approval decisions, and sandbox reset. Reviewer and operator labels are not independent authenticated user identities.
- The stdio launcher supplies the MCP principal. The in-process MCP path shares application and database privileges. Use trusted launchers and restrict database access.
- Scoped authorization, current policy checks, exact-action fingerprints, atomic refund state updates, and idempotency reduce unintended or repeated execution. SQLite audit data is mutable by database writers.
- Use only synthetic ticket data. Live proposals send ticket text to Gemini. The quote service receives the exchange-rate request, independent of ticket content.

Report vulnerabilities privately to the repository owner with affected revision, impact, and relevant evidence. Keep real tokens and private records out of issues and pull requests. Rotate an exposed credential promptly and remove it from publication scope, including prior Git objects.
