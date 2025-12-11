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
from typing import Optional, Dict, List, Any, AsyncIterator, Callable, Awaitable

import httpx
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.markdown import Markdown
from rich.spinner import Spinner
from rich.syntax import Syntax
from rich import box

from .theme import PRIMARY, CYAN, ACCENT, SECONDARY, GOLD, GREEN, GRAY, format_model_name
from .display import get_version
from .auto_context import gather_auto_context, display_auto_context_summary

console = Console()


# ============================================================
# SSE Event Types (mirrors cloud types)
# ============================================================

@dataclass
class CritiqueSummary:
    """Summary of a single critique for grid display."""
    critic: str
    target: str
    severity: str  # 'critical' | 'moderate' | 'minor'
    summary: str   # One-line summary


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
    bishop_status: Dict[str, str] = field(default_factory=dict)  # model -> 'pending'|'running'|'complete'
    bishop_content: Dict[str, str] = field(default_factory=dict)  # model -> content
    bishop_tokens: Dict[str, int] = field(default_factory=dict)  # model -> tokens
    bishop_approach: Dict[str, str] = field(default_factory=dict)  # model -> approach summary

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
    critique_status: Dict[str, str] = field(default_factory=dict)  # "critic->target" -> 'running'|'complete'
    critique_content: Dict[str, str] = field(default_factory=dict)
    critique_severity: Dict[str, str] = field(default_factory=dict)  # "critic->target" -> severity
    critique_summaries: List[CritiqueSummary] = field(default_factory=list)  # For grid display
    running_critiques: List[Dict[str, str]] = field(default_factory=list)  # [{critic, target}, ...] for in-progress
    consensus_reached: bool = False
    consensus_reached_round: int = 0

    # Pope synthesis
    pope_status: str = "pending"
    pope_content: str = ""
    pope_tokens: int = 0

    # Memory
    memories_retrieved: int = 0
    memories_stored: int = 0
    memory_tokens: int = 0

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

    # Tool execution
    tool_calls: List[ToolCall] = field(default_factory=list)
    current_tool: Optional[ToolCall] = None
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
    stage_start_times: Dict[int, float] = field(default_factory=dict)  # stage -> start time
    stage_end_times: Dict[int, float] = field(default_factory=dict)    # stage -> end time


# ============================================================
# SSE Event Handlers
# ============================================================

