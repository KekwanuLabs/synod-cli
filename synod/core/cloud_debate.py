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
    critique_status: Dict[str, str] = field(default_factory=dict)
    critique_content: Dict[str, str] = field(default_factory=dict)
    critique_severity: Dict[str, str] = field(default_factory=dict)
    critique_summaries: List[CritiqueSummary] = field(default_factory=list)  # For grid display
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


# ============================================================
# SSE Event Handlers
# ============================================================

def handle_event(state: DebateState, event: dict) -> None:
    """Update state based on SSE event."""
    event_type = event.get('type')

    if event_type == 'stage':
        state.stage = event['stage']
        state.stage_name = event['name']

    elif event_type == 'analysis_complete':
        state.complexity = event['complexity']
        state.domains = event['domains']
        state.bishops = event['bishops']
        state.pope = event['pope']
        state.reasoning = event.get('reasoning', '')
        state.bishop_status = {b: 'pending' for b in state.bishops}

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
        state.critique_status[event['critic']] = 'running'

    elif event_type == 'critique_summary':
        # One-line summary for grid display
        state.critique_summaries.append(CritiqueSummary(
            critic=event['critic'],
            target=event['target'],
            severity=event['severity'],
            summary=event['summary']
        ))

    elif event_type == 'critique_complete':
        state.critique_status[event['critic']] = 'complete'
        state.critique_severity[event['critic']] = event['severity']

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
_frame_idx = 0


def get_spinner() -> str:
    """Get current spinner frame."""
    global _frame_idx
    frame = SPINNER_FRAMES[_frame_idx % len(SPINNER_FRAMES)]
    _frame_idx += 1
    return frame


def build_analysis_panel(state: DebateState) -> Panel:
    """Build Stage 0 analysis panel."""
    elements = []

    if state.complexity:
        # Analysis complete
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
            elements.append(Text(f"Memory: ", style="dim") + Text(f"{state.memories_retrieved} relevant learnings found", style=CYAN))

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
        # Still analyzing
        elements.append(Text(f"{get_spinner()} Analyzing query...", style=CYAN))

    return Panel(
        Group(*elements),
        title=f"[{CYAN}]Stage 0: Analysis[/{CYAN}]",
        border_style=CYAN,
        padding=(0, 2)
    )


def build_proposals_panel(state: DebateState) -> Panel:
    """Build Stage 1 proposals panel with grid display."""
    elements = []

    # Pope observer
    cursor_frames = ["●", "○", "◐", "◑", "◒", "◓"]
    cursor = cursor_frames[_frame_idx % len(cursor_frames)]
    elements.append(Text(f"👑 Pope {format_model_name(state.pope)} is observing {cursor}", style="grey50"))
    elements.append(Text(""))

    # Build grid table for bishops
    if state.bishops:
        table = Table(box=box.ROUNDED, show_header=True, header_style=f"bold {CYAN}", expand=True)

        # Add columns for each bishop
        for bishop in state.bishops:
            table.add_column(format_model_name(bishop), justify="center", width=25)

        # Status row
        status_cells = []
        for bishop in state.bishops:
            status = state.bishop_status.get(bishop, 'pending')
            if status == 'complete':
                tokens = state.bishop_tokens.get(bishop, 0)
                status_cells.append(Text(f"✓ {tokens} tokens", style=GREEN))
            elif status == 'running':
                status_cells.append(Text(f"{get_spinner()} streaming...", style=CYAN))
            else:
                status_cells.append(Text("○ waiting", style="dim"))
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

    return Panel(
        Group(*elements),
        title=f"[{CYAN}]Stage 1: Bishop Proposals[/{CYAN}]",
        border_style=CYAN,
        padding=(0, 2)
    )


def build_critiques_panel(state: DebateState) -> Panel:
    """Build Stage 2 critiques panel with summary grid."""
    elements = []

    # Check if debate was skipped
    if state.debate_skipped:
        elements.append(Text(f"✓ Debate skipped: {state.debate_skip_reason}", style=GREEN))
        return Panel(
            Group(*elements),
            title=f"[{GOLD}]Stage 2: Adversarial Critiques[/{GOLD}]",
            border_style=GOLD,
            padding=(0, 2)
        )

    # Round info
    if state.current_round > 0:
        elements.append(Text(f"⚔️ Round {state.current_round}/{state.max_rounds} • {state.critique_pairs} disagreeing pairs", style=GOLD))
    else:
        elements.append(Text("⚔️ Adversarial critique phase", style=GOLD))

    # Pope observer
    cursor_frames = ["●", "○", "◐", "◑"]
    cursor = cursor_frames[_frame_idx % len(cursor_frames)]
    elements.append(Text(f"👑 Pope {format_model_name(state.pope)} is observing {cursor}", style="grey50"))
    elements.append(Text(""))

    # Critique summaries table (if we have summaries)
    if state.critique_summaries:
        table = Table(box=box.SIMPLE, show_header=False, expand=True, padding=(0, 1))
        table.add_column("Critique", style="dim", no_wrap=False)

        for crit in state.critique_summaries:
            severity_color = {'critical': 'red', 'moderate': GOLD, 'minor': GREEN}.get(crit.severity, GREEN)
            row_text = Text()
            row_text.append(f"{format_model_name(crit.critic)}", style=CYAN)
            row_text.append(" → ", style="dim")
            row_text.append(f"{format_model_name(crit.target)} ", style=CYAN)
            row_text.append(f"[{crit.severity.upper()}] ", style=f"bold {severity_color}")
            row_text.append(crit.summary[:60], style="dim")
            table.add_row(row_text)

        elements.append(table)
    else:
        # Fallback to old status display
        for critic, status in state.critique_status.items():
            if status == 'complete':
                severity = state.critique_severity.get(critic, 'minor')
                severity_style = {'critical': 'red', 'moderate': GOLD, 'minor': GREEN}.get(severity, GREEN)
                elements.append(Text(f"  ✓ {format_model_name(critic)} ", style=GREEN) +
                            Text(f"[{severity.upper()}]", style=f"bold {severity_style}"))
            else:
                elements.append(Text(f"  {get_spinner()} {format_model_name(critic)} reviewing...", style=CYAN))

    # Consensus reached?
    if state.consensus_reached:
        elements.append(Text(""))
        score_pct = int(state.consensus_score * 100) if state.consensus_score else 0
        elements.append(Text(f"✓ Consensus reached at {score_pct}% after round {state.consensus_reached_round}", style=GREEN))

    return Panel(
        Group(*elements),
        title=f"[{GOLD}]Stage 2: Adversarial Critiques[/{GOLD}]",
        border_style=GOLD,
        padding=(0, 2)
    )


