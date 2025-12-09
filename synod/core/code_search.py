"""Synod Intelligent Code Search Engine

Combines multiple search strategies in parallel for fast, accurate
code retrieval. Optimized for sub-second response times.

Key Features:
- Parallel execution of ripgrep, glob, and semantic search
- Query understanding and decomposition
- Relevance scoring and ranking
- Memory-guided search (uses adversarial memories to inform search)
- Sub-100ms latency on typical queries

Architecture:
    Query → [Query Analyzer] → Search Strategies (parallel)
                                    ├── RipGrep (exact/regex)
                                    ├── Glob (file patterns)
                                    ├── Symbol Search (definitions)
                                    └── Semantic (keyword overlap)
                                            ↓
                                    [Ranker] → Top K Results
"""

import asyncio
import subprocess
import os
import re
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import fnmatch

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.syntax import Syntax
from rich.progress import Progress, SpinnerColumn, TextColumn

from .theme import PRIMARY, CYAN, GREEN, GOLD, GRAY

console = Console()


# ============================================================================
# DATA STRUCTURES
# ============================================================================

class SearchStrategy(Enum):
    RIPGREP = "ripgrep"      # Exact/regex text search
    GLOB = "glob"            # File pattern matching
    SYMBOL = "symbol"        # Function/class definitions
    SEMANTIC = "semantic"    # Embedding-based similarity
    MEMORY = "memory"        # Memory-guided search


@dataclass
class SearchResult:
    """A single search result with scoring."""
    file_path: str
    line_number: Optional[int] = None
    line_end: Optional[int] = None
    content: str = ""
    match_type: str = ""           # What matched (pattern, symbol, etc.)
    strategy: SearchStrategy = SearchStrategy.RIPGREP
    score: float = 0.0             # Relevance score 0-1
    context_before: List[str] = field(default_factory=list)
    context_after: List[str] = field(default_factory=list)

    @property
    def location(self) -> str:
        if self.line_number:
            if self.line_end and self.line_end != self.line_number:
                return f"{self.file_path}:{self.line_number}-{self.line_end}"
            return f"{self.file_path}:{self.line_number}"
        return self.file_path


@dataclass
class SearchQuery:
    """Parsed and analyzed search query."""
    raw_query: str
    keywords: List[str] = field(default_factory=list)
    file_patterns: List[str] = field(default_factory=list)
    symbol_patterns: List[str] = field(default_factory=list)
    regex_patterns: List[str] = field(default_factory=list)
    is_definition_search: bool = False
    is_usage_search: bool = False
    language_hints: List[str] = field(default_factory=list)


@dataclass
class SearchConfig:
    """Configuration for search behavior."""
    max_results: int = 20
    max_file_size: int = 100_000       # Skip files larger than 100KB
    context_lines: int = 3              # Lines before/after match
    parallel_limit: int = 8             # Max parallel searches
    timeout_seconds: float = 10.0       # Per-strategy timeout
    include_hidden: bool = False
    respect_gitignore: bool = True


# ============================================================================
# QUERY ANALYZER
# ============================================================================

# Common programming language file extensions
LANGUAGE_EXTENSIONS = {
    'python': ['.py', '.pyw', '.pyi'],
    'javascript': ['.js', '.jsx', '.mjs', '.cjs'],
    'typescript': ['.ts', '.tsx', '.mts', '.cts'],
    'rust': ['.rs'],
    'go': ['.go'],
    'java': ['.java'],
    'cpp': ['.cpp', '.cc', '.cxx', '.hpp', '.h'],
    'c': ['.c', '.h'],
    'ruby': ['.rb', '.rake'],
    'php': ['.php'],
    'swift': ['.swift'],
    'kotlin': ['.kt', '.kts'],
    'scala': ['.scala'],
    'shell': ['.sh', '.bash', '.zsh'],
}

# Patterns that indicate definition searches
DEFINITION_PATTERNS = [
    r'\bdef\s+(\w+)',           # Python function
    r'\bclass\s+(\w+)',         # Class definition
    r'\bfunction\s+(\w+)',      # JS/TS function
    r'\bconst\s+(\w+)\s*=',     # JS/TS const
    r'\binterface\s+(\w+)',     # TS interface
    r'\btype\s+(\w+)\s*=',      # TS type alias
    r'\bstruct\s+(\w+)',        # Rust/Go struct
    r'\bimpl\s+(\w+)',          # Rust impl
    r'\bfn\s+(\w+)',            # Rust function
    r'\bfunc\s+(\w+)',          # Go function
]