def handle_event(state: DebateState, event: dict) -> None:
    """Update state based on SSE event."""
    event_type = event.get('type')

    if event_type == 'stage':
        # End previous stage timing (if any)
        prev_stage = state.stage
        if prev_stage in state.stage_start_times and prev_stage not in state.stage_end_times:
            state.stage_end_times[prev_stage] = time.time()

        # Start new stage timing (don't overwrite if already set, e.g. stage 0)
        state.stage = event['stage']
        state.stage_name = event['name']
        if state.stage not in state.stage_start_times:
            state.stage_start_times[state.stage] = time.time()

    elif event_type == 'analysis_complete':
        state.complexity = event['complexity']
        state.domains = event['domains']
        state.bishops = event['bishops']
        state.pope = event['pope']
        state.reasoning = event.get('reasoning', '')
        state.bishop_status = {b: 'pending' for b in state.bishops}
        state.classification_done = True
        # Mark stage 0 as complete
        if 0 not in state.stage_end_times:
            state.stage_end_times[0] = time.time()

    elif event_type == 'context_hints':
        # Context analysis from the API
        state.context_hints_received = True
        query_analysis = event.get('query_analysis', {})
        state.search_keywords = query_analysis.get('keywords', [])
        state.search_symbols = query_analysis.get('symbol_names', [])
        state.language_hints = query_analysis.get('language_hints', [])
        search_strategy = event.get('search_strategy', {})
        state.search_type = search_strategy.get('search_type', '')
        state.memory_hints = event.get('memory_hints', [])

    elif event_type == 'bishop_start':
        state.bishop_status[event['model']] = 'running'

    elif event_type == 'bishop_summary':
        # Quick approach summary for grid display
        state.bishop_approach[event['model']] = event['approach']

    elif event_type == 'bishop_complete':
        state.bishop_status[event['model']] = 'complete'
        state.bishop_tokens[event['model']] = event['tokens']

    elif event_type == 'bishop_content':
        state.bishop_content[event['model']] = event['content']

    elif event_type == 'consensus':
        state.consensus_score = event['score']

    # Pope Assessment (before critiques)
    elif event_type == 'pope_assessment':
        state.pope_assessment_done = True
        state.should_debate = event['shouldDebate']
        state.overall_similarity = event['overallSimilarity']
        state.assessment_reasoning = event['reasoning']
        state.disagreement_pairs = event.get('disagreementPairs', [])

    elif event_type == 'debate_skipped':
        state.debate_skipped = True
        state.debate_skip_reason = event['reason']

    # Critique rounds
    elif event_type == 'critique_round_start':
        state.current_round = event['round']
        state.max_rounds = event['maxRounds']
        state.critique_pairs = event['pairs']

    elif event_type == 'critique_start':
        critic = event['critic']
        targets = event.get('targets', [])
        target = targets[0] if targets else 'unknown'
        key = f"{critic}->{target}"
        state.critique_status[key] = 'running'
        # Track running critique for display
        state.running_critiques.append({'critic': critic, 'target': target})

    elif event_type == 'critique_summary':
        # One-line summary for grid display
        critic = event['critic']
        target = event['target']
        key = f"{critic}->{target}"
        # Mark as complete
        state.critique_status[key] = 'complete'
        state.critique_severity[key] = event['severity']
        # Remove from running critiques
        state.running_critiques = [c for c in state.running_critiques
                                   if not (c['critic'] == critic and c['target'] == target)]
        # Add to summaries (avoid duplicates)
        new_summary = CritiqueSummary(
            critic=critic,
            target=target,
            severity=event['severity'],
            summary=event['summary']
        )
        existing = [(c.critic, c.target) for c in state.critique_summaries]
        if (new_summary.critic, new_summary.target) not in existing:
            state.critique_summaries.append(new_summary)

    elif event_type == 'critique_complete':
        # Also handle critique_complete (backup for critique_summary)
        critic = event.get('critic', '')
        target = event.get('target', '')
        if critic and target:
            key = f"{critic}->{target}"
            state.critique_status[key] = 'complete'
            state.critique_severity[key] = event.get('severity', 'minor')
            state.running_critiques = [c for c in state.running_critiques
                                       if not (c['critic'] == critic and c['target'] == target)]

    elif event_type == 'critique_content':
        state.critique_content[event['critic']] = event['content']

    elif event_type == 'critique_round_complete':
        state.consensus_score = event['consensusScore']

    elif event_type == 'consensus_reached':
        state.consensus_reached = True
        state.consensus_reached_round = event['round']
        state.consensus_score = event['score']

    # Memory events
    elif event_type == 'memory_retrieved':
        state.memories_retrieved = event.get('user_memories', 0) + event.get('project_memories', 0)
        state.memory_tokens = event.get('tokens', 0)
        state.memory_search_done = True

    elif event_type == 'memory_extracted':
        state.memories_stored = event.get('stored', 0)

    # Pope synthesis
    elif event_type == 'pope_start':
        state.pope_status = 'running'

    elif event_type == 'pope_stream':
        state.pope_content += event['chunk']

    elif event_type == 'pope_complete':
        state.pope_status = 'complete'
        state.pope_content = event['content']
        state.pope_tokens = event['tokens']

    elif event_type == 'complete':
        state.complete = True
        state.debate_id = event['debate_id']
        state.total_tokens = event['total_tokens']
        state.duration_ms = event['duration_ms']
        state.cost_usd = event.get('cost_usd')
        state.memories_retrieved = event.get('memories_retrieved', state.memories_retrieved)
        state.memories_stored = event.get('memories_stored', state.memories_stored)
        # End final stage timing
        if state.stage in state.stage_start_times and state.stage not in state.stage_end_times:
            state.stage_end_times[state.stage] = time.time()

    elif event_type == 'error':
        state.error = event['message']

    # Tool execution events
    elif event_type == 'tools_required':
        # Receive debate_id early so we can send tool results back
        state.debate_id = event['debate_id']

    elif event_type == 'tool_call':
        tool_call = ToolCall(
            call_id=event['call_id'],
            tool=event['tool'],
            parameters=event.get('parameters', {}),
            status='pending',
        )
        state.tool_calls.append(tool_call)
        state.current_tool = tool_call

    elif event_type == 'tool_result_ack':
        # Cloud acknowledged our tool result
        call_id = event.get('call_id')
        for tc in state.tool_calls:
            if tc.call_id == call_id:
                tc.status = 'complete'
                state.tools_executed += 1
                break
        state.current_tool = None


