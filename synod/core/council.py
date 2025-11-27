"""3-stage LLM Council orchestration with intelligent debate system.

This module provides a compatibility layer between the old council API
and the new intelligent debate system (classifier, expertise, adaptive rounds).
"""

import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from .classifier import show_rejection
from .debate import SynodDebate
from .settings import BISHOP_MODELS, POPE_MODEL

if TYPE_CHECKING:
    from .live_display import LiveDebateDisplay


# Instruction to ensure code blocks always have language specified
CODE_FORMAT_INSTRUCTION = """
When including code in your response, ALWAYS use markdown code blocks with the language specified.
For example: ```python, ```javascript, ```typescript, ```go, ```rust, ```java, etc.
Never use plain ``` without a language identifier."""


async def run_full_council(user_query: str, file_context: str = "") -> Tuple[List, List, Dict]:
    """
    Run the complete intelligent debate process with Stage 0 classification.

    This is the main entry point called by the CLI. It uses the new intelligent
    debate system under the hood but maintains backward compatibility by returning
    results in the old format.

    Args:
        user_query: The user's question or coding problem.
        file_context: Relevant code/file content provided.

    Returns:
        Tuple of (stage1_results, dissents, final_solution) in old format for CLI compatibility.
        If query is rejected (non-coding), returns empty lists and error dict.
    """
    # Parse file context if provided
    context_files = []
    if file_context:
        # file_context is already a string, we'll pass it directly
        # The debate system expects Optional[List[str]] for file paths
        # But since CLI provides pre-read content, we'll handle this in debate.py
        pass

    # Create debate orchestrator with configured models
    debate = SynodDebate(
        bishops=BISHOP_MODELS,
        pope=POPE_MODEL
    )

    # Run the intelligent debate
    result = await debate.run_debate(
        query=user_query,
        context_files=None,  # CLI provides pre-read content
        context_content=file_context if file_context else None
    )

    # If query was rejected (non-coding), return error
    if result is None:
        # Rejection message already shown by debate.run_debate()
        return [], [], {
            "model": "error",
            "response": "Query rejected: Not coding-related. Please ask a programming question."
        }

    # Convert new format to old format for backward compatibility with CLI

    # Stage 1 results: Convert Proposal objects to old dict format
    stage1_results = [
        {
            "model": proposal.bishop_id,
            "solution": proposal.content
        }
        for proposal in result.proposals
    ]

    # Stage 2 results: Convert Critique objects to old dict format
    dissents = [
        {
            "reviewer_model": critique.critic_id,
            "target_model": critique.target_id,
            "critique": critique.content
        }
        for critique in result.critiques
    ]

    # Stage 3 result: Convert Synthesis to old dict format
    final_solution = {
        "model": result.synthesis.model_id,
        "response": result.synthesis.content
    }

    return stage1_results, dissents, final_solution