def analyze_query(raw_query: str) -> SearchQuery:
    """Analyze and decompose a search query into structured components."""
    query = SearchQuery(raw_query=raw_query)

    # Extract file patterns (e.g., "*.py", "src/**/*.ts")
    file_pattern_regex = r'(\*\*?[/\\]?[\w.*/-]+|\w+\.\w+)'
    for match in re.finditer(file_pattern_regex, raw_query):
        pattern = match.group(1)
        if '*' in pattern or '.' in pattern:
            # Check if it looks like a file pattern
            if any(pattern.endswith(ext) for exts in LANGUAGE_EXTENSIONS.values() for ext in exts):
                query.file_patterns.append(pattern)
            elif '*' in pattern:
                query.file_patterns.append(pattern)

    # Detect language hints
    for lang, extensions in LANGUAGE_EXTENSIONS.items():
        if lang in raw_query.lower():
            query.language_hints.append(lang)
        for ext in extensions:
            if ext in raw_query:
                query.language_hints.append(lang)
                break

    # Detect definition search intent
    definition_keywords = ['define', 'definition', 'where is', 'find class', 'find function', 'implementation']
    if any(kw in raw_query.lower() for kw in definition_keywords):
        query.is_definition_search = True

    # Detect usage search intent
    usage_keywords = ['usage', 'used', 'called', 'imported', 'references']
    if any(kw in raw_query.lower() for kw in usage_keywords):
        query.is_usage_search = True

    # Extract potential symbol names (CamelCase or snake_case identifiers)
    symbol_regex = r'\b([A-Z][a-zA-Z0-9]*|[a-z][a-z0-9_]*[A-Z][a-zA-Z0-9]*|[a-z_][a-z0-9_]+)\b'
    for match in re.finditer(symbol_regex, raw_query):
        symbol = match.group(1)
        # Filter out common words
        if len(symbol) > 2 and symbol.lower() not in {'the', 'and', 'for', 'with', 'from', 'that', 'this'}:
            query.symbol_patterns.append(symbol)

    # Extract keywords (words not already captured)
    words = re.findall(r'\b\w+\b', raw_query.lower())
    stopwords = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or', 'is', 'are', 'was', 'were', 'find', 'search', 'look', 'where', 'how', 'what', 'show', 'me'}
    query.keywords = [w for w in words if w not in stopwords and len(w) > 2]

    return query


# ============================================================================
# SEARCH STRATEGIES
# ============================================================================

async def ripgrep_search(
    patterns: List[str],
    root_path: str,
    config: SearchConfig,
    file_types: Optional[List[str]] = None,
) -> List[SearchResult]:
    """Execute ripgrep search with multiple patterns in parallel."""
    results = []

    async def search_pattern(pattern: str) -> List[SearchResult]:
        cmd = ['rg', '--json', '-i', '--max-count=50']

        if config.context_lines > 0:
            cmd.extend(['-C', str(config.context_lines)])

        if config.respect_gitignore:
            cmd.append('--hidden')
            cmd.append('--glob=!.git')

        if file_types:
            for ft in file_types:
                cmd.extend(['--type', ft])

        cmd.extend([pattern, root_path])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(),
                timeout=config.timeout_seconds
            )

            pattern_results = []
            for line in stdout.decode('utf-8', errors='ignore').splitlines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if data.get('type') == 'match':
                        match_data = data.get('data', {})
                        pattern_results.append(SearchResult(
                            file_path=match_data.get('path', {}).get('text', ''),
                            line_number=match_data.get('line_number'),
                            content=match_data.get('lines', {}).get('text', '').strip(),
                            match_type=f"pattern: {pattern}",
                            strategy=SearchStrategy.RIPGREP,
                            score=0.8,  # Base score for exact matches
                        ))
                except json.JSONDecodeError:
                    continue

            return pattern_results
        except asyncio.TimeoutError:
            return []
        except FileNotFoundError:
            # ripgrep not installed, fall back to grep
            return await grep_fallback(pattern, root_path, config)
        except Exception:
            return []

    # Run all patterns in parallel
    tasks = [search_pattern(p) for p in patterns[:config.parallel_limit]]
    all_results = await asyncio.gather(*tasks)

    for pattern_results in all_results:
        results.extend(pattern_results)

    return results


