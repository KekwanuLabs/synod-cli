"""Intelligent debate orchestration with adaptive rounds and consensus detection.

This is the heart of Synod's multi-stage debate system:
- Stage 0: Pre-analysis (complexity, domains, strategy)
- Stage 1: Bishop proposals (parallel, weighted)
- Stage 2: Adversarial critiques (smart pairing)
- Stage 3: Pope synthesis (hybrid solution)
- Stage 4: Challenge round (optional, 30% on complex queries)

The orchestrator dynamically adjusts based on:
- Query complexity
- Consensus detection
- Token budget
- Time limits
"""

from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import time
import random
import asyncio

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn

from .theme import CYAN, ACCENT, SECONDARY, GOLD, GREEN, PRIMARY
from .classifier import analyze_query, QueryAnalysis, show_rejection
from .expertise import calculate_bishop_weights, initialize_bishop_expertise, record_user_feedback
from .openrouter import query_model, query_models_parallel

console = Console()


@dataclass
class Proposal:
    """A bishop's proposal"""
    bishop_id: str
    content: str
    tokens: int
    timestamp: float = field(default_factory=time.time)


@dataclass
class Critique:
    """A bishop's critique of another's proposal"""
    critic_id: str
    target_id: str
    content: str
    severity: str  # minor/moderate/critical
    tokens: int


@dataclass
class Synthesis:
    """Pope's final synthesis"""
    model_id: str  # Pope model that created the synthesis
    content: str
    attribution: Dict[str, List[str]]  # bishop_id -> list of contributions
    rejections: Dict[str, str]  # bishop_id -> rejection reason
    tokens: int


@dataclass
class DebateResult:
    """Complete debate results"""
    query: str
    analysis: QueryAnalysis
    proposals: List[Proposal]
    critiques: List[Critique]
    synthesis: Synthesis
    total_tokens: int
    duration: float
    bishop_weights: Dict[str, float]


