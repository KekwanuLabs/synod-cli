"""Stage 0: Pre-debate query analysis and classification.

This module uses a fast, cheap model (Claude Haiku) to analyze queries before
debate begins. It determines:
- Is the query coding-related? (scope enforcement)
- What's the complexity level? (routing strategy)
- Which domains are involved? (expertise weighting)
- How should the debate be structured? (optimization)

This keeps the main debate focused and token-efficient.
"""

from typing import List, Optional, Dict
from dataclasses import dataclass
import json
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .theme import CYAN, GOLD, PRIMARY, GREEN
from .openrouter import query_model

console = Console()

# Free classifier models (priority order)
# Using FREE models from OpenRouter to keep costs at $0
# NOTE: Grok 4.1 Fast is primary - very reliable with good availability
#       Other free models removed due to issues:
#       - google/gemma-3-12b:free: 400 errors (model unavailable)
#       - qwen/qwen-2.5-coder-32b-instruct:free: 429 errors (heavy rate limiting)
CLASSIFIER_MODELS = [
    "x-ai/grok-4.1-fast:free",  # Primary: fast, reliable, excellent availability
]

# Select primary classifier
CLASSIFIER_MODEL = CLASSIFIER_MODELS[0]  # Grok 4.1 Fast by default

# Domain categories
DOMAINS = [
    "architecture",      # System design, design patterns, structure
    "algorithms",        # Data structures, algorithmic complexity
    "web_dev",          # Frontend, React, Vue, Angular, CSS
    "backend",          # APIs, servers, microservices
    "database",         # SQL, NoSQL, query optimization
    "security",         # Vulnerabilities, auth, encryption
    "performance",      # Optimization, profiling, efficiency
    "testing",          # Unit tests, integration tests, TDD
    "devops",           # CI/CD, Docker, Kubernetes, deployment
    "ml_ai",            # Machine learning, neural networks, transformers
    "data_science",     # Data analysis, pandas, numpy, visualization
    "systems_programming", # OS, low-level, C/C++, kernel, embedded
    "mobile",           # iOS, Android, React Native, mobile apps
    "cloud",            # AWS, GCP, Azure, cloud architecture
    "networking",       # Protocols, TCP/IP, sockets, distributed systems
    "game_dev",         # Game engines, graphics, Unity, Unreal
    "blockchain",       # Smart contracts, Solidity, Web3, crypto
    "automation",       # Scripting, build tools, task automation
    "language_specific" # Language features, idioms, stdlib
]

# Complexity levels with descriptions
COMPLEXITY_LEVELS = {
    "trivial": "Math question or extremely simple query",
    "simple": "Basic function or straightforward task",
    "moderate": "Refactoring, debugging, or optimization",
    "complex": "System design or architectural decisions",
    "expert": "Advanced topics: distributed systems, compilers, etc."
}


@dataclass
class QueryAnalysis:
    """Results from Stage 0 analysis"""
    is_coding_related: bool
    rejection_reason: Optional[str]
    complexity: str  # trivial/simple/moderate/complex/expert
    primary_domain: str
    secondary_domains: List[str]
    technologies: List[str]
    requires_file_context: bool
    estimated_tokens: int
    debate_strategy: Dict[str, any]

    @classmethod
    def from_json(cls, json_str: str) -> 'QueryAnalysis':
        """Parse JSON response from classifier"""
        data = json.loads(json_str)
        return cls(**data)

    def get_token_budget(self) -> int:
        """Get token budget based on complexity"""
        budgets = {
            "trivial": 1000,
            "simple": 3000,
            "moderate": 10000,
            "complex": 30000,
            "expert": 60000
        }
        return budgets.get(self.complexity, 10000)

    def should_debate(self) -> bool:
        """Determine if query needs full debate"""
        return self.complexity not in ["trivial"]