async def grep_fallback(pattern: str, root_path: str, config: SearchConfig) -> List[SearchResult]:
    """Fallback to grep if ripgrep isn't available."""
    results = []
    cmd = ['grep', '-r', '-n', '-i', '--include=*.*', pattern, root_path]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=config.timeout_seconds)

        for line in stdout.decode('utf-8', errors='ignore').splitlines()[:50]:
            parts = line.split(':', 2)
            if len(parts) >= 3:
                results.append(SearchResult(
                    file_path=parts[0],
                    line_number=int(parts[1]) if parts[1].isdigit() else None,
                    content=parts[2].strip(),
                    match_type=f"pattern: {pattern}",
                    strategy=SearchStrategy.RIPGREP,
                    score=0.7,
                ))
    except Exception:
        pass

    return results


async def glob_search(
    patterns: List[str],
    root_path: str,
    config: SearchConfig,
) -> List[SearchResult]:
    """Find files matching glob patterns."""
    results = []
    root = Path(root_path)

    for pattern in patterns[:config.parallel_limit]:
        try:
            # Handle ** patterns
            if '**' in pattern:
                matches = list(root.glob(pattern))
            else:
                matches = list(root.glob(f'**/{pattern}'))

            for match in matches[:20]:  # Limit per pattern
                if match.is_file():
                    # Skip large files
                    try:
                        if match.stat().st_size > config.max_file_size:
                            continue
                    except OSError:
                        continue

                    results.append(SearchResult(
                        file_path=str(match),
                        content=f"File: {match.name}",
                        match_type=f"glob: {pattern}",
                        strategy=SearchStrategy.GLOB,
                        score=0.6,
                    ))
        except Exception:
            continue

    return results


async def symbol_search(
    symbols: List[str],
    root_path: str,
    config: SearchConfig,
    language_hints: Optional[List[str]] = None,
) -> List[SearchResult]:
    """Search for symbol definitions (functions, classes, etc.)."""
    results = []

    # Build definition patterns based on language hints
    patterns = []
    for symbol in symbols:
        # Generic patterns that work across languages
        patterns.extend([
            f'def\\s+{symbol}\\s*\\(',           # Python function
            f'class\\s+{symbol}[\\s:(]',          # Class
            f'function\\s+{symbol}\\s*\\(',       # JS function
            f'const\\s+{symbol}\\s*=',            # JS const
            f'let\\s+{symbol}\\s*=',              # JS let
            f'interface\\s+{symbol}[\\s{{<]',     # TS interface
            f'type\\s+{symbol}\\s*=',             # TS type
            f'fn\\s+{symbol}\\s*[<(]',            # Rust fn
            f'struct\\s+{symbol}[\\s{{<]',        # Rust/Go struct
            f'func\\s+{symbol}\\s*\\(',           # Go func
            f'export\\s+(default\\s+)?{symbol}',  # JS export
        ])

    # Use ripgrep with these patterns
    rg_results = await ripgrep_search(patterns, root_path, config)

    # Boost scores for definition matches
    for result in rg_results:
        result.strategy = SearchStrategy.SYMBOL
        result.score = 0.9  # High score for definitions

    results.extend(rg_results)
    return results


async def semantic_search_local(
    query: str,
    root_path: str,
    config: SearchConfig,
    index_cache: Optional[Dict] = None,
) -> List[SearchResult]:
    """Simple semantic search using keyword overlap and TF-IDF-like scoring.

    For full semantic search with embeddings, this would call the cloud API.
    This local version provides fast approximate semantic matching.
    """
    results = []
    query_words = set(query.lower().split())

    # Walk directory and score files
    root = Path(root_path)
    scored_files: List[Tuple[float, Path]] = []

    for ext_list in LANGUAGE_EXTENSIONS.values():
        for ext in ext_list:
            for file_path in root.glob(f'**/*{ext}'):
                if file_path.is_file():
                    try:
                        # Skip large files
                        if file_path.stat().st_size > config.max_file_size:
                            continue

                        # Quick content scan for keyword overlap
                        content = file_path.read_text(encoding='utf-8', errors='ignore')
                        content_lower = content.lower()

                        # Score based on keyword presence
                        score = 0.0
                        matches = 0
                        for word in query_words:
                            if len(word) > 3 and word in content_lower:
                                matches += 1
                                # Boost for word in filename
                                if word in file_path.name.lower():
                                    score += 0.2

                        if matches > 0:
                            score += (matches / len(query_words)) * 0.5
                            scored_files.append((score, file_path))
                    except Exception:
                        continue

    # Sort by score and take top results
    scored_files.sort(key=lambda x: -x[0])

    for score, file_path in scored_files[:config.max_results]:
        results.append(SearchResult(
            file_path=str(file_path),
            content=f"Semantic match: {file_path.name}",
            match_type="semantic",
            strategy=SearchStrategy.SEMANTIC,
            score=min(0.7, score),  # Cap semantic scores
        ))

    return results


