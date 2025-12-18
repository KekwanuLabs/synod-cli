"""Synod Auto-Context - Automatically gather relevant code for debates

Analyzes user queries and automatically includes relevant code snippets
as context for the AI council. This happens transparently before debates.

Features:
- Zero-latency query analysis (regex-based, no LLM calls)
- Parallel file reading
- Smart token budget management
- Memory-guided context boosting
"""

import os
import re
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass

from rich.console import Console

from .theme import CYAN, GRAY

console = Console()


@dataclass
class AutoContextConfig:
    """Configuration for auto-context gathering."""
    max_files: int = 5
    max_tokens: int = 4000
    max_file_size: int = 50_000  # 50KB per file
    include_line_numbers: bool = True


@dataclass
class ContextFile:
    """A file gathered for context."""
    path: str
    content: str
    relevance: float  # 0-1
    match_reason: str


# Common code file extensions
CODE_EXTENSIONS = {
    '.py', '.js', '.ts', '.tsx', '.jsx', '.rs', '.go', '.java',
    '.cpp', '.c', '.h', '.hpp', '.rb', '.php', '.swift', '.kt',
    '.scala', '.sh', '.bash', '.sql', '.yaml', '.yml', '.json',
    '.toml', '.md', '.txt', '.html', '.css', '.scss',
}


def analyze_query_for_context(query: str) -> Dict[str, Any]:
    """Analyze a query to extract context signals.

    Returns:
        Dict with:
        - file_mentions: Explicit file paths mentioned
        - symbol_mentions: Function/class names mentioned
        - keywords: Important keywords for search
        - is_code_query: Whether this needs code context
    """
    analysis = {
        'file_mentions': [],
        'symbol_mentions': [],
        'keywords': [],
        'is_code_query': False,
    }

    # Extract explicit file paths (e.g., "src/auth.py", "./config.ts")
    file_pattern = r'(?:^|[\s\'\"(])([./\w-]+\.(?:py|js|ts|tsx|jsx|rs|go|java|cpp|c|h|rb|php|swift|kt|scala|sh|sql|yaml|yml|json|toml|md|html|css|scss))(?:[\s\'\")\n,:]|$)'
    file_matches = re.findall(file_pattern, query, re.IGNORECASE)
    analysis['file_mentions'] = list(set(file_matches))

    # Extract symbol names (CamelCase, snake_case, SCREAMING_CASE)
    symbol_pattern = r'\b([A-Z][a-zA-Z0-9]+|[a-z][a-z0-9]*(?:_[a-z0-9]+)+|[A-Z][A-Z0-9_]{2,})\b'
    symbols = re.findall(symbol_pattern, query)
    # Filter out common words
    common_words = {'the', 'and', 'for', 'this', 'that', 'with', 'from', 'have', 'been'}
    analysis['symbol_mentions'] = [s for s in symbols if s.lower() not in common_words and len(s) > 2]

    # Detect if this is a code-related query
    code_indicators = [
        'function', 'class', 'method', 'import', 'module', 'file',
        'error', 'bug', 'fix', 'implement', 'code', 'variable',
        'type', 'interface', 'struct', 'def ', 'const ', 'let ',
        'async', 'await', 'return', 'export', 'import',
    ]
    query_lower = query.lower()
    analysis['is_code_query'] = (
        len(analysis['file_mentions']) > 0 or
        len(analysis['symbol_mentions']) > 0 or
        any(ind in query_lower for ind in code_indicators)
    )

    # Extract important keywords
    stopwords = {
        'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or',
        'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has',
        'do', 'does', 'did', 'will', 'would', 'could', 'should', 'can',
        'this', 'that', 'these', 'those', 'it', 'its', 'my', 'your',
        'i', 'me', 'we', 'you', 'he', 'she', 'they', 'them', 'what',
        'how', 'why', 'where', 'when', 'which', 'who',
    }
    words = re.findall(r'\b\w+\b', query_lower)
    analysis['keywords'] = [w for w in words if w not in stopwords and len(w) > 2][:10]

    return analysis


async def read_file_async(path: Path, max_size: int) -> Optional[str]:
    """Read a file asynchronously with size limit."""
    try:
        if not path.exists() or not path.is_file():
            return None

        if path.stat().st_size > max_size:
            return None

        # Use asyncio to not block
        loop = asyncio.get_event_loop()
        content = await loop.run_in_executor(
            None,
            lambda: path.read_text(encoding='utf-8', errors='ignore')
        )
        return content
    except Exception:
        return None


