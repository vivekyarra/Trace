# LORE — Agent Documentation

## What is LORE?

LORE (Living Organisational Record Engine) is a single GitLab Duo flow that follows features from issue to production — predicting failures, catching conflicts, verifying promises, tracking carbon, detecting patterns, and onboarding new members. Powered by Anthropic Claude.

## The Complete Lifecycle

```
Issue Created → SPECFORGE PRE-MORTEM → Developer Responds → FOLLOW-UP
    → MR Opened → GUARDKEEPER (3 layers) → Conflict? → REPLY_HANDLER
    → MR Merged → LOREKEEPER (decisions + carbon + patterns)
    → Health Check → LORECAST (health + sustainability + graph)
    → New Member → ONBOARDING BRIEFING
    → Any Time → LORE Ask (@mention)
```

## Eight Modes

| Mode | Trigger | What it does |
|---|---|---|
| SPECFORGE PRE-MORTEM | Assigned to issue | Searches past failures, predicts what will go wrong, asks hard questions, generates spec |
| FOLLOW-UP | Re-triggered on issue with existing pre-mortem | Evaluates developer answers: demands specifics if vague, assigns risk level if specific |
| GUARDKEEPER | Assigned as reviewer on open MR | Layer 1: Memory conflicts + cascading impact. Layer 2: Promise verification from linked issue. Layer 3: Security sentinel |
| REPLY_HANDLER | `lore: intentional/accidental/discuss` on MR | Updates, preserves, or escalates memories. Transfers dependency links on override |
| LOREKEEPER | Triggered on merged MR | Extracts decisions with carbon + incident type + dependencies + security flag. Detects recurring review patterns |
| LORECAST | "health"/"audit" keyword | Health report + sustainability report + ASCII knowledge graph + security inventory + coverage gaps |
| ONBOARDING | "onboard"/"briefing" keyword | Complete team knowledge briefing organized by priority |
| LORE Ask | @mention standalone agent | Natural language search with dependency tracing and carbon aggregation |

## Memory Format

Stored as **wiki pages** (primary) with fallback to **issue comments** on LORE Memory Bank.

### LORE-INDEX (wiki page)

```markdown
# LORE Index

| File Path | Memory IDs |
|---|---|
| src/api/auth.py | LORE-MEMORY-001, LORE-MEMORY-003 |
| README.md | LORE-MEMORY-002 |
```

### Individual Memory (wiki page)

```markdown
LORE Memory #001
Source MR: !42 — Add retry logic to auth service
Date: 2026-01-15
Governs files: src/api/auth.py, src/api/retry.py
Decision: Use fixed retry intervals instead of exponential backoff
Rejected: Exponential backoff with jitter
Reason: Exponential backoff caused thundering herd at 1000+ concurrent requests during Jan 15 incident
Future implication: Any retry logic must use fixed intervals. No exponential backoff.
Decided by: @alice, @bob
Confidence: HIGH
Status: Active
Carbon impact: ~300 kWh/month saved (reduced retry storms)
Incident type: retry
Depends on: N/A
Blocks: Memory #003
Security relevant: no
```

### All Fields

| Field | Required | Description |
|---|---|---|
| `id` | Yes | Zero-padded (001, 002) |
| `Source MR` | Yes | `!{iid} — {title}` |
| `Date` | Yes | YYYY-MM-DD |
| `Governs files` | Yes | Comma-separated paths |
| `Decision` | Yes | Verb-first sentence |
| `Rejected` | Yes | What was rejected, or N/A |
| `Reason` | Yes | Specific, with data |
| `Future implication` | Yes | Constraint for future devs |
| `Decided by` | Yes | @usernames |
| `Confidence` | Yes | HIGH / MEDIUM / LOW |
| `Status` | Yes | Active / Superseded / Overridden |
| `Carbon impact` | Yes | kWh/month saved or cost, or N/A |
| `Incident type` | Yes | cache/retry/auth/infra/data/perf/security/none |
| `Depends on` | Yes | Memory #{ids} or N/A |
| `Blocks` | Yes | Memory #{ids} or N/A |
| `Source type` | Yes | discussion / code / both |
| `Security relevant` | Yes | yes / no |