# ============================================================
# Display Rendering
# ============================================================

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
THINKING_FRAMES = ["🧠", "💭", "💡", "✨", "🔮", "⚡"]
STREAMING_FRAMES = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█", "▇", "▆", "▅", "▄", "▃", "▂"]
PULSE_FRAMES = ["◉", "◎", "○", "◎"]
# Mesmerizing gradient wave frames for status bar
WAVE_FRAMES = ["░▒▓█▓▒░", "▒▓█▓▒░░", "▓█▓▒░░▒", "█▓▒░░▒▓", "▓▒░░▒▓█", "▒░░▒▓█▓", "░░▒▓█▓▒", "░▒▓█▓▒░"]
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
        duration = state.stage_end_times[stage] - state.stage_start_times.get(stage, state.start_time)
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
            'trivial': GREEN,
            'simple': CYAN,
            'moderate': GOLD,
            'complex': PRIMARY,
            'expert': 'red'
        }
        color = complexity_colors.get(state.complexity, CYAN)
        elements.append(Text(f"Complexity: ", style="dim") + Text(state.complexity.upper(), style=f"bold {color}"))

        # Domains
        if state.domains:
            elements.append(Text(f"Domains: ", style="dim") + Text(", ".join(state.domains), style=CYAN))

        # Memory retrieved
        if state.memories_retrieved > 0:
            elements.append(Text(f"Memory: ", style="dim") + Text(f"{state.memories_retrieved} relevant learnings found ({state.memory_tokens} tokens)", style=CYAN))
        elif state.memory_search_done:
            elements.append(Text(f"Memory: ", style="dim") + Text("No prior learnings found (fresh query)", style="dim"))

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
                elements.append(Text(f"Context: ", style="dim") + Text(" | ".join(hints_parts), style="dim"))

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

        elements.append(Text(f"{think} Stage 0: Analysis in Progress", style=f"bold {CYAN}"))
        elements.append(Text(""))

        # Show what's happening in parallel
        # Memory search status
        if state.memory_search_done:
            if state.memories_retrieved > 0:
                elements.append(Text(f"  ✓ Memory search: ", style="dim") +
                              Text(f"{state.memories_retrieved} learnings found", style=GREEN))
            else:
                elements.append(Text(f"  ✓ Memory search: ", style="dim") +
                              Text("No prior context", style="dim"))
        else:
            elements.append(Text(f"  {spinner} Memory search: ", style="dim") +
                          Text(f"Searching vector database {bar}", style=CYAN))

        # Query classification status
        if state.classification_done:
            elements.append(Text(f"  ✓ Classification: ", style="dim") +
                          Text("Complete", style=GREEN))
        else:
            elements.append(Text(f"  {spinner} Classification: ", style="dim") +
                          Text(f"Analyzing complexity & selecting bishops {pulse}", style=CYAN))

        # Context hints status
        if state.context_hints_received:
            elements.append(Text(f"  ✓ Context analysis: ", style="dim") +
                          Text("Ready", style=GREEN))
            if state.search_keywords:
                elements.append(Text(f"      Keywords: {', '.join(state.search_keywords[:4])}", style="dim"))
        else:
            elements.append(Text(f"  {spinner} Context analysis: ", style="dim") +
                          Text(f"Extracting search hints {bar}", style=CYAN))

    # Build title with timing
    stage_time = get_stage_time(state, 0)
    time_suffix = f" [{stage_time}]" if stage_time else ""

    return Panel(
        Group(*elements),
        title=f"[{CYAN}]Stage 0: Analysis{time_suffix}[/{CYAN}]",
        border_style=CYAN,
        padding=(0, 2)
    )