CLASSIFIER_PROMPT = """
Analyze this coding query and return JSON only.

Query: "{query}"

Context: {context_info}

Extract the following information:

1. **is_coding_related**: boolean
   - true if related to programming, software development, or computer science
   - false if general knowledge, creative writing, math-only, or other

2. **rejection_reason**: string (only if is_coding_related is false)
   - Brief explanation of why it's not coding-related

3. **complexity**: string (one of: trivial, simple, moderate, complex, expert)
   BE VERY STRICT WITH CLASSIFICATION - default to higher complexity if uncertain!

   - trivial: ONLY for extremely basic queries that require zero debate:
     * Pure math: "what is 5+3?"
     * Print statement: "print hello world in python"
     * Variable declaration: "how to create a variable"
     * NEVER use trivial for functions, algorithms, or any logic

   - simple: Basic single-purpose functions WITHOUT complexity:
     * "Write a function to add two numbers"
     * "Function that returns if number is even"
     * "Basic string concatenation function"

   - moderate: Most coding tasks (DEFAULT for uncertain):
     * "Write factorial function" (requires recursion knowledge)
     * "Refactor this code", "Debug this error"
     * "Optimize performance", "Handle edge cases"
     * Any function with conditionals, loops, or multiple steps

   - complex: System design, architecture, multi-component solutions:
     * "Design a REST API", "Architecture for microservices"
     * "Implement authentication system"
     * "Database schema design"

   - expert: Advanced distributed systems, low-level optimization:
     * "Distributed caching system", "Compiler optimization"
     * "Custom memory allocator", "Consensus algorithms"

4. **primary_domain**: string (one of: {domains})

5. **secondary_domains**: list of strings (up to 2 additional domains)

6. **technologies**: list of strings
   - Programming languages, frameworks, tools mentioned
   - Examples: ["python", "react", "postgresql", "docker"]

7. **requires_file_context**: boolean
   - true if solution needs provided code files
   - false if can be answered without seeing specific code

8. **estimated_tokens**: integer
   - Rough estimate for complete debate (proposals + critiques + synthesis)
   - trivial: ~1000, simple: ~3000, moderate: ~10000, complex: ~30000, expert: ~60000

9. **debate_strategy**: object
   - recommended_bishops: integer (1-5, how many bishops should participate)
   - recommended_rounds: integer (1-4, how many debate rounds)
   - should_pope_challenge: boolean (allow challenge round?)

IMPORTANT:
- Be strict about coding relevance. Synod is for programming ONLY.
- Reject: "What's the weather?", "Tell me a joke", "Translate to French"
- Accept: Any programming, debugging, architecture, or CS theory question

Return ONLY valid JSON:
{{
  "is_coding_related": true,
  "rejection_reason": null,
  "complexity": "moderate",
  "primary_domain": "web_dev",
  "secondary_domains": ["performance"],
  "technologies": ["react", "javascript"],
  "requires_file_context": false,
  "estimated_tokens": 10000,
  "debate_strategy": {{
    "recommended_bishops": 3,
    "recommended_rounds": 3,
    "should_pope_challenge": false
  }}
}}
"""


async def analyze_query(
    query: str,
    context_files: Optional[List[str]] = None
) -> QueryAnalysis:
    """
    Stage 0: Analyze query before debate.

    Uses Claude Haiku for fast, cheap classification.

    Args:
        query: User's coding question
        context_files: Optional list of file paths provided as context

    Returns:
        QueryAnalysis with debate strategy
    """

    # Note: Don't print here - the Live display in council.py handles the UI

    # Prepare context info
    context_info = "No files provided"
    if context_files:
        context_info = f"{len(context_files)} file(s) provided as context"

    # Format prompt
    prompt = CLASSIFIER_PROMPT.format(
        query=query,
        context_info=context_info,
        domains=", ".join(DOMAINS)
    )

    # Try each classifier model with fallback
    for i, classifier_model in enumerate(CLASSIFIER_MODELS):
        try:
            # Query classifier model (silent=True to avoid confusing error messages)
            messages = [{"role": "user", "content": prompt}]
            response = await query_model(
                model=classifier_model,
                messages=messages,
                silent=True
            )

            # Parse response - extract content from response dict
            if response and 'content' in response:
                analysis = QueryAnalysis.from_json(response['content'])
            else:
                raise ValueError("No content in response")

            # Note: Don't call _display_analysis() here - the Live display in
            # council.py handles showing results within the Stage 0 panel.
            # Printing here would break the Live panel update.

            return analysis

        except json.JSONDecodeError as e:
            if i < len(CLASSIFIER_MODELS) - 1:
                # Not the last model, try next silently
                continue
            else:
                # Last model failed, use fallback (don't print - Live display handles it)
                return _get_fallback_analysis()

        except Exception as e:
            if i < len(CLASSIFIER_MODELS) - 1:
                # Not the last model, try next silently
                continue
            else:
                # Last model failed, use fallback (don't print - Live display handles it)
                return _get_fallback_analysis()

    # Should never reach here, but just in case
    return _get_fallback_analysis()


