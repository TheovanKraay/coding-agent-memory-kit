# Decisions

Architectural and design decisions with rationale.

<!-- Format:
## DEC-<number>: <title>
- **Date:** <YYYY-MM-DD>
- **Status:** accepted | superseded | deprecated
- **Context:** <why this decision was needed>
- **Decision:** <what was decided>
- **Rationale:** <why>
- **Consequences:** <trade-offs>
-->

## DEC-001: Markdown for long-term memory
- **Date:** 2026-04-20
- **Status:** accepted
- **Context:** Need a format for persistent project memory that agents and humans can both use.
- **Decision:** Use plain markdown files in the repo root for long-term memory artifacts.
- **Rationale:** Portable, human-readable, git-trackable. Every agent and IDE can read/write markdown. Diffs are meaningful in PRs.
- **Consequences:** Less structured than a database; parsing requires conventions. Mitigated by `LongTermMemoryManager`.

## DEC-002: Cosmos DB for session memory
- **Date:** 2026-04-20
- **Status:** accepted
- **Context:** Session memory needs vector search, cross-agent access, and real-time sync.
- **Decision:** Use Azure Cosmos DB via AgentMemoryToolkit for session/working memory.
- **Rationale:** Built-in vector search, hierarchical partition keys, change feed for processing pipelines, fits Azure ecosystem.
- **Consequences:** Requires Azure infrastructure. Local-only mode uses in-memory store as fallback.

## DEC-003: AgentMemoryToolkit as dependency
- **Date:** 2026-04-20
- **Status:** accepted
- **Context:** Need Cosmos DB integration with embeddings, search, and processing pipelines.
- **Decision:** Depend on AgentMemoryToolkit rather than building Cosmos integration from scratch.
- **Rationale:** Avoids reinventing CRUD, vector search, change feed processing. Maintained alongside this project.
- **Consequences:** Coupling to toolkit API. Mitigated by `CosmosSessionSync` wrapper.

## DEC-004: Hierarchical memory architecture
- **Date:** 2026-04-20
- **Status:** accepted
- **Context:** Need both persistent project knowledge and ephemeral session context.
- **Decision:** Two-layer approach: repo markdown = source of truth, Cosmos DB = working memory.
- **Rationale:** Repo files persist across sessions and are version-controlled. Cosmos provides fast search and cross-agent sharing during sessions.
- **Consequences:** Requires sync logic between layers. `MemoryArtifactUpdater` handles end-of-session promotion.