def build_synthesis_panel(state: DebateState) -> Panel:
    """Build Stage 3 synthesis panel."""
    elements = []

    if state.pope_status == 'complete':
        # Complete - show timing and content
        elapsed = (time.time() - state.start_time)
        elements.append(Text(f"✓ {format_model_name(state.pope)} complete", style=GREEN))
        elements.append(Text(""))

        # Stats line
        stats_parts = [f"⏱ {elapsed:.1f}s", f"📊 {state.total_tokens:,} tokens"]
        if state.cost_usd:
            stats_parts.append(f"💰 ${state.cost_usd:.4f}")
        if state.memories_retrieved > 0:
            stats_parts.append(f"🧠 {state.memories_retrieved} memories used")
        if state.memories_stored > 0:
            stats_parts.append(f"💾 {state.memories_stored} learned")
        elements.append(Text(" | ".join(stats_parts), style="dim"))
        elements.append(Text(""))

        # Render markdown content
        md = Markdown(state.pope_content, code_theme="monokai")
        elements.append(md)
    elif state.pope_status == 'running':
        elements.append(Text(f"{get_spinner()} {format_model_name(state.pope)} synthesizing...", style=SECONDARY))
        if state.pope_content:
            elements.append(Text(""))
            # Show partial content with cursor
            lines = state.pope_content.split('\n')
            # Show last 10 lines for streaming effect
            visible_lines = '\n'.join(lines[-10:]) if len(lines) > 10 else state.pope_content
            elements.append(Text(visible_lines + "█", style="white"))
    else:
        if state.debate_skipped:
            elements.append(Text("○ Waiting to synthesize (debate skipped)...", style="dim"))
        else:
            elements.append(Text("○ Waiting for critiques...", style="dim"))

    return Panel(
        Group(*elements),
        title=f"[{SECONDARY}]Stage 3: Pope Synthesis[/{SECONDARY}]",
        border_style=SECONDARY,
        padding=(1, 2)
    )


def build_error_panel(state: DebateState) -> Panel:
    """Build error panel."""
    return Panel(
        Text(f"❌ {state.error}", style="bold red"),
        title="[red]Error[/red]",
        border_style="red",
        padding=(1, 2)
    )


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

    async with httpx.AsyncClient(timeout=300.0) as client:
        async with client.stream(
            "POST",
            url,
            headers={
                "Authorization": api_key,
                "Content-Type": "application/json",
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
    work_dir = working_directory or os.getcwd()
    proj_path = project_path or work_dir

    # Gather auto-context (zero-latency, runs in parallel with user seeing spinner)
    auto_files, auto_file_paths = await gather_auto_context(
        query=query,
        root_path=proj_path,
    )
    if auto_file_paths:
        display_auto_context_summary(auto_files, auto_file_paths)

    with Live(console=console, refresh_per_second=8, transient=True) as live:
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

        async for event in event_stream:
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

            elif event_type == 'error':
                handle_event(state, event)
                live.update(build_display(state))

            else:
                handle_event(state, event)
                live.update(build_display(state))

            await asyncio.sleep(0.05)

        # Handle tool result loop if we have pending tools
        MAX_TOOL_ROUNDS = 10
        round_count = 0

        while pending_tool_results and state.debate_id and round_count < MAX_TOOL_ROUNDS:
            round_count += 1
            results_to_send = pending_tool_results[:]
            pending_tool_results.clear()

            # Send results and process response
            async for event in send_tool_results(api_url, api_key, state.debate_id, results_to_send):
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

                elif event_type == 'error':
                    handle_event(state, event)
                    live.update(build_display(state))
                    pending_tool_results.clear()  # Stop on error

                else:
                    handle_event(state, event)
                    live.update(build_display(state))

                await asyncio.sleep(0.05)

    # Final render (non-transient)
    console.print(build_display(state))

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