def _get_fallback_analysis() -> QueryAnalysis:
    """Fallback analysis when all classifiers fail"""
    return QueryAnalysis(
        is_coding_related=True,
        rejection_reason=None,
        complexity="moderate",
        primary_domain="language_specific",
        secondary_domains=[],
        technologies=["python"],
        requires_file_context=False,
        estimated_tokens=10000,
        debate_strategy={
            "recommended_bishops": 3,
            "recommended_rounds": 3,
            "should_pope_challenge": False
        }
    )


def _display_analysis(analysis: QueryAnalysis) -> None:
    """Display analysis results in beautiful format"""

    if not analysis.is_coding_related:
        return  # Rejection will be shown separately

    result = Text()
    result.append("  ✓ Coding-related: ", style="dim")
    result.append("YES\n", style=f"bold {GREEN}")

    result.append("  ✓ Complexity: ", style="dim")
    complexity_color = {
        "trivial": GREEN,
        "simple": CYAN,
        "moderate": GOLD,
        "complex": PRIMARY,
        "expert": "red"
    }.get(analysis.complexity, CYAN)
    result.append(f"{analysis.complexity.upper()}\n", style=f"bold {complexity_color}")

    result.append("  ✓ Domains: ", style="dim")
    domains_list = [analysis.primary_domain] + analysis.secondary_domains
    result.append(f"{', '.join(domains_list)}\n", style=CYAN)

    if analysis.technologies:
        result.append("  ✓ Technologies: ", style="dim")
        result.append(f"{', '.join(analysis.technologies)}\n", style="white")

    strategy = analysis.debate_strategy
    result.append("  ✓ Strategy: ", style="dim")
    result.append(
        f"{strategy['recommended_bishops']} bishops, "
        f"{strategy['recommended_rounds']} rounds\n",
        style=PRIMARY
    )

    console.print(result)


def show_rejection(reason: str) -> None:
    """Display rejection message for non-coding queries"""

    rejection = Text()
    rejection.append("⚠️  ", style=f"bold {GOLD}")
    rejection.append("Synod is focused on coding & architecture\n\n", style=f"bold {GOLD}")

    rejection.append("Your query appears to be: ", style="dim")
    rejection.append(f"{reason}\n\n", style="white")

    rejection.append("Please ask a programming-related question.\n\n", style="dim")

    rejection.append("Examples:\n", style=PRIMARY)
    rejection.append("  • ", style="dim")
    rejection.append("\"How do I handle errors in async Python?\"\n", style=CYAN)
    rejection.append("  • ", style="dim")
    rejection.append("\"Design a caching layer for my API\"\n", style=CYAN)
    rejection.append("  • ", style="dim")
    rejection.append("\"Refactor this React component\"\n", style=CYAN)
    rejection.append("  • ", style="dim")
    rejection.append("\"Optimize this database query\"\n", style=CYAN)

    panel = Panel(
        rejection,
        title=f"[{GOLD}]Not a Coding Query[/{GOLD}]",
        border_style=GOLD,
    )

    console.print()
    console.print(panel)
    console.print()


# Quick test
if __name__ == "__main__":
    import asyncio

    async def test():
        # Test coding query
        analysis = await analyze_query(
            "Optimize my React component that re-renders too often"
        )
        print(f"Analysis: {analysis}")

        # Test non-coding query
        analysis2 = await analyze_query("What's the weather in Paris?")
        if not analysis2.is_coding_related:
            show_rejection(analysis2.rejection_reason)

    asyncio.run(test())
