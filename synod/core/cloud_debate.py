"""Cloud-based debate client with SSE streaming and Rich display.

This module is the thin client that:
1. Sends queries to Synod Cloud
2. Receives SSE events (including tool calls)
3. Executes tools locally and sends results back
4. Renders them beautifully using Rich

Intelligence (debate) lives in the cloud. Tool execution happens locally.
"""

import asyncio
import json
import time
import os
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, AsyncIterator, Tuple

import httpx
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.markdown import Markdown
from rich import box

from .theme import PRIMARY, CYAN, SECONDARY, GOLD, GREEN, format_model_name
from .display import get_version
from .auto_context import gather_auto_context

console = Console()


# ============================================================
# Exceptions
# ============================================================


class UpgradeRequiredError(Exception):
    """Raised when CLI version is incompatible with the API (426 response)."""

    def __init__(self, min_version: str, current_version: str):
        self.min_version = min_version
        self.current_version = current_version
        super().__init__(
            f"CLI version {current_version} is incompatible. "
            f"Minimum required: {min_version}"
        )


# ============================================================
# SSE Event Types (mirrors cloud types)
# ============================================================


@dataclass
class CritiqueSummary:
    """Summary of a single critique for grid display."""

    critic: str
    target: str
    severity: str  # 'critical' | 'moderate' | 'minor'
    summary: str  # One-line summary


@dataclass
class ToolCall:
    """A pending tool call from the cloud."""

    call_id: str
    tool: str
    parameters: Dict[str, Any]
    status: str = "pending"  # pending, running, complete, error
    result: Optional[str] = None
    error: Optional[str] = None


@dataclass
class DebateState:
    """Tracks current state of the debate for rendering."""

    stage: int = 0
    stage_name: str = "analysis"

    # Analysis results
    complexity: str = ""
    domains: List[str] = field(default_factory=list)
    bishops: List[str] = field(default_factory=list)
    pope: str = ""
    reasoning: str = ""  # Why these bishops were selected

    # Bishop status
    bishop_status: Dict[str, str] = field(
        default_factory=dict
    )  # model -> 'pending'|'running'|'complete'
    bishop_content: Dict[str, str] = field(default_factory=dict)  # model -> content
    bishop_tokens: Dict[str, int] = field(default_factory=dict)  # model -> tokens
    bishop_approach: Dict[str, str] = field(
        default_factory=dict
    )  # model -> approach summary

    # Consensus
    consensus_score: Optional[float] = None

    # Pope Assessment (before critiques)
    pope_assessment_done: bool = False
    should_debate: bool = True
    overall_similarity: float = 0.0
    assessment_reasoning: str = ""
    disagreement_pairs: List[Dict[str, Any]] = field(default_factory=list)
    debate_skipped: bool = False
    debate_skip_reason: str = ""

    # Critiques
    current_round: int = 0
    max_rounds: int = 3
    critique_pairs: int = 0
    critique_status: Dict[str, str] = field(
        default_factory=dict
    )  # "critic->target" -> 'running'|'complete'
    critique_content: Dict[str, str] = field(default_factory=dict)
    critique_severity: Dict[str, str] = field(
        default_factory=dict
    )  # "critic->target" -> severity
    critique_summaries: List[CritiqueSummary] = field(
        default_factory=list
    )  # For grid display
    running_critiques: List[Dict[str, str]] = field(
        default_factory=list
    )  # [{critic, target}, ...] for in-progress
    consensus_reached: bool = False
    consensus_reached_round: int = 0
    # Round-specific tracking for persistent display
    round_summaries: Dict[int, List[CritiqueSummary]] = field(
        default_factory=dict
    )  # round -> completed critiques
    round_consensus: Dict[int, float] = field(
        default_factory=dict
    )  # round -> consensus after round
    # Issue counts from critiques
    critical_issues: int = 0
    moderate_issues: int = 0
    minor_issues: int = 0
    # Early exit tracking
    debate_early_exit: bool = False
    debate_exit_reason: str = (
        ""  # 'consensus_high', 'no_critical_issues', 'issues_resolved', 'no_new_issues'
    )
    debate_exit_explanation: str = ""  # Human-readable explanation

    # Pope synthesis
    pope_status: str = "pending"
    pope_content: str = ""
    pope_tokens: int = 0

    # Memory
    memories_retrieved: int = 0
    memories_stored: int = 0
    memory_tokens: int = 0
    memory_summaries: List[Dict[str, Any]] = field(
        default_factory=list
    )  # [{type, content, score, scope}, ...]

    # Stage 0 Progress Tracking
    analysis_started: bool = False
    memory_search_done: bool = False
    classification_done: bool = False
    context_hints_received: bool = False

    # Context hints (from API)
    search_keywords: List[str] = field(default_factory=list)
    search_symbols: List[str] = field(default_factory=list)
    search_type: str = ""  # 'broad' | 'focused' | 'definition'
    language_hints: List[str] = field(default_factory=list)
    memory_hints: List[str] = field(default_factory=list)

    # Context plan from classifier (what files SHOULD be gathered)
    context_plan_searches: List[Dict[str, Any]] = field(default_factory=list)

    # Auto-context tracking (displayed within Live)
    auto_context_files: List[str] = field(default_factory=list)  # File paths included

    # Tool execution
    tool_calls: List[ToolCall] = field(default_factory=list)
    current_tool: Optional[ToolCall] = None
    pending_tool_batch: List[ToolCall] = field(
        default_factory=list
    )  # Batch of tools to execute
    tools_executed: int = 0

    # Final
    complete: bool = False
    debate_id: str = ""
    total_tokens: int = 0
    duration_ms: int = 0
    cost_usd: Optional[float] = None
    error: Optional[str] = None

    # Timing
    start_time: float = field(default_factory=time.time)
    stage_start_times: Dict[int, float] = field(
        default_factory=dict
    )  # stage -> start time
    stage_end_times: Dict[int, float] = field(default_factory=dict)  # stage -> end time


# ============================================================
# SSE Event Handlers
# ============================================================