def build_proposals_panel(state: DebateState) -> Panel:
    """Build Stage 1 proposals panel with grid display."""
    elements = []

    # Pope observer with calm watching animation
    observer = get_pope_observe()
    pulse = get_pulse()
    elements.append(Text(f"👑 Pope {format_model_name(state.pope)} observing ", style="grey50") +
                   Text(f"{observer} {pulse}", style=GOLD))
    elements.append(Text(""))

    # Build grid table for bishops
    if state.bishops:
        table = Table(box=box.ROUNDED, show_header=True, header_style=f"bold {CYAN}", expand=True)

        # Add columns for each bishop
        for bishop in state.bishops:
            table.add_column(format_model_name(bishop), justify="center", width=25)

        # Status row with enhanced animations
        status_cells = []
        for bishop in state.bishops:
            status = state.bishop_status.get(bishop, 'pending')
            if status == 'complete':
                tokens = state.bishop_tokens.get(bishop, 0)
                status_cells.append(Text(f"✓ {tokens} tokens", style=GREEN))
            elif status == 'running':
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
    all_complete = all(state.bishop_status.get(b) == 'complete' for b in state.bishops) if state.bishops else False
    if all_complete and state.bishop_content:
        elements.append(Text(""))
        elements.append(Text("📜 Bishop Proposals:", style=f"bold {PRIMARY}"))
        for bishop in state.bishops:
            content = state.bishop_content.get(bishop, "")
            if content:
                # Show first 200 chars with expand indicator
                tokens = state.bishop_tokens.get(bishop, 0)
                preview = content[:300].replace('\n', ' ')
                if len(content) > 300:
                    preview += "..."
                elements.append(Text(""))
                elements.append(Text(f"  {format_model_name(bishop)} ", style=f"bold {CYAN}") +
                              Text(f"({tokens} tokens)", style="dim"))
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
        elements.append(Text(f"📊 Consensus: ", style="dim") + Text(f"{score_pct}% ({label})", style=f"bold {style}"))

    # Pope assessment result
    if state.pope_assessment_done:
        elements.append(Text(""))
        sim_pct = int(state.overall_similarity * 100)
        if state.should_debate:
            elements.append(Text(f"⚖️ Pope Assessment: ", style="dim") +
                          Text(f"{sim_pct}% similarity - debate needed", style=GOLD))
            if state.disagreement_pairs:
                pairs_str = ", ".join([f"{p['bishop1']} vs {p['bishop2']}" for p in state.disagreement_pairs[:2]])
                elements.append(Text(f"   Disagreements: {pairs_str}", style="dim"))
        else:
            elements.append(Text(f"⚖️ Pope Assessment: ", style="dim") +
                          Text(f"{sim_pct}% similarity - skipping debate", style=GREEN))

    # Build title with timing
    stage_time = get_stage_time(state, 1)
    time_suffix = f" [{stage_time}]" if stage_time else ""

    return Panel(
        Group(*elements),
        title=f"[{CYAN}]Stage 1: Bishop Proposals{time_suffix}[/{CYAN}]",
        border_style=CYAN,
        padding=(0, 2)
    )


def build_critiques_panel(state: DebateState) -> Panel:
    """Build Stage 2 critiques panel with summary grid."""
    elements = []

    # Build title with timing
    stage_time = get_stage_time(state, 2)
    time_suffix = f" [{stage_time}]" if stage_time else ""

    # Check if debate was skipped
    if state.debate_skipped:
        elements.append(Text(f"✓ Debate skipped: {state.debate_skip_reason}", style=GREEN))
        return Panel(
            Group(*elements),
            title=f"[{GOLD}]Stage 2: Adversarial Critiques{time_suffix}[/{GOLD}]",
            border_style=GOLD,
            padding=(0, 2)
        )

    # Round info with progress indicator and explanation
    if state.current_round > 0:
        round_text = Text()
        if state.stage >= 3:
            # Stage 2 complete - static display
            round_text.append(f"🛡️ Completed {state.current_round} round{'s' if state.current_round > 1 else ''}", style=f"bold {GOLD}")
        else:
            # Still in progress
            round_text.append(f"🛡️ Round {state.current_round} of {state.max_rounds}", style=f"bold {GOLD}")
        round_text.append(f" • ", style="dim")
        round_text.append(f"{state.critique_pairs} disagreeing pairs", style=GOLD)
        elements.append(round_text)
        # Explain what determines rounds (only during active phase)
        if state.current_round == 1 and state.stage < 3:
            elements.append(Text("   Rounds continue until consensus (>85%) or max rounds reached", style="dim italic"))
    else:
        spinner = get_spinner()
        elements.append(Text(f"🛡️ {spinner} Adversarial critique phase starting...", style=GOLD))

    # Pope presiding - show animation only during active critiques, static when done
    if state.stage >= 3 or state.consensus_reached:
        # Stage 2 complete - static display
        elements.append(Text(f"👑 Pope {format_model_name(state.pope)} presided", style="grey50"))
    else:
        # Active - show animation
        preside = get_pope_preside()
        pulse = get_pulse()
        elements.append(Text(f"👑 Pope {format_model_name(state.pope)} presiding ", style="grey50") +
                       Text(f"{preside} {pulse}", style=GOLD))
    elements.append(Text(""))

    # Show running critiques first (with spinner only - no redundant animations)
    if state.running_critiques:
        for crit in state.running_critiques:
            spinner = get_spinner()
            row_text = Text()
            row_text.append(f"  {spinner} ", style=CYAN)
            row_text.append(f"{format_model_name(crit['critic'])}", style=CYAN)
            row_text.append(" → ", style="dim")
            row_text.append(f"{format_model_name(crit['target'])} ", style=CYAN)
            row_text.append("critiquing", style="dim italic")
            elements.append(row_text)

    # Show completed critiques (with checkmarks and summaries)
    if state.critique_summaries:
        for crit in state.critique_summaries:
            severity_color = {'critical': 'red', 'moderate': GOLD, 'minor': GREEN}.get(crit.severity, GREEN)
            row_text = Text()
            row_text.append(f"  ✓ ", style=GREEN)
            row_text.append(f"{format_model_name(crit.critic)}", style=CYAN)
            row_text.append(" → ", style="dim")
            row_text.append(f"{format_model_name(crit.target)} ", style=CYAN)
            row_text.append(f"[{crit.severity.upper()}] ", style=f"bold {severity_color}")
            row_text.append(crit.summary[:60], style="dim")
            elements.append(row_text)

    # Consensus reached?
    if state.consensus_reached:
        elements.append(Text(""))
        score_pct = int(state.consensus_score * 100) if state.consensus_score else 0
        consensus_text = Text()
        consensus_text.append("✓ ", style=GREEN)
        consensus_text.append(f"Consensus reached!", style=f"bold {GREEN}")
        consensus_text.append(f" ({score_pct}% agreement after round {state.consensus_reached_round})", style="dim")
        elements.append(consensus_text)
        if state.consensus_reached_round < state.max_rounds:
            elements.append(Text(f"   Remaining {state.max_rounds - state.consensus_reached_round} rounds skipped", style="dim italic"))

    # Show completion status in title when stage 2 is done
    if state.stage >= 3:
        title = f"[{GOLD}]Stage 2: Adversarial Critiques{time_suffix} ✓[/{GOLD}]"
    else:
        title = f"[{GOLD}]Stage 2: Adversarial Critiques{time_suffix}[/{GOLD}]"

    return Panel(
        Group(*elements),
        title=title,
        border_style=GOLD,
        padding=(0, 2)
    )