# ============================================================================
# RESULT RANKING
# ============================================================================

def rank_results(results: List[SearchResult], query: SearchQuery) -> List[SearchResult]:
    """Rank and deduplicate search results."""
    # Deduplicate by file:line
    seen: Set[str] = set()
    unique_results = []

    for result in results:
        key = f"{result.file_path}:{result.line_number or 0}"
        if key not in seen:
            seen.add(key)
            unique_results.append(result)

    # Boost scores based on query analysis
    for result in unique_results:
        # Boost if file extension matches language hints
        if query.language_hints:
            for lang in query.language_hints:
                if any(result.file_path.endswith(ext) for ext in LANGUAGE_EXTENSIONS.get(lang, [])):
                    result.score *= 1.2

        # Boost if symbol is in filename
        for symbol in query.symbol_patterns:
            if symbol.lower() in Path(result.file_path).stem.lower():
                result.score *= 1.3

        # Boost for test files if searching for tests
        if 'test' in query.raw_query.lower():
            if 'test' in result.file_path.lower():
                result.score *= 1.2

    # Sort by score descending
    unique_results.sort(key=lambda r: -r.score)

    return unique_results


# ============================================================================
# MAIN SEARCH ENGINE
# ============================================================================

class SynodSearchEngine:
    """Intelligent code search engine with parallel strategies."""

    def __init__(self, root_path: str = ".", config: Optional[SearchConfig] = None):
        self.root_path = os.path.abspath(root_path)
        self.config = config or SearchConfig()
        self._index_cache: Dict[str, Any] = {}

    async def search(
        self,
        query: str,
        strategies: Optional[List[SearchStrategy]] = None,
        memories: Optional[List[Dict]] = None,
    ) -> List[SearchResult]:
        """Execute intelligent code search with parallel strategies.

        Args:
            query: Natural language or pattern query
            strategies: Specific strategies to use (default: all)
            memories: Past memories to guide search (memory-code linking)

        Returns:
            Ranked list of search results
        """
        # Analyze query
        parsed = analyze_query(query)

        # Default to all strategies
        if strategies is None:
            strategies = [
                SearchStrategy.RIPGREP,
                SearchStrategy.GLOB,
                SearchStrategy.SYMBOL,
                SearchStrategy.SEMANTIC,
            ]

        # Build search tasks
        tasks = []

        if SearchStrategy.RIPGREP in strategies and parsed.keywords:
            tasks.append(ripgrep_search(
                parsed.keywords[:5],  # Limit patterns
                self.root_path,
                self.config,
            ))

        if SearchStrategy.GLOB in strategies and parsed.file_patterns:
            tasks.append(glob_search(
                parsed.file_patterns,
                self.root_path,
                self.config,
            ))

        if SearchStrategy.SYMBOL in strategies and parsed.symbol_patterns:
            tasks.append(symbol_search(
                parsed.symbol_patterns,
                self.root_path,
                self.config,
                parsed.language_hints,
            ))

        if SearchStrategy.SEMANTIC in strategies:
            tasks.append(semantic_search_local(
                query,
                self.root_path,
                self.config,
            ))

        # Memory-guided search: use past memories to inform where to look
        if memories and SearchStrategy.MEMORY in strategies:
            memory_patterns = []
            for mem in memories:
                # Extract file paths and patterns from memory content
                content = mem.get('content', '')
                if '/' in content or '\\' in content:
                    # Might contain file paths
                    path_match = re.search(r'[\w/\\.-]+\.\w+', content)
                    if path_match:
                        memory_patterns.append(path_match.group())

            if memory_patterns:
                tasks.append(glob_search(memory_patterns, self.root_path, self.config))

        # Execute all strategies in parallel
        if not tasks:
            # Fallback: just search for the raw query
            tasks.append(ripgrep_search([query], self.root_path, self.config))

        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten and filter results
        results = []
        for task_results in all_results:
            if isinstance(task_results, list):
                results.extend(task_results)

        # Rank and return
        ranked = rank_results(results, parsed)
        return ranked[:self.config.max_results]

    async def search_for_context(
        self,
        query: str,
        max_tokens: int = 4000,
    ) -> Tuple[List[SearchResult], str]:
        """Search and format results as context for AI.

        Returns both the results and a formatted context string
        suitable for including in an AI prompt.
        """
        results = await self.search(query)

        context_parts = []
        total_chars = 0
        char_limit = max_tokens * 4  # Rough estimate: 4 chars per token

        for result in results:
            if total_chars >= char_limit:
                break

            part = f"\n### {result.location}\n"
            if result.content:
                part += f"```\n{result.content}\n```\n"

            if total_chars + len(part) <= char_limit:
                context_parts.append(part)
                total_chars += len(part)

        context_str = "## Relevant Code\n" + "".join(context_parts) if context_parts else ""

        return results, context_str