def handle_event(state: DebateState, event: dict) -> None:
    """Update state based on SSE event."""
    event_type = event.get("type")

    if event_type == "stage":
        # End previous stage timing (if any)
        prev_stage = state.stage
        if (
            prev_stage in state.stage_start_times
            and prev_stage not in state.stage_end_times
        ):
            state.stage_end_times[prev_stage] = time.time()

        # Start new stage timing (don't overwrite if already set, e.g. stage 0)
        state.stage = event["stage"]
        state.stage_name = event["name"]
        if state.stage not in state.stage_start_times:
            state.stage_start_times[state.stage] = time.time()

    elif event_type == "analysis_complete":
        state.complexity = event["complexity"]
        state.domains = event["domains"]
        state.bishops = event["bishops"]
        state.pope = event["pope"]
        state.reasoning = event.get("reasoning", "")
        state.bishop_status = {b: "pending" for b in state.bishops}
        state.classification_done = True
        # Store context plan for future reference (what files SHOULD be gathered)
        context_plan = event.get("context_plan", {})
        if context_plan.get("needs_codebase_search"):
            state.context_plan_searches = context_plan.get("searches", [])
        # Mark stage 0 as complete
        if 0 not in state.stage_end_times:
            state.stage_end_times[0] = time.time()

    elif event_type == "context_hints":
        # Context analysis from the API
        state.context_hints_received = True
        query_analysis = event.get("query_analysis", {})
        state.search_keywords = query_analysis.get("keywords", [])
        state.search_symbols = query_analysis.get("symbol_names", [])
        state.language_hints = query_analysis.get("language_hints", [])
        search_strategy = event.get("search_strategy", {})
        state.search_type = search_strategy.get("search_type", "")
        state.memory_hints = event.get("memory_hints", [])

    elif event_type == "bishop_start":
        state.bishop_status[event["model"]] = "running"

    elif event_type == "bishop_summary":
        # Quick approach summary for grid display
        state.bishop_approach[event["model"]] = event["approach"]

    elif event_type == "bishop_complete":
        state.bishop_status[event["model"]] = "complete"
        state.bishop_tokens[event["model"]] = event["tokens"]

    elif event_type == "bishop_stream":
        # Streaming chunk from a bishop - accumulate content
        model = event["model"]
        chunk = event["chunk"]
        if model not in state.bishop_content:
            state.bishop_content[model] = ""
        state.bishop_content[model] += chunk

    elif event_type == "bishop_content":
        state.bishop_content[event["model"]] = event["content"]

    elif event_type == "consensus":
        state.consensus_score = event["score"]

    # Pope Assessment (before critiques)
    elif event_type == "pope_assessment":
        state.pope_assessment_done = True
        state.should_debate = event["shouldDebate"]
        state.overall_similarity = event["overallSimilarity"]
        state.assessment_reasoning = event["reasoning"]
        state.disagreement_pairs = event.get("disagreementPairs", [])

    elif event_type == "debate_skipped":
        state.debate_skipped = True
        state.debate_skip_reason = event["reason"]

    # Critique rounds
    elif event_type == "critique_round_start":
        state.current_round = event["round"]
        state.max_rounds = event["maxRounds"]
        state.critique_pairs = event["pairs"]
        # Initialize round tracking
        if state.current_round not in state.round_summaries:
            state.round_summaries[state.current_round] = []

    elif event_type == "critique_start":
        critic = event["critic"]
        targets = event.get("targets", [])
        target = targets[0] if targets else "unknown"
        key = f"{critic}->{target}"
        state.critique_status[key] = "running"
        # Track running critique for display
        state.running_critiques.append({"critic": critic, "target": target})

    elif event_type == "critique_summary":
        # One-line summary for grid display
        critic = event["critic"]
        target = event["target"]
        key = f"{critic}->{target}"
        # Mark as complete
        state.critique_status[key] = "complete"
        state.critique_severity[key] = event["severity"]
        # Remove from running critiques
        state.running_critiques = [
            c
            for c in state.running_critiques
            if not (c["critic"] == critic and c["target"] == target)
        ]
        # Add to summaries (avoid duplicates)
        new_summary = CritiqueSummary(
            critic=critic,
            target=target,
            severity=event["severity"],
            summary=event["summary"],
        )
        # Always add to round_summaries for the current round (each round can have its own critiques)
        if state.current_round in state.round_summaries:
            state.round_summaries[state.current_round].append(new_summary)
        # For global critique_summaries, dedupe by critic->target pair
        existing = [(c.critic, c.target) for c in state.critique_summaries]
        if (new_summary.critic, new_summary.target) not in existing:
            state.critique_summaries.append(new_summary)

    elif event_type == "critique_complete":
        # Also handle critique_complete (backup for critique_summary)
        critic = event.get("critic", "")
        target = event.get("target", "")
        if critic and target:
            key = f"{critic}->{target}"
            state.critique_status[key] = "complete"
            state.critique_severity[key] = event.get("severity", "minor")
            state.running_critiques = [
                c
                for c in state.running_critiques
                if not (c["critic"] == critic and c["target"] == target)
            ]

    elif event_type == "critique_content":
        state.critique_content[event["critic"]] = event["content"]

    elif event_type == "critique_round_complete":
        state.consensus_score = event["consensusScore"]
        # Store consensus for this round (for persistent display)
        state.round_consensus[state.current_round] = event["consensusScore"]
        # Capture issue counts
        state.critical_issues += event.get("criticalIssues", 0)
        state.moderate_issues += event.get("moderateIssues", 0)
        state.minor_issues += event.get("minorIssues", 0)

    elif event_type == "consensus_reached":
        state.consensus_reached = True
        state.consensus_reached_round = event["round"]
        state.consensus_score = event["score"]

    elif event_type == "debate_early_exit":
        state.debate_early_exit = True
        state.debate_exit_reason = event.get("reason", "")
        state.debate_exit_explanation = event.get("explanation", "")
        state.consensus_score = event.get("finalConsensus", state.consensus_score)

    # Memory events
    elif event_type == "memory_retrieved":
        state.memories_retrieved = event.get("user_memories", 0) + event.get(
            "project_memories", 0
        )
        state.memory_tokens = event.get("tokens", 0)
        state.memory_summaries = event.get("memories", [])
        state.memory_search_done = True

    elif event_type == "memory_extracted":
        state.memories_stored = event.get("stored", 0)

    # Pope synthesis
    elif event_type == "pope_start":
        state.pope_status = "running"

    elif event_type == "pope_stream":
        state.pope_content += event["chunk"]

    elif event_type == "pope_complete":
        state.pope_status = "complete"
        state.pope_content = event["content"]
        state.pope_tokens = event["tokens"]

    elif event_type == "complete":
        state.complete = True
        state.debate_id = event["debate_id"]
        state.total_tokens = event["total_tokens"]
        state.duration_ms = event["duration_ms"]
        state.cost_usd = event.get("cost_usd")
        state.memories_retrieved = event.get(
            "memories_retrieved", state.memories_retrieved
        )
        state.memories_stored = event.get("memories_stored", state.memories_stored)
        # End final stage timing
        if (
            state.stage in state.stage_start_times
            and state.stage not in state.stage_end_times
        ):
            state.stage_end_times[state.stage] = time.time()

    elif event_type == "error":
        state.error = event["message"]

    # Tool execution events
    elif event_type == "tools_required":
        # Receive debate_id early so we can send tool results back
        state.debate_id = event["debate_id"]

    elif event_type == "tool_call":
        tool_call = ToolCall(
            call_id=event["call_id"],
            tool=event["tool"],
            parameters=event.get("parameters", {}),
            status="pending",
        )
        state.tool_calls.append(tool_call)
        state.current_tool = tool_call

    elif event_type == "tool_result_ack":
        # Cloud acknowledged our tool result
        call_id = event.get("call_id")
        for tc in state.tool_calls:
            if tc.call_id == call_id:
                tc.status = "complete"
                state.tools_executed += 1
                break
        state.current_tool = None


# ============================================================
# Display Rendering
# ============================================================

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
THINKING_FRAMES = ["🧠", "💭", "💡", "✨", "🔮", "⚡"]
STREAMING_FRAMES = [
    "▁",
    "▂",
    "▃",
    "▄",
    "▅",
    "▆",
    "▇",
    "█",
    "▇",
    "▆",
    "▅",
    "▄",
    "▃",
    "▂",
]
PULSE_FRAMES = ["◉", "◎", "○", "◎"]
# Mesmerizing gradient wave frames for status bar
WAVE_FRAMES = [
    "░▒▓█▓▒░",
    "▒▓█▓▒░░",
    "▓█▓▒░░▒",
    "█▓▒░░▒▓",
    "▓▒░░▒▓█",
    "▒░░▒▓█▓",
    "░░▒▓█▓▒",
    "░▒▓█▓▒░",
]
DOT_WAVE_FRAMES = ["·•●•·", "•●•··", "●•··•", "•··•●", "··•●•", "·•●•·"]
PROGRESS_FRAMES = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]
# Pope observation frames - calm, watching
POPE_OBSERVE_FRAMES = ["👁️ ", "👁️ ", "👁️‍🗨️", "👁️ "]
# Pope presiding frames - more authoritative
POPE_PRESIDE_FRAMES = ["⚖️ ", "📜", "⚖️ ", "🔱"]
_frame_idx = 0
# Animation speed divisor - higher = slower animations
ANIMATION_SPEED_DIVISOR = 4  # Animations change every 4 frames instead of every frame


def _slow_frame_idx() -> int:
    """Get slowed down frame index for animations."""
    return _frame_idx // ANIMATION_SPEED_DIVISOR


def get_spinner() -> str:
    """Get current spinner frame."""
    return SPINNER_FRAMES[_slow_frame_idx() % len(SPINNER_FRAMES)]


def get_thinking_indicator() -> str:
    """Get animated thinking indicator."""
    return THINKING_FRAMES[_slow_frame_idx() % len(THINKING_FRAMES)]


def get_streaming_bar() -> str:
    """Get animated streaming bar."""
    return STREAMING_FRAMES[_slow_frame_idx() % len(STREAMING_FRAMES)]


def get_pulse() -> str:
    """Get pulsing indicator."""
    return PULSE_FRAMES[_slow_frame_idx() % len(PULSE_FRAMES)]


def get_wave() -> str:
    """Get mesmerizing wave animation."""
    return WAVE_FRAMES[_slow_frame_idx() % len(WAVE_FRAMES)]


def get_dot_wave() -> str:
    """Get dot wave animation."""
    return DOT_WAVE_FRAMES[_slow_frame_idx() % len(DOT_WAVE_FRAMES)]


def get_progress_spinner() -> str:
    """Get braille progress spinner."""
    return PROGRESS_FRAMES[_slow_frame_idx() % len(PROGRESS_FRAMES)]


def get_pope_observe() -> str:
    """Get pope observation animation frame."""
    return POPE_OBSERVE_FRAMES[_slow_frame_idx() % len(POPE_OBSERVE_FRAMES)]


def get_pope_preside() -> str:
    """Get pope presiding animation frame."""
    return POPE_PRESIDE_FRAMES[_slow_frame_idx() % len(POPE_PRESIDE_FRAMES)]


def advance_animation() -> None:
    """Advance the global animation frame."""
    global _frame_idx
    _frame_idx += 1


def get_stage_time(state: DebateState, stage: int) -> str:
    """Get formatted time for a stage (elapsed or completed)."""
    if stage in state.stage_end_times:
        # Stage completed - show total time
        duration = state.stage_end_times[stage] - state.stage_start_times.get(
            stage, state.start_time
        )
        return f"{max(0, duration):.1f}s"  # Ensure non-negative
    elif stage in state.stage_start_times:
        # Stage in progress - show elapsed time
        elapsed = time.time() - state.stage_start_times[stage]
        return f"{max(0, elapsed):.1f}s"  # Ensure non-negative
    elif stage == 0:
        # Stage 0 starts at debate start
        elapsed = time.time() - state.start_time
        return f"{max(0, elapsed):.1f}s"  # Ensure non-negative
    return ""