class DebateStrategy:
    """Determines debate flow based on query complexity"""

    def __init__(self, analysis: QueryAnalysis, token_budget: int):
        self.analysis = analysis
        self.token_budget = token_budget
        self.max_rounds = self._calculate_max_rounds()
        self.recommended_bishops = analysis.debate_strategy["recommended_bishops"]
        self.recommended_rounds = analysis.debate_strategy["recommended_rounds"]

    def _calculate_max_rounds(self) -> int:
        """Calculate maximum debate rounds"""
        complexity_rounds = {
            "trivial": 1,   # Just pick fastest bishop
            "simple": 2,    # Proposals + synthesis
            "moderate": 3,  # Proposals + critiques + synthesis
            "complex": 4,   # + rebuttals
            "expert": 5     # + challenge round
        }
        return complexity_rounds.get(self.analysis.complexity, 3)

    async def should_continue(
        self,
        current_round: int,
        proposals: List[Proposal],
        critiques: List[Critique],
        tokens_used: int,
        elapsed_time: float
    ) -> bool:
        """Determine if debate should continue to next round (with smart consensus detection)"""

        # Always do at least Stage 1
        if current_round == 1:
            return True

        # Stage 2 (critiques) - ALWAYS run to get diverse perspectives
        # High consensus doesn't mean correct - all models could make the same mistake
        # Smart pairwise skipping in council.py handles truly redundant critiques
        if current_round == 2:
            # Measure consensus for display and to inform critique intensity
            consensus = await self._measure_consensus(proposals)
            # Always continue to Stage 2 - don't skip based on consensus
            return True

        # After critiques, proceed to synthesis
        if current_round == 3 and critiques:
            # Always proceed to synthesis after critiques
            return False

        # Token budget check
        if tokens_used > self.token_budget * 0.8:
            console.print(f"[{GOLD}]⚠️  Token budget limit - proceeding to synthesis[/{GOLD}]")
            return False

        # Time limit (45s per round max)
        if elapsed_time > 45 * current_round:
            console.print(f"[{GOLD}]⏱️  Time limit - proceeding to synthesis[/{GOLD}]")
            return False

        # Continue if under max rounds
        return current_round < self.max_rounds

    async def _measure_consensus(self, proposals: List[Proposal]) -> float:
        """
        Measure consensus between proposals using LLM semantic analysis.
        Returns value 0.0-1.0 (1.0 = perfect agreement)

        Uses free classifier LLM to determine if solutions are semantically similar.
        Falls back to keyword heuristic if LLM unavailable.
        """
        if len(proposals) < 2:
            return 1.0

        # Try LLM-based semantic consensus first (more accurate)
        try:
            return await self._measure_consensus_llm(proposals)
        except Exception as e:
            console.print(f"[dim]LLM consensus unavailable, using keyword fallback[/dim]")
            return self._measure_consensus_keyword(proposals)

    async def _measure_consensus_llm(self, proposals: List[Proposal]) -> float:
        """Use LLM to measure semantic consensus between proposals.

        Uses a sophisticated multi-dimensional analysis rather than simple text comparison:
        1. Analyzes core algorithm/approach of each proposal
        2. Compares data structures and design patterns used
        3. Evaluates architectural decisions
        4. Considers error handling strategies
        5. Looks at overall problem-solving philosophy

        Tries all free classifier models with fallback to avoid rate limiting.
        """
        from .classifier import CLASSIFIER_MODELS
        from .openrouter import query_model
        import asyncio
        import re

        # Build a comprehensive view of all proposals for holistic comparison
        proposals_summary = []
        for i, p in enumerate(proposals):
            # Include more content but be strategic about what we include
            # Take beginning (approach), middle (implementation), and end (error handling)
            content = p.content
            content_len = len(content)

            if content_len <= 2000:
                excerpt = content
            else:
                # Smart excerpting: beginning + middle + end
                beginning = content[:800]
                middle_start = content_len // 2 - 400
                middle = content[middle_start:middle_start + 800]
                end = content[-400:]
                excerpt = f"{beginning}\n\n[...middle section...]\n\n{middle}\n\n[...end section...]\n\n{end}"

            proposals_summary.append(f"=== PROPOSAL {i+1} (from {p.bishop_id}) ===\n{excerpt}")

        all_proposals_text = "\n\n".join(proposals_summary)

        # Shorter consensus prompt for faster analysis
        consensus_prompt = f"""Rate how much these solutions AGREE (0-100).

{all_proposals_text}

Focus on: same algorithm? same data structures? same approach?
Ignore: variable names, formatting, comments.

90-100 = same approach, 50-74 = similar but different, 0-49 = very different.

Reply with ONLY a number:"""

        # Try each classifier model with fallback
        for model_idx, classifier_model in enumerate(CLASSIFIER_MODELS):
            try:
                messages = [{"role": "user", "content": consensus_prompt}]
                response = await query_model(classifier_model, messages, silent=True)

                if response and response.get('content'):
                    content = response.get('content', '0')
                    # Find the number in response
                    match = re.search(r'\b(\d+)\b', content)
                    if match:
                        score = int(match.group(1))
                        return min(100, max(0, score)) / 100.0

                # No valid response, try next model
                if model_idx < len(CLASSIFIER_MODELS) - 1:
                    continue
                else:
                    raise Exception("No valid LLM responses from any classifier")

            except Exception as e:
                # Model failed, try next one
                if model_idx < len(CLASSIFIER_MODELS) - 1:
                    continue
                else:
                    # Last model failed
                    raise Exception(f"All classifier models failed for consensus: {e}")

        # Should never reach here
        raise Exception("Consensus detection failed")

    def _measure_consensus_keyword(self, proposals: List[Proposal]) -> float:
        """Fallback keyword-based consensus measurement"""
        # Extract keywords from each proposal
        def get_keywords(text: str) -> set:
            words = text.lower().split()
            return {w.strip('.,;()[]{}') for w in words if len(w) > 4}

        keyword_sets = [get_keywords(p.content) for p in proposals]

        # Calculate pairwise overlaps
        overlaps = []
        for i in range(len(keyword_sets)):
            for j in range(i + 1, len(keyword_sets)):
                intersection = len(keyword_sets[i] & keyword_sets[j])
                union = len(keyword_sets[i] | keyword_sets[j])
                if union > 0:
                    overlaps.append(intersection / union)

        return sum(overlaps) / len(overlaps) if overlaps else 0.0

    async def get_pairwise_similarities(self, proposals: List[Proposal]) -> dict:
        """
        Get pairwise similarity scores between all proposals.

        Returns a dict like:
        {
            ("bishop_a", "bishop_b"): 0.85,  # 85% similar
            ("bishop_a", "bishop_c"): 0.45,  # 45% similar
            ...
        }

        This enables smart critique pairing - only critique dissimilar proposals.
        """
        from .classifier import CLASSIFIER_MODELS
        from .openrouter import query_model
        import asyncio
        import re

        if len(proposals) < 2:
            return {}

        # Generate all pairs
        pairs = []
        for i in range(len(proposals)):
            for j in range(i + 1, len(proposals)):
                pairs.append((proposals[i], proposals[j]))

        async def compare_pair(p1: Proposal, p2: Proposal, classifier_model: str) -> tuple:
            """Compare two proposals and return similarity score."""
            # Smart excerpting for each proposal
            def excerpt(content: str) -> str:
                if len(content) <= 1500:
                    return content
                # Beginning + middle + end
                return f"{content[:600]}\n[...]\n{content[len(content)//2-300:len(content)//2+300]}\n[...]\n{content[-300:]}"

            # Shorter prompt for faster comparison
            prompt = f"""Rate how similar these two solutions are (0-100).

A: {excerpt(p1.content)[:800]}

B: {excerpt(p2.content)[:800]}

Focus: same algorithm? same data structures? same approach?
Ignore: variable names, formatting, comments.

90-100 = nearly identical, 50-70 = moderately similar, 0-49 = very different.

Reply with ONLY a number:"""

            try:
                result = await query_model(classifier_model, [{"role": "user", "content": prompt}], silent=True)
                if result and result.get('content'):
                    match = re.search(r'\b(\d+)\b', result['content'])
                    if match:
                        score = int(match.group(1))
                        return (p1.bishop_id, p2.bishop_id, min(100, max(0, score)) / 100.0)
            except:
                pass
            return (p1.bishop_id, p2.bishop_id, 0.5)  # Default to 50% if comparison fails

        # Try each classifier model
        for classifier_model in CLASSIFIER_MODELS:
            try:
                # Run all comparisons in parallel
                tasks = [compare_pair(p1, p2, classifier_model) for p1, p2 in pairs]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Build similarity dict
                similarities = {}
                for result in results:
                    if isinstance(result, tuple) and len(result) == 3:
                        bishop_a, bishop_b, score = result
                        # Store both directions for easy lookup
                        similarities[(bishop_a, bishop_b)] = score
                        similarities[(bishop_b, bishop_a)] = score

                if similarities:
                    return similarities

            except Exception:
                continue

        # Fallback: use keyword similarity
        return self._get_pairwise_similarities_keyword(proposals)

    def _get_pairwise_similarities_keyword(self, proposals: List[Proposal]) -> dict:
        """Fallback keyword-based pairwise similarity."""
        def get_keywords(text: str) -> set:
            words = text.lower().split()
            return {w.strip('.,;()[]{}') for w in words if len(w) > 4}

        similarities = {}
        for i in range(len(proposals)):
            for j in range(i + 1, len(proposals)):
                p1, p2 = proposals[i], proposals[j]
                kw1 = get_keywords(p1.content)
                kw2 = get_keywords(p2.content)

                intersection = len(kw1 & kw2)
                union = len(kw1 | kw2)
                score = intersection / union if union > 0 else 0.0

                similarities[(p1.bishop_id, p2.bishop_id)] = score
                similarities[(p2.bishop_id, p1.bishop_id)] = score

        return similarities


