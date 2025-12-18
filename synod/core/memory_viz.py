"""Memory Visualization Module - Beautiful CLI visualizations for Synod Adversarial Memory.

This module provides stunning terminal visualizations including:
- Animated memory graphs
- Memory timeline with sparklines
- Type distribution charts
- Confidence heatmaps
- Live memory stats dashboard
"""

import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass
import httpx

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.box import ROUNDED
from rich.align import Align
from rich.columns import Columns

from .theme import (
    PRIMARY,
    CYAN,
    GOLD,
    GREEN,
)

console = Console()

# Memory type colors matching the API
MEMORY_TYPE_COLORS = {
    "preference": "#FF6B35",  # Synod Orange
    "pattern": "#00D9FF",  # Cyan
    "fact": "#22C55E",  # Green
    "correction": "#FBBF24",  # Gold
    "architecture": "#7C3AED",  # Purple
    "convention": "#06B6D4",  # Teal
    "bug": "#EF4444",  # Red
    "decision": "#F59E0B",  # Amber
    "skill": "#FFD700",  # Gold (premium)
    "relationship": "#8B5CF6",  # Violet
}

MEMORY_TYPE_ICONS = {
    "preference": "",
    "pattern": "",
    "fact": "",
    "correction": "",
    "architecture": "",
    "convention": "",
    "bug": "",
    "decision": "",
    "skill": "",
    "relationship": "",
}


@dataclass
class MemoryStats:
    """Memory statistics from the API."""

    total_memories: int
    user_memories: int
    project_memories: int
    by_type: Dict[str, int]
    by_domain: Dict[str, int]
    by_technology: Dict[str, int]
    average_confidence: float
    average_decay: float
    skill_count: int
    tier: str
    at_limit: bool
    max_memories: int
    visualization_enabled: bool


async def fetch_memory_stats(
    api_key: str, project_path: Optional[str] = None
) -> Optional[MemoryStats]:
    """Fetch memory statistics from Synod Cloud."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            params = {}
            if project_path:
                params["project_path"] = project_path

            response = await client.get(
                "https://api.synod.run/memory/stats",
                headers={"Authorization": api_key},
                params=params,
            )

            if response.status_code != 200:
                return None

            data = response.json()
            limits = data.get("limits", {})

            return MemoryStats(
                total_memories=data.get("total_memories", 0),
                user_memories=data.get("user_memories", 0),
                project_memories=data.get("project_memories", 0),
                by_type=data.get("by_type", {}),
                by_domain=data.get("by_domain", {}),
                by_technology=data.get("by_technology", {}),
                average_confidence=data.get("average_confidence", 0),
                average_decay=data.get("average_decay", 1),
                skill_count=data.get("skill_count", 0),
                tier=data.get("tier", "free"),
                at_limit=limits.get("at_limit", False),
                max_memories=limits.get("max_memories", 1000),
                visualization_enabled=limits.get("visualization_enabled", False),
            )
    except Exception as e:
        console.print(f"[dim]Error fetching memory stats: {e}[/dim]")
        return None


async def fetch_memory_timeline(
    api_key: str, project_path: Optional[str] = None, days: int = 30
) -> Optional[Dict]:
    """Fetch memory timeline from Synod Cloud."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            params = {"days": str(days)}
            if project_path:
                params["project_path"] = project_path

            response = await client.get(
                "https://api.synod.run/memory/timeline",
                headers={"Authorization": api_key},
                params=params,
            )

            if response.status_code != 200:
                return None

            return response.json()
    except Exception:
        return None