def build_synthesis_panel(state: DebateState) -> Panel:
    """Build Stage 3 synthesis panel for live display."""
    elements = []

    if state.pope_status == 'complete':
        # Complete - show full synthesis content with stats
        elapsed = (time.time() - state.start_time)
        elements.append(Text(f"✓ {format_model_name(state.pope)} synthesis complete", style=f"bold {GREEN}"))
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

        # Show full synthesis content with markdown rendering
        if state.pope_content:
            md = Markdown(state.pope_content, code_theme="monokai")
            elements.append(md)

    elif state.pope_status == 'running':
        # Pope is synthesizing - clean animation (thinking indicator only)
        think = get_thinking_indicator()
        elements.append(Text(f"👑 {think} ", style=SECONDARY) +
                       Text(f"{format_model_name(state.pope)} synthesizing", style=f"bold {SECONDARY}"))

        if state.pope_content:
            elements.append(Text(""))
            # Show streaming content preview with markdown rendering
            content = state.pope_content
            lines = content.split('\n')
            # Show last 15 lines for streaming effect
            if len(lines) > 15:
                visible_content = '\n'.join(lines[-15:])
                elements.append(Text(f"... ({len(lines) - 15} lines above)", style="dim"))
            else:
                visible_content = content

            # Render as markdown for code highlighting
            try:
                md = Markdown(visible_content, code_theme="monokai")
                elements.append(md)
            except Exception:
                # Fallback to plain text if markdown fails
                elements.append(Text(visible_content, style="white"))

            # Animated cursor
            cursor_frames = ["█", "▓", "▒", "░"]
            cursor = cursor_frames[_slow_frame_idx() % len(cursor_frames)]
            elements.append(Text(cursor, style=GOLD))
    else:
        # Waiting state with animation
        spinner = get_spinner()
        if state.debate_skipped:
            elements.append(Text(f"{spinner} Preparing synthesis (debate skipped)...", style="dim"))
        else:
            elements.append(Text(f"{spinner} Awaiting debate conclusion...", style="dim"))

    # Build title with timing - show "Final Synthesis" when complete
    stage_time = get_stage_time(state, 3)
    time_suffix = f" [{stage_time}]" if stage_time else ""

    if state.pope_status == 'complete':
        title = f"[bold {GREEN}]✓ Final Synthesis{time_suffix}[/bold {GREEN}]"
        border = GREEN
    else:
        title = f"[{SECONDARY}]Stage 3: Pope Synthesis{time_suffix}[/{SECONDARY}]"
        border = SECONDARY

    return Panel(
        Group(*elements),
        title=title,
        border_style=border,
        padding=(1, 2)
    )


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
            padding=(1, 2)
        )

    return Panel(
        Text(f"❌ {error_msg}", style="bold red"),
        title="[red]Error[/red]",
        border_style="red",
        padding=(1, 2)
    )