async def gather_auto_context(
    query: str,
    root_path: str = ".",
    config: Optional[AutoContextConfig] = None,
    memory_hints: Optional[List[str]] = None,
) -> Tuple[Dict[str, str], List[str]]:
    """Automatically gather relevant code context for a query.

    Args:
        query: The user's query
        root_path: Project root directory
        config: Configuration options
        memory_hints: Hints from past memories (file paths, patterns)

    Returns:
        Tuple of (files_dict, file_paths_list) where files_dict maps
        relative path -> content, ready for API submission
    """
    cfg = config or AutoContextConfig()
    root = Path(root_path).resolve()

    # Analyze query
    analysis = analyze_query_for_context(query)

    if not analysis['is_code_query']:
        return {}, []

    gathered: List[ContextFile] = []

    # 1. First, try explicit file mentions (highest priority)
    for file_mention in analysis['file_mentions'][:cfg.max_files]:
        found = False

        # Try different path resolutions
        candidates = [
            root / file_mention,
            root / file_mention.lstrip('./'),
        ]

        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                content = await read_file_async(candidate, cfg.max_file_size)
                if content:
                    rel_path = str(candidate.relative_to(root))
                    gathered.append(ContextFile(
                        path=rel_path,
                        content=content,
                        relevance=1.0,  # Explicit mentions are highest relevance
                        match_reason=f"Mentioned in query: {file_mention}",
                    ))
                    found = True
                break

        # If not found at exact path, search recursively for the filename
        if not found:
            filename = Path(file_mention).name  # Get just the filename
            for match in root.glob(f'**/{filename}'):
                # Skip common non-source directories
                path_str = str(match)
                if any(skip in path_str for skip in ['node_modules', '.git', '__pycache__', 'venv', '.venv', '.env', 'dist', 'build']):
                    continue

                content = await read_file_async(match, cfg.max_file_size)
                if content:
                    rel_path = str(match.relative_to(root))
                    gathered.append(ContextFile(
                        path=rel_path,
                        content=content,
                        relevance=0.95,  # Slightly lower than exact match
                        match_reason=f"Found file matching: {file_mention}",
                    ))
                    found = True
                    break  # Take first match

    # 2. Search for symbol definitions (medium priority)
    if len(gathered) < cfg.max_files and analysis['symbol_mentions']:
        symbols_to_find = analysis['symbol_mentions'][:3]

        for ext in CODE_EXTENSIONS:
            if len(gathered) >= cfg.max_files:
                break

            for file_path in root.glob(f'**/*{ext}'):
                if len(gathered) >= cfg.max_files:
                    break

                # Skip common non-source directories
                path_str = str(file_path)
                if any(skip in path_str for skip in ['node_modules', '.git', '__pycache__', 'venv', '.env']):
                    continue

                content = await read_file_async(file_path, cfg.max_file_size)
                if not content:
                    continue

                # Check if any symbol is defined in this file
                for symbol in symbols_to_find:
                    # Pattern for definitions
                    def_patterns = [
                        rf'\bdef\s+{re.escape(symbol)}\s*\(',      # Python
                        rf'\bclass\s+{re.escape(symbol)}[\s:(]',   # Class
                        rf'\bfunction\s+{re.escape(symbol)}\s*\(', # JS
                        rf'\bconst\s+{re.escape(symbol)}\s*=',     # JS const
                        rf'\binterface\s+{re.escape(symbol)}[\s{{<]', # TS
                        rf'\btype\s+{re.escape(symbol)}\s*=',      # TS type
                    ]

                    for pattern in def_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            rel_path = str(file_path.relative_to(root))
                            # Check not already added
                            if not any(g.path == rel_path for g in gathered):
                                gathered.append(ContextFile(
                                    path=rel_path,
                                    content=content,
                                    relevance=0.8,
                                    match_reason=f"Contains definition of '{symbol}'",
                                ))
                            break

    # 3. Use memory hints (if available)
    if len(gathered) < cfg.max_files and memory_hints:
        for hint in memory_hints[:5]:
            if len(gathered) >= cfg.max_files:
                break

            # Try to resolve hint as a file path
            hint_path = root / hint
            if hint_path.exists() and hint_path.is_file():
                rel_path = str(hint_path.relative_to(root))
                if not any(g.path == rel_path for g in gathered):
                    content = await read_file_async(hint_path, cfg.max_file_size)
                    if content:
                        gathered.append(ContextFile(
                            path=rel_path,
                            content=content,
                            relevance=0.6,
                            match_reason=f"From memory: {hint}",
                        ))

    # Sort by relevance and apply token budget
    gathered.sort(key=lambda x: -x.relevance)

    files_dict: Dict[str, str] = {}
    file_paths: List[str] = []
    total_chars = 0
    char_limit = cfg.max_tokens * 4  # Rough estimate

    for ctx_file in gathered:
        content = ctx_file.content
        if cfg.include_line_numbers:
            lines = content.split('\n')
            content = '\n'.join(f"{i+1:4}| {line}" for i, line in enumerate(lines))

        if total_chars + len(content) > char_limit:
            # Truncate if needed
            remaining = char_limit - total_chars
            if remaining > 500:  # Only include if we can fit something useful
                content = content[:remaining] + "\n... (truncated)"
            else:
                continue

        files_dict[ctx_file.path] = content
        file_paths.append(ctx_file.path)
        total_chars += len(content)

    return files_dict, file_paths


def display_auto_context_summary(files: Dict[str, str], file_paths: List[str]) -> None:
    """Display a brief summary of auto-gathered context."""
    if not file_paths:
        return

    console.print(f"[{GRAY}]Auto-context: {len(file_paths)} file(s) included[/{GRAY}]")
    for path in file_paths[:3]:
        console.print(f"[{GRAY}]  + {path}[/{GRAY}]")
    if len(file_paths) > 3:
        console.print(f"[{GRAY}]  ... and {len(file_paths) - 3} more[/{GRAY}]")