async def fetch_memory_graph(
    api_key: str, project_path: Optional[str] = None, limit: int = 50
) -> Optional[Dict]:
    """Fetch memory graph from Synod Cloud (Pro+ only)."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            params = {"limit": str(limit)}
            if project_path:
                params["project_path"] = project_path

            response = await client.get(
                "https://api.synod.run/memory/graph",
                headers={"Authorization": api_key},
                params=params,
            )

            if response.status_code == 403:
                # Feature not available for tier
                return {"error": "pro_required"}

            if response.status_code != 200:
                return None

            return response.json()
    except Exception:
        return None


def create_sparkline(values: List[int], width: int = 20) -> str:
    """Create a sparkline from values."""
    if not values:
        return "━" * width

    # Sparkline characters from lowest to highest
    chars = "▁▂▃▄▅▆▇█"

    max_val = max(values) if max(values) > 0 else 1
    min_val = min(values)
    scale = len(chars) - 1

    sparkline = ""
    for v in values[-width:]:
        if max_val == min_val:
            idx = len(chars) // 2
        else:
            idx = int((v - min_val) / (max_val - min_val) * scale)
        sparkline += chars[idx]

    # Pad if needed
    if len(sparkline) < width:
        sparkline = "▁" * (width - len(sparkline)) + sparkline

    return sparkline


def create_horizontal_bar(
    value: float, max_value: float, width: int = 20, color: str = CYAN, label: str = ""
) -> Text:
    """Create a horizontal bar chart."""
    if max_value == 0:
        filled = 0
    else:
        filled = int((value / max_value) * width)

    bar = Text()
    if label:
        bar.append(f"{label:12} ", style="dim")
    bar.append("█" * filled, style=color)
    bar.append("░" * (width - filled), style="dim")
    bar.append(f" {int(value)}", style="bold")

    return bar


def create_memory_type_chart(by_type: Dict[str, int]) -> Panel:
    """Create a beautiful bar chart for memory types."""
    if not by_type:
        return Panel(
            Text("No memories yet", style="dim", justify="center"),
            title="[cyan]Memory Types[/cyan]",
            border_style="cyan",
        )

    max_count = max(by_type.values()) if by_type else 1

    content = Text()
    for mem_type, count in sorted(by_type.items(), key=lambda x: -x[1]):
        color = MEMORY_TYPE_COLORS.get(mem_type, "#888888")
        icon = MEMORY_TYPE_ICONS.get(mem_type, "")

        # Create bar
        bar_width = 20
        filled = int((count / max_count) * bar_width) if max_count > 0 else 0

        content.append(f"{icon} {mem_type:12} ", style=color)
        content.append("█" * filled, style=color)
        content.append("░" * (bar_width - filled), style="dim")
        content.append(f" {count}\n", style="bold")

    return Panel(
        content,
        title="[cyan]Memory Types[/cyan]",
        border_style="cyan",
        padding=(1, 2),
    )


def create_confidence_gauge(confidence: float) -> Text:
    """Create a confidence gauge visualization."""
    # Gauge characters
    segments = 10
    filled = int(confidence * segments)

    gauge = Text()
    gauge.append("Confidence ", style="dim")
    gauge.append("[", style="dim")

    for i in range(segments):
        if i < filled:
            if confidence >= 0.8:
                gauge.append("█", style="green")
            elif confidence >= 0.5:
                gauge.append("█", style="yellow")
            else:
                gauge.append("█", style="red")
        else:
            gauge.append("░", style="dim")

    gauge.append("] ", style="dim")
    gauge.append(f"{confidence:.0%}", style="bold")

    return gauge


def create_tier_badge(tier: str) -> Text:
    """Create a tier badge."""
    badge = Text()

    if tier == "free":
        badge.append(" FREE ", style="bold white on bright_black")
    elif tier == "pro":
        badge.append(" PRO ", style="bold white on #FF6B35")
    elif tier == "team":
        badge.append(" TEAM ", style="bold black on #FFD700")
    elif tier == "enterprise":
        badge.append(" ENTERPRISE ", style="bold white on #7C3AED")

    return badge


async def animate_memory_loading() -> None:
    """Animated loading screen for memory visualization."""
    _frames = [
        "◐ Loading memories...",
        "◓ Loading memories...",
        "◑ Loading memories...",
        "◒ Loading memories...",
    ]

    with console.status(
        "[cyan]Connecting to Synod Cloud...[/cyan]", spinner="dots"
    ) as status:
        await asyncio.sleep(0.5)
        status.update("[cyan]Fetching memory statistics...[/cyan]")
        await asyncio.sleep(0.3)
        status.update("[cyan]Building visualization...[/cyan]")
        await asyncio.sleep(0.2)


async def display_memory_dashboard(
    api_key: str, project_path: Optional[str] = None
) -> None:
    """Display the full memory dashboard with animations."""
    # Animated loading
    await animate_memory_loading()

    # Fetch data
    stats = await fetch_memory_stats(api_key, project_path)

    if not stats:
        console.print(
            Panel(
                Text("Could not connect to Synod Cloud", style="red", justify="center"),
                title="[red]Error[/red]",
                border_style="red",
            )
        )
        return

    console.clear()

    # Build dashboard layout
    console.print()

    # Header with branding
    header = Text()
    header.append("  SYNOD ADVERSARIAL MEMORY  ", style="bold white on #FF6B35")
    console.print(Align.center(header))
    console.print(
        Align.center(Text("Memory you can trust. Verified by debate.", style="dim"))
    )
    console.print()

    # Tier and limits info
    tier_info = Text()
    tier_info.append("Tier: ")
    tier_info.append_text(create_tier_badge(stats.tier))
    tier_info.append("  ")

    if stats.max_memories > 0:
        usage_pct = stats.total_memories / stats.max_memories
        if usage_pct >= 0.9:
            tier_info.append(
                f"Storage: {stats.total_memories}/{stats.max_memories} ",
                style="red bold",
            )
            tier_info.append("(NEAR LIMIT)", style="red")
        else:
            tier_info.append(
                f"Storage: {stats.total_memories}/{stats.max_memories}", style="dim"
            )
    else:
        tier_info.append(f"Storage: {stats.total_memories} (Unlimited)", style="green")

    console.print(Align.center(tier_info))
    console.print()

    # Main stats in columns
    stats_panel = Table.grid(padding=(0, 4))
    stats_panel.add_column(justify="center")
    stats_panel.add_column(justify="center")
    stats_panel.add_column(justify="center")
    stats_panel.add_column(justify="center")

    # Row 1: Big numbers
    stats_panel.add_row(
        Panel(
            Align.center(Text(str(stats.total_memories), style=f"bold {PRIMARY}")),
            title="Total",
            border_style=PRIMARY,
            width=16,
        ),
        Panel(
            Align.center(Text(str(stats.user_memories), style=f"bold {CYAN}")),
            title="User",
            border_style=CYAN,
            width=16,
        ),
        Panel(
            Align.center(Text(str(stats.project_memories), style=f"bold {GREEN}")),
            title="Project",
            border_style=GREEN,
            width=16,
        ),
        Panel(
            Align.center(Text(str(stats.skill_count), style=f"bold {GOLD}")),
            title="Skills",
            border_style=GOLD,
            width=16,
        ),
    )

    console.print(Align.center(stats_panel))
    console.print()

    # Confidence and decay gauges
    gauge_text = Text()
    gauge_text.append_text(create_confidence_gauge(stats.average_confidence))
    gauge_text.append("    ")

    # Decay gauge
    gauge_text.append("Memory Health ", style="dim")
    gauge_text.append("[", style="dim")
    decay_filled = int(stats.average_decay * 10)
    for i in range(10):
        if i < decay_filled:
            gauge_text.append("█", style="green")
        else:
            gauge_text.append("░", style="dim")
    gauge_text.append("] ", style="dim")
    gauge_text.append(f"{stats.average_decay:.0%}", style="bold")

    console.print(Align.center(gauge_text))
    console.print()

    # Memory type distribution
    if stats.by_type:
        console.print(create_memory_type_chart(stats.by_type))
        console.print()

    # Top domains and technologies
    if stats.by_domain or stats.by_technology:
        cols = []

        if stats.by_domain:
            domain_text = Text()
            domain_text.append("Top Domains\n", style=f"bold {CYAN}")
            for domain, count in sorted(stats.by_domain.items(), key=lambda x: -x[1])[
                :5
            ]:
                domain_text.append(f"  {domain}: ", style="dim")
                domain_text.append(f"{count}\n", style="bold")
            cols.append(Panel(domain_text, border_style="cyan", width=30))

        if stats.by_technology:
            tech_text = Text()
            tech_text.append("Top Technologies\n", style=f"bold {GREEN}")
            for tech, count in sorted(stats.by_technology.items(), key=lambda x: -x[1])[
                :5
            ]:
                tech_text.append(f"  {tech}: ", style="dim")
                tech_text.append(f"{count}\n", style="bold")
            cols.append(Panel(tech_text, border_style="green", width=30))

        if cols:
            console.print(Columns(cols, equal=True, expand=True))

    # Pro features hint for free users
    if not stats.visualization_enabled:
        console.print()
        console.print(
            Panel(
                Text.from_markup(
                    f"[{GOLD}]Upgrade to Pro[/{GOLD}] for memory visualization graph, "
                    f"skill learning, and unlimited memories.\n"
                    f"[dim]synod.run/dashboard/upgrade[/dim]"
                ),
                border_style="yellow",
                title="[yellow]Pro Features[/yellow]",
            )
        )


async def display_memory_graph_ascii(
    api_key: str, project_path: Optional[str] = None
) -> None:
    """Display an ASCII representation of the memory graph (Pro+ only)."""
    graph_data = await fetch_memory_graph(api_key, project_path, limit=30)

    if graph_data is None:
        console.print("[red]Failed to fetch memory graph[/red]")
        return

    if graph_data.get("error") == "pro_required":
        console.print(
            Panel(
                Text.from_markup(
                    f"[{GOLD}]Memory visualization requires Pro tier[/{GOLD}]\n\n"
                    f"Upgrade to see your memory connections as a beautiful graph.\n\n"
                    f"[dim]synod.run/dashboard/upgrade[/dim]"
                ),
                title="[yellow]Pro Feature[/yellow]",
                border_style="yellow",
            )
        )
        return

    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    stats = graph_data.get("stats", {})

    if not nodes:
        console.print("[dim]No memories to visualize yet.[/dim]")
        return

    console.print()
    console.print(Align.center(Text("  MEMORY GRAPH  ", style="bold white on #7C3AED")))
    console.print(
        Align.center(Text(f"{len(nodes)} nodes, {len(edges)} connections", style="dim"))
    )
    console.print()

    # Create a simple ASCII graph representation
    # Group nodes by type for visualization
    type_groups: Dict[str, List[Dict]] = {}
    for node in nodes:
        t = node["type"]
        if t not in type_groups:
            type_groups[t] = []
        type_groups[t].append(node)

    # Display each type group with connections
    for mem_type, type_nodes in type_groups.items():
        color = MEMORY_TYPE_COLORS.get(mem_type, "#888888")
        icon = MEMORY_TYPE_ICONS.get(mem_type, "")

        header = Text()
        header.append(f"\n{icon} {mem_type.upper()} ", style=f"bold {color}")
        header.append(f"({len(type_nodes)} memories)", style="dim")
        console.print(header)

        for i, node in enumerate(type_nodes[:5]):  # Show max 5 per type
            # Node visualization
            content = (
                node["content"][:60] + "..."
                if len(node["content"]) > 60
                else node["content"]
            )
            conf = node["confidence"]

            # Find connections for this node
            node_edges = [
                e
                for e in edges
                if e["source"] == node["id"] or e["target"] == node["id"]
            ]

            node_text = Text()

            # Connection indicator
            if node_edges:
                node_text.append("├── ", style="dim")
            else:
                node_text.append("○── ", style="dim")

            # Confidence indicator
            if conf >= 0.8:
                node_text.append("● ", style="green")
            elif conf >= 0.5:
                node_text.append("● ", style="yellow")
            else:
                node_text.append("○ ", style="red")

            # Content
            node_text.append(f'"{content}"', style=color)

            # Connections count
            if node_edges:
                node_text.append(f" [{len(node_edges)} links]", style="dim")

            console.print(node_text)

        if len(type_nodes) > 5:
            console.print(
                Text(f"    └── ... and {len(type_nodes) - 5} more", style="dim")
            )

    console.print()

    # Stats summary
    stats_text = Text()
    stats_text.append("Graph Stats: ", style="bold")
    stats_text.append(
        f"Avg Confidence: {stats.get('average_confidence', 0):.0%} ", style="dim"
    )
    stats_text.append(f"| Health: {stats.get('average_decay', 1):.0%} ", style="dim")
    stats_text.append(f"| Skills: {stats.get('skill_count', 0)}", style=GOLD)
    console.print(stats_text)


async def display_memory_timeline_viz(
    api_key: str, project_path: Optional[str] = None, days: int = 14
) -> None:
    """Display memory timeline with sparklines."""
    timeline_data = await fetch_memory_timeline(api_key, project_path, days)

    if not timeline_data:
        console.print("[dim]No timeline data available.[/dim]")
        return

    timeline = timeline_data.get("timeline", [])

    if not timeline:
        console.print("[dim]No memories in the last {days} days.[/dim]")
        return

    console.print()
    console.print(
        Align.center(Text("  MEMORY TIMELINE  ", style="bold white on #06B6D4"))
    )
    console.print()

    # Create sparkline data
    daily_counts = [day["count"] for day in reversed(timeline)]
    sparkline = create_sparkline(daily_counts, width=min(30, len(daily_counts)))

    sparkline_text = Text()
    sparkline_text.append("Activity: ", style="dim")
    sparkline_text.append(sparkline, style=CYAN)
    sparkline_text.append(f" ({sum(daily_counts)} total)", style="dim")
    console.print(Align.center(sparkline_text))
    console.print()

    # Show recent days with memories
    table = Table(show_header=True, header_style="bold", box=ROUNDED)
    table.add_column("Date", style="dim", width=12)
    table.add_column("Count", justify="right", width=6)
    table.add_column("Types", width=30)
    table.add_column("Sample", width=40)

    for day in timeline[:7]:  # Last 7 days
        date = day["date"]
        count = day["count"]
        memories = day["memories"]

        # Count types
        type_counts: Dict[str, int] = {}
        for mem in memories:
            t = mem["type"]
            type_counts[t] = type_counts.get(t, 0) + 1

        types_text = Text()
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
            color = MEMORY_TYPE_COLORS.get(t, "#888888")
            types_text.append(f"{t}:{c} ", style=color)

        # Sample memory
        sample = memories[0]["content"][:35] + "..." if memories else ""

        table.add_row(date, str(count), types_text, sample)

    console.print(table)


async def handle_memory_viz_command(
    args: str, api_key: str, project_path: Optional[str] = None
) -> None:
    """Handle /memory command with visualization subcommands."""
    parts = args.strip().split()
    subcommand = parts[0] if parts else ""

    if subcommand == "graph":
        await display_memory_graph_ascii(api_key, project_path)
    elif subcommand == "timeline":
        days = 14
        if len(parts) > 1 and parts[1].isdigit():
            days = int(parts[1])
        await display_memory_timeline_viz(api_key, project_path, days)
    elif subcommand == "stats" or subcommand == "":
        await display_memory_dashboard(api_key, project_path)
    elif subcommand == "show":
        await display_memory_dashboard(api_key, project_path)
    else:
        # Show help
        console.print(
            Panel(
                Text.from_markup(
                    f"[{CYAN}]/memory[/{CYAN}]             Show memory dashboard\n"
                    f"[{CYAN}]/memory stats[/{CYAN}]       Show detailed statistics\n"
                    f"[{CYAN}]/memory graph[/{CYAN}]       Visualize memory connections (Pro)\n"
                    f"[{CYAN}]/memory timeline[/{CYAN}]    Show memory activity timeline\n"
                    f"[{CYAN}]/memory show[/{CYAN}]        Display local context files"
                ),
                title="[cyan]Memory Commands[/cyan]",
                border_style="cyan",
            )
        )