def build_final_synthesis(state: DebateState) -> Group:
    """Build the final synthesis output with proper markdown rendering.

    This is displayed after the live view ends, showing only the final result
    without re-displaying all the intermediate stages.
    """
    elements = []

    # Header with stats
    elapsed = (time.time() - state.start_time)
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
        md = Markdown(state.pope_content, code_theme="monokai")
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
        elements.append(Text(f"{get_spinner()} Executing: ", style=CYAN) + Text(tc.tool, style=f"bold {PRIMARY}"))

        # Show parameters summary
        params_str = ", ".join(f"{k}={repr(v)[:30]}" for k, v in list(tc.parameters.items())[:3])
        if params_str:
            elements.append(Text(f"   {params_str}", style="dim"))

    # Show recent completed tools
    completed = [tc for tc in state.tool_calls if tc.status == 'complete']
    if completed:
        elements.append(Text(""))
        for tc in completed[-5:]:  # Show last 5
            result_preview = (tc.result or "")[:50] + "..." if tc.result and len(tc.result) > 50 else (tc.result or "")
            if tc.error:
                elements.append(Text(f"  ✗ {tc.tool}: ", style="red") + Text(tc.error[:50], style="dim"))
            else:
                elements.append(Text(f"  ✓ {tc.tool}", style=GREEN))

    if not elements:
        return None

    return Panel(
        Group(*elements),
        title=f"[{CYAN}]Tool Execution[/{CYAN}]",
        border_style=CYAN,
        padding=(0, 2)
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
        running_bishops = [b for b, s in state.bishop_status.items() if s == 'running']
        if running_bishops:
            if len(running_bishops) == 1:
                return f"{format_model_name(running_bishops[0])} proposing"
            else:
                return f"{len(running_bishops)} bishops proposing"
        pending = [b for b, s in state.bishop_status.items() if s == 'pending']
        if pending:
            return "Awaiting proposals"
        return "Assessing consensus"

    # Stage 2: Critiques
    if state.stage == 2:
        if state.debate_skipped:
            return "Debate skipped (high consensus)"
        running_critics = [k for k, s in state.critique_status.items() if s == 'running']
        if running_critics:
            if len(running_critics) == 1:
                parts = running_critics[0].split('→')
                if len(parts) == 2:
                    return f"{format_model_name(parts[0])} critiquing"
            return f"{len(running_critics)} critiques in parallel"
        if state.consensus_reached:
            return "Consensus reached"
        return f"Round {state.current_round} critiques"

    # Stage 3: Synthesis
    if state.stage == 3:
        if state.pope_status == 'running':
            return f"Pope {format_model_name(state.pope)} synthesizing"
        elif state.pope_status == 'complete':
            return "Synthesis complete"
        return "Preparing synthesis"

    return "Processing"


def get_parallel_activities(state: DebateState) -> List[str]:
    """Get list of activities happening in parallel for status display."""
    activities = []

    # Stage 1: Running bishops
    if state.stage == 1:
        for bishop, status in state.bishop_status.items():
            if status == 'running':
                tokens = state.bishop_tokens.get(bishop, 0)
                activities.append(f"{format_model_name(bishop)}: {tokens} tokens")

    # Stage 2: Running critiques
    if state.stage == 2 and not state.debate_skipped:
        for key, status in state.critique_status.items():
            if status == 'running':
                parts = key.split('→')
                if len(parts) == 2:
                    activities.append(f"{format_model_name(parts[0])}→{format_model_name(parts[1])}")

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
    status.append(f"{token_indicator} ", style=f"dim {'green' if state.complete else GOLD}")
    status.append(f"{state.total_tokens:,}", style=f"{'green' if state.complete else GOLD}")
    status.append(" tokens", style="dim")

    # Cost if available
    if state.cost_usd and state.cost_usd > 0:
        status.append(f" · ${state.cost_usd:.4f}", style="dim")

    # Trailing wave
    status.append(f" {get_wave()}", style=f"dim {CYAN}")

    return status


def build_display(state: DebateState) -> Group:
    """Build full display from current state."""
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
            if response.status_code != 200:
                error_body = await response.aread()
                try:
                    error_json = json.loads(error_body)
                    yield {"type": "error", "message": error_json.get("error", "Unknown error")}
                except:
                    yield {"type": "error", "message": f"HTTP {response.status_code}: {error_body.decode()}"}
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
) -> Dict[str, Any]:
    """Execute a tool call locally and return the result."""
    from synod.tools import ToolExecutor

    executor = ToolExecutor(working_directory)

    tool_call.status = 'running'

    try:
        result = await executor.execute(
            tool_call.tool,
            tool_call.parameters,
            skip_confirmation=False,  # Prompt for confirmation
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
        tool_call.status = 'error'
        tool_call.error = str(e)
        return {
            "call_id": tool_call.call_id,
            "status": "error",
            "output": "",
            "error": str(e),
            "metadata": {},
        }


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
    base_url = api_url.rstrip('/').replace('/debate', '')
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

    async with httpx.AsyncClient(timeout=300.0) as client:
        async with client.stream(
            "POST",
            url,
            headers={
                "Authorization": api_key,
                "Content-Type": "application/json",
                "X-Synod-Version": get_version(),
            },
            json=payload,
        ) as response:
            if response.status_code != 200:
                error_body = await response.aread()
                try:
                    error_json = json.loads(error_body)
                    yield {"type": "error", "message": error_json.get("error", "Unknown error")}
                except:
                    yield {"type": "error", "message": f"HTTP {response.status_code}: {error_body.decode()}"}
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

async def process_events(
    event_stream: AsyncIterator[dict],
    state: DebateState,
    live: Live,
    api_url: str,
    api_key: str,
    work_dir: str,
) -> bool:
    """Process SSE events and handle tool calls.

    Returns:
        True if we have pending tool calls that need to be sent back
    """
    pending_tool_results: List[Dict[str, Any]] = []

    async for event in event_stream:
        event_type = event.get('type')

        # Handle tool calls specially
        if event_type == 'tool_call':
            handle_event(state, event)
            live.update(build_display(state))

            # Execute the tool locally
            if state.current_tool:
                # Execute tool outside of live context for interactive prompts
                live.stop()

                result = await execute_tool_call(state.current_tool, work_dir)

                live.start()
                live.update(build_display(state))

                # Store result for batch sending
                pending_tool_results.append(result)

        elif event_type == 'complete':
            handle_event(state, event)
            live.update(build_display(state))
            # Debate is complete, no more tool calls
            return False

        elif event_type == 'error':
            handle_event(state, event)
            live.update(build_display(state))
            return False

        else:
            handle_event(state, event)
            live.update(build_display(state))

        # Small delay for smoother animation
        await asyncio.sleep(0.05)

    # If we have pending tool results and a debate_id, we need to send them back
    if pending_tool_results and state.debate_id:
        # Send all tool results back to the cloud
        async for event in send_tool_results(api_url, api_key, state.debate_id, pending_tool_results):
            event_type = event.get('type')

            if event_type == 'tool_call':
                handle_event(state, event)
                live.update(build_display(state))

                # Execute the new tool
                if state.current_tool:
                    live.stop()
                    result = await execute_tool_call(state.current_tool, work_dir)
                    live.start()
                    live.update(build_display(state))
                    pending_tool_results.append(result)

            elif event_type == 'complete':
                handle_event(state, event)
                live.update(build_display(state))
                return False

            elif event_type == 'error':
                handle_event(state, event)
                live.update(build_display(state))
                return False

            else:
                handle_event(state, event)
                live.update(build_display(state))

            await asyncio.sleep(0.05)

        # If we still have pending results after this round, recurse
        if pending_tool_results:
            return True

    return False


async def run_cloud_debate(
    api_key: str,
    query: str,
    context: Optional[str] = None,
    bishops: Optional[List[str]] = None,
    pope: Optional[str] = None,
    api_url: str = "https://api.synod.run/debate",
    working_directory: Optional[str] = None,
    project_path: Optional[str] = None,
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

    Returns:
        Final DebateState with results
    """
    state = DebateState()
    state.stage_start_times[0] = state.start_time  # Stage 0 starts immediately
    work_dir = working_directory or os.getcwd()
    proj_path = project_path or work_dir

    # Start Live display IMMEDIATELY so user sees Stage 0 animation right away
    with Live(console=console, refresh_per_second=12, transient=False) as live:
        # Show initial Stage 0 display immediately (timer starts counting)
        live.update(build_display(state))

        # Gather auto-context while showing Stage 0 animation
        # Use a task so we can update display during context gathering
        auto_context_task = asyncio.create_task(gather_auto_context(
            query=query,
            root_path=proj_path,
        ))

        # Update display while waiting for auto-context
        while not auto_context_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(auto_context_task), timeout=0.1)
            except asyncio.TimeoutError:
                advance_animation()
                live.update(build_display(state))

        auto_files, auto_file_paths = auto_context_task.result()

        # Show auto-context summary (briefly pause live to print)
        if auto_file_paths:
            live.stop()
            display_auto_context_summary(auto_files, auto_file_paths)
            live.start()
            live.update(build_display(state))

        # Process initial debate stream with auto-context
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

        pending_tool_results: List[Dict[str, Any]] = []

        # Process events with animated waiting using asyncio.shield
        # shield() prevents cancellation on timeout while allowing animations
        event_iter = event_stream.__aiter__()
        pending_task: Optional[asyncio.Task] = None
        stream_done = False

        try:
            while not stream_done:
                try:
                    # Create task if we don't have one pending
                    if pending_task is None:
                        pending_task = asyncio.create_task(event_iter.__anext__())

                    # Wait with timeout, but shield the task from cancellation
                    event = await asyncio.wait_for(asyncio.shield(pending_task), timeout=0.1)
                    pending_task = None  # Task completed, clear it

                    event_type = event.get('type')

                    # Handle tool calls
                    if event_type == 'tool_call':
                        handle_event(state, event)
                        live.update(build_display(state))

                        if state.current_tool:
                            # Execute tool (stop live for prompts)
                            live.stop()
                            result = await execute_tool_call(state.current_tool, work_dir)
                            live.start()
                            live.update(build_display(state))
                            pending_tool_results.append(result)

                    elif event_type == 'complete':
                        handle_event(state, event)
                        live.update(build_display(state))
                        stream_done = True

                    elif event_type == 'error':
                        handle_event(state, event)
                        live.update(build_display(state))
                        stream_done = True

                    else:
                        handle_event(state, event)
                        live.update(build_display(state))

                except asyncio.TimeoutError:
                    # No event yet - advance animation and continue waiting
                    advance_animation()
                    live.update(build_display(state))

                except StopAsyncIteration:
                    # Stream ended
                    stream_done = True

        except httpx.ReadError as e:
            state.error = f"Network error: {str(e)}"
            live.update(build_display(state))

        except GeneratorExit:
            # Generator closed early (e.g., error response) - this is normal
            pass

        except Exception as e:
            if not state.error:
                state.error = f"Unexpected error: {str(e)}"
                live.update(build_display(state))

        finally:
            # Clean up any pending task
            if pending_task is not None and not pending_task.done():
                pending_task.cancel()
                try:
                    await pending_task
                except (asyncio.CancelledError, StopAsyncIteration, GeneratorExit):
                    pass
            # Close the async generator properly - suppress all errors
            try:
                await event_stream.aclose()
            except (GeneratorExit, StopAsyncIteration, asyncio.CancelledError, RuntimeError):
                pass
            except Exception:
                pass

        # Check for unexpected stream end
        if not state.complete and not state.error:
            state.error = "Connection to server closed unexpectedly. Please try again."
            live.update(build_display(state))

        # Handle tool result loop if we have pending tools
        MAX_TOOL_ROUNDS = 10
        round_count = 0

        while pending_tool_results and state.debate_id and round_count < MAX_TOOL_ROUNDS:
            round_count += 1
            results_to_send = pending_tool_results[:]
            pending_tool_results.clear()

            # Send results and process response with animations
            tool_stream = send_tool_results(api_url, api_key, state.debate_id, results_to_send)
            tool_iter = tool_stream.__aiter__()
            tool_task: Optional[asyncio.Task] = None
            tool_done = False

            try:
                while not tool_done:
                    try:
                        if tool_task is None:
                            tool_task = asyncio.create_task(tool_iter.__anext__())

                        event = await asyncio.wait_for(asyncio.shield(tool_task), timeout=0.1)
                        tool_task = None

                        event_type = event.get('type')

                        if event_type == 'tool_call':
                            handle_event(state, event)
                            live.update(build_display(state))

                            if state.current_tool:
                                live.stop()
                                result = await execute_tool_call(state.current_tool, work_dir)
                                live.start()
                                live.update(build_display(state))
                                pending_tool_results.append(result)

                        elif event_type == 'complete':
                            handle_event(state, event)
                            live.update(build_display(state))
                            pending_tool_results.clear()  # Done
                            tool_done = True

                        elif event_type == 'error':
                            handle_event(state, event)
                            live.update(build_display(state))
                            pending_tool_results.clear()  # Stop on error
                            tool_done = True

                        else:
                            handle_event(state, event)
                            live.update(build_display(state))

                    except asyncio.TimeoutError:
                        advance_animation()
                        live.update(build_display(state))

                    except StopAsyncIteration:
                        tool_done = True

            except httpx.ReadError as e:
                state.error = f"Network error during tool processing: {str(e)}"
                live.update(build_display(state))
                break

            except Exception as e:
                if not state.error:
                    state.error = f"Unexpected error during tool processing: {str(e)}"
                    live.update(build_display(state))
                break

            finally:
                if tool_task is not None and not tool_task.done():
                    tool_task.cancel()
                    try:
                        await tool_task
                    except (asyncio.CancelledError, StopAsyncIteration):
                        pass

    # Final output is now shown in the combined Stage 3/Final Synthesis panel
    # No need for a separate print - it's all in build_synthesis_panel() when complete

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
) -> DebateState:
    """Synchronous wrapper for run_cloud_debate."""
    return asyncio.run(run_cloud_debate(api_key, query, context, bishops, pope, api_url))
