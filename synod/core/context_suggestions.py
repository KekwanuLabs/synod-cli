"""Smart context suggestions for Synod debates.

This module analyzes user queries and suggests relevant files from the indexed
project to include as context for the bishops.
"""

import re
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass

from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from .indexer import IndexedProject
from .theme import PRIMARY, CYAN, GOLD, emoji
from .display import console


@dataclass
class FileSuggestion:
    """A suggested file with relevance score."""

    path: str
    score: int
    reasons: List[str]
    preview: Optional[str] = None


class ContextSuggester:
    """Smart context suggestion engine."""

    def __init__(self, indexed_project: IndexedProject):
        """Initialize suggester with indexed project.

        Args:
            indexed_project: The indexed project to search
        """
        self.project = indexed_project

    def analyze_query(self, query: str) -> Dict[str, Any]:
        """Analyze query to extract hints about relevant files.

        Args:
            query: User's coding query

        Returns:
            Dict with extracted hints (keywords, file_mentions, languages)
        """
        hints = {
            'keywords': [],
            'file_mentions': [],
            'languages': [],
            'extensions': [],
        }

        # Extract potential file mentions (e.g., "utils.py", "config.json")
        file_pattern = r'\b[\w\-\.]+\.(py|js|ts|tsx|jsx|java|cpp|c|go|rs|rb|php|swift|kt|cs|scala|sh|json|yml|yaml|md|txt)\b'
        hints['file_mentions'] = re.findall(file_pattern, query, re.IGNORECASE)

        # Extract language mentions
        language_keywords = {
            'python': ['python', 'py', 'django', 'flask', 'fastapi'],
            'javascript': ['javascript', 'js', 'node', 'react', 'vue', 'angular'],
            'typescript': ['typescript', 'ts', 'tsx'],
            'java': ['java', 'spring', 'maven', 'gradle'],
            'go': ['go', 'golang'],
            'rust': ['rust', 'cargo'],
        }

        query_lower = query.lower()
        for lang, keywords in language_keywords.items():
            if any(kw in query_lower for kw in keywords):
                hints['languages'].append(lang.capitalize())

        # Extract general keywords (split by spaces, remove common words)
        common_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'can', 'may', 'might', 'this', 'that', 'these', 'those',
            'how', 'what', 'where', 'when', 'why', 'which', 'who', 'i', 'you',
            'we', 'they', 'it', 'my', 'your', 'our', 'their', 'its'
        }

        words = re.findall(r'\b\w+\b', query_lower)
        hints['keywords'] = [
            w for w in words
            if len(w) > 3 and w not in common_words
        ][:10]  # Top 10 keywords

        return hints

    def search_file_contents(self, keyword: str, max_results: int = 20) -> List[Tuple[str, str]]:
        """Search for keyword in file contents using ripgrep.

        Args:
            keyword: Keyword to search for
            max_results: Maximum number of results

        Returns:
            List of (file_path, matching_line) tuples
        """
        try:
            # Use ripgrep to search file contents
            cmd = [
                'rg',
                '--max-count', '1',  # Only first match per file
                '--no-heading',
                '--with-filename',
                '--line-number',
                '--case-insensitive',
                '--glob', '!.git/',
                '--glob', '!.synod/',
                '--glob', '!node_modules/',
                '--glob', '!__pycache__/',
                keyword,
                str(self.project.path)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project.path
            )

            matches = []
            for line in result.stdout.strip().split('\n')[:max_results]:
                if not line:
                    continue

                # Parse: "path:line:content"
                parts = line.split(':', 2)
                if len(parts) >= 3:
                    file_path = parts[0]
                    content = parts[2].strip()
                    matches.append((file_path, content))

            return matches

        except Exception:
            return []

    def suggest_files(self, query: str, top_n: int = 5) -> List[FileSuggestion]:
        """Suggest relevant files based on query analysis.

        Args:
            query: User's coding query
            top_n: Number of top suggestions to return

        Returns:
            List of FileSuggestion objects, sorted by relevance
        """
        hints = self.analyze_query(query)
        scored_files: Dict[str, FileSuggestion] = {}

        # Strategy 1: Direct file mentions
        for file_mention in hints['file_mentions']:
            matches = self.project.search_files(file_mention)
            for file_path in matches:
                if file_path not in scored_files:
                    scored_files[file_path] = FileSuggestion(
                        path=file_path,
                        score=100,  # Highest priority
                        reasons=[f"📄 Mentioned in query: {file_mention}"]
                    )

        # Strategy 2: Language-specific files
        for language in hints['languages']:
            lang_files = self.project.find_files_by_language(language)
            for file_path in lang_files[:10]:  # Limit per language
                if file_path not in scored_files:
                    scored_files[file_path] = FileSuggestion(
                        path=file_path,
                        score=30,
                        reasons=[f"🔤 {language} file"]
                    )
                else:
                    scored_files[file_path].score += 30
                    scored_files[file_path].reasons.append(f"🔤 {language} file")

        # Strategy 3: Keyword search in file contents
        for keyword in hints['keywords'][:3]:  # Top 3 keywords
            matches = self.search_file_contents(keyword)
            for file_path, content in matches:
                # Make path relative if it's absolute
                if file_path.startswith(str(self.project.path)):
                    file_path = str(Path(file_path).relative_to(self.project.path))

                if file_path not in scored_files:
                    scored_files[file_path] = FileSuggestion(
                        path=file_path,
                        score=50,
                        reasons=[f"🔍 Contains '{keyword}'"],
                        preview=content[:80] + "..." if len(content) > 80 else content
                    )
                else:
                    scored_files[file_path].score += 50
                    scored_files[file_path].reasons.append(f"🔍 Contains '{keyword}'")

        # Strategy 4: Path-based keyword matching (with fuzzy matching)
        for keyword in hints['keywords'][:5]:
            # Try exact match first
            matches = self.project.search_files(keyword)

            # Also try without common suffixes for better matching
            # e.g., "indexing" -> "index", "testing" -> "test"
            if not matches and keyword.endswith('ing'):
                stem = keyword[:-3]  # Remove 'ing'
                matches = self.project.search_files(stem)
            elif not matches and keyword.endswith('er'):
                stem = keyword[:-2]  # Remove 'er'
                matches = self.project.search_files(stem)

            for file_path in matches[:5]:
                if file_path not in scored_files:
                    scored_files[file_path] = FileSuggestion(
                        path=file_path,
                        score=20,
                        reasons=[f"📂 Path contains '{keyword}'"]
                    )
                else:
                    scored_files[file_path].score += 20

        # Sort by score and return top N
        sorted_suggestions = sorted(
            scored_files.values(),
            key=lambda s: s.score,
            reverse=True
        )

        return sorted_suggestions[:top_n]

    def show_suggestions(self, suggestions: List[FileSuggestion]) -> None:
        """Display file suggestions in a beautiful panel.

        Args:
            suggestions: List of FileSuggestion objects
        """
        if not suggestions:
            return

        # Build table
        table = Table(
            show_header=True,
            box=None,
            padding=(0, 1),
            collapse_padding=True,
            expand=False,
        )
        table.add_column("#", style="dim", width=2, justify="right")
        table.add_column("File", style=CYAN, width=45)
        table.add_column("Why", style="dim")

        for i, suggestion in enumerate(suggestions, 1):
            # File path with smart truncation
            file_display = suggestion.path
            if len(file_display) > 43:
                parts = file_display.split('/')
                if len(parts) > 2:
                    file_display = f".../{'/'.join(parts[-2:])}"
                else:
                    file_display = "..." + file_display[-40:]

            # Combine all reasons
            all_reasons = " • ".join(suggestion.reasons)
            if len(all_reasons) > 50:
                all_reasons = all_reasons[:47] + "..."

            table.add_row(
                str(i),
                file_display,
                all_reasons
            )

            # Show preview if available
            if suggestion.preview:
                preview_text = suggestion.preview
                if len(preview_text) > 70:
                    preview_text = preview_text[:67] + "..."
                table.add_row(
                    "",
                    Text(f"  └─ {preview_text}", style="dim italic"),
                    ""
                )

        # Panel
        title_text = Text()
        title_text.append(emoji('project'), style=PRIMARY)
        title_text.append(" Smart Context Suggestions ", style="primary")

        panel = Panel(
            table,
            title=title_text,
            border_style=PRIMARY,
            subtitle=f"[dim]Found {len(suggestions)} relevant files for your query[/dim]",
        )

        console.print()
        console.print(panel)


def suggest_context_files(
    indexed_project: IndexedProject,
    query: str,
    top_n: int = 5
) -> List[str]:
    """Suggest relevant context files for a query.

    Args:
        indexed_project: The indexed project
        query: User's coding query
        top_n: Number of suggestions to return

    Returns:
        List of suggested file paths
    """
    if not indexed_project:
        return []

    suggester = ContextSuggester(indexed_project)
    suggestions = suggester.suggest_files(query, top_n)

    if suggestions:
        suggester.show_suggestions(suggestions)

    return [s.path for s in suggestions]