def build_analysis_panel(state: DebateState) -> Panel:
    """Build Stage 0 analysis panel with detailed progress."""
    elements = []

    if state.complexity:
        # Analysis complete - show results
        elements.append(Text("✓ Analysis complete", style=f"bold {GREEN}"))
        elements.append(Text(""))

        # Complexity with color
        complexity_colors = {
            "trivial": GREEN,
            "simple": CYAN,
            "moderate": GOLD,
            "complex": PRIMARY,
            "expert": "red",
        }
        color = complexity_colors.get(state.complexity, CYAN)
        elements.append(
            Text("Complexity: ", style="dim")
            + Text(state.complexity.upper(), style=f"bold {color}")
        )

        # Domains
        if state.domains:
            elements.append(
                Text("Domains: ", style="dim")
                + Text(", ".join(state.domains), style=CYAN)
            )

        # Memory retrieved - show what was actually found
        if state.memories_retrieved > 0:
            elements.append(
                Text("🧠 Memory: ", style="dim")
                + Text(
                    f"{state.memories_retrieved} relevant learnings ({state.memory_tokens} tokens)",
                    style=CYAN,
                )
            )
            # Show actual memories
            for mem in state.memory_summaries[:5]:  # Show top 5
                mem_type = mem.get("type", "unknown")
                mem_content = mem.get("content", "")
                mem_score = mem.get("score", 0)
                mem_scope = mem.get("scope", "user")
                score_pct = int(mem_score * 100)

                # Color by type
                type_colors = {
                    "preference": CYAN,
                    "pattern": GOLD,
                    "skill": GREEN,
                    "architecture": PRIMARY,
                    "convention": "magenta",
                    "bug": "red",
                    "decision": "blue",
                }
                type_color = type_colors.get(mem_type, "white")
                scope_icon = "👤" if mem_scope == "user" else "📁"

                elements.append(
                    Text(f"   {scope_icon} ", style="dim")
                    + Text(f"[{mem_type}] ", style=f"bold {type_color}")
                    + Text(f"{score_pct}% ", style="dim")
                    + Text(
                        mem_content[:60] + ("..." if len(mem_content) > 60 else ""),
                        style="dim italic",
                    )
                )
        elif state.memory_search_done:
            elements.append(
                Text("🧠 Memory: ", style="dim")
                + Text("No prior learnings found (fresh query)", style="dim")
            )

        # Context hints (if received)
        if state.context_hints_received:
            hints_parts = []
            if state.search_keywords:
                hints_parts.append(f"keywords: {', '.join(state.search_keywords[:3])}")
            if state.language_hints:
                hints_parts.append(f"lang: {', '.join(state.language_hints)}")
            if state.search_type:
                hints_parts.append(f"search: {state.search_type}")
            if hints_parts:
                elements.append(
                    Text("Context: ", style="dim")
                    + Text(" | ".join(hints_parts), style="dim")
                )

        # Bishops selected
        elements.append(Text(""))
        elements.append(Text("🎓 Selected Bishops:", style=f"bold {PRIMARY}"))
        for bishop in state.bishops:
            elements.append(Text(f"  ✓ {format_model_name(bishop)}", style=GREEN))

        # Reasoning (why these bishops were selected)
        if state.reasoning:
            elements.append(Text(""))
            elements.append(Text(f"💡 {state.reasoning}", style="dim italic"))
    else:
        # Still analyzing - show detailed animated progress
        think = get_thinking_indicator()
        spinner = get_spinner()
        bar = get_streaming_bar()
        pulse = get_pulse()

        elements.append(
            Text(f"{think} Stage 0: Analysis in Progress", style=f"bold {CYAN}")
        )
        elements.append(Text(""))

        # Show what's happening in parallel
        # Memory search status
        if state.memory_search_done:
            if state.memories_retrieved > 0:
                elements.append(
                    Text("  ✓ Memory search: ", style="dim")
                    + Text(f"{state.memories_retrieved} learnings found", style=GREEN)
                )
            else:
                elements.append(
                    Text("  ✓ Memory search: ", style="dim")
                    + Text("No prior context", style="dim")
                )
        else:
            elements.append(
                Text(f"  {spinner} Memory search: ", style="dim")
                + Text(f"Searching vector database {bar}", style=CYAN)
            )

        # Query classification status
        if state.classification_done:
            elements.append(
                Text("  ✓ Classification: ", style="dim")
                + Text("Complete", style=GREEN)
            )
        else:
            elements.append(
                Text(f"  {spinner} Classification: ", style="dim")
                + Text(f"Analyzing complexity & selecting bishops {pulse}", style=CYAN)
            )

        # Context hints status
        if state.context_hints_received:
            elements.append(
                Text("  ✓ Context analysis: ", style="dim") + Text("Ready", style=GREEN)
            )
            if state.search_keywords:
                elements.append(
                    Text(
                        f"      Keywords: {', '.join(state.search_keywords[:4])}",
                        style="dim",
                    )
                )
        else:
            elements.append(
                Text(f"  {spinner} Context analysis: ", style="dim")
                + Text(f"Extracting search hints {bar}", style=CYAN)
            )

        # Auto-context files (if gathered)
        if state.auto_context_files:
            elements.append(
                Text("  ✓ Auto-context: ", style="dim")
                + Text(f"{len(state.auto_context_files)} file(s) included", style=GREEN)
            )
            for path in state.auto_context_files[:3]:
                elements.append(Text(f"      + {path}", style="dim"))
            if len(state.auto_context_files) > 3:
                elements.append(
                    Text(
                        f"      ... and {len(state.auto_context_files) - 3} more",
                        style="dim",
                    )
                )

    # Build title with timing
    stage_time = get_stage_time(state, 0)
    time_suffix = f" [{stage_time}]" if stage_time else ""

    return Panel(
        Group(*elements),
        title=f"[{CYAN}]Stage 0: Analysis{time_suffix}[/{CYAN}]",
        border_style=CYAN,
        padding=(0, 2),
    )


def build_proposals_panel(state: DebateState) -> Panel:
    """Build Stage 1 proposals panel with grid display."""
    elements = []

    # Pope observer - only animate during Stage 1
    if state.stage == 1:
        observer = get_pope_observe()
        pulse = get_pulse()
        elements.append(
            Text(f"👑 Pope {format_model_name(state.pope)} observing ", style="grey50")
            + Text(f"{observer} {pulse}", style=GOLD)
        )
    else:
        # Stage complete - static text
        elements.append(
            Text(f"👑 Pope {format_model_name(state.pope)} observed", style="grey50")
        )
    elements.append(Text(""))

    # Build grid table for bishops
    if state.bishops:
        table = Table(
            box=box.ROUNDED, show_header=True, header_style=f"bold {CYAN}", expand=True
        )

        # Add columns for each bishop
        for bishop in state.bishops:
            table.add_column(format_model_name(bishop), justify="center", width=25)

        # Status row with enhanced animations
        status_cells = []
        for bishop in state.bishops:
            status = state.bishop_status.get(bishop, "pending")
            if status == "complete":
                tokens = state.bishop_tokens.get(bishop, 0)
                status_cells.append(Text(f"✓ {tokens} tokens", style=GREEN))
            elif status == "running":
                # More expressive running animation
                bar = get_streaming_bar()
                think = get_thinking_indicator()
                status_cells.append(Text(f"{think} {bar} reasoning...", style=CYAN))
            else:
                # Waiting animation
                spinner = get_spinner()
                status_cells.append(Text(f"{spinner} waiting...", style="dim"))
        table.add_row(*status_cells)

        # Approach row (if available)
        approach_cells = []
        has_approaches = any(state.bishop_approach.get(b) for b in state.bishops)
        if has_approaches:
            for bishop in state.bishops:
                approach = state.bishop_approach.get(bishop, "")
                if approach:
                    # Truncate for display
                    display = approach[:35] + "..." if len(approach) > 35 else approach
                    approach_cells.append(Text(display, style="dim italic"))
                else:
                    approach_cells.append(Text("", style="dim"))
            table.add_row(*approach_cells)

        elements.append(table)

    # Show full proposals once all bishops are complete (collapsible style)
    all_complete = (
        all(state.bishop_status.get(b) == "complete" for b in state.bishops)
        if state.bishops
        else False
    )
    if all_complete and state.bishop_content:
        elements.append(Text(""))
        elements.append(Text("📜 Bishop Proposals:", style=f"bold {PRIMARY}"))
        for bishop in state.bishops:
            content = state.bishop_content.get(bishop, "")
            if content:
                # Show first 200 chars with expand indicator
                tokens = state.bishop_tokens.get(bishop, 0)
                preview = content[:300].replace("\n", " ")
                if len(content) > 300:
                    preview += "..."
                elements.append(Text(""))
                elements.append(
                    Text(f"  {format_model_name(bishop)} ", style=f"bold {CYAN}")
                    + Text(f"({tokens} tokens)", style="dim")
                )
                elements.append(Text(f"  {preview}", style="dim"))

    # Consensus score
    if state.consensus_score is not None:
        elements.append(Text(""))
        score_pct = int(state.consensus_score * 100)
        if score_pct >= 80:
            style = GREEN
            label = "HIGH"
        elif score_pct >= 50:
            style = GOLD
            label = "MODERATE"
        else:
            style = "red"
            label = "LOW"
        elements.append(
            Text("📊 Consensus: ", style="dim")
            + Text(f"{score_pct}% ({label})", style=f"bold {style}")
        )

    # Pope assessment result - shows consensus level with detailed pairwise breakdown
    if state.pope_assessment_done:
        elements.append(Text(""))
        sim_pct = int(state.overall_similarity * 100)

        # Overall consensus assessment
        if sim_pct >= 80:
            consensus_label = "HIGH AGREEMENT"
            consensus_style = GREEN
        elif sim_pct >= 50:
            consensus_label = "MODERATE AGREEMENT"
            consensus_style = GOLD
        else:
            consensus_label = "LOW AGREEMENT"
            consensus_style = "red"

        elements.append(
            Text("⚖️ Pope Assessment: ", style="dim")
            + Text(f"{sim_pct}% consensus ", style=f"bold {consensus_style}")
            + Text(f"({consensus_label})", style=consensus_style)
        )

        # Show the reasoning from the server
        if state.assessment_reasoning:
            elements.append(
                Text(f"   → {state.assessment_reasoning}", style="dim italic")
            )

        # Explain why debate happens even with high consensus
        if sim_pct >= 80 and not state.debate_skipped:
            elements.append(
                Text(
                    "   ⚠️ High consensus ≠ correct answer. Debate verifies no shared blind spots.",
                    style=f"dim {GOLD}",
                )
            )

        # Show pairwise similarities if available
        if state.disagreement_pairs:
            elements.append(Text("   Pairwise scores:", style="dim"))
            for pair in state.disagreement_pairs:
                b1 = format_model_name(pair["bishop1"])
                b2 = format_model_name(pair["bishop2"])
                pair_sim = int(pair["similarity"] * 100)
                pair_style = (
                    GREEN if pair_sim >= 80 else (GOLD if pair_sim >= 50 else "red")
                )
                elements.append(
                    Text(f"     • {b1} ↔ {b2}: ", style="dim")
                    + Text(f"{pair_sim}%", style=pair_style)
                )

    # Build title with timing
    stage_time = get_stage_time(state, 1)
    time_suffix = f" [{stage_time}]" if stage_time else ""

    return Panel(
        Group(*elements),
        title=f"[{CYAN}]Stage 1: Bishop Proposals{time_suffix}[/{CYAN}]",
        border_style=CYAN,
        padding=(0, 2),
    )