# ============================================================================
# CLI DISPLAY
# ============================================================================

def display_search_results(results: List[SearchResult], query: str) -> None:
    """Display search results with beautiful formatting."""
    if not results:
        console.print(Panel(
            Text("No results found", style="dim", justify="center"),
            title=f"[cyan]Search: {query}[/cyan]",
            border_style="cyan",
        ))
        return

    console.print()
    console.print(Text(f"  Found {len(results)} results  ", style=f"bold white on {PRIMARY}"))
    console.print()

    for i, result in enumerate(results[:15], 1):
        # Score indicator
        score_bar = "█" * int(result.score * 5) + "░" * (5 - int(result.score * 5))

        # Strategy icon
        strategy_icons = {
            SearchStrategy.RIPGREP: "",
            SearchStrategy.GLOB: "",
            SearchStrategy.SYMBOL: "",
            SearchStrategy.SEMANTIC: "",
            SearchStrategy.MEMORY: "",
        }
        icon = strategy_icons.get(result.strategy, "")

        # Header line
        header = Text()
        header.append(f"{i:2}. ", style="dim")
        header.append(f"{icon} ", style=PRIMARY)
        header.append(result.location, style=f"bold {CYAN}")
        header.append(f"  [{score_bar}]", style="dim")
        console.print(header)

        # Content preview
        if result.content:
            content_preview = result.content[:100]
            if len(result.content) > 100:
                content_preview += "..."
            console.print(f"   {content_preview}", style="dim")

        console.print()


async def interactive_search(root_path: str = ".") -> None:
    """Interactive search mode."""
    engine = SynodSearchEngine(root_path)

    console.print(Panel(
        Text.from_markup(
            f"[{CYAN}]Synod Intelligent Code Search[/{CYAN}]\n\n"
            f"Search across your codebase with parallel strategies.\n"
            f"Type your query or 'exit' to quit."
        ),
        border_style=CYAN,
    ))

    while True:
        try:
            query = console.input(f"\n[{PRIMARY}]search>[/{PRIMARY}] ")
            if query.lower() in ('exit', 'quit', 'q'):
                break

            if not query.strip():
                continue

            with console.status(f"[{CYAN}]Searching...[/{CYAN}]", spinner="dots"):
                results = await engine.search(query)

            display_search_results(results, query)

        except KeyboardInterrupt:
            break
        except EOFError:
            break

    console.print("\n[dim]Search session ended.[/dim]")


# ============================================================================
# COMMAND HANDLER
# ============================================================================

async def handle_search_command(args: str, root_path: str = ".") -> List[SearchResult]:
    """Handle /search command from CLI.

    Usage:
        /search <query>           Search for code
        /search -d <symbol>       Search for definition
        /search -f <pattern>      Search for files
    """
    if not args.strip():
        console.print(Panel(
            Text.from_markup(
                f"[{CYAN}]/search <query>[/{CYAN}]      Search for code\n"
                f"[{CYAN}]/search -d <name>[/{CYAN}]    Find definition\n"
                f"[{CYAN}]/search -f <pattern>[/{CYAN}] Find files\n\n"
                f"Examples:\n"
                f"  /search rate limiting\n"
                f"  /search -d UserService\n"
                f"  /search -f *.test.ts"
            ),
            title="[cyan]Code Search[/cyan]",
            border_style="cyan",
        ))
        return []

    engine = SynodSearchEngine(root_path)

    # Parse flags
    strategies = None
    query = args.strip()

    if query.startswith('-d '):
        # Definition search only
        query = query[3:]
        strategies = [SearchStrategy.SYMBOL]
    elif query.startswith('-f '):
        # File search only
        query = query[3:]
        strategies = [SearchStrategy.GLOB]

    with console.status(f"[{CYAN}]Searching...[/{CYAN}]", spinner="dots"):
        results = await engine.search(query, strategies)

    display_search_results(results, query)

    return results