async def run_full_council_with_display(
    user_query: str,
    file_context: str = "",
    live_display: Optional["LiveDebateDisplay"] = None
) -> Tuple[List, List, Dict]:
    """
    Run the complete debate process with real-time streaming to a live display.

    This version supports streaming each Bishop's and the Pope's responses
    in real-time to a LiveDebateDisplay for better UX.

    Args:
        user_query: The user's question or coding problem.
        file_context: Relevant code/file content provided.
        live_display: Optional LiveDebateDisplay instance for real-time updates.

    Returns:
        Tuple of (stage1_results, dissents, final_solution) in old format for CLI compatibility.
        If query is rejected (non-coding), returns empty lists and error dict.
    """
    import time

    from rich.box import ROUNDED
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text

    from .classifier import analyze_query, show_rejection
    from .expertise import (calculate_bishop_weights,
                            initialize_bishop_expertise, select_top_bishops)
    from .providers import query_model_stream_auto
    from .theme import (ACCENT, CYAN, GOLD, GREEN, PRIMARY, SECONDARY,
                        format_model_name)

    console = Console()

    # Track timing for each stage
    debate_start = time.time()
    stage_times = {}

    # STAGE 0: Classification and Analysis - All in one live panel
    stage0_start = time.time()

    from rich.live import Live
    from rich.console import Group

    # Spinner frames for animation
    spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    spinner_index = [0]  # Use list to allow mutation in nested function

    # State for Stage 0 panel
    stage0_state = {
        "phase": "analyzing",  # analyzing -> selecting -> complete
        "analysis": None,
        "domains": None,
        "active_bishops": None,
        "all_weights": None,
        "recommended_count": None,
        "recommended_rounds": None,
        "not_selected": None
    }

    # Smooth cursor animation for Pope observer (typing indicator style)
    cursor_frames = ["●", "●", "●", "◐", "◐", "◐", "◑", "◑", "◑", "○", "○", "○"]

    def build_stage0_panel():
        """Build the Stage 0 panel with current state."""
        lines = [Text("🔍 Analyzing query complexity and selecting optimal bishops...", style=CYAN)]
        lines.append(Text(""))

        if stage0_state["phase"] == "analyzing":
            # Still analyzing
            spinner = spinner_frames[spinner_index[0] % len(spinner_frames)]
            lines.append(Text(f"{spinner} Analyzing query...", style=CYAN))
        else:
            # Analysis complete - show results
            lines.append(Text("✓ Analysis complete", style=GREEN))
            lines.append(Text(""))

            analysis = stage0_state["analysis"]
            domains = stage0_state["domains"]
            active_bishops = stage0_state["active_bishops"]
            all_weights = stage0_state["all_weights"]
            recommended_count = stage0_state["recommended_count"]
            recommended_rounds = stage0_state["recommended_rounds"]

            # Query Analysis section with highlighted values
            complexity_line = Text()
            complexity_line.append("Complexity: ", style="dim")
            complexity_line.append(f"{analysis.complexity.upper()}", style=f"bold {GOLD}")
            lines.append(complexity_line)

            domains_line = Text()
            domains_line.append("Domains: ", style="dim")
            domains_line.append(f"{', '.join(domains)}", style=CYAN)
            lines.append(domains_line)

            strategy_line = Text()
            strategy_line.append("Strategy: ", style="dim")
            strategy_line.append(f"{len(active_bishops)} bishops", style=f"bold {PRIMARY}")
            strategy_line.append(", ", style="dim")
            strategy_line.append(f"{recommended_rounds} rounds", style=f"bold {PRIMARY}")
            lines.append(strategy_line)
            lines.append(Text(""))

            # Selected bishops section
            lines.append(Text(f"🎓 Selected {len(active_bishops)} Bishops by Expertise:", style=GOLD))
            for bishop in active_bishops:
                weight = all_weights[bishop]
                bishop_line = Text()
                bishop_line.append("  ✓ ", style=GREEN)
                bishop_line.append(f"{format_model_name(bishop)}", style="white")
                bishop_line.append(": ", style="dim")
                bishop_line.append(f"{weight:.2f}x", style=f"bold {GOLD}")
                bishop_line.append(" weight", style="dim")
                lines.append(bishop_line)

            # Not selected bishops (dimmed)
            not_selected = stage0_state["not_selected"]
            if not_selected:
                lines.append(Text(""))
                lines.append(Text("Other bishops:", style="dim"))
                for bishop in not_selected:
                    weight = all_weights[bishop]
                    lines.append(Text(f"    {format_model_name(bishop)}: {weight:.2f}x (not selected)", style="dim"))

        content = Group(*lines)
        return Panel(
            content,
            border_style=CYAN,
            title="Stage 0: Analysis",
            padding=(0, 2)
        )

    console.print()

    async def run_stage0_with_display():
        """Run Stage 0 analysis with live updating panel."""
        import asyncio

        # Start analysis task
        analysis_task = asyncio.create_task(analyze_query(user_query, file_context))

        with Live(build_stage0_panel(), console=console, refresh_per_second=10) as live:
            # Poll until analysis completes
            while not analysis_task.done():
                spinner_index[0] += 1
                live.update(build_stage0_panel())
                await asyncio.sleep(0.1)

            # Get analysis result
            analysis = await analysis_task

            if not analysis.is_coding_related:
                # Update state to show rejection
                stage0_state["phase"] = "complete"
                stage0_state["analysis"] = analysis
                live.update(build_stage0_panel())
                return analysis, None, None

            # Calculate bishop weights based on query domains
            initialize_bishop_expertise(BISHOP_MODELS)
            domains = [analysis.primary_domain] + analysis.secondary_domains

            # INTELLIGENT BISHOP SELECTION
            recommended_count = analysis.debate_strategy.get('recommended_bishops', 3)
            recommended_rounds = analysis.debate_strategy.get('recommended_rounds', 3)
            active_bishops, all_weights = select_top_bishops(
                query_domains=domains,
                all_bishops=BISHOP_MODELS,
                pope_model=POPE_MODEL,
                recommended_count=recommended_count
            )

            not_selected = [b for b in BISHOP_MODELS if b not in active_bishops and b != POPE_MODEL]

            # Update state with all results
            stage0_state["phase"] = "complete"
            stage0_state["analysis"] = analysis
            stage0_state["domains"] = domains
            stage0_state["active_bishops"] = active_bishops
            stage0_state["all_weights"] = all_weights
            stage0_state["recommended_count"] = recommended_count
            stage0_state["recommended_rounds"] = recommended_rounds
            stage0_state["not_selected"] = not_selected

            # Final update
            live.update(build_stage0_panel())

            return analysis, active_bishops, all_weights

    analysis, active_bishops, all_weights = await run_stage0_with_display()

    stage_times['stage0'] = time.time() - stage0_start

    if not analysis.is_coding_related:
        # Rejected - not a coding query
        show_rejection(analysis.rejection_reason)
        return [], [], {
            "model": "error",
            "response": f"Query rejected: {analysis.rejection_reason}"
        }

    # Get domains for later use
    domains = [analysis.primary_domain] + analysis.secondary_domains

    console.print()

    # Start timing Stage 1
    stage1_start = time.time()

    # Prepare full context (simple version for streaming)
    full_context = user_query
    if file_context:
        full_context = f"Context:\n```\n{file_context}\n```\n\nQuestion: {user_query}"

    # Stage 1: Propose solutions with streaming (IN PARALLEL) + Consensus Analysis
    # IMPORTANT: Pope is UNBIASED - exclude from Stage 1 debate (observes only)
    # active_bishops already contains only the selected bishops (Pope excluded by select_top_bishops)

    stage1_results = []
    proposals = []

    from .debate import DebateStrategy, Proposal

    # Create a table to show streaming bishops with animated spinners
    bishop_status = {b: {"complete": False, "failed": False, "response": "", "error": None} for b in active_bishops}

    # State for the combined Stage 1 panel (proposals + consensus)
    stage1_state = {
        "phase": "proposing",  # proposing -> consensus -> complete
        "consensus_score": None
    }

    def build_stage1_panel():
        """Build the Stage 1 panel with proposals and consensus analysis."""
        pope_name = format_model_name(POPE_MODEL)
        cursor = cursor_frames[spinner_index[0] % len(cursor_frames)]

        lines = [Text(f"🎬 {len(active_bishops)} bishops will debate in parallel!", style=f"bold {PRIMARY}")]

        # Pope observer line - subtle gray with smooth animation
        pope_line = Text()
        pope_line.append("👑 ", style="dim")
        pope_line.append("Pope ", style="grey50")
        pope_line.append(f"{pope_name}", style="grey70")
        pope_line.append(" is observing ", style="grey50")
        pope_line.append(f"{cursor}", style="grey62")
        lines.append(pope_line)
        lines.append(Text(""))  # Empty line

        # Bishop proposal status
        for bishop in active_bishops:
            status = bishop_status[bishop]
            name = format_model_name(bishop)

            if status["complete"] and not status["failed"]:
                # Success - green checkmark with white name
                line = Text()
                line.append("✓ ", style=GREEN)
                line.append(f"{name}", style="white")
                line.append(" complete", style=GREEN)
                lines.append(line)
            elif status["failed"]:
                # Failed - red X with error
                error_msg = f" - {status['error']}" if status["error"] else ""
                lines.append(Text(f"✗ {name}{error_msg}", style="dim red"))
            else:
                # In progress - spinning
                spinner = spinner_frames[spinner_index[0] % len(spinner_frames)]
                line = Text()
                line.append(f"{spinner} ", style=CYAN)
                line.append(f"{name}", style="white")
                line.append(" proposing...", style=CYAN)
                lines.append(line)

        # Consensus analysis section (shown after proposals complete)
        if stage1_state["phase"] in ["consensus", "complete"]:
            lines.append(Text(""))  # Separator
            lines.append(Text("🔍 Analyzing bishop proposals for consensus...", style=CYAN))

            if stage1_state["phase"] == "consensus":
                # Still measuring consensus
                spinner = spinner_frames[spinner_index[0] % len(spinner_frames)]
                lines.append(Text(f"{spinner} Measuring semantic consensus...", style=CYAN))
            else:
                # Consensus complete
                lines.append(Text("✓ Consensus measured", style=GREEN))
                lines.append(Text(""))

                score = stage1_state["consensus_score"]
                if score >= 0.90:
                    consensus_line = Text()
                    consensus_line.append("✅ Exceptional Consensus ", style=f"bold {GREEN}")
                    consensus_line.append(f"({score:.1%})", style="white")
                    lines.append(consensus_line)
                    lines.append(Text("Bishops strongly agree - reviews will verify.", style="dim"))
                elif score > 0.75:
                    consensus_line = Text()
                    consensus_line.append("✓ High Consensus ", style=f"bold {CYAN}")
                    consensus_line.append(f"({score:.1%})", style="white")
                    lines.append(consensus_line)
                    lines.append(Text("Good alignment - reviews will catch blind spots.", style="dim"))
                elif score > 0.5:
                    consensus_line = Text()
                    consensus_line.append("⚠️  Moderate Consensus ", style=f"bold {GOLD}")
                    consensus_line.append(f"({score:.1%})", style="white")
                    lines.append(consensus_line)
                    lines.append(Text("Some disagreement - reviews will identify best approach.", style="dim"))
                else:
                    consensus_line = Text()
                    consensus_line.append("❌ Low Consensus ", style=f"bold {ACCENT}")
                    consensus_line.append(f"({score:.1%})", style="white")
                    lines.append(consensus_line)
                    lines.append(Text("Significant divergence - reviews critical!", style=ACCENT))

        content = Group(*lines)
        return Panel(
            content,
            border_style=PRIMARY,
            title="Stage 1: Bishop Proposals",
            padding=(0, 2)
        )

    # Create callback for each bishop (with closure to capture the correct bishop)
    def make_callback(b):
        def callback(chunk):
            # Chunks are accumulated silently for streaming
            bishop_status[b]["response"] += chunk
        return callback

    # Create tasks for all bishops to run IN PARALLEL
    async def query_bishop(bishop):
        try:
            response = await query_model_stream_auto(
                model=bishop,
                messages=[
                    {"role": "system", "content": f"You are an expert software engineer participating in a technical debate.{CODE_FORMAT_INSTRUCTION}"},
                    {"role": "user", "content": full_context}
                ],
                chunk_callback=make_callback(bishop),
                silent=True  # Silent to avoid duplicate output
            )

            if response:
                bishop_status[bishop]["complete"] = True
                bishop_status[bishop]["failed"] = False
                return {
                    "model": bishop,
                    "solution": response
                }
            else:
                # No response received - mark as failed
                bishop_status[bishop]["complete"] = True
                bishop_status[bishop]["failed"] = True
                bishop_status[bishop]["error"] = "no response"
                return None
        except Exception as e:
            # Error occurred - mark as failed
            bishop_status[bishop]["complete"] = True
            bishop_status[bishop]["failed"] = True
            bishop_status[bishop]["error"] = str(e)[:40]
            return None

    # Show progress with animated spinners inside a panel using Live display
    console.print()

    async def run_stage1_with_consensus():
        """Run bishop queries and consensus analysis with live updating panel."""
        import asyncio

        # Start all bishop queries
        query_tasks = [asyncio.create_task(query_bishop(bishop)) for bishop in active_bishops]

        with Live(build_stage1_panel(), console=console, refresh_per_second=10) as live:
            # Phase 1: Wait for all proposals to complete
            while not all(task.done() for task in query_tasks):
                spinner_index[0] += 1
                live.update(build_stage1_panel())
                await asyncio.sleep(0.1)

            # Gather proposal results
            responses = await asyncio.gather(*query_tasks)

            # Collect valid responses
            for response in responses:
                if response:
                    stage1_results.append(response)
                    proposals.append({
                        "bishop_id": response["model"],
                        "content": response["solution"]
                    })

            # Convert proposals to Proposal objects for consensus analysis
            proposal_objects = [
                Proposal(
                    bishop_id=p["bishop_id"],
                    content=p["content"],
                    tokens=len(p["content"].split())
                )
                for p in proposals
            ]

            # Phase 2: Measure consensus AND pairwise similarity IN PARALLEL
            # This saves ~10-15 seconds by running both classifier calls concurrently
            stage1_state["phase"] = "consensus"
            live.update(build_stage1_panel())

            debate_strategy = DebateStrategy(analysis=analysis, token_budget=100000)

            # Run BOTH in parallel - they're independent and both use the classifier
            consensus_task = asyncio.create_task(debate_strategy._measure_consensus(proposal_objects))
            pairwise_task = asyncio.create_task(debate_strategy.get_pairwise_similarities(proposal_objects))

            while not (consensus_task.done() and pairwise_task.done()):
                spinner_index[0] += 1
                live.update(build_stage1_panel())
                await asyncio.sleep(0.1)

            # Get results
            consensus_score = await consensus_task
            pairwise_similarities = await pairwise_task

            stage1_state["consensus_score"] = consensus_score
            stage1_state["phase"] = "complete"

            # Final update
            live.update(build_stage1_panel())

            return responses, consensus_score, debate_strategy, proposal_objects, pairwise_similarities

    responses, consensus_score, debate_strategy, proposal_objects, pairwise_similarities = await run_stage1_with_consensus()
    console.print()

    # Record Stage 1 completion time
    stage_times['stage1'] = time.time() - stage1_start

    # Stage 2: Adversarial Critiques with SMART PAIRING (run in parallel, non-streaming for speed)
    # ALWAYS run Stage 2 - the whole point is to get diverse perspectives even when models agree
    # High consensus doesn't mean correct - all models could make the same mistake
    stage2_start = time.time()
    dissents = []

    # 1-TO-ALL CRITIQUE MODEL: Each bishop critiques ALL other proposals in one call
    # This is more efficient: n calls instead of n*(n-1) calls
    # And produces better critiques: critic can compare proposals directly
    from .openrouter import query_model

    # Use Grok Fast for critiques - fast and good at code review
    FAST_CRITIQUE_MODEL = "x-ai/grok-4.1-fast"

    # Explain WHY adversarial debate is needed based on consensus level
    if consensus_score >= 0.75:
        critique_reason = f"Even with {consensus_score:.0%} consensus, adversarial debate catches blind spots."
    elif consensus_score >= 0.50:
        critique_reason = f"With {consensus_score:.0%} consensus, bishops challenge each other to find the best approach."
    else:
        critique_reason = f"With {consensus_score:.0%} consensus, fierce debate needed to resolve divergent approaches."

    # Build list of critics (each bishop critiques all others)
    critics = [p["bishop_id"] for p in proposals]
    num_critics = len(critics)

    # Track status of each critic (status: pending, complete, skipped, failed)
    critique_status = {critic: {"status": "pending", "error": None, "skipped": False} for critic in critics}

    def build_stage2_panel():
        """Build the Stage 2 panel with current state."""
        pope_name = format_model_name(POPE_MODEL)
        cursor = cursor_frames[spinner_index[0] % len(cursor_frames)]

        lines = [Text(f"⚔️ {critique_reason}", style=ACCENT)]

        # Pope observer line - subtle gray with smooth animation
        pope_line = Text()
        pope_line.append("👑 ", style="dim")
        pope_line.append("Pope ", style="grey50")
        pope_line.append(f"{pope_name}", style="grey70")
        pope_line.append(" is observing ", style="grey50")
        pope_line.append(f"{cursor}", style="grey62")
        lines.append(pope_line)
        lines.append(Text(""))

        # Show each critic's status
        for critic in critics:
            status = critique_status[critic]
            critic_name = format_model_name(critic)
            others = [format_model_name(c) for c in critics if c != critic]
            others_str = " vs ".join(others)

            if status["skipped"]:
                # Skipped due to high similarity
                line = Text()
                line.append("⏭ ", style="dim")
                line.append(f"{critic_name}", style="dim")
                line.append(" skipped ", style="dim")
                line.append("(proposals identical)", style="dim")
                lines.append(line)
            elif status["status"] == "complete":
                line = Text()
                line.append("✓ ", style=GREEN)
                line.append(f"{critic_name}", style="white")
                line.append(" challenged ", style=GREEN)
                line.append(f"[{others_str}]", style="dim")
                lines.append(line)
            elif status["status"] == "failed":
                error_msg = f" ({status['error']})" if status["error"] else ""
                lines.append(Text(f"✗ {critic_name}{error_msg}", style="dim red"))
            else:
                spinner = spinner_frames[spinner_index[0] % len(spinner_frames)]
                line = Text()
                line.append(f"{spinner} ", style=ACCENT)
                line.append(f"{critic_name}", style="white")
                line.append(" challenging ", style=ACCENT)
                line.append(f"[{others_str}]", style="dim")
                line.append("...", style=ACCENT)
                lines.append(line)

        # Show summary
        skipped = sum(1 for s in critique_status.values() if s["skipped"])
        completed = sum(1 for s in critique_status.values() if s["status"] == "complete" and not s["skipped"])
        total_done = completed + skipped

        if total_done == num_critics:
            lines.append(Text(""))
            if skipped == num_critics:
                # All skipped
                summary_line = Text()
                summary_line.append("⏭ ", style="dim")
                summary_line.append("All debates skipped ", style="dim")
                summary_line.append("(proposals nearly identical)", style="dim")
                lines.append(summary_line)
            elif skipped > 0:
                # Some skipped
                summary_line = Text()
                summary_line.append("✓ ", style=GREEN)
                summary_line.append(f"{completed}", style=f"bold {GREEN}")
                summary_line.append(" challenged, ", style=GREEN)
                summary_line.append(f"{skipped}", style="dim")
                summary_line.append(" skipped", style="dim")
                lines.append(summary_line)
            else:
                # None skipped
                summary_line = Text()
                summary_line.append("✓ ", style=GREEN)
                summary_line.append(f"{completed}", style=f"bold {GREEN}")
                summary_line.append(" adversarial challenges complete", style=GREEN)
                lines.append(summary_line)

        return Panel(Group(*lines), border_style=ACCENT, title="Stage 2: Adversarial Debate", padding=(0, 2))

    # Check which proposals are too similar to need separate critiques
    # If proposals A and B are 85%+ similar, skip redundant critiques
    # (85% threshold balances avoiding redundant work vs ensuring review coverage)
    similar_pairs = set()
    if pairwise_similarities:
        for (model_a, model_b), similarity in pairwise_similarities.items():
            if similarity >= 0.85:
                similar_pairs.add((model_a, model_b))

    async def generate_critique_for_all(critic_id: str):
        """One bishop critiques ALL other proposals in a single call."""
        # Gather all other proposals (skip if too similar to critic's own)
        other_proposals = []
        for p in proposals:
            if p["bishop_id"] != critic_id:
                # Check if this proposal is 95%+ similar to critic's - if so, skip
                pair1 = (critic_id, p["bishop_id"])
                pair2 = (p["bishop_id"], critic_id)
                if pair1 in similar_pairs or pair2 in similar_pairs:
                    continue  # Skip redundant critique
                model_name = format_model_name(p["bishop_id"])
                other_proposals.append(f"=== {model_name} ===\n{p['content'][:2000]}")

        # If all other proposals are too similar to ours, skip this critique entirely
        if not other_proposals:
            critique_status[critic_id]["status"] = "complete"
            critique_status[critic_id]["skipped"] = True
            return {
                "reviewer_model": critic_id,
                "critique": "[Skipped - proposals too similar to require adversarial review]"
            }

        all_proposals_text = "\n\n".join(other_proposals)

        # ADVERSARIAL critique prompts - designed to extract maximum value
        # Focus on: (1) production failures, (2) what to steal, (3) what's missing
        if consensus_score >= 0.90:
            # High consensus: Hunt for the shared blind spot
            critique_prompt = f"""You are an adversarial code reviewer. The proposals below AGREE ({consensus_score:.0%}).

When all experts agree, they often share the SAME blind spot. Your job: find it.

Query: {user_query}

{all_proposals_text}

Answer these SPECIFIC questions:
1. 🔴 PRODUCTION FAILURE: What input/scenario would make ALL these solutions fail or behave incorrectly?
2. 🔒 SECURITY: Any injection, overflow, or trust boundary issues they all missed?
3. 🎯 MISSING REQUIREMENT: Did they all misunderstand or ignore part of the query?
4. ⚡ PERFORMANCE TRAP: Would this blow up with large inputs? N+1 queries? Memory leaks?

If you find nothing critical, say so - but TRY HARD to break these solutions.
Quote specific code when you find issues."""

        elif consensus_score >= 0.50:
            # Moderate consensus: Pick a winner and steal the best parts
            critique_prompt = f"""You are an adversarial code reviewer in a debate. Consensus is {consensus_score:.0%}.

Query: {user_query}

{all_proposals_text}

Your job is to be DECISIVE. Answer:

1. 🏆 WINNER: Which solution would you ship to production? (Pick ONE)
2. 🔴 FATAL FLAWS: For EACH losing solution, what's the critical issue that disqualifies it?
3. 🎁 STEAL: What's ONE thing from each losing solution that the winner should adopt?
4. 🕳️ BLIND SPOT: What do ALL solutions miss that you'd add?

Be harsh but fair. Quote specific code. No hedging - pick a winner."""

        else:
            # Low consensus: Arbitrate the disagreement
            critique_prompt = f"""You are an adversarial code reviewer. Major disagreement detected ({consensus_score:.0%}).

Query: {user_query}

{all_proposals_text}

The experts DISAGREE. Your job is to figure out WHY and WHO IS RIGHT.

Answer:
1. 🔍 ROOT CAUSE: Why do these solutions differ? (Different interpretation? Different trade-offs? One is just wrong?)
2. 🏆 CORRECT APPROACH: Which fundamental approach is RIGHT for this query? Defend your choice.
3. 🔴 DISQUALIFIED: Which solution(s) are fundamentally flawed? What's the fatal error?
4. 🔀 HYBRID?: Can the best parts be combined, or are the approaches incompatible?
5. 📋 VERDICT: In ONE sentence, what should the final solution do?

Take a strong stance. Quote code to support your arguments."""

        try:
            result = await query_model(
                model=FAST_CRITIQUE_MODEL,
                messages=[
                    {"role": "system", "content": "You are a brutal but fair code reviewer. Your job is to find flaws, pick winners, and be decisive. No wishy-washy answers."},
                    {"role": "user", "content": critique_prompt}
                ],
                silent=True
            )

            if result and result.get('content'):
                critique_status[critic_id]["status"] = "complete"
                return {
                    "reviewer_model": critic_id,
                    "critique": result['content']
                }
            else:
                critique_status[critic_id]["status"] = "failed"
                critique_status[critic_id]["error"] = "no response"
                return None
        except Exception as e:
            critique_status[critic_id]["status"] = "failed"
            critique_status[critic_id]["error"] = str(e)[:30]
            return None

    console.print()

    async def run_critiques_with_display():
        """Run all critique tasks in parallel with live display."""
        # Each bishop critiques all others - just n tasks instead of n*(n-1)
        tasks = [asyncio.create_task(generate_critique_for_all(critic)) for critic in critics]

        with Live(build_stage2_panel(), console=console, refresh_per_second=10) as live:
            while not all(task.done() for task in tasks):
                spinner_index[0] += 1
                live.update(build_stage2_panel())
                await asyncio.sleep(0.1)

            results = await asyncio.gather(*tasks)
            live.update(build_stage2_panel())

        return [c for c in results if c is not None]

    dissents = await run_critiques_with_display()

    # Record Stage 2 completion time
    stage_times['stage2'] = time.time() - stage2_start

    console.print()

    # Stage 3: Pope synthesis with streaming (displayed in cli.py as unified panel)
    stage3_start = time.time()

    # Build synthesis prompt with proposals AND critiques
    proposals_text = "\n\n".join([
        f"**Proposal from {p['bishop_id']}:**\n{p['content']}"
        for p in proposals
    ])

    critiques_text = ""
    if dissents:
        # 1-to-all format: each reviewer critiques all other proposals
        critiques_text = "\n\nAdversarial Reviews:\n" + "\n\n".join([
            f"**Review by {format_model_name(d['reviewer_model'])}:**\n{d['critique']}"
            for d in dissents
        ])

    # Consensus-aware synthesis prompts with active Pope contribution
    # The Pope is the most capable model - it should ADD value, not just merge

    pope_authority = """
You are the POPE - the most capable model in this council. You are NOT just a merger.

Your authority:
- ADD your own improvements where you see gaps
- OVERRIDE bishop proposals if you know a better way
- CORRECT misunderstandings if the bishops got the problem wrong
- CHALLENGE assumptions that all proposals share but are flawed

Produce the BEST solution - even if it differs significantly from all proposals."""

    if consensus_score >= 0.90:
        # High consensus: Proposals agree - but Pope can still improve
        synthesis_prompt = f"""Bishops reached STRONG AGREEMENT ({consensus_score:.0%} consensus).

User Query: {user_query}

All Proposals:
{proposals_text}
{critiques_text}

{pope_authority}

The bishops agree, but that doesn't mean they're complete. Your task:
1. Start with the cleanest implementation
2. Apply valid fixes from reviews
3. ADD anything important they ALL missed
4. If you see a better approach, use it - consensus doesn't mean optimal"""

    elif consensus_score >= 0.50:
        # Moderate consensus: Mix and match + Pope's own ideas
        synthesis_prompt = f"""Bishops reached MODERATE AGREEMENT ({consensus_score:.0%} consensus).

User Query: {user_query}

All Proposals:
{proposals_text}
{critiques_text}

{pope_authority}

The bishops have different ideas. Your task:
1. Cherry-pick the best parts from each proposal
2. Resolve contradictions using your judgment
3. ADD your own improvements - fill gaps none of them covered
4. The final solution should be BETTER than any individual proposal"""

    else:
        # Low consensus: Pope arbitrates AND contributes
        synthesis_prompt = f"""Bishops reached LOW AGREEMENT ({consensus_score:.0%} consensus) - major divergence!

User Query: {user_query}

All Proposals:
{proposals_text}
{critiques_text}

{pope_authority}

The bishops fundamentally disagree. Your task:
1. Analyze WHY they disagree - different interpretations? trade-offs?
2. Determine the CORRECT approach (don't just pick one - reason through it)
3. You may create a HYBRID or entirely NEW solution if that's best
4. Explain your reasoning - why is your solution better?

When experts disagree, the answer often isn't any of their proposals."""

    # Stage 3: Pope synthesis with Live panel (consistent with other stages)
    console.print()
    pope_response = None
    pope_error = None

    # Stage 3: Show spinner while Pope synthesizes, then let cli.py show final panel
    def build_stage3_panel():
        """Build the Stage 3 panel with spinner."""
        pope_name = format_model_name(POPE_MODEL)
        spinner = spinner_frames[spinner_index[0] % len(spinner_frames)]
        lines = [Text(f"{spinner} {pope_name} synthesizing...", style=SECONDARY)]
        return Panel(Group(*lines), border_style=SECONDARY, title="Stage 3: Pope Synthesis", padding=(0, 2))

    async def run_synthesis_with_display():
        """Run Pope synthesis with live updating panel."""
        nonlocal pope_response, pope_error

        # Start synthesis task
        synthesis_task = asyncio.create_task(query_model_stream_auto(
            model=POPE_MODEL,
            messages=[
                {"role": "system", "content": f"You are the lead synthesizer, combining the best ideas from all proposals.{CODE_FORMAT_INSTRUCTION}"},
                {"role": "user", "content": synthesis_prompt}
            ],
            chunk_callback=None,
            silent=True
        ))

        with Live(build_stage3_panel(), console=console, refresh_per_second=10, transient=True) as live:
            # transient=True clears the panel when done - final result shown by cli.py
            while not synthesis_task.done():
                spinner_index[0] += 1
                live.update(build_stage3_panel())
                await asyncio.sleep(0.1)

            try:
                pope_response = await synthesis_task
            except Exception as e:
                pope_error = str(e)

    await run_synthesis_with_display()

    # Record Stage 3 completion time
    stage_times['stage3'] = time.time() - stage3_start
    total_time = time.time() - debate_start

    # Build error message if synthesis failed
    if not pope_response:
        error_msg = "Synthesis failed"
        if pope_error:
            error_msg += f": {pope_error}"

    final_solution = {
        "model": POPE_MODEL,
        "response": pope_response or error_msg,
        "timing": {
            "analysis": stage_times.get('stage0', 0),
            "proposals": stage_times.get('stage1', 0),
            "critiques": stage_times.get('stage2', 0),
            "synthesis": stage_times.get('stage3', 0),
            "total": total_time
        }
    }

    return stage1_results, dissents, final_solution


# Legacy functions for backward compatibility
# These are now deprecated but maintained for any direct imports

async def stage1_propose_solutions(user_query: str, file_context: str = "") -> List[Dict[str, Any]]:
    """
    DEPRECATED: Use run_full_council() instead.

    Legacy function maintained for backward compatibility.
    """
    results, _, _ = await run_full_council(user_query, file_context)
    return results


async def stage2_collect_dissents(
    user_query: str,
    file_context: str,
    stage1_results: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    DEPRECATED: Use run_full_council() instead.

    Legacy function maintained for backward compatibility.
    """
    _, dissents, _ = await run_full_council(user_query, file_context)
    return dissents


async def stage3_synthesize_final(
    user_query: str,
    file_context: str,
    stage1_results: List[Dict[str, Any]],
    dissents: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    DEPRECATED: Use run_full_council() instead.

    Legacy function maintained for backward compatibility.
    """
    _, _, final_solution = await run_full_council(user_query, file_context)
    return final_solution