def build_critiques_panel(state: DebateState) -> Panel:
    """Build Stage 2 critiques panel with persistent round-by-round display."""
    elements = []

    # Build title with timing
    stage_time = get_stage_time(state, 2)
    time_suffix = f" [{stage_time}]" if stage_time else ""

    # Check if debate was skipped
    if state.debate_skipped:
        elements.append(
            Text(f"✓ Debate skipped: {state.debate_skip_reason}", style=GREEN)
        )
        return Panel(
            Group(*elements),
            title=f"[{GOLD}]Stage 2: Adversarial Critiques{time_suffix}[/{GOLD}]",
            border_style=GOLD,
            padding=(0, 2),
        )

    # Show debate explanation header
    if state.max_rounds > 0 and state.stage == 2:
        elements.append(
            Text(
                f"📋 Debate plan: Up to {state.max_rounds} round(s), exit early at 80%+ consensus",
                style="dim",
            )
        )
        elements.append(Text(""))

    # Pope presiding - show animation only during active critiques, static when done
    if state.stage >= 3 or state.consensus_reached or state.debate_early_exit:
        elements.append(
            Text(
                f"👑 Pope {format_model_name(state.pope)} presided over debate",
                style="grey50",
            )
        )
    else:
        preside = get_pope_preside()
        pulse = get_pulse()
        elements.append(
            Text(f"👑 Pope {format_model_name(state.pope)} presiding ", style="grey50")
            + Text(f"{preside} {pulse}", style=GOLD)
        )
    elements.append(Text(""))

    # Display completed rounds persistently
    completed_rounds = sorted(
        [
            r
            for r in state.round_summaries.keys()
            if r < state.current_round or state.stage >= 3
        ]
    )
    for round_num in completed_rounds:
        round_critiques = state.round_summaries.get(round_num, [])
        round_cons = state.round_consensus.get(round_num)

        # Round header
        round_header = Text()
        round_header.append(f"  Round {round_num}", style=f"bold {GOLD}")
        if round_cons is not None:
            cons_pct = int(round_cons * 100)
            round_header.append(" • ", style="dim")
            round_header.append(f"{cons_pct}% consensus", style="dim")
        round_header.append(" ✓", style=GREEN)
        elements.append(round_header)

        # Critiques for this round
        for crit in round_critiques:
            severity_color = {"critical": "red", "moderate": GOLD, "minor": GREEN}.get(
                crit.severity, GREEN
            )
            row_text = Text()
            row_text.append("    ✓ ", style=GREEN)
            row_text.append(f"{format_model_name(crit.critic)}", style=CYAN)
            row_text.append(" → ", style="dim")
            row_text.append(f"{format_model_name(crit.target)} ", style=CYAN)
            row_text.append(
                f"[{crit.severity.upper()}] ", style=f"bold {severity_color}"
            )
            # Show more of the summary - truncate at 80 chars
            summary_text = crit.summary[:80] + ("..." if len(crit.summary) > 80 else "")
            row_text.append(summary_text, style="dim")
            elements.append(row_text)
        elements.append(Text(""))

    # Current round (if in progress)
    if (
        state.current_round > 0
        and state.stage < 3
        and not state.consensus_reached
        and not state.debate_early_exit
    ):
        # Check if this round has any completed critiques yet
        current_round_done = state.current_round in completed_rounds
        if not current_round_done:
            round_header = Text()
            spinner = get_spinner()
            round_header.append(
                f"  {spinner} Round {state.current_round}", style=f"bold {GOLD}"
            )
            round_header.append(f" of {state.max_rounds}", style="dim")
            round_header.append(" • ", style="dim")
            round_header.append(f"{state.critique_pairs} pairs critiquing", style=GOLD)
            elements.append(round_header)

            # Show running critiques for current round
            for crit in state.running_critiques:
                spinner = get_spinner()
                row_text = Text()
                row_text.append(f"    {spinner} ", style=CYAN)
                row_text.append(f"{format_model_name(crit['critic'])}", style=CYAN)
                row_text.append(" → ", style="dim")
                row_text.append(f"{format_model_name(crit['target'])} ", style=CYAN)
                row_text.append("critiquing...", style="dim italic")
                elements.append(row_text)

            # Show completed critiques in current round (not yet moved to round_summaries)
            current_round_critiques = state.round_summaries.get(state.current_round, [])
            for crit in current_round_critiques:
                severity_color = {
                    "critical": "red",
                    "moderate": GOLD,
                    "minor": GREEN,
                }.get(crit.severity, GREEN)
                row_text = Text()
                row_text.append("    ✓ ", style=GREEN)
                row_text.append(f"{format_model_name(crit.critic)}", style=CYAN)
                row_text.append(" → ", style="dim")
                row_text.append(f"{format_model_name(crit.target)} ", style=CYAN)
                row_text.append(
                    f"[{crit.severity.upper()}] ", style=f"bold {severity_color}"
                )
                summary_text = crit.summary[:80] + ("..." if len(crit.summary) > 80 else "")
                row_text.append(summary_text, style="dim")
                elements.append(row_text)

    # Starting message if no rounds yet
    if state.current_round == 0:
        spinner = get_spinner()
        elements.append(
            Text(f"  {spinner} Adversarial critique phase starting...", style=GOLD)
        )

    # Early exit message (smart dynamic exit)
    if state.debate_early_exit:
        score_pct = int(state.consensus_score * 100) if state.consensus_score else 0
        exit_text = Text()
        exit_text.append("✓ ", style=GREEN)
        exit_text.append("Debate concluded early", style=f"bold {GREEN}")
        exit_text.append(
            f" (round {state.current_round}/{state.max_rounds})", style="dim"
        )
        elements.append(exit_text)
        # Show the explanation
        if state.debate_exit_explanation:
            elements.append(
                Text(f"   → {state.debate_exit_explanation}", style="dim italic")
            )
        # Show issue counts
        if state.critical_issues or state.moderate_issues or state.minor_issues:
            issue_text = Text("   Issues: ", style="dim")
            if state.critical_issues:
                issue_text.append(f"🔴 {state.critical_issues} critical  ", style="red")
            if state.moderate_issues:
                issue_text.append(
                    f"🟡 {state.moderate_issues} moderate  ", style="yellow"
                )
            if state.minor_issues:
                issue_text.append(f"🟢 {state.minor_issues} minor", style="green")
            elements.append(issue_text)

    # Consensus reached message (legacy - kept for compatibility)
    elif state.consensus_reached:
        score_pct = int(state.consensus_score * 100) if state.consensus_score else 0
        consensus_text = Text()
        consensus_text.append("✓ ", style=GREEN)
        consensus_text.append("Consensus reached!", style=f"bold {GREEN}")
        consensus_text.append(
            f" ({score_pct}% after round {state.consensus_reached_round})", style="dim"
        )
        elements.append(consensus_text)
        if state.consensus_reached_round < state.max_rounds:
            elements.append(
                Text(
                    f"   Skipped {state.max_rounds - state.consensus_reached_round} remaining round(s)",
                    style="dim italic",
                )
            )

    # Final summary when stage 2 complete (no early exit, no consensus reached)
    elif state.stage >= 3:
        final_cons = int(state.consensus_score * 100) if state.consensus_score else 0
        summary_text = Text()
        summary_text.append("✓ ", style=GREEN)
        summary_text.append("Debate complete", style=f"bold {GREEN}")
        summary_text.append(
            f" • {state.current_round} round(s) • {final_cons}% consensus", style="dim"
        )
        elements.append(summary_text)
        # Show issue counts
        if state.critical_issues or state.moderate_issues or state.minor_issues:
            issue_text = Text("   Issues: ", style="dim")
            if state.critical_issues:
                issue_text.append(f"🔴 {state.critical_issues} critical  ", style="red")
            if state.moderate_issues:
                issue_text.append(
                    f"🟡 {state.moderate_issues} moderate  ", style="yellow"
                )
            if state.minor_issues:
                issue_text.append(f"🟢 {state.minor_issues} minor", style="green")
            elements.append(issue_text)

    # Show completion status in title when stage 2 is done
    if state.stage >= 3:
        title = f"[{GOLD}]Stage 2: Adversarial Critiques{time_suffix} ✓[/{GOLD}]"
    else:
        title = f"[{GOLD}]Stage 2: Adversarial Critiques{time_suffix}[/{GOLD}]"

    return Panel(Group(*elements), title=title, border_style=GOLD, padding=(0, 2))


