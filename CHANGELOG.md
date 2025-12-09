# Changelog

All notable changes to Synod will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2025-12-09

### Added
- **Automatic code context**: Synod now intelligently includes relevant files before debates start
  - Zero-latency query analysis (regex-based, no LLM calls)
  - Detects file mentions and symbol names in your queries
  - Memory-guided context boosting from past insights
- **`/search` command**: Search your codebase with parallel strategies (ripgrep, glob, symbol search)
- **Memory-code linking**: Memories now track which files they relate to for smarter retrieval

### Changed
- Debates are now more accurate due to automatic inclusion of relevant code context
- Memory system stores file path associations for project-scoped memories

## [0.3.0] - 2025-11-27

### Added
- **Active Pope**: Pope now ADDs its own improvements, OVERRIDEs proposals if it knows better, CORRECTs misunderstandings, and CHALLENGEs flawed assumptions
- **Consensus-aware critique prompts**: Different critique strategies based on consensus level:
  - High consensus (90%+): Hunt for shared blind spots
  - Moderate consensus (50-90%): Pick a winner, identify fatal flaws
  - Low consensus (<50%): Arbitrate disagreement, determine correct approach
- **Smart skipping**: Automatically skip redundant critiques when proposals are 85%+ similar
- **Pope observer indicator**: Shows "👑 Pope Claude Opus 4.5 is observing" during Stages 1 & 2
- **Skip display**: Shows `⏭ skipped (proposals identical)` when critiques are skipped
- **Smoother animations**: Improved cursor animation for Pope observer (`●◐◑○` cycle)

### Changed
- **Stage 2 renamed**: "Adversarial Reviews" → "Adversarial Debate" (better reflects the challenge-based approach)
- **Terminology update**: "reviewed" → "challenged", "reviewing" → "challenging"
- **Critique prompts**: More adversarial - force decisive answers, pick winners, no hedging
- **Faster logo animation**: 2-3x faster typewriter effect
- **Cleaner Stage 3 panel**: Single panel with status + timing + content (removed duplicate)

### Fixed
- Stage 0 UI no longer shows duplicate panels (removed direct console.print calls)
- Stage 3 status no longer appears outside its panel
- Removed redundant "You asked" panel after prompt input

## [0.2.1] - 2025-11-27

### Fixed
- Minor bug fixes and stability improvements

## [0.2.0] - 2025-11-26

### Added
- **Stage 0: Pre-debate Intelligence** - FREE classification using Grok 4.1 Fast
- **Expertise weighting** - Bishops weighted 0.5-1.2x based on domain expertise
- **Consensus detection** - LLM-based semantic similarity measurement
- **Slash commands** - `/help`, `/context`, `/files`, `/config`, `/compact`, `/cost`, `/stats`
- **Interactive mode** - Continues like Claude Code until you type `exit`
- **Context management** - Auto-compacting archives for Pope's context
- **19 specialized domains** - ML/AI, blockchain, security, algorithms, etc.

### Changed
- Dynamic bishop selection based on query complexity (2-5 bishops)
- Adaptive rounds based on consensus level
- Token budget management (1K-60K based on complexity)

## [0.1.0] - 2025-11-24

### Added
- Initial release with 3-stage debate system
- Bishop proposals (Stage 1)
- Adversarial critiques (Stage 2)
- Pope synthesis (Stage 3)
- OpenRouter integration for multiple SOTA models
- Rich CLI interface with color-coded output
- File context support with `-f` flag
