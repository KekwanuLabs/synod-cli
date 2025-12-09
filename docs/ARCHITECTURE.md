# Synod Architecture Documentation

**Last Updated**: 2025-12-06
**Version**: 0.3.0
**Status**: Active Development - Memory System Design Complete ✨

> ⚠️ **IMPORTANT**: This document must be kept up-to-date with every architectural change. Future Claude instances should update this file whenever making significant changes to the codebase.

---

## Table of Contents
1. [Project Vision](#project-vision)
2. [System Architecture](#system-architecture)
3. [Intelligent Debate System](#intelligent-debate-system)
4. [Memory System](#memory-system)
5. [Color & Design System](#color--design-system)
6. [Module Structure](#module-structure)
7. [Data Flow](#data-flow)
8. [Session Management](#session-management)
9. [File System Integration](#file-system-integration)
10. [Implementation Status](#implementation-status)

---

## Project Vision

**Synod** is a CLI-based coding agent inspired by historical ecumenical councils—assemblies where diverse perspectives debated to synthesize truth. It orchestrates adversarial debates among multiple state-of-the-art LLMs (we call them "Bishops" in the historical parallel) with a lead model (the "Pope") synthesizing the best ideas from each into a final solution.

**Core Differentiator**: Not just multi-model voting, but **true synthesis**—combining the best parts from each model's proposal through an intelligent, adaptive debate process.

**The Power**:
- Automates what developers used to do manually (comparing outputs from Claude, GPT, etc.)
- **Intelligent pre-analysis** classifies queries and routes to appropriate experts
- **Dynamic expertise weighting** - models with domain expertise get higher influence
- **Adaptive debate rounds** - simple queries skip unnecessary debate stages
- The lead model sees ALL proposals + ALL critiques simultaneously
- Takes Model A's algorithm, Model B's error handling, Model C's optimization
- Weaves them into one battle-tested solution with clear attribution

**Goals**:
- Fast parallel execution across multiple SOTA models
- Minimize hallucinations through adversarial validation
- Intelligent routing based on query complexity and domain
- Zero-cost classification using free models
- Adaptive learning from user feedback
- Delightful, beautiful user experience that breaks CLI conventions
- Real-time token/cost tracking across all models
- Smart context management and file system integration

**The Metaphor**: We use historical council terminology (bishops, pope) as organizational labels, not religious references. It's about governance structure and collective intelligence.

---

## System Architecture

### High-Level Flow

```
User Input → Session Manager → Intelligent Debate Orchestrator
                                           ↓
                        ┌──────────────────┴────────────────────┐
                        ↓                                        ↓
                   Stage 0: Classification               Context Manager
                   (Free Qwen Coder)                    (File Indexing)
                   - Scope enforcement
                   - Complexity detection
                   - Domain extraction
                   - Strategy suggestion
                        ↓
                   Expertise Weighting
                   (Bishop selection by domain)
                        ↓
                   Stage 1: Proposal
                   (Top N Bishops by weight)
                        ↓
                   Consensus Detection
                   (Skip if high agreement)
                        ↓
                   Stage 2: Critiques
                   (Targeted adversarial review)
                        ↓
                   Stage 3: Synthesis
                   (Pope hybrid solution)
                        ↓
                   Display Results → Exit Summary
```

### Four-Stage Intelligent Debate Process

**Stage 0: Pre-Debate Analysis** ✨ ENHANCED
- **Free classifier** (Grok 4.1 Fast - reliable, fast, excellent availability)
- **Graceful fallback**: If unavailable, uses moderate complexity defaults
- **Scope enforcement**: Rejects non-coding queries
- **Strict complexity detection**: VERY conservative classification
  - **Trivial**: ONLY for zero-logic queries (math, print statements, variable declaration)
  - **Never trivial**: Functions, algorithms, loops, conditionals
  - **Default to higher** complexity when uncertain
- **Domain extraction**: 19 specialized domains (architecture, algorithms, web_dev, ML/AI, blockchain, etc.)
- **Technology detection**: Identifies languages, frameworks, tools
- **Debate strategy**: Recommends bishops count, rounds, token budget
- **Cost**: $0 (uses free models)

**Stage 1: Proposal** (Enhanced)
- **Pope as Unbiased Observer**: Pope does NOT participate in Stage 1—observes silently without bias
- **Smart bishop selection**: Top N bishops by domain expertise weight (excludes Pope)
- **Dynamic participant count**: 1-5 bishops based on complexity
- All selected Bishops generate independent solutions
- Executed in parallel using `asyncio`
- Real-time streaming with animated spinners (⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏)
- Checkmarks (✓) appear when each bishop completes

**Stage 2: Critique** ✨ RIGOROUS & PARALLEL
- **Pope as Unbiased Observer**: Pope does NOT participate in Stage 2—remains impartial
- **Smart LLM consensus detection**: Uses free classifier to semantically compare proposals (not just keywords)
- **Early termination**: Skips if >95% exceptional consensus (Pope still verifies) or >85% high consensus
- **Dynamic allocation**: 1-5 critics based on complexity (trivial:1, simple:2, moderate:3, complex:4, expert:5)
- **Smart pairing**: Critics matched to targets by complementary expertise (algorithm experts critique UI code)
- **Evidence-based critiques**: MUST quote code, provide evidence, be specific, suggest fixes
- **Rigorous requirements**:
  - Quote specific parts being critiqued
  - Explain WHY it's bad (not just "this is bad")
  - Reference lines/functions/approaches
  - Use domain expertise (security, performance, architecture)
  - Be constructive (suggest improvements)
- **Parallel execution**: All N critique tasks run concurrently using `asyncio`
- **Severity detection**: 🔴 Critical, 🟡 Moderate, 🟢 Minor
- **Real-time progress**: Animated spinners with checkmarks on completion

**Stage 3: Synthesis** ✨ PAPAL AUTHORITY WITH VETO POWER
- **Pope's unique role**: UNBIASED observer with FINAL AUTHORITY
- **Verification-first approach**: Pope must verify correctness before synthesizing
- **VETO POWER**: Can override even 100% consensus if bishops missed errors
- Pope receives:
  - All proposals with **bishop expertise weights**
  - All critiques with severity levels (or note if high consensus)
  - Domain and complexity context
  - **Explicit veto authority** against group-think
- **Consensus alerts**: When >95% consensus, Pope is warned to check for group-think errors
- **Hybrid synthesis**: Mixes best parts from each proposal (doesn't just pick one)
- **Clear attribution**: Documents which ideas came from which bishop
- **Output format**:
  - ## Verification: Issues Pope caught that bishops missed?
  - ## Synthesis Process: What taken from whom, improvements made
  - ## Final Solution: Authoritative hybrid code
  - ## Attribution: Credits with veto corrections if needed
- Takes Model A's approach + Model B's edge case handling + Model C's optimization
- Produces comprehensive explanation with attribution
- Adaptive token budget based on complexity

**Key Innovation**: The entire debate adapts to query complexity:
- **Trivial** (math): Direct answer, no debate
- **Simple**: 2-3 bishops, 2 rounds, consensus-based
- **Moderate**: 3 bishops, 3 rounds, targeted critiques
- **Complex**: 4-5 bishops, 4 rounds, full adversarial review
- **Expert**: 5 bishops, 5 rounds, optional challenge round

### Quality Control & Rigor System ✨ NEW

Synod implements a **multi-layered quality control system** to ensure rigorous, evidence-based debate and catch errors that might slip through consensus:

#### 1. **Strict Trivial Classification** (`classifier.py:121-148`)

**Problem**: Can't waste 6 bishops on "What is 5+3?"

**Solution**: VERY conservative classification - default to higher complexity when uncertain.

**Criteria**:
```
TRIVIAL (1 bishop, no debate):
✅ "What is 5+3?" - pure math
✅ "Print hello world" - single statement
✅ "How to create variable" - zero logic

NEVER TRIVIAL:
❌ "Write factorial function" → MODERATE (recursion knowledge required)
❌ "Add two numbers function" → SIMPLE (needs 2 bishops)
❌ "Check if even" → SIMPLE (needs review)
```

**Guideline in prompt**: "BE VERY STRICT WITH CLASSIFICATION - default to higher complexity if uncertain!"

#### 2. **Smart LLM-Based Consensus** (`debate.py:148-242`)

**Problem**: Keyword overlap too simplistic - "using cache" vs "implementing caching" = 0% match but semantically identical.

**Solution**: Use free classifier LLM to semantically compare proposals.

**Implementation**:
```python
async def _measure_consensus_llm(proposals) -> float:
    # For each pair of proposals:
    # Ask classifier: "Are these essentially the same approach? Rate 0-100"
    # Run all comparisons in PARALLEL
    # Return average similarity score
```

**Benefits**:
- Semantic understanding (not just keywords)
- Parallel execution (fast)
- Uses free models ($0 cost)
- Fallback to keyword method if LLM unavailable

#### 3. **Papal Veto Power** (`debate.py:803-867`)

**Problem**: Consensus ≠ Correctness. All bishops could agree on the WRONG answer.

**Solution**: Pope has FINAL AUTHORITY and explicit VETO POWER.

**How it works**:
1. **Always reviews**: Even with 100% consensus, Pope synthesizes
2. **Verification first**: Pope must check for fundamental errors before synthesis
3. **Consensus alert**: Pope explicitly warned when >95% consensus detected
4. **Veto authority**: Can override group-think with better solution

**Example scenario**:
```
Stage 1: All bishops propose bubble sort (O(n²))
Consensus: 95%

Stage 2: SKIPPED (high consensus)

Stage 3: Pope reviews
"⚠️ HIGH CONSENSUS - But bubble sort is O(n²).
VETO: Use quicksort O(n log n) instead.
Bishops missed the performance issue."
```

**Output format includes Verification section**:
```markdown
## Verification
[Did Pope find issues bishops missed? Veto needed?]

## Synthesis Process
[What taken from whom, improvements made]

## Final Solution
[Authoritative code]

## Attribution
[Credits + veto corrections if applied]
```

#### 4. **Rigorous Evidence-Based Critiques** (`debate.py:727-776`)

**Problem**: Critics could say "this is bad" without actually analyzing.

**Solution**: Enforce SUBSTANTIVE peer review with specific requirements.

**5 Requirements for valid critique**:
1. ✅ **ACTUALLY READ** - Quote specific parts being critiqued
2. ✅ **PROVIDE EVIDENCE** - Explain WHY it's bad (not just "this is bad")
3. ✅ **BE SPECIFIC** - Reference lines, functions, or specific approaches
4. ✅ **USE EXPERTISE** - Apply domain knowledge (security, performance, architecture)
5. ✅ **BE CONSTRUCTIVE** - Suggest fixes, not just complaints

**Examples in prompt**:
```
❌ BAD: "This is inefficient"
✅ GOOD: "The nested loops (O(n²)) will cause performance issues
         for large datasets. Use hash map for O(n) lookup."

❌ BAD: "Has security vulnerability"
✅ GOOD: "SQL query uses string concatenation on line 5,
         vulnerable to injection. Use parameterized queries:
         cursor.execute('SELECT * FROM users WHERE id = ?', (id,))"
```

**Enforcement**: Prompts explicitly show good vs bad critique examples.

#### 5. **Dynamic Critique Allocation** (`debate.py:490-502`)

**Problem**: Simple queries don't need 5 critics reviewing everything.

**Solution**: Scale critic count with complexity.

**Allocation**:
```python
complexity_critic_count = {
    "trivial": 1,   # Minimal review
    "simple": 2,    # Quick review
    "moderate": 3,  # Standard
    "complex": 4,   # Deep review
    "expert": 5     # All hands on deck
}
```

**Benefits**:
- Saves tokens on simple queries
- Full coverage on complex queries
- Adapts to problem difficulty

#### 6. **Smart Critic-Target Pairing** (`debate.py:573-612`)

**Problem**: Random pairing wastes expertise (architecture expert reviewing algorithm minutiae).

**Solution**: Match critics to targets by complementary expertise.

**Strategy**:
- Each proposal gets top 2-3 critics by expertise weight
- For ≤3 proposals: Exhaustive review (all critics review all)
- For >3 proposals: Strategic pairing (top experts review each)

**Implementation**:
```python
# For each proposal:
# - Get critics sorted by expertise weight
# - Select top 2-3 critics
# - Assign: (critic, target, "expert (weight: 1.2)")
```

**Result**: Cross-domain critique for better issue detection.

---

## Memory System

### Overview

The Synod Memory System enables persistent, intelligent context that improves over time. It remembers user preferences, coding patterns, project context, and prior debate insights across sessions.

**Design Decisions:**

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Vector Database | Qdrant Cloud | Managed, scalable, free tier |
| Embedding Model | OpenAI text-embedding-3-small | Fast (~50ms), cheap ($0.02/1M tokens) |
| Memory Extraction | Grok 4.1 Fast (free) | Zero cost extraction |
| CLI Cache | Local SQLite | Offline support, fast retrieval |

### Memory Architecture

```
Query → Memory Retrieval → Qdrant Cloud
              ↓                    │
         Embedding         ┌──────┴──────┐
         OpenAI            │  user_memories │
     text-embed-3-small    │  project_memories │
              ↓            └──────────────────┘
         SQLite Cache              │
         ~/.synod/cache/           │
              ↓                    ↓
         DEBATE PIPELINE (with memory context)
              ↓
         Memory Extraction (Grok 4.1 Fast - FREE)
              ↓
         Store to Qdrant + Update Cache
```

### Memory Types

**User Memories** (cross-project):
- `preference`: User's stated or demonstrated preferences
- `pattern`: Observed coding patterns or habits
- `fact`: Knowledge about user's skills, tools, environment
- `correction`: Explicit corrections of previous assumptions

**Project Memories** (project-specific):
- `architecture`: High-level structural decisions
- `pattern`: Code patterns used in this project
- `convention`: Naming, formatting, organizational conventions
- `bug`: Known bugs, edge cases, gotchas
- `decision`: Why certain choices were made
- `file_context`: Important file/folder context

### Memory Flow

1. **Retrieval** (on new query):
   - Embed query using text-embedding-3-small (~50ms)
   - Parallel search: SQLite cache + Qdrant user + Qdrant project
   - Rank by: similarity × confidence × decay × importance
   - Select top 3 user + 5 project memories (~500 tokens)

2. **Injection** (into prompts):
   - Stage 0 (Classification): User preferences, project domains
   - Stage 1 (Proposals): All relevant memories
   - Stage 3 (Synthesis): All relevant memories

3. **Extraction** (post-debate):
   - Grok 4.1 Fast analyzes query + synthesis
   - Extracts 0-5 memory candidates as JSON
   - Embed each memory
   - Deduplicate against existing (cosine > 0.85)
   - Store to SQLite cache → async sync to Qdrant

### SQLite Cache

Located at `~/.synod/cache/memory_cache.db`:
- Mirrors Qdrant for offline access
- Fast local retrieval (<10ms)
- Sync queue for offline writes
- Background sync when online

### Memory Lifecycle

**Decay Formula:**
```python
if days_since_access <= 30:
    decay = 1.0
else:
    weeks_over = (days_since_access - 30) / 7
    decay = max(0.3, 1.0 - 0.05 * weeks_over)
```

**Cleanup** (weekly):
- Delete memories with decay < 0.3
- Delete superseded memories > 90 days old
- Compact inactive project memories

### Cost Analysis

| Operation | Cost | Frequency |
|-----------|------|-----------|
| Memory Extraction | $0 (Grok free) | Per debate |
| Query Embedding | ~$0.00002 | Per query |
| Memory Embeddings | ~$0.00006 | Per debate (avg 3) |
| Qdrant Storage | $0 (free tier) | Ongoing |

**Total: <$0.01/month per active user**

> **Full Design**: See [MEMORY_SYSTEM.md](/MEMORY_SYSTEM.md) for complete architecture, schemas, and implementation details.

---

## Intelligent Debate System

### Domain Classification (19 Domains)

```python
DOMAINS = [
    "architecture",        # System design, patterns, structure
    "algorithms",          # Data structures, complexity
    "web_dev",            # Frontend, React, Vue, CSS
    "backend",            # APIs, servers, microservices
    "database",           # SQL, NoSQL, optimization
    "security",           # Auth, encryption, vulnerabilities
    "performance",        # Optimization, profiling
    "testing",            # Unit tests, TDD, integration
    "devops",             # CI/CD, Docker, Kubernetes
    "ml_ai",              # Machine learning, neural networks
    "data_science",       # Analysis, pandas, visualization
    "systems_programming", # OS, low-level, C/C++, kernel
    "mobile",             # iOS, Android, React Native
    "cloud",              # AWS, GCP, Azure
    "networking",         # Protocols, TCP/IP, distributed
    "game_dev",           # Game engines, Unity, graphics
    "blockchain",         # Smart contracts, Web3, crypto
    "automation",         # Scripting, build tools
    "language_specific"   # Language features, idioms
]
```

### Expertise Weighting System

**Provider Benchmarks**:
- Based on published model benchmarks (Anthropic, OpenAI, DeepSeek, Google, xAI)
- 19 domains × 7 models = 133 initial weights
- Example weights (0.5-1.0 scale):
  ```python
  "deepseek/deepseek-v3": {
      "algorithms": 0.98,    # Excellent
      "ml_ai": 0.95,         # Excellent
      "data_science": 0.94,  # Strong
      "web_dev": 0.72        # Moderate
  }
  ```

**Dynamic Calculation**:
- Query classified into primary + secondary domains
- Each bishop's weight calculated as average across relevant domains
- Normalized to 0.5-1.2 range:
  - 0.5 = Minimum (still participates, lower influence)
  - 1.0 = Average expertise
  - 1.2 = Domain expert (high influence)
- Top N bishops selected for debate

**Adaptive Learning**:
- User feedback (thumbs up/down) adjusts weights over time
- Stored in `~/.synod/expertise.json`
- Blends initial benchmarks with learned performance
- Confidence increases with participation count

### Free Classifier

**Single Reliable Model**: Grok 4.1 Fast (free)
- Fast, reliable, excellent availability
- Proven stability with minimal rate limiting
- Code-aware classification

**Graceful Fallback**: If Grok 4.1 Fast unavailable, uses `_get_fallback_analysis()` with moderate complexity defaults

**Why only one model?**
- Previous fallback models (Gemma 3, Qwen Coder) had 400/429 errors
- Simpler configuration = fewer failure points
- Grok 4.1 Fast has proven extremely reliable

### Consensus Detection

**Implementation**:
- After Round 2, measure similarity between proposals
- If consensus > 85%, skip to synthesis
- Saves tokens and time on non-controversial solutions
- Still collects bishop weights and reasoning

### Token Budget Management

**Complexity-Based Budgets**:
```python
{
    "trivial": 1_000,      # "What is 2+2?"
    "simple": 3_000,       # "Write add function"
    "moderate": 10_000,    # "Refactor this code"
    "complex": 30_000,     # "Design REST API"
    "expert": 60_000       # "Distributed cache system"
}
```

**Tracking**:
- Monitor tokens used in each stage
- Warn if approaching budget
- Adjust strategy mid-debate if needed

---

## Display System

### Animated Progress Indicators

Synod uses **Rich Progress** for real-time animated spinners during debate stages:

**Stage 0: Classification**
- Persistent panel showing analysis results (remains visible throughout)
- Shows: coding-related status, complexity, domains, technologies, debate strategy

**Stage 1: Proposals**
- Animated dots spinner (⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏) for each bishop streaming in parallel
- Cyan color for bishops
- Checkmarks (✓) appear when each bishop completes
- No pre-drawn empty boxes—bishops appear as they start

**Stage 2: Critiques**
- Animated spinners for each critic-target pair
- Magenta/pink color for critiques
- Shows "Critic → Target" as each completes

**Stage 3: Synthesis**
- Purple/pink spinner for Pope synthesis
- Single synthesis phase (Pope observes, doesn't debate)

**Interactive Mode**
- Automatically enters after any query (like Claude Code)
- Uses Python's built-in `input()` for terminal compatibility
- Continues until user types `exit`

**Implementation**: Uses `Rich.Progress` with `SpinnerColumn`, `TextColumn`, `BarColumn`. No pre-drawn UI—elements appear dynamically as work starts.

---

## Color & Design System

### Brand Colors

**Primary: Bright Orange** `#FF6B35`
- Represents energy, debate, intellectual fire
- Used for: Logo, primary actions, highlights

**Secondary: Deep Purple** `#7C3AED`
- Represents authority, wisdom, papal decisions
- Used for: Pope synthesis, important information

**Accent: Pink** `#EC4899`
- Represents conflict, passion, critical reviews
- Used for: Dissents, warnings, critiques

**Supporting Colors**:
- **Cyan** `#06B6D4` - Bishop proposals, information
- **Gold** `#FBBF24` - Success, completed actions
- **Green** `#10B981` - Confirmations, positive results
- **Red** `#EF4444` - Errors, high disagreement

### Rich Theme Configuration

```python
# synod/core/theme.py
SYNOD_THEME = Theme({
    "primary": "#FF6B35",      # Bright Orange
    "secondary": "#7C3AED",    # Deep Purple
    "accent": "#EC4899",       # Pink
    "info": "#06B6D4",         # Cyan
    "success": "#10B981",      # Green
    "warning": "#FBBF24",      # Gold
    "error": "#EF4444",        # Red
    "bishop": "#06B6D4",       # Cyan for bishops
    "pope": "#7C3AED",         # Purple for pope
    "dissent": "#EC4899",      # Pink for critiques
})
```

### Typography & Borders

- **Box style**: `ROUNDED` for friendly, modern feel
- **Progress bars**: Custom gradient orange→purple
- **ASCII Art**: Block style for logo
- **Input prompts**: Beautiful bordered boxes

---

## Module Structure

### Current Structure

```
synod/
├── __init__.py
├── __main__.py                 # Entry point
├── cli.py                      # CLI commands, interactive mode, query handling
├── core/
│   ├── __init__.py
│   │
│   │── # === CONFIGURATION ===
│   ├── config.py              # API key, paths, config directories
│   ├── settings.py            # Bishop/Pope configuration management
│   ├── template.py            # Template-based configuration (.synod.template.yaml)
│   ├── model_registry.py      # Model→Provider availability mapping
│   │
│   │── # === INTELLIGENT DEBATE SYSTEM ===
│   ├── council.py             # Compatibility wrapper for CLI
│   ├── debate.py              # Main intelligent debate orchestrator
│   ├── classifier.py          # Stage 0: Free pre-debate analysis
│   ├── expertise.py           # Dynamic bishop expertise weighting
│   │
│   │── # === MEMORY SYSTEM === ✨ NEW
│   ├── memory/
│   │   ├── __init__.py        # Memory module exports
│   │   ├── types.py           # Memory dataclasses and enums
│   │   ├── extractor.py       # Grok 4.1 Fast memory extraction
│   │   ├── embedder.py        # OpenAI text-embedding-3-small client
│   │   ├── qdrant_client.py   # Qdrant Cloud operations
│   │   ├── cache.py           # SQLite local cache operations
│   │   ├── retriever.py       # Search, rank, and select memories
│   │   ├── injector.py        # Format memories for prompt injection
│   │   └── sync.py            # Background sync operations
│   │
│   │── # === API CLIENTS ===
│   ├── openrouter.py          # OpenRouter API client (streaming SSE)
│   ├── providers.py           # Multi-provider LLM client (Azure, Anthropic, etc.)
│   │
│   │── # === INTERACTIVE MODE ===
│   ├── chat_interface.py      # Chat-style input with prompt-toolkit
│   ├── slash_commands.py      # Slash command registry (/help, /config, etc.)
│   ├── archives.py            # Conversation context management (CouncilArchives)
│   │
│   │── # === DISPLAY & UX ===
│   ├── display.py             # Launch screen, exit summary, visualizations
│   ├── live_display.py        # Real-time streaming debate panels
│   ├── theme.py               # Color system & Rich themes
│   ├── syntax.py              # Code block syntax highlighting
│   │
│   │── # === FILE SYSTEM ===
│   ├── indexer.py             # File indexing with ripgrep
│   ├── context.py             # File content reading for debates
│   ├── context_suggestions.py # Smart file suggestion engine
│   ├── workspace.py           # Workspace trust management
│   │
│   │── # === SESSION & STORAGE ===
│   ├── session.py             # Token/cost tracking per session
│   ├── storage.py             # Persistent data storage utilities
│   │
│   │── # === ONBOARDING ===
│   └── onboarding.py          # First-run setup wizard
```

### New Module Details

**synod/core/classifier.py** ✅ NEW
- `CLASSIFIER_MODELS`: Single reliable model (Grok 4.1 Fast)
- `DOMAINS`: 19 specialized domain categories
- `COMPLEXITY_LEVELS`: 5 levels with descriptions
- `QueryAnalysis`: Dataclass with analysis results
- `analyze_query()`: Main classification function
- `show_rejection()`: Beautiful rejection display for non-coding queries
- `_get_fallback_analysis()`: Graceful degradation to moderate defaults if classifier unavailable

**synod/core/expertise.py** ✅ NEW
- `PROVIDER_BENCHMARKS`: Initial weights for 7 models × 19 domains
- `BishopExpertise`: Dataclass tracking initial + learned weights
- `load_expertise()` / `save_expertise()`: Persistent storage
- `initialize_bishop_expertise()`: Setup with provider benchmarks
- `calculate_bishop_weights()`: Dynamic weight calculation per query
- `record_user_feedback()`: Update weights from thumbs up/down
- Storage: `~/.synod/expertise.json`

**synod/core/debate.py** ✅ NEW
- `Proposal`, `Critique`, `Synthesis`: Dataclasses for debate data
- `DebateResult`: Complete result with analysis, weights, tokens
- `DebateStrategy`: Configuration for adaptive behavior
- `SynodDebate`: Main orchestrator class
  - `run_debate()`: Complete 4-stage process
  - `_stage1_proposals()`: Parallel proposal collection
  - `_stage2_critiques()`: Targeted adversarial review
  - `_stage3_synthesis()`: Pope hybrid synthesis
  - `should_continue()`: Consensus detection logic
  - `_measure_consensus()`: Similarity calculation
  - `_select_top_bishops()`: Weight-based selection

**synod/core/council.py** ✅ UPDATED
- Now a **compatibility wrapper** for existing CLI
- `run_full_council()`: Calls SynodDebate internally
- Converts new DebateResult format to old format (stage1_results, dissents, final_solution)
- Maintains backward compatibility with CLI display
- Legacy functions marked as deprecated

**synod/core/providers.py** ✅ NEW
- Multi-provider LLM client supporting Azure, Anthropic, OpenAI, AWS Bedrock, Google Vertex AI, OpenRouter
- `Provider` enum for all supported providers
- `PROVIDER_ENDPOINTS`: Provider-specific API endpoints
- `MODEL_MAPPINGS`: Maps canonical model names to provider-specific IDs
- `query_provider()`: Unified interface for querying any provider
- `async_retry()`: Decorator for automatic retry on transient network failures
  - Retries on: RemoteProtocolError, ReadTimeout, ConnectTimeout, ConnectError
  - 2 retries with exponential backoff (1s, 2s delays)
  - Does NOT block parallel requests - each retries independently
- Enables users to use existing cloud credits instead of being locked into OpenRouter
- Session-aware token tracking

**synod/core/model_registry.py** ✅ NEW
- Model availability registry mapping models to providers
- `ModelProvider` enum for all available providers
- `MODEL_AVAILABILITY`: Dict mapping model patterns to available providers
- `get_available_providers()`: Returns providers that support a given model
- Enables smart routing and credential collection during onboarding
- Used by template system and onboarding wizards

**synod/core/template.py** ✅ NEW
- Template-based configuration system (.synod.template.yaml)
- `find_template()`: Locates template file in current/home directory
- `load_template()`: Loads and parses YAML template
- `validate_template()`: Comprehensive validation with clear error messages
- `apply_template()`: Generates config.json and .env from template
- Supports simple mode (one provider) and mixed mode (per-model routing)
- Priority: project template → home template → interactive prompts

**synod/core/onboarding.py** ✅ ENHANCED
- Simplified onboarding with smart per-model provider routing
- Uses `model_registry.py` for dynamic model availability
- `check_config_exists()`: Checks if user has configured Synod
- `run_interactive_setup()`: Main entry point for guided setup
- `is_onboarded()`: Returns True if user has completed setup
- `run_onboarding_flow()`: Complete 7-step wizard flow
- Multi-provider credential collection
- Automatic provider routing optimization
- Simple mode (OpenRouter only) or Custom mode (multi-provider)
- Beautiful Rich + inquirer UI
- Saves configuration to ~/.synod/config.json
- Generates .env with provider credentials and routing

**synod/core/context_suggestions.py** ✅ NEW
- Smart file suggestion engine for debates
- `FileSuggestion`: Dataclass with path, score, reasons, preview
- `ContextSuggester`: Main suggestion engine class
- `analyze_query()`: Extracts keywords, file mentions, languages from query
- `suggest_files()`: Returns ranked list of relevant files
- Uses ripgrep for fast full-text search
- Scores files based on: direct mentions, keyword matches, file type relevance
- Future: ML-based relevance scoring

**synod/core/storage.py**
- Persistent data storage utilities
- File-based storage with JSON serialization
- Creates ~/.synod directory for user data
- Thread-safe file operations
- Used by expertise system and session tracking

**synod/core/chat_interface.py**
- Modern chat-style input using prompt-toolkit
- `SynodChatInterface`: Main interface class with prompt session
- `SlashCommandCompleter`: Auto-completion for slash commands
- Features: multi-line input, command history, auto-suggest
- Key bindings: Enter to submit, Ctrl+J for newline, Ctrl+D to exit
- Multi-column completion menu for slash commands

**synod/core/slash_commands.py**
- Slash command registry system (like Claude Code)
- `SlashCommand`: Dataclass with name, description, handler, aliases
- `SlashCommandRegistry`: Singleton registry for all commands
- Built-in commands: /exit, /clear, /config, /bishops, /pope, /cost, /context, /help, /compact, /version, /history, /stats, /index, /files, /add
- Extensible for future custom commands

**synod/core/archives.py**
- Conversation context management (`CouncilArchives`)
- Stores query + synthesis pairs across session
- Auto-compacts at 80% context usage
- `add_exchange()`: Add new debate exchange
- `get_context_for_debate()`: Format context for Pope
- `compact()`: Manually trigger compaction
- Keeps last 2 exchanges in full, summarizes older ones

**synod/core/live_display.py**
- Real-time streaming display for debate panels
- `LiveDebateDisplay`: Responsive grid layout class
- Shows each bishop's output as it streams
- Adaptive columns (1-4) based on terminal width
- Status indicators: waiting, streaming, complete

**synod/core/syntax.py**
- Code block syntax highlighting for responses
- Parses markdown code blocks with language identifiers
- Uses Rich's syntax highlighting (monokai theme)

**synod/core/workspace.py**
- Workspace trust management
- `check_workspace_trust()`: Verify user trusts project directory
- First-run permission prompts for file access

### Module Dependencies

```
cli.py
  ├─> onboarding.py (setup wizard)
  │    ├─> template.py (template config)
  │    ├─> model_registry.py (model availability)
  │    └─> settings.py (config management)
  │
  ├─> chat_interface.py (interactive input)
  │    ├─> slash_commands.py (command registry)
  │    └─> theme.py (styling)
  │
  ├─> archives.py (conversation context - Pope only)
  │
  ├─> council.py (compatibility layer)
  │    └─> debate.py (intelligent orchestrator)
  │         ├─> classifier.py (Stage 0 analysis)
  │         ├─> expertise.py (bishop weighting)
  │         ├─> openrouter.py (OpenRouter API)
  │         ├─> providers.py (multi-provider API)
  │         └─> session.py (token tracking)
  │
  ├─> workspace.py (trust management)
  │    └─> indexer.py (file indexing)
  │
  ├─> context.py (file reading)
  ├─> context_suggestions.py (smart suggestions)
  │    └─> indexer.py (file indexing)
  │
  ├─> display.py (launch screen, summaries)
  │    └─> theme.py (colors)
  │
  ├─> live_display.py (streaming panels)
  │    └─> theme.py (colors)
  │
  └─> settings.py (config)
       ├─> template.py (template loading)
       ├─> config.py (paths, API keys)
       └─> storage.py (persistence)
```

---

## Data Flow

### Session Lifecycle

1. **Launch**
   - Display ASCII art logo
   - Show version info
   - Detect project directory
   - Request permission for file access
   - Index files with ripgrep
   - Display project stats
   - Initialize session tracker

2. **Query Processing** (Enhanced)
   - Parse user input
   - **Stage 0: Classification** (free classifier)
     - Determine if coding-related
     - Extract complexity and domains
     - Suggest debate strategy
     - Reject if non-coding
   - **Bishop selection** (by expertise weight)
   - Load relevant file context
   - Display session info panel
   - **Stage 1-3: Adaptive debate**
   - Show real-time progress
   - Display results with attribution

3. **Exit**
   - Show beautiful summary
   - Token usage by bishop
   - Cost breakdown
   - Session statistics
   - Bishop analytics
   - Expertise learning summary

### Configuration Data

Stored in `~/.synod/config.json`:
```json
{
  "bishop_models": [
    "anthropic/claude-opus-4.5",
    "openai/gpt-5.1-chat",
    "deepseek/deepseek-chat-v3.1",
    "google/gemini-3-pro-preview",
    "x-ai/grok-4.1-fast:free"
  ],
  "pope_model": "anthropic/claude-opus-4.5",
  "api_key": "sk-or-v1-...",
  "version": "0.2.0"
}
```

### Expertise Data ✨ NEW

Stored in `~/.synod/expertise.json`:
```json
{
  "anthropic/claude-opus-4.5": {
    "model_id": "anthropic/claude-opus-4.5",
    "initial_weights": {
      "architecture": 0.95,
      "algorithms": 0.85,
      "ml_ai": 0.82,
      ...
    },
    "learned_weights": {
      "web_dev": {
        "participations": 15,
        "upvotes": 12,
        "downvotes": 3,
        "success_rate": 0.80
      }
    },
    "total_participations": 47,
    "total_upvotes": 38,
    "total_downvotes": 9,
    "last_updated": "2025-11-24T15:30:00"
  }
}
```

### Session Data

Tracked in memory during session:
```python
{
  "start_time": "2025-11-24T10:30:00",
  "debates": 3,
  "files_modified": 5,
  "bishop_usage": {
    "claude-opus-4.5": {
      "tokens": 15234,
      "cost": 0.46,
      "percentage": 33.7,
      "weight_avg": 1.15  # NEW: Average expertise weight
    },
    "gpt-5.1-chat": {...},
    "deepseek-chat-v3.1": {...}
  },
  "total_tokens": 45234,
  "total_cost": 1.50,
  "context_used": 0.32,
  "classifier_cost": 0.00  # NEW: Free classification
}
```

---

## Session Management

### Context Architecture: Why Only the Pope Maintains State

A critical architectural decision in Synod is that **only the Pope maintains conversation context**. Here's why:

**Bishops are Stateless:**
- Bishops provide independent opinions on each individual query
- They do NOT maintain conversation history between queries
- Each debate round starts fresh for bishops—they only see the current query + relevant file context
- This ensures bishops aren't biased by previous discussions

**The Pope Maintains Session Context:**
- The Pope receives the accumulated conversation history via `CouncilArchives`
- The Pope synthesizes all bishop opinions + prior context into the final response
- When context runs out, it's the Pope who loses history—bishops don't care since they're stateless

**Why This Design?**
1. **Cost Efficiency**: Maintaining context for 5+ bishops would multiply token costs
2. **Fresh Perspectives**: Bishops give unbiased opinions without being anchored to prior answers
3. **Single Source of Truth**: Only one model (Pope) needs to maintain coherent session state
4. **Scalability**: Adding more bishops doesn't increase context complexity

**The `/context` Command:**
- Shows the Pope model's context limit (e.g., 200k tokens for Claude Opus 4.5)
- Shows how much of that context has been used by session history
- This is the only context that matters for session continuity

**CouncilArchives (`synod/core/archives.py`):**
- Stores conversation exchanges (query + synthesis pairs)
- Auto-compacts at 80% usage by summarizing old exchanges
- Keeps last 2 exchanges in full, summarizes older ones
- Provides context string for Pope's synthesis stage

### Token Tracking

OpenRouter returns usage data in API responses:
```json
{
  "usage": {
    "prompt_tokens": 1234,
    "completion_tokens": 567,
    "total_tokens": 1801
  }
}
```

We track per-bishop and aggregate:
- Input tokens (prompts sent)
- Output tokens (responses received)
- Cost calculation (per model pricing)
- Context window usage (percentage)
- **NEW**: Expertise weight utilization
- **NEW**: Classifier usage (always $0)

### Cost Calculation

OpenRouter provides pricing in response headers:
- `x-ratelimit-tokens-remaining`
- Pricing varies by model
- Calculate: `tokens × price_per_1k / 1000`
- **Stage 0 classifier**: Always $0 (free models)

### Context Window Management

Each model has different context limits:
- Claude Opus 4.5: 200k tokens
- GPT-5.1: 200k tokens
- DeepSeek V3: 64k tokens
- Gemini 3 Pro: 1M tokens

Track usage to prevent overflow and warn user.

---

## File System Integration

### Indexing Strategy

**Tool**: ripgrep (`rg`)
- Fastest search tool available
- Respects `.gitignore` by default
- Cross-platform
- Falls back to pathlib if ripgrep not available

**Implementation** (`synod/core/indexer.py`):
```python
class FileIndexer:
    def __init__(self, project_path: str)
    def index_with_ripgrep(self, show_progress=True) -> List[str]
    def index_with_pathlib(self, show_progress=True) -> List[str]
    def get_stats_summary() -> Table
```

**Index on Launch**:
```bash
rg --files --hidden --glob '!.git/' --glob '!node_modules/' ...
```

**Skipped Directories**:
- `.git/`, `.synod/`, `node_modules/`, `__pycache__/`
- `.venv/`, `venv/`, `dist/`, `build/`

**Project Statistics**:
- Total file count
- Languages detected (by extension)
- Total size (in MB/KB)
- Files by type breakdown

### Permission System

**Implementation**: Permission stored in `.synod/permission.json`

On first launch in a directory:
```
📁 Detected project folder
   /Users/you/projects/my-app

⚠️  Synod needs to index your codebase
   This enables smart context suggestions

   Analyzing...
   ├─ Python files: 47 found
   └─ Total: 153 files
```

**Permission Flow**:
1. Check if `.synod/permission.json` exists
2. If not, do quick scan (no progress bar)
3. Show beautiful permission prompt with stats
4. Grant permission (currently auto-granted for testing)
5. Create `.synod/permission.json`
6. Re-index with full progress visualization

**Future**: Add interactive Y/n prompt using questionary

---

## Implementation Status

### ✅ Phase 1: Launch & Brand System - COMPLETE!
- [x] Basic 3-stage debate system
- [x] Bishop/Pope configuration
- [x] OpenRouter API integration
- [x] File context reading
- [x] Color system & Rich theme
- [x] Beautiful launch screen
- [x] Session tracking system
- [x] Exit summary screen
- [x] Real-time token/cost tracking
- [x] Interactive model selection
- [x] Pope selected from Bishops

### ✅ Phase 2: File System & Context - COMPLETE!
- [x] File indexing with ripgrep
- [x] Permission system for folders
- [x] Beautiful permission prompt with stats
- [x] Animated progress bars
- [x] CLI integration with launch flow
- [ ] Smart context suggestions (Next)
- [ ] .synodignore support
- [ ] Auto-detect relevant files
- [ ] Live file tree visualization

### ✅ Phase 3: Intelligent Debate System - COMPLETE! ✨
- [x] **Stage 0: Pre-debate classification** ✨
- [x] **Free classifier (Grok 4.1 Fast)** ✨
- [x] **Graceful fallback to moderate defaults** ✨
- [x] **19 domain classification** ✨
- [x] **Expertise weighting system** ✨
- [x] **Provider benchmark integration** ✨
- [x] **Dynamic bishop selection** ✨
- [x] **Pope as unbiased observer (excludes from Stage 1 & 2)** ✨
- [x] **Adaptive debate rounds (1-5)** ✨
- [x] **Smart LLM-based consensus detection (85% threshold)** ✨
- [x] **Smart critic-target pairing (complementary expertise)** ✨
- [x] **Token budget management** ✨
- [x] **Hybrid synthesis with attribution** ✨
- [x] **Papal veto power** ✨
- [x] **Evidence-based critiques enforcement** ✨
- [x] **Scope enforcement (reject non-coding)** ✨
- [x] **Adaptive learning infrastructure** ✨
- [x] **Real-time animated spinners (Rich Progress)** ✨
- [x] **Parallel execution with asyncio.gather()** ✨
- [x] **Always-on interactive mode (like Claude Code)** ✨
- [ ] User feedback UI (thumbs up/down)
- [ ] Challenge round (30% on complex queries)
- [ ] Self-assessment first-run

### ✅ Phase 4: Interactive Mode - COMPLETE! ✨
- [x] **Always-on interactive mode** ✨
- [x] **Automatic entry after queries** ✨
- [x] **Terminal-compatible input handling** ✨
- [x] **Slash command system** ✨ - /help, /config, /context, /files, /compact, etc.
- [x] **Command history** ✨ - Up/Down arrow navigation
- [x] **Auto-completion** ✨ - Type / to see command menu
- [x] **Chat-style input** ✨ - prompt-toolkit with multi-line support
- [x] **Syntax highlighting** ✨ - Code blocks in responses use monokai theme
- [x] **Context management** ✨ - CouncilArchives with auto-compacting
- [ ] Real-time session panel (future)
- [ ] Inline feedback (thumbs up/down) (future)

### 📋 Phase 5: Advanced Features (Future)
- [ ] Live debate visualization
- [ ] Debate history & analytics
- [ ] Bishop performance dashboard
- [ ] File watching mode
- [ ] Debate replays
- [ ] Interactive debate steering
- [ ] Bishop vs Bishop analytics
- [ ] Domain-specific model recommendations

---

## Development Guidelines

### When Adding New Features

1. **Update this document first** - Plan the architecture
2. **Update CLAUDE.md** - Add any new conventions
3. **Implement with tests** - Write test cases
4. **Update session tracking** - If feature uses tokens/context
5. **Update expertise system** - If affects bishop selection
6. **Add slash command** - If user-facing feature
7. **Document in README** - Update user-facing docs

### Code Conventions

- **Async by default** - Use `asyncio` for all LLM calls
- **Type hints** - All functions should have type annotations
- **Error handling** - Graceful degradation, never crash
- **Beautiful output** - Every user-facing message uses Rich
- **Session tracking** - Log all token/cost usage
- **Dataclasses** - Use for structured data (Proposal, Critique, etc.)
- **Free first** - Prioritize free models for classification/routing

### Color Usage Rules

- **Orange** - Primary actions, energy, highlights
- **Purple** - Pope, authority, final decisions
- **Pink** - Critiques, conflicts, warnings
- **Cyan** - Bishops, proposals, information, Stage 0 analysis
- **Gold** - Success, achievements, warnings
- **Red** - Errors only

### Expertise System Guidelines

- **Initialize on first run** - Use provider benchmarks
- **Update gradually** - Blend initial + learned (max 50% learned weight)
- **Track everything** - Participations, upvotes, downvotes, success rate
- **Normalize weights** - Always 0.5-1.2 range
- **Save frequently** - After each feedback

---

## Notes for Future Development

### Performance Optimization
- Cache bishop responses for similar queries
- Implement smart model selection (cheaper models for simple queries) ✅ DONE
- Parallel file reading for large codebases
- Stage 0 result caching for repeated queries
- Consensus-based early termination ✅ DONE

### Enhanced Features
- Debate replay/review system
- Bishop voting visualization
- Interactive debate steering (pause and interject)
- Integration with git for auto-commit with debate context
- VS Code extension for inline debates
- Live bishop performance dashboard
- Domain expertise heatmap visualization

### Analytics & Learning
- Track which bishop's suggestions get adopted most ✅ INFRASTRUCTURE READY
- Learn optimal bishop combinations for different query types
- Cost optimization suggestions
- Expertise evolution over time graphs
- Domain-specific bishop recommendations

### Intelligent Routing
- Query similarity detection (avoid redundant debates)
- Automatic domain classification refinement
- Bishop specialty auto-discovery
- Complexity prediction improvements
- Token budget optimization by query type

---

**End of Architecture Documentation**

*This document is the source of truth for Synod's architecture. Keep it updated!*