def build_synthesis_panel(state: DebateState) -> Panel:
    """Build Stage 3 synthesis panel for live display."""
    elements = []

    if state.pope_status == "complete":
        # Complete - show full synthesis content with stats
        total_elapsed = time.time() - state.start_time
        # Use stage 3 time for synthesis duration, total time for the stats line
        _stage3_time = get_stage_time(state, 3)
        elements.append(
            Text(
                f"✓ {format_model_name(state.pope)} synthesis complete",
                style=f"bold {GREEN}",
            )
        )
        elements.append(Text(""))

        # Stats line - show total debate time, tokens, and other stats
        stats_parts = [
            f"⏱ {total_elapsed:.1f}s total",
            f"📊 {state.total_tokens:,} tokens",
        ]
        if state.cost_usd:
            stats_parts.append(f"💰 ${state.cost_usd:.4f}")
        if state.memories_retrieved > 0:
            stats_parts.append(f"🧠 {state.memories_retrieved} memories")
        if state.memories_stored > 0:
            stats_parts.append(f"💾 {state.memories_stored} learned")
        elements.append(Text(" | ".join(stats_parts), style="dim"))
        elements.append(Text(""))

        # Show full synthesis content with markdown rendering
        if state.pope_content:
            md = Markdown(
                state.pope_content,
                code_theme="monokai",
                hyperlinks=False,  # Avoid terminal compatibility issues
            )
            elements.append(md)

    elif state.pope_status == "running":
        # Pope is synthesizing - use SLOWER animation (divide by 8 instead of 4)
        # This reduces flickering during the long synthesis phase
        slow_idx = _frame_idx // 8  # Extra slow for synthesis
        think_frames = ["🧠", "💭", "💡", "✨"]
        think = think_frames[slow_idx % len(think_frames)]
        elements.append(
            Text(f"👑 {think} ", style=SECONDARY)
            + Text(
                f"{format_model_name(state.pope)} synthesizing",
                style=f"bold {SECONDARY}",
            )
        )

        if state.pope_content:
            elements.append(Text(""))
            # Show streaming content preview with markdown rendering
            content = state.pope_content
            lines = content.split("\n")
            # Show last 15 lines for streaming effect
            if len(lines) > 15:
                visible_content = "\n".join(lines[-15:])
                elements.append(
                    Text(f"... ({len(lines) - 15} lines above)", style="dim")
                )
            else:
                visible_content = content

            # During streaming: plain text (fast, no flicker)
            # Markdown syntax will be visible but that's fine while watching it stream
            # Full Markdown rendering happens when synthesis is complete
            elements.append(Text(visible_content, style="white"))

            # Simple blinking cursor - less flashy (changes every ~1 second at 12fps)
            cursor = "█" if (slow_idx % 2) == 0 else " "
            elements.append(Text(cursor, style=GOLD))
        else:
            # No content yet - show simple waiting animation
            spinner = get_spinner()
            elements.append(Text(""))
            elements.append(Text(f"{spinner} Waiting for response...", style="dim"))
    else:
        # Waiting state with animation
        spinner = get_spinner()
        if state.debate_skipped:
            elements.append(
                Text(f"{spinner} Preparing synthesis (debate skipped)...", style="dim")
            )
        else:
            elements.append(
                Text(f"{spinner} Awaiting debate conclusion...", style="dim")
            )

    # Build title with timing - show "Final Synthesis" when complete
    stage_time = get_stage_time(state, 3)
    time_suffix = f" [{stage_time}]" if stage_time else ""

    if state.pope_status == "complete":
        title = f"[bold {GREEN}]✓ Final Synthesis{time_suffix}[/bold {GREEN}]"
        border = GREEN
    else:
        title = f"[{SECONDARY}]Stage 3: Pope Synthesis{time_suffix}[/{SECONDARY}]"
        border = SECONDARY

    return Panel(Group(*elements), title=title, border_style=border, padding=(1, 2))


def build_error_panel(state: DebateState) -> Panel:
    """Build error panel with user-friendly messages."""
    error_msg = state.error

    # Make rate limit errors more user-friendly
    if "rate limit" in error_msg.lower():
        return Panel(
            Text.from_markup(
                "[bold yellow]Daily debate limit reached[/bold yellow]\n\n"
                "You've used all 10 free debates for today.\n"
                "Your limit resets at midnight UTC.\n\n"
                "[dim]Upgrade to Pro for unlimited debates: [cyan]synod.run/pricing[/cyan][/dim]"
            ),
            title="[yellow]⏰ Limit Reached[/yellow]",
            border_style="yellow",
            padding=(1, 2),
        )

    return Panel(
        Text(f"❌ {error_msg}", style="bold red"),
        title="[red]Error[/red]",
        border_style="red",
        padding=(1, 2),
    )


def build_final_synthesis(state: DebateState) -> Group:
    """Build the final synthesis output with proper markdown rendering.

    This is displayed after the live view ends, showing only the final result
    without re-displaying all the intermediate stages.
    """
    elements = []

    # Header with stats
    elapsed = time.time() - state.start_time
    header_parts = [
        f"✓ {format_model_name(state.pope)} synthesis complete",
    ]
    elements.append(Text(header_parts[0], style=f"bold {GREEN}"))
    elements.append(Text(""))

    # Stats line
    stats_parts = [f"⏱ {elapsed:.1f}s", f"📊 {state.total_tokens:,} tokens"]
    if state.cost_usd:
        stats_parts.append(f"💰 ${state.cost_usd:.4f}")
    if state.memories_retrieved > 0:
        stats_parts.append(f"🧠 {state.memories_retrieved} memories")
    if state.memories_stored > 0:
        stats_parts.append(f"💾 {state.memories_stored} learned")
    elements.append(Text(" | ".join(stats_parts), style="dim"))
    elements.append(Text(""))

    # Render the synthesis content with proper markdown
    # Use Markdown renderer for proper code highlighting
    if state.pope_content:
        md = Markdown(
            state.pope_content,
            code_theme="monokai",
            hyperlinks=False,
        )
        elements.append(md)

    return Group(*elements)


def build_tool_panel(state: DebateState) -> Optional[Panel]:
    """Build tool execution panel if there are tool calls."""
    if not state.tool_calls and not state.current_tool:
        return None

    elements = []

    # Show tools executed count
    if state.tools_executed > 0:
        elements.append(Text(f"🔧 {state.tools_executed} tools executed", style=GREEN))
        elements.append(Text(""))

    # Show current tool being executed
    if state.current_tool:
        tc = state.current_tool
        elements.append(
            Text(f"{get_spinner()} Executing: ", style=CYAN)
            + Text(tc.tool, style=f"bold {PRIMARY}")
        )

        # Show parameters - smart display based on tool type
        if tc.tool == "bash" and "command" in tc.parameters:
            # For bash, show the full command with wrapping
            cmd = tc.parameters["command"]
            # Create a Text object that will wrap naturally
            cmd_text = Text(overflow="fold")
            cmd_text.append("   $ ", style="dim")
            cmd_text.append(cmd, style="white")
            elements.append(cmd_text)
        elif tc.tool == "file_editor":
            # For file editor, show the operation and file path
            op = tc.parameters.get("operation", "unknown")
            path = tc.parameters.get("path", "")
            elements.append(Text(f"   {op}: ", style="dim") + Text(path, style="white"))
        elif tc.tool == "search":
            # For search, show query and path
            query = tc.parameters.get("query", "")
            path = tc.parameters.get("path", ".")
            elements.append(
                Text("   query: ", style="dim") + Text(query, style="white")
            )
            elements.append(Text("   path: ", style="dim") + Text(path, style="white"))
        else:
            # Generic: show all parameters with reasonable truncation
            for k, v in list(tc.parameters.items())[:5]:
                v_str = str(v)
                if len(v_str) > 100:
                    v_str = v_str[:100] + "..."
                param_text = Text(overflow="fold")
                param_text.append(f"   {k}: ", style="dim")
                param_text.append(v_str, style="white")
                elements.append(param_text)

    # Show recent completed tools
    completed = [tc for tc in state.tool_calls if tc.status == "complete"]
    if completed:
        elements.append(Text(""))
        for tc in completed[-5:]:  # Show last 5
            if tc.error:
                elements.append(
                    Text(f"  ✗ {tc.tool}: ", style="red")
                    + Text(tc.error[:80], style="dim")
                )
            else:
                elements.append(Text(f"  ✓ {tc.tool}", style=GREEN))

    if not elements:
        return None

    return Panel(
        Group(*elements),
        title=f"[{CYAN}]Tool Execution[/{CYAN}]",
        border_style=CYAN,
        padding=(0, 2),
    )