## GUARDKEEPER — Three Layers

**Layer 1: Memory Conflict Check**
Semantic analysis using Anthropic Claude. Detects equivalent patterns ("exponential backoff" = "progressive delay with multiplier"). Checks cascading impact via depends_on/blocks — overriding one decision may affect others.

**Layer 1b: Code Intelligence Check**
Analyzes the actual diff for architectural patterns: new dependencies, API endpoints, schema changes, auth patterns, caching strategies, retry logic. Cross-references against existing code-sourced memories. Flags technology drift when a new library is introduced for the same purpose as an existing one.

**Layer 2: Promise Consistency Check**
Reads linked issue thread (Closes #N / Fixes #N). Extracts specific technical claims. Compares against actual diff. Flags unfulfilled promises.

**Layer 3: Security Sentinel**
Scans for security-sensitive patterns: auth, crypto, tokens, SQL, XSS, CORS, secrets, API keys, sessions, certificates. Cross-references against security-relevant memories. Flags regressions and common anti-patterns (hardcoded secrets, SQL concatenation, missing input validation, disabled security headers).

## SPECFORGE PRE-MORTEM

**Fresh issue:** Searches ALL memories + past issues + MRs + notes for failure patterns. Generates pre-mortem with past failures, predictions, hard questions, security precedents, and engineering spec with carbon estimate.

**Follow-up:** Evaluates developer answers. Vague → demands specifics. Specific → assigns risk level (LOW/MEDIUM/HIGH) and lists promises to verify in eventual MR.

## Carbon Impact Tracking

LOREKEEPER estimates carbon/compute impact per decision:
- Batch vs individual: ~200-500 kWh/month saved
- Connection pooling: ~100-300 kWh/month saved
- Caching: ~50-200 kWh/month saved
- Fixed retry vs thundering herd: ~100-400 kWh/month saved

LORECAST aggregates into sustainability report: total kWh/month, CO2 equivalent, trees equivalent.

## Decision Dependencies

Memories have `depends_on` and `blocks` fields. When GUARDKEEPER finds a conflict with a memory that blocks others, it warns about cascading impact. LORECAST generates an ASCII knowledge graph showing all relationships. REPLY_HANDLER transfers dependency links when overriding a decision.

## Code Intelligence

LOREKEEPER doesn't just read discussions — it reads the actual code. Most architectural decisions are never discussed; someone just writes the code. LORE detects:
- **Structural changes:** New dependencies, API endpoints, schema changes, services, config changes
- **Pattern introductions:** Auth handling, caching strategies, retry logic, data access patterns
- **Removals and replacements:** Swapped dependencies, deprecated endpoints, replaced patterns
- **Technology drift:** When the team was using library X but a new MR introduces library Y for the same purpose

Code-sourced memories have `Source type: code` and `Confidence: MEDIUM` (lower than discussion-based, since no explicit reasoning was stated). When discussion corroborates a code finding, it upgrades to `Source type: both` and `Confidence: HIGH`.

## Code Pattern Rules

When a reviewer says "don't use `Optional`, use `X | None`" or "use `pathlib` not `os.path`", LOREKEEPER captures this as a **Code Pattern Rule** — a structured memory with:
- The **rule** (what to do)
- The **anti-pattern** (what not to do)
- **Language** and **examples** (bad/good)
- **Who established it** and **why**

GUARDKEEPER then enforces these rules on every future MR. If someone uses `Optional` again, LORE flags it and references the original review where this was corrected.

### Code Pattern Rule Format

```
LORE Pattern #{id}
Source MR: !42 — Modernize type hints
Date: 2026-01-20
Rule: Use X | None instead of Optional
Anti-pattern: typing.Optional[X]
Language: python
Reason: Optional is soft-deprecated in Python 3.10+, X | None is the standard
Established by: @alice
Status: Active
Examples:
  Bad:  def get_user(id: int) -> Optional[User]:
  Good: def get_user(id: int) -> User | None:
```

## Feature Changelog

LOREKEEPER generates a **LORE Changelog** after each merge — a human-readable entry describing what was actually built, not just what was decided. Posted to a "LORE Changelog" issue (label: `lore-changelog`). Onboarding briefings include the last 10 entries so new members see what was built and when.

## Pattern Recognition

LOREKEEPER scans recent MR comments for recurring feedback. If same feedback appears 3+ times, creates issue with label `lore-pattern` suggesting a coding standard. Also detects technology drift across MRs and creates issues with label `tech-drift`.

## Onboarding Briefing

ONBOARDING mode creates an issue with the complete team knowledge briefing:
1. Security decisions (first, non-negotiable)
2. Architecture decisions by file
3. Performance decisions with carbon data
4. Style conventions
5. ASCII decision map
6. Top 3 past incidents
7. Key people table

## Reply Protocol

| Command | Effect |
|---|---|
| `lore: intentional — [reasoning]` | New memory created, old Superseded, dependencies transferred |
| `lore: accidental` | Original stays Active, developer revises code |
| `lore: discuss` | Original decision makers pinged |

## Labels Used

| Label | Created by | Meaning |
|---|---|---|
| `lore-spec-pending` | SPECFORGE | Spec generated, awaiting approval |
| `lore-risk-low/medium/high` | FOLLOW-UP | Risk level after evaluating answers |
| `lore-memory-bank` | LOREKEEPER | Issue storing memory comments |
| `lore-pattern` | LOREKEEPER | Recurring review pattern detected |
| `lore-health` | LORECAST | Health/sustainability report |
| `lore-onboarding` | ONBOARDING | New member briefing |

## Voice

LORE speaks as institutional memory with opinions — a senior engineer who has seen things break. Direct, specific, slightly haunted. Never corporate, never apologetic. Every message signed "— LORE" and attributed to Anthropic Claude.

## Architecture

LORE uses a multi-component router architecture. A **triage router** inspects context (issue, MR, keywords) and dispatches to one of six specialized agents:

| Component | Role | Anthropic Claude Capability |
|---|---|---|
| `triage_router` | Context classification → dispatch | Instruction-following precision |
| `specforge_agent` | Issue pre-mortem + spec generation | Long-context cross-MR pattern synthesis |
| `guardkeeper_agent` | Three-layer MR analysis | Semantic equivalence reasoning |
| `reply_handler_agent` | Memory evolution via `lore:` commands | Nuanced reasoning for memory updates |
| `lorekeeper_agent` | Decision extraction from merged MRs | Decision vs. noise discrimination |
| `lorecast_agent` | Health audit + sustainability report | Opinionated assessment generation |
| `onboarding_agent` | New member briefing | Multi-topic synthesis into actionable briefings |

## Files

| File | Purpose |
|---|---|
| `.gitlab/duo/flows/lore.yaml` | Multi-component flow (full prompts, 7 agents) |
| `flows/flow.yml` | AI Catalog flow definition (condensed prompts) |
| `agents/lore-ask.yml` | LORE Ask standalone agent — conversational memory search |
| `agents/lore-migrate.yml` | LORE Migrate standalone agent — retroactive decision import |
| `.gitlab-ci.yml` | CI pipeline: YAML validation, catalog sync, scheduled health checks |

## Triggering

| Event | Mode | Component |
|---|---|---|
| Assigned to issue | SPECFORGE PRE-MORTEM | `specforge_agent` |
| Re-assigned to issue (existing pre-mortem) | FOLLOW-UP | `specforge_agent` |
| Assigned as reviewer on open MR | GUARDKEEPER | `guardkeeper_agent` |
| `lore:` comment on MR | REPLY_HANDLER | `reply_handler_agent` |
| Pipeline event on merged MR | LOREKEEPER | `lorekeeper_agent` |
| "health"/"audit" keyword | LORECAST | `lorecast_agent` |
| "onboard"/"briefing" keyword | ONBOARDING | `onboarding_agent` |
| @mention LORE Ask agent | LORE Ask | standalone agent |
| @mention LORE Migrate agent | LORE Migrate | standalone agent |