class SynodDebate:
    """Orchestrates intelligent multi-round debate"""

    def __init__(self, bishops: List[str], pope: str):
        # Pope is UNBIASED - does not debate, only synthesizes
        # Exclude Pope from bishops list (Pope observes Stage 1 & 2, speaks only in Stage 3)
        self.bishops = [b for b in bishops if b != pope]
        self.pope = pope
        self.start_time = time.time()

    async def run_debate(
        self,
        query: str,
        context_files: Optional[List[str]] = None,
        context_content: Optional[str] = None
    ) -> Optional[DebateResult]:
        """
        Run complete debate from Stage 0 through synthesis.

        Args:
            query: User's coding question
            context_files: Optional list of file paths to read for context
            context_content: Optional pre-read file content (used by CLI)

        Returns:
            DebateResult or None if query rejected.
        """

        # ═══════════════════════════════════════════════════
        # STAGE 0: PRE-DEBATE ANALYSIS
        # ═══════════════════════════════════════════════════
        console.print(f"\n[{CYAN}]━━━ Stage 0: Query Analysis ━━━[/{CYAN}]\n")

        analysis = await analyze_query(query, context_files)

        # Reject if not coding-related
        if not analysis.is_coding_related:
            show_rejection(analysis.rejection_reason)
            return None

        # Initialize expertise if needed
        initialize_bishop_expertise(self.bishops)

        # Calculate bishop weights for this query
        query_domains = [analysis.primary_domain] + analysis.secondary_domains
        bishop_weights = calculate_bishop_weights(query_domains, self.bishops)

        # Show weights
        self._display_weights(bishop_weights)

        # Determine debate strategy
        strategy = DebateStrategy(
            analysis=analysis,
            token_budget=analysis.get_token_budget()
        )

        # Display token budget with explanation
        complexity_desc = {
            "trivial": "Quick answer",
            "simple": "Brief debate",
            "moderate": "Standard debate",
            "complex": "Deep debate",
            "expert": "Extensive debate"
        }.get(analysis.complexity, "Standard debate")

        console.print(
            f"[dim]💬 Debate scope: {complexity_desc} "
            f"(~{strategy.token_budget:,} tokens = controls response length & cost)[/dim]\n"
        )

        # Select participating bishops (top N by weight)
        participating_bishops = self._select_top_bishops(
            bishop_weights,
            count=strategy.recommended_bishops
        )

        console.print(f"[{PRIMARY}]🎭 Debate participants: {len(participating_bishops)} bishops[/{PRIMARY}]")
        console.print(f"[{SECONDARY}]⚖️  Pope {self._format_bishop_name(self.pope)} observing (will synthesize in Stage 3)[/{SECONDARY}]\n")

        # ═══════════════════════════════════════════════════
        # STAGE 1: BISHOP PROPOSALS
        # ═══════════════════════════════════════════════════
        console.print(f"[{CYAN}]━━━ Stage 1: Bishop Proposals ━━━[/{CYAN}]\n")

        proposals = await self._stage1_proposals(
            query=query,
            bishops=participating_bishops,
            context_files=context_files,
            context_content=context_content,
            analysis=analysis
        )

        tokens_used = sum(p.tokens for p in proposals)

        # Check if should continue (with smart LLM-based consensus detection!)
        if not await strategy.should_continue(
            current_round=2,
            proposals=proposals,
            critiques=[],
            tokens_used=tokens_used,
            elapsed_time=time.time() - self.start_time
        ):
            # Skip to synthesis
            console.print(f"\n[{SECONDARY}]━━━ Stage 3: Papal Synthesis ━━━[/{SECONDARY}]\n")
            synthesis = await self._stage3_synthesis(
                query=query,
                proposals=proposals,
                critiques=[],
                bishop_weights=bishop_weights,
                analysis=analysis
            )

            return DebateResult(
                query=query,
                analysis=analysis,
                proposals=proposals,
                critiques=[],
                synthesis=synthesis,
                total_tokens=tokens_used + synthesis.tokens,
                duration=time.time() - self.start_time,
                bishop_weights=bishop_weights
            )

        # ═══════════════════════════════════════════════════
        # STAGE 2: ADVERSARIAL CRITIQUES
        # ═══════════════════════════════════════════════════
        if strategy.max_rounds >= 3:
            console.print(f"\n[{ACCENT}]━━━ Stage 2: Adversarial Critiques ━━━[/{ACCENT}]\n")

            critiques = await self._stage2_critiques(
                proposals=proposals,
                critics=participating_bishops,
                bishop_weights=bishop_weights,
                analysis=analysis
            )

            tokens_used += sum(c.tokens for c in critiques)
        else:
            critiques = []

        # ═══════════════════════════════════════════════════
        # STAGE 3: PAPAL SYNTHESIS
        # ═══════════════════════════════════════════════════
        console.print(f"\n[{SECONDARY}]━━━ Stage 3: Papal Synthesis ━━━[/{SECONDARY}]\n")

        synthesis = await self._stage3_synthesis(
            query=query,
            proposals=proposals,
            critiques=critiques,
            bishop_weights=bishop_weights,
            analysis=analysis
        )

        tokens_used += synthesis.tokens

        # ═══════════════════════════════════════════════════
        # STAGE 4: CHALLENGE (OPTIONAL)
        # ═══════════════════════════════════════════════════
        if strategy.max_rounds >= 5 and random.random() < 0.3:
            console.print(f"\n[{GOLD}]━━━ Stage 4: Devil's Advocate Challenge ━━━[/{GOLD}]\n")
            # TODO: Implement challenge round
            pass

        # ═══════════════════════════════════════════════════
        # FINALIZE
        # ═══════════════════════════════════════════════════
        result = DebateResult(
            query=query,
            analysis=analysis,
            proposals=proposals,
            critiques=critiques,
            synthesis=synthesis,
            total_tokens=tokens_used,
            duration=time.time() - self.start_time,
            bishop_weights=bishop_weights
        )

        return result

    async def _stage1_proposals(
        self,
        query: str,
        bishops: List[str],
        context_files: Optional[List[str]],
        context_content: Optional[str],
        analysis: QueryAnalysis
    ) -> List[Proposal]:
        """Stage 1: Collect proposals from bishops (pope observes silently)"""

        # Build proposal prompt
        proposal_prompt = self._build_proposal_prompt(query, context_files, context_content, analysis)

        console.print(f"[{CYAN}]💭 Bishops are now deliberating...[/{CYAN}]\n")

        # Query all bishops in parallel with REAL-TIME updates
        import asyncio
        from .openrouter import query_model

        messages = [{"role": "user", "content": proposal_prompt}]

        # Create tasks for all bishops
        bishop_tasks = [
            (bishop, asyncio.create_task(query_model(bishop, messages)))
            for bishop in bishops
        ]

        proposals = []

        # Process bishops as they complete (real-time streaming!)
        pending = {task: bishop for bishop, task in bishop_tasks}

        while pending:
            done, _ = await asyncio.wait(pending.keys(), return_when=asyncio.FIRST_COMPLETED)

            for task in done:
                bishop = pending.pop(task)
                response = await task

                if response:
                    proposals.append(Proposal(
                        bishop_id=bishop,
                        content=response.get("content", ""),
                        tokens=len(response.get("content", "").split()) * 1.3  # Rough token estimate
                    ))
                    # Show checkmark IN REAL-TIME as each bishop completes
                    console.print(f"  [{GREEN}]✓[/{GREEN}] {self._format_bishop_name(bishop)} has spoken")

        console.print()
        return proposals

    async def _stage2_critiques(
        self,
        proposals: List[Proposal],
        critics: List[str],
        bishop_weights: Dict[str, float],
        analysis: QueryAnalysis = None
    ) -> List[Critique]:
        """Stage 2: Bishops critique each other's proposals with smart pairing (all in parallel)"""

        # DYNAMIC CRITIQUE ALLOCATION based on complexity
        complexity_critic_count = {
            "trivial": 1,
            "simple": 2,
            "moderate": 3,
            "complex": 4,
            "expert": 5
        }
        max_critics = complexity_critic_count.get(analysis.complexity if analysis else "moderate", 3)

        # Select top N critics by weight (dynamically allocated)
        sorted_critics = sorted(critics, key=lambda b: bishop_weights[b], reverse=True)
        top_critics = sorted_critics[:min(max_critics, len(sorted_critics))]

        console.print(f"[dim]Critique allocation: {len(top_critics)} critics for {analysis.complexity if analysis else 'moderate'} complexity[/dim]")
        console.print(f"[dim]Top critics: {', '.join(self._format_bishop_name(c) for c in top_critics)}[/dim]\n")
        console.print(f"[{ACCENT}]💬 Critics are now reviewing proposals with smart pairing...[/{ACCENT}]\n")

        # SMART CRITIC-TARGET PAIRING
        critique_pairs = self._match_critics_to_targets(
            critics=top_critics,
            proposals=proposals,
            bishop_weights=bishop_weights,
            analysis=analysis
        )

        console.print(f"[dim]Generated {len(critique_pairs)} strategic critique pairings[/dim]\n")

        # Create all critique tasks in parallel
        import asyncio
        from .openrouter import query_model

        critique_tasks = []
        for critic, target_id, rationale in critique_pairs:
            # Find proposal
            proposal = next((p for p in proposals if p.bishop_id == target_id), None)
            if not proposal:
                continue

            critique_prompt = self._build_critique_prompt(proposal, proposals)
            messages = [{"role": "user", "content": critique_prompt}]

            # Create task and store metadata
            task = asyncio.create_task(query_model(critic, messages))
            critique_tasks.append((critic, target_id, task))

        critiques = []

        # Process critiques as they complete (real-time streaming!)
        pending = {task: (critic, target_id) for critic, target_id, task in critique_tasks}

        while pending:
            done, _ = await asyncio.wait(pending.keys(), return_when=asyncio.FIRST_COMPLETED)

            for task in done:
                critic, target_id = pending.pop(task)
                response = await task

                if response:
                    # Detect severity
                    content = response.get("content", "")
                    severity = self._detect_severity(content)

                    critiques.append(Critique(
                        critic_id=critic,
                        target_id=target_id,
                        content=content,
                        severity=severity,
                        tokens=response.get("tokens", 0)
                    ))

                    # Show real-time progress
                    severity_icon = {"critical": "🔴", "moderate": "🟡", "minor": "🟢"}[severity]
                    console.print(
                        f"  {severity_icon} {self._format_bishop_name(critic)} → "
                        f"{self._format_bishop_name(target_id)}: {severity}"
                    )

        console.print()
        return critiques

    def _match_critics_to_targets(
        self,
        critics: List[str],
        proposals: List[Proposal],
        bishop_weights: Dict[str, float],
        analysis: QueryAnalysis
    ) -> List[tuple]:
        """
        Smart critic-target pairing based on expertise weights.
        Returns list of (critic, target_id, rationale) tuples.

        Strategy: Each proposal gets reviewed by top critics (excluding self).
        """
        pairs = []

        # For small number of proposals (<=3), use exhaustive review
        if len(proposals) <= 3:
            for critic in critics:
                for proposal in proposals:
                    if proposal.bishop_id != critic:
                        pairs.append((critic, proposal.bishop_id, "exhaustive"))
            return pairs

        # For larger debates, each proposal gets top 2-3 critics
        for proposal in proposals:
            # Get critics sorted by weight (excluding proposal author)
            available_critics = [
                (c, bishop_weights.get(c, 0.5))
                for c in critics
                if c != proposal.bishop_id
            ]
            available_critics.sort(key=lambda x: x[1], reverse=True)

            # Select top 2-3 critics for this proposal
            top_critics = available_critics[:min(3, len(available_critics))]

            for critic, weight in top_critics:
                pairs.append((critic, proposal.bishop_id, f"expert (weight: {weight:.2f})"))

        return pairs

    async def _stage3_synthesis(
        self,
        query: str,
        proposals: List[Proposal],
        critiques: List[Critique],
        bishop_weights: Dict[str, float],
        analysis: QueryAnalysis
    ) -> Synthesis:
        """Stage 3: Pope synthesizes hybrid solution"""

        synthesis_prompt = self._build_synthesis_prompt(
            query=query,
            proposals=proposals,
            critiques=critiques,
            bishop_weights=bishop_weights,
            analysis=analysis
        )

        console.print(f"[dim]Pope synthesizing hybrid solution...[/dim]\n")

        messages = [{"role": "user", "content": synthesis_prompt}]
        response = await query_model(
            model=self.pope,
            messages=messages
        )

        if response:
            content = response.get("content", "")

            # Parse attribution and rejections (simple heuristic)
            attribution = self._parse_attribution(content, proposals)
            rejections = self._parse_rejections(content, proposals)

            return Synthesis(
                model_id=self.pope,
                content=content,
                attribution=attribution,
                rejections=rejections,
                tokens=response.get("tokens", 0)
            )

        # Fallback
        return Synthesis(
            model_id=self.pope,
            content="Error: Could not generate synthesis",
            attribution={},
            rejections={},
            tokens=0
        )

    def _build_proposal_prompt(
        self,
        query: str,
        context_files: Optional[List[str]],
        context_content: Optional[str],
        analysis: QueryAnalysis
    ) -> str:
        """Build prompt for bishop proposals"""

        context_section = ""
        if context_content:
            # CLI provides pre-read content
            context_section = f"\n\nFILE CONTEXT PROVIDED:\n```\n{context_content}\n```\n"
        elif context_files:
            context_section = f"\n\nCONTEXT FILES PROVIDED:\n{len(context_files)} files available\n"

        return f"""
You are a bishop in the Synod council, an expert coding assistant.

USER QUERY:
{query}
{context_section}
COMPLEXITY: {analysis.complexity}
DOMAINS: {', '.join([analysis.primary_domain] + analysis.secondary_domains)}

YOUR TASK:
Provide a concise, practical solution to this coding problem.

GUIDELINES:
- Focus on {analysis.primary_domain} best practices
- Be specific and actionable
- Include code if applicable
- Mention potential edge cases
- Keep response under 2000 tokens

The Pope will review all proposals and synthesize the best solution.
"""

    def _build_critique_prompt(self, proposal: Proposal, all_proposals: List[Proposal]) -> str:
        """Build prompt for RIGOROUS, evidence-based critique"""

        target_name = self._format_bishop_name(proposal.bishop_id)

        # Include other bishops' names for context
        other_bishops = [self._format_bishop_name(p.bishop_id) for p in all_proposals if p.bishop_id != proposal.bishop_id]

        return f"""
You are a bishop in the Synod council - an expert code reviewer.

You are reviewing Bishop {target_name}'s proposal.

Other bishops in debate: {', '.join(other_bishops)}

═══════════════════════════════════════════════
PROPOSAL FROM {target_name.upper()}:
═══════════════════════════════════════════════
{proposal.content}

YOUR TASK: RIGOROUS EVIDENCE-BASED CRITIQUE

This is NOT a generic code review. This is a SUBSTANTIVE peer review by an expert.

REQUIREMENTS:
1. **ACTUALLY READ THE PROPOSAL** - Quote specific parts you're critiquing
2. **PROVIDE EVIDENCE** - Don't say "this is bad", explain WHY it's bad
3. **BE SPECIFIC** - Reference line numbers, function names, or specific approaches
4. **USE YOUR EXPERTISE** - Apply domain knowledge (security, performance, architecture)
5. **BE CONSTRUCTIVE** - If you find an issue, suggest a fix

EXAMPLES OF GOOD CRITIQUES:
❌ BAD: "{target_name}'s code is inefficient"
✅ GOOD: "{target_name}'s use of nested loops (O(n²)) will cause performance issues for large datasets. Consider using a hash map for O(n) lookup instead."

❌ BAD: "This has a security vulnerability"
✅ GOOD: "{target_name}'s SQL query uses string concatenation on line 5, which is vulnerable to SQL injection. Use parameterized queries: `cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))`"

❌ BAD: "I don't like this approach"
✅ GOOD: "{target_name}'s approach will fail when the input is null. Add validation: `if (!input) throw new Error('Input required')`"

PRIORITY ISSUES:
🔴 CRITICAL: Security holes, bugs, incorrect logic
🟡 MODERATE: Performance problems, missing edge cases, poor error handling
🟢 MINOR: Code style, readability improvements

**IMPORTANT**: If {target_name}'s proposal is solid, SAY SO! Don't invent problems.

Reference {target_name} by name. Keep under 800 tokens.
"""

    def _build_synthesis_prompt(
        self,
        query: str,
        proposals: List[Proposal],
        critiques: List[Critique],
        bishop_weights: Dict[str, float],
        analysis: QueryAnalysis
    ) -> str:
        """Build prompt for pope's synthesis"""

        # Format proposals
        proposals_text = ""
        for i, p in enumerate(proposals, 1):
            name = self._format_bishop_name(p.bishop_id)
            weight = bishop_weights.get(p.bishop_id, 1.0)
            proposals_text += f"\n{'='*60}\nBISHOP {i}: {name} (Expertise weight: {weight:.2f})\n{'='*60}\n{p.content}\n"

        # Format critiques
        critiques_text = ""
        if critiques:
            for c in critiques:
                critic_name = self._format_bishop_name(c.critic_id)
                target_name = self._format_bishop_name(c.target_id)
                critiques_text += f"\n{critic_name} → {target_name} [{c.severity.upper()}]:\n{c.content}\n"

        # Detect if this is a high consensus case
        consensus_note = ""
        if not critiques:
            consensus_note = "\n⚠️ **HIGH CONSENSUS DETECTED** - Bishops largely agree. YOUR VETO POWER: Even with consensus, you MUST verify correctness. If all bishops missed something fundamental, you must catch it!\n"

        return f"""
You are the Pope of the Synod council with FINAL AUTHORITY and VETO POWER.

You have OBSERVED the complete debate WITHOUT participating, remaining SILENT during Stages 1 & 2.

Now, as the unbiased arbiter with supreme authority, you must verify and synthesize.

ORIGINAL QUERY:
{query}

COMPLEXITY: {analysis.complexity}
DOMAINS: {', '.join([analysis.primary_domain] + analysis.secondary_domains)}
{consensus_note}
═══════════════════════════════════════════════
STAGE 1: PROPOSALS YOU OBSERVED
═══════════════════════════════════════════════
{proposals_text}

═══════════════════════════════════════════════
STAGE 2: CRITIQUES YOU OBSERVED
═══════════════════════════════════════════════
{"CRITIQUES RECEIVED:" + critiques_text if critiques else "No critiques were made (bishops reached consensus)"}

BISHOP EXPERTISE WEIGHTS:
{chr(10).join(f"  - {self._format_bishop_name(b)}: {w:.2f}" for b, w in sorted(bishop_weights.items(), key=lambda x: x[1], reverse=True))}

YOUR PAPAL AUTHORITY:
You have FINAL SAY. Even if all bishops agree, you can VETO if you detect:
- Fundamental errors they ALL missed
- Security vulnerabilities overlooked
- Edge cases no one considered
- Better approaches they didn't think of

SYNTHESIS PROCESS:
1. **VERIFY CORRECTNESS FIRST** - Are the proposals actually correct?
2. Identify BEST elements from each bishop (weighted by expertise)
3. Address ALL critical issues from critiques
4. **USE YOUR VETO** if needed - Don't rubber-stamp bad consensus
5. Synthesize a superior hybrid solution
6. Explain your reasoning clearly

OUTPUT FORMAT:

## Verification
[Did you find any fundamental issues the bishops missed? Any concerns with the consensus?]

## Synthesis Process
[What you took from whom, critiques addressed, elements rejected, improvements made]

## Final Solution
[The authoritative hybrid solution]

## Attribution
- Element X from Bishop [name]
- Element Y from Bishop [name]
- Addressed [critic]'s concern about [issue]
- [If vetoed consensus] Corrected group-think error: [explanation]

Remember: You have VETO POWER. Consensus ≠ Correctness. Catch what they missed.
"""

    def _select_top_bishops(self, weights: Dict[str, float], count: int) -> List[str]:
        """Select top N bishops by weight"""
        sorted_bishops = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        return [b for b, w in sorted_bishops[:count]]

    def _format_bishop_name(self, bishop_id: str) -> str:
        """Format bishop ID for clean, user-friendly display"""
        from .theme import format_model_name
        return format_model_name(bishop_id)

    def _detect_severity(self, critique: str) -> str:
        """Detect critique severity from content"""
        critique_lower = critique.lower()

        critical_keywords = ["security", "vulnerability", "exploit", "bug", "crash", "error", "incorrect", "wrong"]
        moderate_keywords = ["performance", "inefficient", "slow", "missing", "edge case"]

        if any(kw in critique_lower for kw in critical_keywords):
            return "critical"
        elif any(kw in critique_lower for kw in moderate_keywords):
            return "moderate"
        else:
            return "minor"

    def _parse_attribution(self, synthesis: str, proposals: List[Proposal]) -> Dict[str, List[str]]:
        """Parse attribution from synthesis text (simple heuristic)"""
        attribution = {}
        for proposal in proposals:
            bishop_name = self._format_bishop_name(proposal.bishop_id)
            if bishop_name.lower() in synthesis.lower():
                attribution[proposal.bishop_id] = ["mentioned in synthesis"]
        return attribution

    def _parse_rejections(self, synthesis: str, proposals: List[Proposal]) -> Dict[str, str]:
        """Parse rejections from synthesis text"""
        rejections = {}
        # Look for "rejected" mentions
        synthesis_lower = synthesis.lower()
        if "reject" in synthesis_lower:
            for proposal in proposals:
                bishop_name = self._format_bishop_name(proposal.bishop_id)
                if f"reject" in synthesis_lower and bishop_name.lower() in synthesis_lower:
                    rejections[proposal.bishop_id] = "mentioned in rejections"
        return rejections

    def _display_weights(self, weights: Dict[str, float]) -> None:
        """Display bishop weights in a formatted panel with explanation"""
        from rich.text import Text
        from rich.panel import Panel

        # Build the content
        content = Text()

        # Add explanation
        content.append("Each bishop has been weighted based on their expertise for this query.\n", style="dim")
        content.append("Higher weights = stronger expertise in relevant domains.\n\n", style="dim")

        # Sort bishops by weight (highest first)
        sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)

        # Display each bishop with colored bar
        for bishop, weight in sorted_weights:
            name = self._format_bishop_name(bishop)

            # Color bar based on weight strength
            if weight >= 1.0:
                bar_color = GREEN  # Excellent expertise
            elif weight >= 0.8:
                bar_color = CYAN   # Good expertise
            elif weight >= 0.6:
                bar_color = GOLD   # Moderate expertise
            else:
                bar_color = "dim"  # Lower expertise

            # Create visual bar (scaled to 25 chars max)
            bar_length = int(weight * 25)
            bar = "█" * bar_length

            # Format the line
            content.append(f"  {name:<25} ", style="white")
            content.append(f"{bar:<25}", style=bar_color)
            content.append(f" {weight:.2f}\n", style="dim")

        # Display in a panel
        panel = Panel(
            content,
            title=f"[{CYAN}]🎯 Bishop Expertise Matching[/{CYAN}]",
            border_style=CYAN,
            padding=(0, 1),
        )
        console.print(panel)