def get_current_action(state: DebateState) -> str:
    """Get human-readable description of current action based on state."""
    if state.error:
        return "Error occurred"

    if state.complete:
        return "Complete"

    # Stage 0: Analysis
    if state.stage == 0:
        if not state.memory_search_done and not state.classification_done:
            return "Analyzing query"
        elif not state.memory_search_done:
            return "Searching memories"
        elif not state.classification_done:
            return "Classifying complexity"
        else:
            return "Selecting bishops"

    # Stage 1: Proposals
    if state.stage == 1:
        running_bishops = [b for b, s in state.bishop_status.items() if s == "running"]
        if running_bishops:
            if len(running_bishops) == 1:
                return f"{format_model_name(running_bishops[0])} proposing"
            else:
                return f"{len(running_bishops)} bishops proposing"
        pending = [b for b, s in state.bishop_status.items() if s == "pending"]
        if pending:
            return "Awaiting proposals"
        return "Assessing consensus"

    # Stage 2: Critiques
    if state.stage == 2:
        if state.debate_skipped:
            return "Debate skipped (high consensus)"
        running_critics = [
            k for k, s in state.critique_status.items() if s == "running"
        ]
        if running_critics:
            if len(running_critics) == 1:
                parts = running_critics[0].split("→")
                if len(parts) == 2:
                    return f"{format_model_name(parts[0])} critiquing"
            return f"{len(running_critics)} critiques in parallel"
        if state.consensus_reached:
            return "Consensus reached"
        if state.debate_early_exit:
            return "Debate concluded"
        return f"Round {state.current_round} critiques"

    # Stage 3: Synthesis
    if state.stage == 3:
        if state.pope_status == "running":
            return f"Pope {format_model_name(state.pope)} synthesizing"
        elif state.pope_status == "complete":
            return "Synthesis complete"
        return "Preparing synthesis"

    return "Processing"


def get_parallel_activities(state: DebateState) -> List[str]:
    """Get list of activities happening in parallel for status display."""
    activities = []

    # Stage 1: Running bishops
    if state.stage == 1:
        for bishop, status in state.bishop_status.items():
            if status == "running":
                tokens = state.bishop_tokens.get(bishop, 0)
                activities.append(f"{format_model_name(bishop)}: {tokens} tokens")

    # Stage 2: Running critiques
    if state.stage == 2 and not state.debate_skipped:
        for key, status in state.critique_status.items():
            if status == "running":
                parts = key.split("→")
                if len(parts) == 2:
                    activities.append(
                        f"{format_model_name(parts[0])}→{format_model_name(parts[1])}"
                    )

    return activities


def build_status_bar(state: DebateState) -> Text:
    """Build clean status bar with minimal animation.

    Shows: [spinner] Action (parallel activities) · elapsed · ↓ tokens
    """
    # Get single animated element - keep it simple
    spinner = get_spinner()

    # Calculate elapsed time
    elapsed = int(time.time() - state.start_time)
    if elapsed < 60:
        time_str = f"{elapsed}s"
    elif elapsed < 3600:
        mins = elapsed // 60
        secs = elapsed % 60
        time_str = f"{mins}m {secs}s"
    else:
        hours = elapsed // 3600
        mins = (elapsed % 3600) // 60
        time_str = f"{hours}h {mins}m"

    # Get current action
    action = get_current_action(state)

    # Get parallel activities
    parallel = get_parallel_activities(state)

    # Build status text - clean and simple
    status = Text()

    # Spinner + action
    status.append(f" {spinner} ", style=f"bold {CYAN}")
    status.append(f"{action}", style=f"{CYAN}")

    # Parallel activities (if any)
    if parallel and len(parallel) <= 3:
        status.append(" (", style="dim")
        for i, activity in enumerate(parallel):
            if i > 0:
                status.append(" | ", style="dim")
            status.append(activity, style=f"dim {GOLD}")
        status.append(")", style="dim")
    elif parallel:
        status.append(f" ({len(parallel)} parallel)", style="dim")

    # Separator
    status.append(" · ", style="dim")

    # Elapsed time
    status.append(f"{time_str}", style="dim")
    status.append(" · ", style="dim")

    # Token counter with live accumulation indicator
    token_indicator = "↓" if not state.complete else "✓"
    status.append(
        f"{token_indicator} ", style=f"dim {'green' if state.complete else GOLD}"
    )
    status.append(
        f"{state.total_tokens:,}", style=f"{'green' if state.complete else GOLD}"
    )
    status.append(" tokens", style="dim")

    # Cost if available
    if state.cost_usd and state.cost_usd > 0:
        status.append(f" · ${state.cost_usd:.4f}", style="dim")

    # Trailing wave
    status.append(f" {get_wave()}", style=f"dim {CYAN}")

    return status


def build_display(state: DebateState) -> Group:
    """Build full display from current state.

    Shows all stages. With vertical_overflow="visible" on Live display,
    content scrolls naturally as new stages are added.
    """
    panels = []

    # Error takes precedence
    if state.error:
        panels.append(build_error_panel(state))
        return Group(*panels)

    # Stage 0: Analysis
    if state.stage >= 0:
        panels.append(build_analysis_panel(state))

    # Tool execution (if any)
    tool_panel = build_tool_panel(state)
    if tool_panel:
        panels.append(tool_panel)

    # Stage 1: Proposals
    if state.stage >= 1:
        panels.append(build_proposals_panel(state))

    # Stage 2: Critiques
    if state.stage >= 2:
        panels.append(build_critiques_panel(state))

    # Stage 3: Synthesis
    if state.stage >= 3:
        panels.append(build_synthesis_panel(state))

    # Status bar at bottom (only while in progress)
    if not state.complete and not state.error:
        panels.append(Text(""))  # Spacing
        panels.append(build_status_bar(state))

    return Group(*panels)


def build_current_stage_display(state: DebateState) -> Group:
    """Build display showing only the current active stage.

    Used with stage-by-stage printing where completed stages are printed
    permanently and only the current stage uses Live updates.
    """
    panels = []

    # Error takes precedence
    if state.error:
        panels.append(build_error_panel(state))
        return Group(*panels)

    # Only show the current stage panel
    if state.stage == 0:
        panels.append(build_analysis_panel(state))
    elif state.stage == 1:
        panels.append(build_proposals_panel(state))
    elif state.stage == 2:
        panels.append(build_critiques_panel(state))
    elif state.stage == 3:
        panels.append(build_synthesis_panel(state))

    # Tool execution (if any) - show alongside current stage
    tool_panel = build_tool_panel(state)
    if tool_panel:
        panels.append(tool_panel)

    # Status bar at bottom (only while in progress)
    if not state.complete and not state.error:
        panels.append(Text(""))  # Spacing
        panels.append(build_status_bar(state))

    return Group(*panels)


def get_completed_stage_panel(state: DebateState, stage: int) -> Optional[Panel]:
    """Get the panel for a completed stage to print permanently.

    Returns the appropriate panel builder for the given stage number.
    """
    if stage == 0:
        return build_analysis_panel(state)
    elif stage == 1:
        return build_proposals_panel(state)
    elif stage == 2:
        return build_critiques_panel(state)
    elif stage == 3:
        return build_synthesis_panel(state)
    return None


# ============================================================
# SSE Client
# ============================================================


async def stream_sse(
    url: str,
    api_key: str,
    query: str,
    context: Optional[str] = None,
    bishops: Optional[List[str]] = None,
    pope: Optional[str] = None,
    project_path: Optional[str] = None,
    files: Optional[Dict[str, str]] = None,  # Auto-context files
) -> AsyncIterator[dict]:
    """Stream SSE events from Synod Cloud.

    Yields:
        Parsed SSE event dictionaries
    """
    payload = {"query": query}

    # Build files payload (combines manual context with auto-context)
    files_payload = {}
    if context:
        files_payload["context"] = context
    if files:
        files_payload.update(files)
    if files_payload:
        payload["files"] = files_payload

    if bishops:
        payload["bishops"] = bishops
    if pope:
        payload["pope"] = pope
    if project_path:
        payload["project_path"] = project_path

    cli_version = get_version()

    async with httpx.AsyncClient(timeout=300.0) as client:
        async with client.stream(
            "POST",
            url,
            headers={
                "Authorization": api_key,
                "Content-Type": "application/json",
                "X-Synod-Version": cli_version,
            },
            json=payload,
        ) as response:
            if response.status_code == 426:
                # Upgrade Required - CLI version is incompatible
                error_body = await response.aread()
                try:
                    error_json = json.loads(error_body)
                    min_version = error_json.get("min_version", "unknown")
                except Exception:
                    min_version = "unknown"
                raise UpgradeRequiredError(min_version, cli_version)

            if response.status_code != 200:
                error_body = await response.aread()
                try:
                    error_json = json.loads(error_body)
                    yield {
                        "type": "error",
                        "message": error_json.get("error", "Unknown error"),
                    }
                except Exception:
                    yield {
                        "type": "error",
                        "message": f"HTTP {response.status_code}: {error_body.decode()}",
                    }
                return

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        event = json.loads(line[6:])
                        yield event
                    except json.JSONDecodeError:
                        pass


