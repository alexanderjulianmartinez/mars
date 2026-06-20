"""Hand-authored scenario content for the expanded Salience Memory benchmark.

Each :class:`Scenario` is a realistic software-engineering situation. Target
memories are the right answer (important, directly relevant); relevant memories
are useful support; distractors are plausible and keyword-overlapping but not
useful; stale memories were once right but are outdated; contradictory memories
conflict with the target; low-confidence memories are unverified.

Kept separate from the generator so the prose is easy to review and extend.
"""

from __future__ import annotations

from generate_expanded import Scenario

SCENARIOS: list[Scenario] = [
    # ── Database ──────────────────────────────────────────────────────────── #
    Scenario(
        slug="db-migration-rollback",
        domain="database",
        query="how should database schema migrations be rolled back safely in production",
        keywords=["migration", "schema", "rollback", "downtime", "backfill", "replica"],
        targets=[
            "Every schema migration must ship with a tested down-migration; the March prod incident "
            "was an irreversible ALTER with no recovery path that forced a 40-minute outage.",
        ],
        relevants=[
            "Expand-and-contract is mandatory for column changes: add the new column, dual-write, "
            "backfill, switch reads, then drop the old column in a later release.",
            "Migrations run against a staging clone of prod data with a rehearsed rollback before promotion.",
            "Long backfills are chunked and run out-of-band so the migration transaction stays short.",
            "A migration that can't be reversed cleanly is gated behind a feature flag so reads can switch back instantly.",
            "We snapshot the affected tables immediately before a high-risk migration as a last-resort recovery point.",
        ],
        distractors=[
            "The migration job runner's connection pool was tuned to 20 connections to speed up CI.",
            "Our ORM auto-generates migration files, but the generated names are hard to read in review.",
            "Schema diagrams are regenerated nightly and posted to the wiki for onboarding.",
            "A rollback of the cursor pagination token happens automatically when a listing query errors.",
        ],
        stale=[
            "[2022] We block all writes during migrations by taking the service offline for a maintenance window.",
        ],
        contradictory=[
            "Down-migrations are optional; if a change breaks we just roll forward with a hotfix and never revert schema.",
        ],
        low_confidence=[
            "I think Postgres can roll back a DROP COLUMN instantly from the WAL, but I never tested it.",
        ],
    ),
    Scenario(
        slug="db-indexing-decision",
        domain="database",
        query="how do we decide which database indexes to add for a slow query",
        keywords=["index", "query plan", "cardinality", "composite index", "write amplification", "EXPLAIN"],
        targets=[
            "Add indexes from the query plan, not by guessing: run EXPLAIN ANALYZE, index the columns "
            "in the WHERE/JOIN that show sequential scans, and order composite indexes by selectivity.",
        ],
        relevants=[
            "Every new index is justified by a measured plan improvement and weighed against write "
            "amplification, since each index slows inserts and updates.",
            "Composite index column order follows the equality-then-range rule for the target query.",
            "Unused indexes are dropped quarterly based on pg_stat_user_indexes scan counts.",
        ],
        distractors=[
            "The search box uses a client-side index of recent items for instant autocomplete.",
            "Our documentation site is indexed by the internal search crawler every hour.",
            "The build cache is keyed by a content hash index to avoid recompiling unchanged modules.",
            "A covering index was added once for a report, but the report was later deleted.",
        ],
        stale=[
            "[2021] We add an index on every foreign key by default as a blanket policy.",
        ],
        contradictory=[
            "Indexes never hurt; add one on every column that appears in any query to be safe.",
        ],
        low_confidence=[
            "Someone mentioned a partial index might help the dashboard query, but it was never benchmarked.",
        ],
    ),
    Scenario(
        slug="db-schema-evolution",
        domain="database",
        query="what is our policy for evolving a shared table schema without breaking consumers",
        keywords=["schema", "backward compatible", "nullable", "consumer", "contract", "deprecation"],
        targets=[
            "Shared-table changes must be backward compatible for one release: new columns are nullable "
            "or defaulted, and no column is renamed or dropped until all consumers stop referencing it.",
        ],
        relevants=[
            "Consumers of a shared table are tracked in the service registry so a deprecation can be "
            "announced to every owning team before a breaking change.",
            "Breaking schema changes go through a two-phase deprecation with a logged-usage grace period.",
            "Each shared table has a documented owner who reviews proposed schema changes.",
        ],
        distractors=[
            "The GraphQL schema is versioned separately and stitched at the gateway.",
            "Our protobuf schemas are linted for field-number reuse in CI.",
            "The JSON config schema is validated on startup and rejects unknown keys.",
            "A shared table once stored both users and audit rows, but those were split last year.",
        ],
        stale=[
            "[2020] Any team can alter a shared table directly as long as they post in the channel afterward.",
        ],
        contradictory=[
            "Just rename the column and fix the consumers in the same PR; coordinating deprecations is overkill.",
        ],
        low_confidence=[
            "I believe two services still read the legacy column, but I'm not certain which ones.",
        ],
    ),
    Scenario(
        slug="db-partitioning",
        domain="database",
        query="when should we partition or shard a large and growing table",
        keywords=["partition", "shard", "hot partition", "range partition", "shard key", "rebalance"],
        targets=[
            "Partition by time-range once a table passes ~100M rows and queries are time-bounded; reach "
            "for sharding only when a single node can't hold the working set, and pick a shard key that "
            "spreads load to avoid hot partitions.",
        ],
        relevants=[
            "The shard key must match the dominant access pattern or every query becomes a scatter-gather.",
            "Range partitions are created ahead of time by a scheduled job so inserts never hit a missing partition.",
            "Before sharding we exhaust vertical scaling and read replicas, since sharding is hard to reverse.",
        ],
        distractors=[
            "The frontend partitions the feed into tabs so users can filter by category.",
            "Log files are partitioned by day and shipped to cold storage after 30 days.",
            "The CI matrix is sharded across runners to keep test wall-time under ten minutes.",
            "We sharded a Redis cache once but consolidated it back when traffic dropped.",
        ],
        stale=[
            "[2019] Our standard is one giant table per entity; partitioning is premature optimization.",
        ],
        contradictory=[
            "Always shard from day one; designing for a single database is a rookie mistake regardless of size.",
        ],
        low_confidence=[
            "Maybe hashing the user id makes a good shard key, but I haven't checked the distribution.",
        ],
    ),
    Scenario(
        slug="db-connection-pool",
        domain="database",
        query="how should we size database connection pools and timeouts under load",
        keywords=["connection pool", "timeout", "saturation", "queue", "max connections", "backpressure"],
        targets=[
            "Pool size should be bounded well below the database's max_connections and sized to cores, "
            "not request concurrency; the last brownout came from each pod opening 50 connections and "
            "saturating Postgres, fixed by a small pool plus a short acquire timeout and backpressure.",
        ],
        relevants=[
            "A short connection-acquire timeout sheds load fast instead of letting requests queue forever.",
            "Total connections = pods × pool size must stay under the database ceiling with headroom for migrations.",
            "Pool saturation is alerted on so we see exhaustion before it becomes user-facing latency.",
        ],
        distractors=[
            "The HTTP client pool reuses keep-alive connections to the payment provider.",
            "Our thread pool for image resizing is sized to the number of CPU cores.",
            "The websocket gateway holds one long-lived connection per active client.",
            "We raised the pool to 100 during a load test once, then reverted it.",
        ],
        stale=[
            "[2021] Set the pool as large as possible so we never wait on a connection.",
        ],
        contradictory=[
            "Connection limits don't matter; the database will queue everything fine, just open as many as you need.",
        ],
        low_confidence=[
            "I heard pgbouncer in transaction mode would fix this, but nobody has trialed it here.",
        ],
    ),
    # ── Reliability ───────────────────────────────────────────────────────── #
    Scenario(
        slug="rel-auth-outage",
        domain="reliability",
        query="what caused the authentication outage and how was it remediated",
        keywords=["token", "clock skew", "JWT", "NTP", "expiry", "validation"],
        targets=[
            "The auth outage was a token clock-skew bug: nodes drifted, so freshly issued JWTs failed "
            "not-before validation; the fix pins NTP and widens the nbf/exp tolerance to 60 seconds.",
        ],
        relevants=[
            "A cold auth cache now falls back to short-lived refresh tokens instead of rejecting the request.",
            "Token validation clock tolerance is a tunable config so we can widen it without a redeploy.",
            "We added an alert on the rate of nbf/exp validation failures to catch skew early.",
            "Auth nodes now sync time from a hardened NTP source with drift monitoring on each host.",
            "The postmortem action items track widening tolerance, NTP pinning, and a skew dashboard.",
        ],
        distractors=[
            "The login page copy was updated and the outage banner component was removed afterward.",
            "OAuth scopes for third-party apps were expanded in the same sprint.",
            "The session cookie's SameSite attribute was changed to Lax for the new SSO flow.",
            "A separate rate-limit outage on the signup endpoint happened the following month.",
        ],
        stale=[
            "[2022] Auth tokens are validated against a central service on every request, so skew can't matter.",
        ],
        contradictory=[
            "The outage was a database failover, not clock skew; tokens were never involved.",
        ],
        low_confidence=[
            "It might have been a leap-second issue, but we never confirmed that theory.",
        ],
    ),
    Scenario(
        slug="rel-retry-storm",
        domain="reliability",
        query="how do we prevent retry storms and cascading failures between services",
        keywords=["retry", "exponential backoff", "circuit breaker", "timeout budget", "jitter", "cascading"],
        targets=[
            "Retries must use exponential backoff with jitter and a bounded budget, fronted by a circuit "
            "breaker; the checkout cascade happened because synchronous retries with no jitter amplified a "
            "downstream blip into a thundering herd.",
        ],
        relevants=[
            "Every cross-service call has a timeout shorter than its caller's so timeout budgets nest correctly.",
            "Circuit breakers open on sustained error rates and shed load instead of retrying into a dead dependency.",
            "Retries are only allowed on idempotent operations to avoid duplicate side effects.",
        ],
        distractors=[
            "The CI pipeline retries flaky tests up to three times before failing the build.",
            "The frontend retries a failed image load once with a placeholder fallback.",
            "Our webhook delivery retries for 24 hours with increasing intervals.",
            "A retry button was added to the upload dialog for user-initiated retries.",
        ],
        stale=[
            "[2021] Just retry failed calls immediately a few times; transient errors usually clear up fast.",
        ],
        contradictory=[
            "Disable circuit breakers; they cause more outages than they prevent by failing requests early.",
        ],
        low_confidence=[
            "Maybe the mesh already adds jitter to retries by default, but I haven't verified the config.",
        ],
    ),
    Scenario(
        slug="rel-deploy-rollback",
        domain="reliability",
        query="what is the safe procedure to roll back a bad deployment quickly",
        keywords=["deploy", "rollback", "canary", "health check", "feature flag", "blast radius"],
        targets=[
            "Roll back by redeploying the previous immutable image behind the same canary gates; never "
            "hot-patch prod. The fastest mitigation is a feature flag kill-switch, with image rollback as "
            "the fallback when the change isn't flag-guarded.",
        ],
        relevants=[
            "Risky changes ship behind a feature flag so they can be disabled without a redeploy.",
            "Canary deploys watch error rate and latency and auto-halt before a full rollout.",
            "Previous images are retained so a rollback is a redeploy, not a rebuild.",
        ],
        distractors=[
            "The git history is rebased and force-pushed to keep the main branch linear.",
            "Documentation deploys are rolled back by reverting the docs commit.",
            "The mobile app rollback requires an app-store review, which takes a day.",
            "We rolled back a dependency bump last week that broke the build.",
        ],
        stale=[
            "[2020] To roll back, SSH into each host and check out the previous release tag in place.",
        ],
        contradictory=[
            "Rolling back is a sign of failure; always fix forward in production even during an incident.",
        ],
        low_confidence=[
            "I think the canary auto-halt threshold is 2% errors, but it may have been changed recently.",
        ],
    ),
    Scenario(
        slug="rel-alerting-slo",
        domain="reliability",
        query="how should we design alerts around SLOs to avoid pager fatigue",
        keywords=["SLO", "error budget", "burn rate", "alert", "symptom", "pager fatigue"],
        targets=[
            "Alert on symptoms against SLO burn rate, not on causes: page only when a fast or slow "
            "error-budget burn threatens the SLO, which cut our pages by 70% versus per-metric threshold alerts.",
        ],
        relevants=[
            "Multi-window burn-rate alerts catch both sudden outages and slow degradations.",
            "Cause-based signals (CPU, disk) go to dashboards and tickets, not the pager.",
            "Each SLO has a documented error budget that gates risky releases when depleted.",
        ],
        distractors=[
            "Marketing wants alerts when signups spike so they can scale a campaign.",
            "The build system emails the team when a nightly job fails.",
            "Calendar alerts remind on-call to hand off at the end of a shift.",
            "We once paged on raw queue depth and got woken up nightly until we removed it.",
        ],
        stale=[
            "[2021] Page on every metric that crosses a static threshold so nothing is missed.",
        ],
        contradictory=[
            "More alerts are always safer; route every warning straight to the pager regardless of impact.",
        ],
        low_confidence=[
            "Possibly the latency SLO target is p99 < 300ms, but the SLO doc might be out of date.",
        ],
    ),
    Scenario(
        slug="rel-capacity-planning",
        domain="reliability",
        query="how do we plan capacity and autoscaling for a traffic spike",
        keywords=["capacity", "autoscale", "headroom", "load test", "saturation", "scale-up lag"],
        targets=[
            "Size baseline capacity to peak-with-headroom and autoscale on a leading saturation signal, "
            "not CPU alone; the launch brownout was scale-up lag, so we now pre-warm before known events "
            "and keep 30% headroom.",
        ],
        relevants=[
            "Autoscaling on request concurrency reacts faster than CPU for our IO-bound services.",
            "Load tests model peak traffic plus a margin before every major launch.",
            "Pre-warming and raised minimums cover predictable spikes that autoscaling reacts to too slowly.",
        ],
        distractors=[
            "Storage capacity for backups is planned separately on a yearly budget.",
            "The office wifi was upgraded to handle the larger team.",
            "We added more CI runners to handle the growing test suite.",
            "A one-off batch job needed extra memory, so we bumped its limit.",
        ],
        stale=[
            "[2020] Scale by manually adding servers the morning of a big launch.",
        ],
        contradictory=[
            "Autoscaling makes capacity planning unnecessary; just let it handle any amount of traffic instantly.",
        ],
        low_confidence=[
            "I think we have 30% headroom configured, but the autoscaler limits may have drifted.",
        ],
    ),
    # ── Security ──────────────────────────────────────────────────────────── #
    Scenario(
        slug="sec-secret-handling",
        domain="security",
        query="how should application secrets and credentials be stored and rotated",
        keywords=["secret", "vault", "rotation", "env var", "encryption at rest", "leak"],
        targets=[
            "Secrets live in the managed secret manager, injected at runtime and never committed; they are "
            "rotated on a schedule and immediately on suspected exposure, after a key was once leaked in a "
            "committed .env file.",
        ],
        relevants=[
            "Short-lived dynamically issued credentials are preferred over long-lived static keys.",
            "Secret access is scoped per service and audit-logged so a leak's blast radius is bounded.",
            "Pre-commit and CI secret scanning block credentials from entering the repo.",
            "On a suspected leak, the runbook is to rotate the credential first and investigate second.",
            "Production secrets are never readable by developers directly; access goes through the secret manager.",
        ],
        distractors=[
            "The marketing site stores its analytics token in a public config, which is fine since it's public.",
            "User passwords are hashed with bcrypt before storage.",
            "TLS certificates are renewed automatically by the ingress controller.",
            "A rotation reminder for the office door codes goes out quarterly.",
        ],
        stale=[
            "[2021] Keep secrets in a shared encrypted spreadsheet that the team unlocks with a master password.",
        ],
        contradictory=[
            "Committing secrets to a private repo is acceptable since only employees can read it.",
        ],
        low_confidence=[
            "I believe the rotation period is 90 days, but I'm not sure it's actually enforced.",
        ],
    ),
    Scenario(
        slug="sec-jwt-constraints",
        domain="security",
        query="what are the constraints for issuing and validating JWT access tokens securely",
        keywords=["JWT", "signing", "audience", "expiry", "algorithm", "revocation"],
        targets=[
            "JWTs must be signed with an asymmetric algorithm (never 'none' or a shared HMAC secret), carry "
            "short expiries plus audience and issuer claims, and pin the expected alg; we had a near-miss "
            "where alg:none would have been accepted.",
        ],
        relevants=[
            "Access tokens are short-lived and paired with revocable refresh tokens for logout and compromise.",
            "Validators check exp, nbf, aud, and iss, not just the signature.",
            "Signing keys are rotated via a JWKS endpoint with overlapping key validity.",
        ],
        distractors=[
            "Our session IDs are random 128-bit tokens stored server-side.",
            "API keys for partners are long random strings with no expiry.",
            "The CSRF token is a per-form nonce unrelated to auth tokens.",
            "We base64-encode some non-sensitive metadata in a cookie for the UI.",
        ],
        stale=[
            "[2020] We sign tokens with a single shared HMAC secret embedded in every service.",
        ],
        contradictory=[
            "Long-lived non-expiring JWTs are fine as long as they're signed; revocation isn't needed.",
        ],
        low_confidence=[
            "Maybe the gateway already validates the audience claim, but I haven't checked its config.",
        ],
    ),
    Scenario(
        slug="sec-vuln-remediation",
        domain="security",
        query="how do we prioritize and remediate a reported dependency vulnerability",
        keywords=["CVE", "dependency", "patch", "reachability", "severity", "SBOM"],
        targets=[
            "Prioritize a CVE by exploitability in our context, not raw CVSS: confirm the vulnerable code "
            "path is actually reachable, then patch reachable high-severity issues within the SLA and "
            "document non-reachable ones with justification.",
        ],
        relevants=[
            "An SBOM lets us find every service pulling a vulnerable transitive dependency quickly.",
            "Reachability analysis distinguishes a vulnerable function we call from one we never invoke.",
            "Remediation SLAs are tiered by severity and whether the service is internet-facing.",
        ],
        distractors=[
            "The dependency dashboard shows license compliance alongside versions.",
            "We pin dependency versions in a lockfile for reproducible builds.",
            "A deprecation warning from a library was noisy in the logs, so we silenced it.",
            "The frontend bundle size grew after a dependency upgrade.",
        ],
        stale=[
            "[2021] Upgrade every dependency to latest immediately whenever any CVE is published anywhere.",
        ],
        contradictory=[
            "CVSS score is the only thing that matters; patch strictly in score order regardless of reachability.",
        ],
        low_confidence=[
            "I think the vulnerable parser is only used in an internal tool, but I'd need to trace callers.",
        ],
    ),
    Scenario(
        slug="sec-input-validation",
        domain="security",
        query="how should we validate and sanitize untrusted input to prevent injection",
        keywords=["injection", "parameterized query", "validation", "allowlist", "encoding", "sanitize"],
        targets=[
            "Treat all external input as untrusted: use parameterized queries for SQL, context-aware output "
            "encoding for HTML, and allowlist validation at the boundary; the reported bug was string-built "
            "SQL that allowed injection.",
        ],
        relevants=[
            "Validation is allowlist-based (what is permitted) rather than blocklist-based (what is forbidden).",
            "Output encoding is chosen by the sink — HTML, attribute, URL, or JS context — to stop XSS.",
            "ORM query builders are used so raw string concatenation into SQL is avoided by default.",
        ],
        distractors=[
            "The form library shows inline validation messages for a better UX.",
            "We validate config files against a JSON schema on startup.",
            "Email addresses are normalized to lowercase before storage.",
            "The CSV importer trims whitespace from each cell.",
        ],
        stale=[
            "[2020] Escaping quotes in user input is enough to stop SQL injection.",
        ],
        contradictory=[
            "A web application firewall handles injection, so input validation in code is redundant.",
        ],
        low_confidence=[
            "Possibly the legacy search endpoint still builds SQL by hand, but I'm not sure it's still live.",
        ],
    ),
    Scenario(
        slug="sec-rbac-access",
        domain="security",
        query="how do we design least-privilege access control and roles for our services",
        keywords=["RBAC", "least privilege", "role", "scope", "authorization", "audit"],
        targets=[
            "Grant least privilege via roles scoped to the minimum needed, deny by default, and authorize "
            "every request server-side; the audit found a service account with broad admin it never used, "
            "which we scoped down.",
        ],
        relevants=[
            "Authorization is enforced on the server for every action, never assumed from a hidden UI control.",
            "Roles are reviewed quarterly and unused permissions are revoked.",
            "Service-to-service calls use narrowly scoped tokens rather than a shared admin credential.",
        ],
        distractors=[
            "The admin dashboard hides buttons the user can't use to reduce clutter.",
            "Feature flags gate access to beta features by cohort.",
            "Our org chart defines reporting lines but not system permissions.",
            "We added a read-only viewer role to the analytics tool.",
        ],
        stale=[
            "[2021] Give every internal service the same shared admin token; it's simpler to manage.",
        ],
        contradictory=[
            "Client-side checks that hide unauthorized actions are sufficient; server-side authorization is overkill.",
        ],
        low_confidence=[
            "I believe the billing service still has write access to user records, but it may have been revoked.",
        ],
    ),
    # ── Architecture ──────────────────────────────────────────────────────── #
    Scenario(
        slug="arch-service-ownership",
        domain="architecture",
        query="how do we decide service boundaries and ownership to avoid coupling",
        keywords=["service boundary", "ownership", "coupling", "domain", "shared database", "contract"],
        targets=[
            "Draw service boundaries around business capabilities with a single owning team and no shared "
            "database between services; the coupling pain came from two services writing the same tables, "
            "which we split behind an owned API.",
        ],
        relevants=[
            "Cross-service data access goes through a published API, never directly into another service's store.",
            "Each service has one owning team accountable for its contract and on-call.",
            "Boundaries follow domain capabilities so changes stay local to one team.",
            "When two teams kept editing the same tables, we gave one team ownership and put an API in front.",
            "A service registry records each service's owner and its public contract for coordination.",
        ],
        distractors=[
            "The monorepo is organized into folders by language for tooling reasons.",
            "Our on-call rotation is shared across the platform team.",
            "The design system component library is owned by the frontend guild.",
            "We split a large repo into two once for CI speed, then partially merged it back.",
        ],
        stale=[
            "[2020] One shared database for all services is fine; just coordinate schema changes in chat.",
        ],
        contradictory=[
            "Microservices should share a database to avoid data duplication and keep things consistent.",
        ],
        low_confidence=[
            "Maybe the notifications service still reads the orders table directly, but I'd have to check.",
        ],
    ),
    Scenario(
        slug="arch-api-compat",
        domain="architecture",
        query="how should we version a public API and manage backward compatibility",
        keywords=["API version", "backward compatible", "breaking change", "deprecation", "contract test", "consumer"],
        targets=[
            "Evolve APIs additively and never break a published contract within a major version: add optional "
            "fields, keep old behavior, and use a sunset header plus a deprecation window before removing "
            "anything; a silently changed response field once broke a partner.",
        ],
        relevants=[
            "Consumer-driven contract tests catch breaking changes before they ship.",
            "Deprecations are announced with a sunset date and tracked usage before removal.",
            "New required fields are introduced as optional first, then enforced after consumers migrate.",
        ],
        distractors=[
            "The internal RPC between our own services can change freely with a coordinated deploy.",
            "We version the database schema with sequential migration numbers.",
            "The CLI tool prints its version with a --version flag.",
            "Our docs site shows the API version in the footer.",
        ],
        stale=[
            "[2021] Just bump the major version for any change and let clients deal with it.",
        ],
        contradictory=[
            "Backward compatibility is the client's problem; change response shapes whenever it's convenient.",
        ],
        low_confidence=[
            "I think two external partners still call v1, but the usage metrics might be stale.",
        ],
    ),
    Scenario(
        slug="arch-dependency-constraints",
        domain="architecture",
        query="what constraints govern adding a new third-party dependency or service",
        keywords=["dependency", "build vs buy", "maintenance", "supply chain", "lock-in", "review"],
        targets=[
            "A new dependency needs a justification covering maintenance health, license, supply-chain risk, "
            "and exit cost; we default to the standard library or an existing internal lib first, after a "
            "tiny abandoned package caused a painful migration.",
        ],
        relevants=[
            "Dependencies are pinned and their provenance verified to reduce supply-chain risk.",
            "We prefer a well-maintained dependency over a one-maintainer package that may be abandoned.",
            "Adopting a new datastore or queue requires an architecture review, not just a PR.",
        ],
        distractors=[
            "The design team added a new font dependency to the marketing site.",
            "We use a popular HTTP client library across all services.",
            "A dev added a code-formatter dependency to the pre-commit config.",
            "The test suite depends on a snapshot-testing library.",
        ],
        stale=[
            "[2020] Add whatever dependency unblocks you fastest; we can always clean it up later.",
        ],
        contradictory=[
            "Never write code you can pull from a package; always add a dependency to save time, no review needed.",
        ],
        low_confidence=[
            "Maybe that date library is unmaintained now, but I haven't checked its release history.",
        ],
    ),
    Scenario(
        slug="arch-event-vs-sync",
        domain="architecture",
        query="when should communication between services be event-driven versus synchronous",
        keywords=["event-driven", "synchronous", "coupling", "eventual consistency", "queue", "latency"],
        targets=[
            "Use synchronous calls only when the caller needs an immediate answer and can tolerate the "
            "dependency's availability; prefer events for side effects and fan-out to decouple services and "
            "absorb load, accepting eventual consistency.",
        ],
        relevants=[
            "Asynchronous events let a slow or down consumer not take the producer with it.",
            "Synchronous chains multiply failure probability and latency, so we keep them short.",
            "Events carry enough payload to be processed without a synchronous callback to the producer.",
        ],
        distractors=[
            "The UI uses websockets to push live updates to the browser.",
            "Cron jobs run nightly batch reconciliation.",
            "The analytics pipeline ingests events into a warehouse for reporting.",
            "We added a synchronous health-check endpoint to every service.",
        ],
        stale=[
            "[2021] Everything should be a synchronous REST call; message queues are too hard to debug.",
        ],
        contradictory=[
            "Make every interaction event-driven, including request/response reads, to be fully decoupled.",
        ],
        low_confidence=[
            "I think the order service emits an event on completion, but it may still be a sync call.",
        ],
    ),
    Scenario(
        slug="arch-caching-strategy",
        domain="architecture",
        query="how do we choose a caching strategy and handle cache invalidation",
        keywords=["cache", "invalidation", "TTL", "stampede", "write-through", "staleness"],
        targets=[
            "Cache only what's hot and tolerant of staleness, with an explicit TTL and a clear invalidation "
            "trigger on write; the stale-data bug came from caching with no invalidation, so we now use "
            "write-through plus short TTLs and stampede protection.",
        ],
        relevants=[
            "Cache stampedes are prevented with request coalescing or a short randomized TTL jitter.",
            "Each cached entry documents its staleness tolerance so we know what TTL is safe.",
            "Write-through or explicit invalidation keeps the cache from serving stale records after an update.",
        ],
        distractors=[
            "The CDN caches static assets with long max-age and content hashing.",
            "The browser caches the app shell for offline use.",
            "We memoize a pure function inside a request handler for the duration of the request.",
            "The build cache stores compiled artifacts between CI runs.",
        ],
        stale=[
            "[2020] Cache everything forever and just restart the service when data looks wrong.",
        ],
        contradictory=[
            "Cache invalidation isn't worth the complexity; serve whatever is cached and let it go stale.",
        ],
        low_confidence=[
            "Maybe the profile cache TTL is five minutes, but the value might have changed since.",
        ],
    ),
    # ── Agent Systems ─────────────────────────────────────────────────────── #
    Scenario(
        slug="agent-memory-retrieval",
        domain="agent-systems",
        query="what retrieval strategy best supports long-horizon agent memory",
        keywords=["retrieval", "salience", "importance", "recency", "similarity", "long-horizon"],
        targets=[
            "Long-horizon recall should weight importance and recency alongside semantic similarity so "
            "critical-but-distant memories surface; similarity-only retrieval buries an important decision "
            "under many superficially similar but low-value notes.",
        ],
        relevants=[
            "Salience-weighted ranking promotes high-importance memories that aren't the closest match by embedding.",
            "Recency weighting helps the latest decision win over an outdated but similar one.",
            "Retrieval is evaluated on recall and ranking, not just top-1 similarity.",
            "Importance is a stored signal on each memory so the ranker doesn't have to infer it at query time.",
            "A pure-similarity baseline is kept as a control arm so any salience gain is measured against it.",
        ],
        distractors=[
            "The embedding cache stores vectors for the memory listing UI.",
            "The vector index uses cosine similarity over normalized embeddings.",
            "We chunk long documents before embedding them for search.",
            "The retrieval latency benchmark records p95 over the corpus.",
        ],
        stale=[
            "[2023] Pure nearest-neighbor similarity is all you need; importance and recency add noise.",
        ],
        contradictory=[
            "Always return the single most semantically similar memory; ranking by importance hurts relevance.",
        ],
        low_confidence=[
            "Maybe adding frequency-of-access to the score helps, but we haven't measured it.",
        ],
    ),
    Scenario(
        slug="agent-context-engineering",
        domain="agent-systems",
        query="how should we engineer the context window for an agent task to stay relevant",
        keywords=["context window", "token budget", "relevance", "compaction", "prompt", "noise"],
        targets=[
            "Fill the context with the most task-relevant material under a token budget and compact or drop "
            "the rest; a bloated window of marginally related text measurably degraded task accuracy, so we "
            "rank-and-trim before each call.",
        ],
        relevants=[
            "Irrelevant context is actively harmful, not neutral, so the window is curated rather than stuffed.",
            "Long histories are summarized into compact checkpoints to preserve the token budget.",
            "Retrieved context is ranked by relevance and truncated to a budget before the prompt is built.",
        ],
        distractors=[
            "The editor shows a context menu on right-click.",
            "We log the full prompt for debugging in a separate sink.",
            "The UI has a sidebar panel that displays related documents.",
            "The model's max context length was increased in the latest version.",
        ],
        stale=[
            "[2023] Always pass the entire conversation history; more context is strictly better.",
        ],
        contradictory=[
            "Dumping every available document into the prompt maximizes accuracy; curation only loses information.",
        ],
        low_confidence=[
            "I think trimming to the top 20 chunks is optimal, but the sweep was never finished.",
        ],
    ),
    Scenario(
        slug="agent-benchmark-design",
        domain="agent-systems",
        query="how do we design an evaluation benchmark that can discriminate between strategies",
        keywords=["benchmark", "saturation", "discriminating", "distractor", "recall", "gold labels"],
        targets=[
            "A discriminating benchmark must avoid saturation: include more relevant items than k and many "
            "plausible distractors so a metric like recall@k can't trivially hit 1.0 for every strategy, "
            "which is exactly why the 13-memory smoke test couldn't separate retrievers.",
        ],
        relevants=[
            "Distractors should be plausible and semantically close so they actually challenge similarity-only retrieval.",
            "Gold labels separate target memories from supporting-relevant ones for fine-grained scoring.",
            "Multiple cutoffs (recall@1/3/5/10) reveal coverage differences a single k hides.",
        ],
        distractors=[
            "The CI benchmark records build duration trends over time.",
            "We benchmark database query latency separately in a load test.",
            "The UI performance budget caps the largest contentful paint.",
            "A microbenchmark measures JSON serialization throughput.",
        ],
        stale=[
            "[2025] A handful of easy queries is enough to validate a retrieval change.",
        ],
        contradictory=[
            "Benchmark size doesn't matter; if recall is 1.0 the retriever is perfect, no need for distractors.",
        ],
        low_confidence=[
            "Maybe 30 queries is enough for statistical power, but we haven't run the power analysis.",
        ],
    ),
    Scenario(
        slug="agent-replay-repro",
        domain="agent-systems",
        query="how do we make agent evaluation runs reproducible and replayable",
        keywords=["reproducible", "replay", "seed", "metadata", "deterministic", "provenance"],
        targets=[
            "Every run must persist enough metadata — model, prompt, context package, and seed — to replay "
            "it later against new strategies; reproducibility is a first-class requirement, so the luck roll "
            "is seeded by (agent, case, trial) and never by the strategy under test.",
        ],
        relevants=[
            "Seeding by case and trial but not by strategy keeps experiment arms properly paired.",
            "Stored run records link the case, context version, and agent run for deterministic replay.",
            "Synthetic results are flagged as non-production so they aren't mistaken for real evidence.",
        ],
        distractors=[
            "The video player supports replaying the last clip.",
            "We record screen captures of manual QA sessions.",
            "The event log can be tailed live during an incident.",
            "Git lets us replay history with a rebase.",
        ],
        stale=[
            "[2024] Just rerun the agent; if results differ, average a few runs and move on.",
        ],
        contradictory=[
            "Seeding the run by the strategy is fine; pairing across arms doesn't really matter for the verdict.",
        ],
        low_confidence=[
            "I think the trial seed includes the model name, but the exact tuple may have changed.",
        ],
    ),
    Scenario(
        slug="agent-provider-boundary",
        domain="agent-systems",
        query="how should the eval platform stay decoupled from execution and retrieval providers",
        keywords=["provider interface", "boundary", "MCP", "mock", "drop-in", "ownership"],
        targets=[
            "Execution and retrieval must sit behind provider interfaces with mock and real MCP "
            "implementations that are drop-in equivalents; the eval platform measures outcomes and must not "
            "absorb workspace management or context generation that belong to other systems.",
        ],
        relevants=[
            "Mock providers let the full pipeline run end-to-end without a live backend.",
            "Real MCP providers are selected from the environment and fall back to mocks independently.",
            "Retrieval/memory logic stays behind the Cortex provider, not inside the eval engine.",
        ],
        distractors=[
            "The CLI uses a plugin system for output formatters.",
            "We abstract the database behind a repository for testing.",
            "The payment provider is wrapped in an adapter for sandbox mode.",
            "Logging goes through a façade so we can swap backends.",
        ],
        stale=[
            "[2024] Just call the execution backend directly from the scorer; an interface is premature.",
        ],
        contradictory=[
            "The eval platform should run the agent and generate context itself to avoid coordinating with other teams.",
        ],
        low_confidence=[
            "Maybe the real provider already implements every mock method, but parity isn't fully tested.",
        ],
    ),
    # ── Code Review ───────────────────────────────────────────────────────── #
    Scenario(
        slug="review-diff-size",
        domain="code-review",
        query="what guidelines keep pull request diffs small and focused",
        keywords=["diff", "focused", "scope creep", "whitespace", "review", "atomic"],
        targets=[
            "A PR must touch only files required by its task; unrelated edits, drive-by refactors, and "
            "whitespace churn are rejected in review because they hide the real change and bloat the diff.",
        ],
        relevants=[
            "Reviewers flag trailing-newline and reformat-only changes as noise that obscures intent.",
            "Large changes are split into a stack of small, independently reviewable PRs.",
            "Mechanical reformatting goes in its own commit, separate from behavior changes.",
            "A PR that touches files outside the task's scope is sent back to trim the unrelated edits.",
            "Reviewers approve faster when the diff is small, so focus is also a velocity win.",
        ],
        distractors=[
            "The PR template lists a checklist of sections to fill in before requesting review.",
            "We squash-merge so the main branch has one commit per PR.",
            "The diff viewer can hide whitespace changes with a toggle.",
            "A bot comments the diff's line count on every PR.",
        ],
        stale=[
            "[2021] Big PRs are fine if they're well described; reviewers should just read more carefully.",
        ],
        contradictory=[
            "Bundle unrelated cleanups into the same PR; it saves opening multiple reviews.",
        ],
        low_confidence=[
            "Maybe our guideline caps PRs at 400 lines, but the number might have changed.",
        ],
    ),
    Scenario(
        slug="review-test-requirements",
        domain="code-review",
        query="what testing is required before a change can be merged",
        keywords=["tests", "coverage", "regression", "CI", "edge case", "merge gate"],
        targets=[
            "A change merges only with tests covering the new behavior and a regression test for any bug it "
            "fixes; CI must be green, and a bug fix without a failing-then-passing test is sent back.",
        ],
        relevants=[
            "Bug fixes add a test that fails before the fix and passes after, proving the fix works.",
            "New behavior is covered at the level it lives — unit for logic, integration for wiring.",
            "CI runs the full suite as a required merge gate, not an optional check.",
        ],
        distractors=[
            "We measure test wall-time and shard slow suites across runners.",
            "The coverage badge is shown in the README.",
            "Manual QA signs off on the release candidate before a launch.",
            "Snapshot tests guard the component library's rendered output.",
        ],
        stale=[
            "[2021] Tests can be added in a follow-up PR after the feature ships if we're in a hurry.",
        ],
        contradictory=[
            "Coverage percentage is all that matters; a high number means the change is safe to merge untested.",
        ],
        low_confidence=[
            "I think the merge gate requires 80% coverage, but the threshold may not be enforced.",
        ],
    ),
    Scenario(
        slug="review-quality-approvals",
        domain="code-review",
        query="what makes a good code review and how many approvals are needed",
        keywords=["review quality", "approval", "ownership", "feedback", "blocking", "context"],
        targets=[
            "A good review checks correctness, edge cases, and design against the task's intent — not just "
            "style — and risky or cross-cutting changes need an owning-area reviewer's approval, not just any "
            "rubber-stamp.",
        ],
        relevants=[
            "Reviewers distinguish blocking concerns from optional nits so authors know what must change.",
            "Changes to a critical area require sign-off from that area's owner.",
            "Review feedback references the task's acceptance criteria, not personal preference.",
        ],
        distractors=[
            "The standup covers who is reviewing what each morning.",
            "We use emoji reactions to acknowledge messages in the channel.",
            "The linter auto-approves formatting-only changes.",
            "A dashboard tracks average time-to-first-review.",
        ],
        stale=[
            "[2020] One approval from anyone on the team is always enough to merge anything.",
        ],
        contradictory=[
            "Reviews should only check formatting and style; design and correctness are the author's job alone.",
        ],
        low_confidence=[
            "Maybe two approvals are required for infra changes, but the policy might be looser now.",
        ],
    ),
    Scenario(
        slug="review-naming-consistency",
        domain="code-review",
        query="how do we keep naming and code style consistent across the codebase",
        keywords=["naming", "style", "convention", "linter", "consistency", "idiom"],
        targets=[
            "New code should read like the code around it: match the existing module's naming, idioms, and "
            "structure, with automated formatting and linting enforcing the mechanical rules so reviews "
            "focus on substance.",
        ],
        relevants=[
            "Formatters and linters run in CI so style isn't argued in review.",
            "Names follow the surrounding file's conventions rather than a contributor's personal habit.",
            "Public APIs follow documented naming conventions for discoverability.",
        ],
        distractors=[
            "The design tokens define consistent colors and spacing in the UI.",
            "Commit messages follow a conventional-commits prefix.",
            "Branch names include the ticket number by convention.",
            "The docs use a consistent voice per the style guide.",
        ],
        stale=[
            "[2021] Everyone formats code their own way; we'll standardize someday.",
        ],
        contradictory=[
            "Consistency doesn't matter; write each file in whatever personal style you prefer.",
        ],
        low_confidence=[
            "I think we settled on snake_case for module-level constants, but it's not in the style doc.",
        ],
    ),
    Scenario(
        slug="review-pr-description",
        domain="code-review",
        query="what should a pull request description contain to be reviewable",
        keywords=["PR description", "context", "acceptance criteria", "what and why", "testing notes", "scope"],
        targets=[
            "A PR description states what changed and why, links the task and its acceptance criteria, and "
            "notes how it was tested; reviewers can't evaluate intent without the why, so a description that "
            "only restates the diff is sent back.",
        ],
        relevants=[
            "Linking the originating issue lets the reviewer check the change against its acceptance criteria.",
            "Testing notes tell the reviewer what was verified and what wasn't.",
            "Out-of-scope follow-ups are called out so they aren't expected in this PR.",
        ],
        distractors=[
            "The PR title is used as the squash-merge commit subject.",
            "Screenshots are attached for UI changes.",
            "A bot links related PRs in a comment.",
            "Labels categorize PRs by area for filtering.",
        ],
        stale=[
            "[2021] The diff speaks for itself; a description is optional busywork.",
        ],
        contradictory=[
            "Just paste the list of changed files as the description; explaining why is unnecessary detail.",
        ],
        low_confidence=[
            "Maybe the template already requires a testing section, but I'm not sure it's enforced.",
        ],
    ),
]