# ============================================================
# Tool Execution
# ============================================================


async def execute_tool_call(
    tool_call: ToolCall,
    working_directory: str,
    auto_approve: bool = False,
) -> Dict[str, Any]:
    """Execute a tool call locally and return the result.

    Args:
        tool_call: The tool call to execute
        working_directory: Working directory for tool execution
        auto_approve: If True, skip confirmation prompts for all tools
    """
    from synod.tools import ToolExecutor

    executor = ToolExecutor(working_directory)

    tool_call.status = "running"

    try:
        result = await executor.execute(
            tool_call.tool,
            tool_call.parameters,
            skip_confirmation=auto_approve,  # Prompt for confirmation unless auto_approve
        )

        tool_call.result = result.output
        if result.error:
            tool_call.error = result.error

        return {
            "call_id": tool_call.call_id,
            "status": result.status.value,
            "output": result.output,
            "error": result.error,
            "metadata": result.metadata,
        }

    except Exception as e:
        tool_call.status = "error"
        tool_call.error = str(e)
        return {
            "call_id": tool_call.call_id,
            "status": "error",
            "output": "",
            "error": str(e),
            "metadata": {},
        }


async def call_classify(
    api_url: str,
    api_key: str,
    query: str,
    bishops: Optional[List[str]] = None,
    pope: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Call the pre-flight /classify endpoint to get context_plan.

    Args:
        api_url: Base API URL (e.g., https://api.synod.run/debate)
        api_key: Synod API key
        query: The user's query
        bishops: Optional list of bishops
        pope: Optional pope model

    Returns:
        Classification result with context_plan, or None if failed
    """
    base_url = api_url.rstrip("/").replace("/debate", "")
    url = f"{base_url}/debate/classify"

    payload: Dict[str, Any] = {"query": query}
    if bishops:
        payload["bishops"] = bishops
    if pope:
        payload["pope"] = pope

    cli_version = get_version()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": api_key,
                    "Content-Type": "application/json",
                    "X-Synod-Version": cli_version,
                },
                json=payload,
            )

            if response.status_code == 426:
                # Upgrade Required - CLI version is incompatible
                try:
                    error_json = response.json()
                    min_version = error_json.get("min_version", "unknown")
                except Exception:
                    min_version = "unknown"
                raise UpgradeRequiredError(min_version, cli_version)

            if response.status_code == 200:
                return response.json()
            else:
                # Classification failed, return None (will fall back to old behavior)
                return None
    except UpgradeRequiredError:
        # Re-raise upgrade errors
        raise
    except Exception:
        # Network error, return None
        return None


async def gather_context_from_plan(
    context_plan: Dict[str, Any],
    root_path: str,
    max_tokens: int = 8000,
) -> Tuple[Dict[str, str], List[str]]:
    """Gather files based on context_plan from classifier.

    Args:
        context_plan: The context_plan from /classify response
        root_path: Root directory to search in
        max_tokens: Maximum tokens of file content to gather

    Returns:
        Tuple of (files dict, file_paths list)
    """
    if not context_plan.get("needs_codebase_search"):
        return {}, []

    searches = context_plan.get("searches", [])
    max_files = context_plan.get("max_files", 5)

    files: Dict[str, str] = {}
    file_paths: List[str] = []
    total_chars = 0
    max_chars = max_tokens * 4  # Rough estimate: 4 chars per token

    for search in searches:
        if len(file_paths) >= max_files:
            break

        patterns = search.get("patterns", [])
        file_types = search.get("file_types", [])
        limit = search.get("limit", 3)

        for pattern in patterns:
            if len(file_paths) >= max_files:
                break

            # Try to find files matching the pattern
            found_files = await _search_files(root_path, pattern, file_types, limit)

            for file_path in found_files:
                if len(file_paths) >= max_files:
                    break
                if file_path in file_paths:
                    continue

                # Read file content
                try:
                    full_path = (
                        os.path.join(root_path, file_path)
                        if not os.path.isabs(file_path)
                        else file_path
                    )
                    if os.path.exists(full_path) and os.path.isfile(full_path):
                        with open(
                            full_path, "r", encoding="utf-8", errors="ignore"
                        ) as f:
                            content = f.read()

                        # Check token budget
                        if total_chars + len(content) > max_chars:
                            # Truncate or skip
                            remaining = max_chars - total_chars
                            if (
                                remaining > 1000
                            ):  # Only include if we can get meaningful content
                                content = (
                                    content[:remaining] + "\n\n[... truncated ...]"
                                )
                            else:
                                continue

                        files[file_path] = content
                        file_paths.append(file_path)
                        total_chars += len(content)
                except Exception:
                    pass

    return files, file_paths


async def _search_files(
    root_path: str,
    pattern: str,
    file_types: List[str],
    limit: int,
) -> List[str]:
    """Search for files matching a pattern.

    Args:
        root_path: Root directory to search in
        pattern: Search pattern (filename or keyword)
        file_types: File extensions to filter (e.g., ['py', 'ts'])
        limit: Maximum number of files to return

    Returns:
        List of relative file paths
    """
    import glob as glob_module

    results: List[str] = []

    # Build glob patterns
    if "." in pattern and "*" not in pattern:
        # Looks like a filename - search for exact match
        glob_patterns = [f"**/{pattern}"]
    else:
        # Keyword search - try various patterns
        if file_types:
            glob_patterns = [f"**/*{pattern}*.{ext}" for ext in file_types]
            glob_patterns += [f"**/{pattern}*.{ext}" for ext in file_types]
        else:
            glob_patterns = [f"**/*{pattern}*"]

    for glob_pattern in glob_patterns:
        if len(results) >= limit:
            break

        try:
            full_pattern = os.path.join(root_path, glob_pattern)
            for match in glob_module.glob(full_pattern, recursive=True):
                if len(results) >= limit:
                    break
                if os.path.isfile(match):
                    # Get relative path
                    rel_path = os.path.relpath(match, root_path)
                    # Skip common non-code directories
                    if any(
                        skip in rel_path
                        for skip in [
                            "node_modules",
                            ".git",
                            "__pycache__",
                            ".venv",
                            "venv",
                            "dist",
                            "build",
                        ]
                    ):
                        continue
                    if rel_path not in results:
                        results.append(rel_path)
        except Exception:
            pass

    return results


async def send_tool_results(
    api_url: str,
    api_key: str,
    debate_id: str,
    results: List[Dict[str, Any]],
) -> AsyncIterator[dict]:
    """Send tool execution results back to the cloud and stream the response.

    Args:
        api_url: Base API URL
        api_key: Synod API key
        debate_id: ID of the debate
        results: List of tool results to send

    Yields:
        SSE events from the continued synthesis
    """
    # Construct the tool-result endpoint URL
    base_url = api_url.rstrip("/").replace("/debate", "")
    url = f"{base_url}/debate/{debate_id}/tool-result"

    payload = {
        "results": [
            {
                "call_id": r["call_id"],
                "content": r.get("output", ""),
                "is_error": r.get("status") == "error",
            }
            for r in results
        ]
    }

    cli_version = get_version()

    async with httpx.AsyncClient(timeout=300.0) as client:
        async with client.stream(
            "POST",
            url,
            headers={
                "Authorization": api_key,
                "Content-Type": "application/json",
                "X-Synod-Version": cli_version,
            },
            json=payload,
        ) as response:
            if response.status_code == 426:
                # Upgrade Required - CLI version is incompatible
                error_body = await response.aread()
                try:
                    error_json = json.loads(error_body)
                    min_version = error_json.get("min_version", "unknown")
                except Exception:
                    min_version = "unknown"
                raise UpgradeRequiredError(min_version, cli_version)

            if response.status_code != 200:
                error_body = await response.aread()
                try:
                    error_json = json.loads(error_body)
                    yield {
                        "type": "error",
                        "message": error_json.get("error", "Unknown error"),
                    }
                except Exception:
                    yield {
                        "type": "error",
                        "message": f"HTTP {response.status_code}: {error_body.decode()}",
                    }
                return

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        event = json.loads(line[6:])
                        yield event
                    except json.JSONDecodeError:
                        pass


# ============================================================
# Main Entry Point
# ============================================================


async def run_cloud_debate(
    api_key: str,
    query: str,
    context: Optional[str] = None,
    bishops: Optional[List[str]] = None,
    pope: Optional[str] = None,
    api_url: str = "https://api.synod.run/debate",
    working_directory: Optional[str] = None,
    project_path: Optional[str] = None,
    auto_approve: bool = False,
) -> DebateState:
    """Run a debate via Synod Cloud with live display.

    Args:
        api_key: Synod API key (sk_live_...)
        query: The coding question
        context: Optional file context
        bishops: Optional list of bishop models to use
        pope: Optional pope model to use
        api_url: Cloud API URL
        working_directory: Directory for tool execution (default: cwd)
        project_path: Project path for memory scoping (default: working_directory)
        auto_approve: If True, automatically approve all tool executions without prompting

    Returns:
        Final DebateState with results
    """
    state = DebateState()
    state.stage_start_times[0] = state.start_time  # Stage 0 starts immediately
    work_dir = working_directory or os.getcwd()
    proj_path = project_path or work_dir

    pending_tool_results: List[Dict[str, Any]] = []
    live: Optional[Live] = None

    # Track which stages have been printed permanently
    printed_stages: set = set()

    async def process_stream(event_stream, collect_tools: bool = True):
        """Process an SSE stream with Live display.

        Returns True if stream completed normally, False if interrupted for tools.
        When tools are requested, we wait for stream to end to collect ALL tool calls.

        Stage-by-stage display: When a stage completes and we move to the next,
        we print the completed stage permanently and restart Live for only the
        current stage. This allows natural terminal scrolling.
        """
        nonlocal live, pending_tool_results, printed_stages

        event_iter = event_stream.__aiter__()
        pending_task: Optional[asyncio.Task] = None
        stream_done = False
        need_tool_execution = False
        collected_tools: List[ToolCall] = []  # Collect all tool calls from this batch

        def handle_stage_transition(event):
            """Handle stage transition: print completed stage, restart Live."""
            nonlocal live, printed_stages

            new_stage = event.get("stage", 0)
            old_stage = state.stage

            # If moving to a new stage, print the completed stage permanently
            if new_stage > old_stage and old_stage not in printed_stages:
                if live:
                    live.stop()

                # Print the completed stage panel permanently
                completed_panel = get_completed_stage_panel(state, old_stage)
                if completed_panel:
                    console.print(completed_panel)
                printed_stages.add(old_stage)

                # Now update state with the new stage
                handle_event(state, event)

                # Start new Live for the current stage only
                live = Live(console=console, auto_refresh=False, transient=False)
                live.start()
                live.update(build_current_stage_display(state), refresh=True)
                return True  # Handled

            return False  # Not a stage transition, handle normally

        try:
            while not stream_done:
                try:
                    if pending_task is None:
                        pending_task = asyncio.create_task(event_iter.__anext__())

                    done, _ = await asyncio.wait({pending_task}, timeout=0.1)

                    if done:
                        try:
                            event = pending_task.result()
                            pending_task = None
                        except StopAsyncIteration:
                            stream_done = True
                            continue

                        event_type = event.get("type")

                        # Handle stage transitions specially
                        if event_type == "stage":
                            if handle_stage_transition(event):
                                continue  # Already handled

                        if event_type == "tool_call":
                            handle_event(state, event)
                            if live:
                                live.update(build_current_stage_display(state), refresh=True)
                            # Collect tool for later execution - don't break yet
                            if state.current_tool and collect_tools:
                                collected_tools.append(state.current_tool)
                                need_tool_execution = True
                                # DON'T break - wait for all tool_call events

                        elif event_type == "complete":
                            handle_event(state, event)
                            # Print final stage before showing complete
                            if state.stage not in printed_stages:
                                if live:
                                    live.stop()
                                completed_panel = get_completed_stage_panel(state, state.stage)
                                if completed_panel:
                                    console.print(completed_panel)
                                printed_stages.add(state.stage)
                                live = None  # No more live updates needed
                            elif live:
                                live.update(build_current_stage_display(state), refresh=True)
                            stream_done = True

                        elif event_type == "error":
                            handle_event(state, event)
                            if live:
                                live.update(build_current_stage_display(state), refresh=True)
                            stream_done = True

                        else:
                            handle_event(state, event)
                            if live:
                                live.update(build_current_stage_display(state), refresh=True)
                    else:
                        advance_animation()
                        # During synthesis, only refresh every 5th frame to reduce flicker
                        if live:
                            if state.stage == 3 and state.pope_status == "running":
                                if _frame_idx % 5 == 0:
                                    live.update(build_current_stage_display(state), refresh=True)
                            else:
                                live.update(build_current_stage_display(state), refresh=True)

                except StopAsyncIteration:
                    stream_done = True

        except httpx.ReadError as e:
            state.error = f"Network error: {str(e)}"
            if live:
                live.update(build_current_stage_display(state), refresh=True)

        except GeneratorExit:
            pass

        except Exception as e:
            if not state.error:
                state.error = f"Unexpected error: {str(e)}"
                if live:
                    live.update(build_current_stage_display(state), refresh=True)

        finally:
            if pending_task is not None and not pending_task.done():
                pending_task.cancel()
                try:
                    await pending_task
                except (asyncio.CancelledError, StopAsyncIteration, GeneratorExit):
                    pass
            try:
                await event_stream.aclose()
            except Exception:
                pass

        # Store collected tools for execution
        if collected_tools:
            state.pending_tool_batch = collected_tools

        return not need_tool_execution

    # Phase 1: Pre-flight classification + smart context gathering
    # Stage 0 uses its own Live display, will be printed when moving to Stage 1
    live = Live(console=console, auto_refresh=False, transient=False)
    live.start()
    live.update(build_current_stage_display(state), refresh=True)

    # Step 1: Call /classify to get context_plan
    classify_task = asyncio.create_task(
        call_classify(
            api_url=api_url,
            api_key=api_key,
            query=query,
            bishops=bishops,
            pope=pope,
        )
    )

    while not classify_task.done():
        try:
            await asyncio.wait_for(asyncio.shield(classify_task), timeout=0.1)
        except asyncio.TimeoutError:
            advance_animation()
            live.update(build_current_stage_display(state), refresh=True)

    classification = classify_task.result()

    # Step 2: Gather context based on context_plan (or fall back to old method)
    auto_files: Dict[str, str] = {}
    auto_file_paths: List[str] = []

    if classification and classification.get("context_plan"):
        # Use smart AI-driven context gathering
        context_plan = classification["context_plan"]
        max_tokens = context_plan.get("max_tokens", 8000)

        gather_task = asyncio.create_task(
            gather_context_from_plan(
                context_plan=context_plan,
                root_path=proj_path,
                max_tokens=max_tokens,
            )
        )

        while not gather_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(gather_task), timeout=0.1)
            except asyncio.TimeoutError:
                advance_animation()
                live.update(build_current_stage_display(state), refresh=True)

        auto_files, auto_file_paths = gather_task.result()

        # Store context plan in state for display
        if context_plan.get("searches"):
            state.context_plan_searches = [
                s.get("intent", "") for s in context_plan["searches"]
            ]
    else:
        # Fall back to old keyword-based context gathering
        fallback_task = asyncio.create_task(
            gather_auto_context(
                query=query,
                root_path=proj_path,
            )
        )

        while not fallback_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(fallback_task), timeout=0.1)
            except asyncio.TimeoutError:
                advance_animation()
                live.update(build_current_stage_display(state), refresh=True)

        auto_files, auto_file_paths = fallback_task.result()

    if auto_file_paths:
        state.auto_context_files = auto_file_paths
        live.update(build_current_stage_display(state), refresh=True)

    # Phase 2: Process initial debate stream
    event_stream = stream_sse(
        url=api_url,
        api_key=api_key,
        query=query,
        context=context,
        bishops=bishops,
        pope=pope,
        project_path=proj_path,
        files=auto_files if auto_files else None,
    )

    stream_complete = await process_stream(event_stream)

    # Phase 3: Tool execution loop (if needed)
    # Execute ALL tools in the batch, then send ALL results together
    MAX_TOOL_ROUNDS = 10
    round_count = 0

    while state.pending_tool_batch and round_count < MAX_TOOL_ROUNDS:
        round_count += 1

        # Stop Live display for tool execution (allows user prompts)
        if live:
            live.stop()
            live = None

        # Execute ALL tools in the batch
        tools_to_execute = state.pending_tool_batch[:]
        state.pending_tool_batch.clear()

        for tool in tools_to_execute:
            state.current_tool = tool
            result = await execute_tool_call(tool, work_dir, auto_approve)
            pending_tool_results.append(result)
            state.current_tool = None

        # Send ALL tool results together and continue
        if pending_tool_results and state.debate_id:
            results_to_send = pending_tool_results[:]
            pending_tool_results.clear()

            # Start new Live display for continued streaming
            live = Live(console=console, auto_refresh=False, transient=False)
            live.start()
            live.update(build_current_stage_display(state), refresh=True)

            tool_stream = send_tool_results(
                api_url, api_key, state.debate_id, results_to_send
            )
            stream_complete = await process_stream(tool_stream)

            if stream_complete:
                break

    # Cleanup
    if not state.complete and not state.error:
        state.error = "Connection to server closed unexpectedly. Please try again."

    # Always stop live display if it exists
    if live:
        live.stop()

    # With stage-by-stage printing, completed stages are already printed
    # Only print error state separately if there was an error
    if state.error:
        console.print()
        console.print(build_error_panel(state))

    return state


# ============================================================
# Synchronous wrapper for CLI
# ============================================================


def run_debate_sync(
    api_key: str,
    query: str,
    context: Optional[str] = None,
    bishops: Optional[List[str]] = None,
    pope: Optional[str] = None,
    api_url: str = "https://api.synod.run/debate",
    auto_approve: bool = False,
) -> DebateState:
    """Synchronous wrapper for run_cloud_debate.

    Args:
        auto_approve: If True, automatically approve all tool executions without prompting
    """
    return asyncio.run(
        run_cloud_debate(
            api_key, query, context, bishops, pope, api_url, auto_approve=auto_approve
        )
    )
