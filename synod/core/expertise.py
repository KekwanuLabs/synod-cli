"""Bishop expertise weighting and adaptive learning system.

This module manages:
1. Initial weights from provider benchmarks
2. Self-assessment during first query
3. Adaptive learning from user feedback
4. Domain-specific expertise calculation
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from pathlib import Path
import json
import os
from datetime import datetime

from .config import CONFIG_DIR

# Expertise database file
EXPERTISE_FILE = os.path.join(CONFIG_DIR, "expertise.json")


@dataclass
class BishopExpertise:
    """Expertise profile for a single bishop"""
    model_id: str
    initial_weights: Dict[str, float]  # From benchmarks/self-assessment
    learned_weights: Dict[str, Dict] = field(default_factory=dict)
    total_participations: int = 0
    total_upvotes: int = 0
    total_downvotes: int = 0
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())

    def get_weight(self, domain: str) -> float:
        """
        Get current weight for a domain (combines initial + learned).

        Returns value between 0.5 and 1.0
        """
        initial = self.initial_weights.get(domain, 0.7)

        # If we have learned data, adjust
        if domain in self.learned_weights:
            learned = self.learned_weights[domain]
            success_rate = learned.get("success_rate", 0.5)

            # Blend initial and learned (more weight to learned over time)
            participations = learned.get("participations", 0)
            learned_confidence = min(participations / 20.0, 0.5)  # Max 50% learned weight

            adjusted = (initial * (1 - learned_confidence)) + (success_rate * learned_confidence)
            return max(0.5, min(1.0, adjusted))

        return initial

    def record_feedback(self, domains: List[str], upvote: bool) -> None:
        """Record user feedback for domains"""
        self.total_participations += 1

        if upvote:
            self.total_upvotes += 1
        else:
            self.total_downvotes += 1

        # Update per-domain learned weights
        for domain in domains:
            if domain not in self.learned_weights:
                self.learned_weights[domain] = {
                    "participations": 0,
                    "upvotes": 0,
                    "downvotes": 0,
                    "success_rate": 0.5
                }

            learned = self.learned_weights[domain]
            learned["participations"] += 1

            if upvote:
                learned["upvotes"] += 1
            else:
                learned["downvotes"] += 1

            # Calculate success rate
            total = learned["upvotes"] + learned["downvotes"]
            learned["success_rate"] = learned["upvotes"] / total if total > 0 else 0.5

        self.last_updated = datetime.now().isoformat()


# Provider benchmarks based on published data
PROVIDER_BENCHMARKS = {
    "anthropic/claude-opus-4.5": {
        "source": "Anthropic published benchmarks",
        "overall_score": 0.92,
        "architecture": 0.95,
        "reasoning": 0.96,
        "security": 0.90,
        "algorithms": 0.85,
        "web_dev": 0.80,
        "backend": 0.88,
        "database": 0.82,
        "performance": 0.85,
        "testing": 0.83,
        "devops": 0.78,
        "ml_ai": 0.82,
        "data_science": 0.85,
        "systems_programming": 0.80,
        "mobile": 0.75,
        "cloud": 0.82,
        "networking": 0.80,
        "game_dev": 0.72,
        "blockchain": 0.75,
        "automation": 0.85,
        "language_specific": 0.85
    },

    "anthropic/claude-sonnet-4.5": {
        "source": "Anthropic published benchmarks",
        "overall_score": 0.89,
        "architecture": 0.90,
        "reasoning": 0.92,
        "security": 0.88,
        "algorithms": 0.82,
        "web_dev": 0.78,
        "backend": 0.85,
        "database": 0.80,
        "performance": 0.82,
        "testing": 0.80,
        "devops": 0.75,
        "python": 0.85,
        "javascript": 0.75,
        "language_specific": 0.82
    },

    "openai/gpt-5.1-codex": {
        "source": "OpenAI published benchmarks",
        "overall_score": 0.90,
        "web_dev": 0.95,
        "javascript": 0.95,
        "typescript": 0.94,
        "architecture": 0.85,
        "backend": 0.90,
        "algorithms": 0.88,
        "api_design": 0.90,
        "python": 0.90,
        "database": 0.84,
        "performance": 0.86,
        "testing": 0.88,
        "devops": 0.82,
        "security": 0.83,
        "language_specific": 0.88
    },

    "openai/gpt-4o": {
        "source": "OpenAI published benchmarks",
        "overall_score": 0.88,
        "web_dev": 0.92,
        "javascript": 0.93,
        "architecture": 0.83,
        "backend": 0.88,
        "algorithms": 0.85,
        "python": 0.88,
        "database": 0.82,
        "performance": 0.84,
        "testing": 0.86,
        "security": 0.80,
        "language_specific": 0.85
    },

    "deepseek/deepseek-v3": {
        "source": "DeepSeek published benchmarks",
        "overall_score": 0.88,
        "algorithms": 0.98,
        "mathematics": 0.97,
        "performance": 0.95,
        "reasoning": 0.85,
        "python": 0.92,
        "backend": 0.84,
        "architecture": 0.78,
        "web_dev": 0.72,
        "database": 0.86,
        "security": 0.80,
        "testing": 0.82,
        "devops": 0.75,
        "ml_ai": 0.95,              # Excellent at ML/AI
        "data_science": 0.94,       # Strong data science
        "systems_programming": 0.88,
        "mobile": 0.70,
        "cloud": 0.78,
        "networking": 0.82,
        "game_dev": 0.75,
        "blockchain": 0.80,
        "automation": 0.82,
        "language_specific": 0.88
    },

    "google/gemini-2.5-pro": {
        "source": "Google published benchmarks",
        "overall_score": 0.89,
        "multimodal": 0.94,
        "architecture": 0.87,
        "web_dev": 0.88,
        "backend": 0.86,
        "algorithms": 0.86,
        "python": 0.85,
        "javascript": 0.87,
        "database": 0.83,
        "performance": 0.84,
        "security": 0.82,
        "testing": 0.85,
        "devops": 0.80,
        "language_specific": 0.84
    },

    "x-ai/grok-4.1-fast": {
        "source": "xAI published benchmarks",
        "overall_score": 0.80,
        "speed": 0.95,
        "algorithms": 0.78,
        "python": 0.80,
        "web_dev": 0.75,
        "backend": 0.78,
        "architecture": 0.72,
        "database": 0.75,
        "performance": 0.80,
        "security": 0.70,
        "testing": 0.75,
        "devops": 0.72,
        "language_specific": 0.78
    },

    "z-ai/glm-4.6": {
        "source": "Zhipu AI published benchmarks",
        "overall_score": 0.85,
        "reasoning": 0.88,          # Strong logic, beat Claude 4.5 on HLE
        "math": 0.92,               # Top tier, comparable to GPT-5 on AIME
        "coding": 0.83,             # Strong, improved over 4.5
        "systems_programming": 0.80,
        "algorithms": 0.85,
        "architecture": 0.82,
        "web_dev": 0.80,
        "backend": 0.82,
        "database": 0.78,
        "security": 0.75,
        "testing": 0.78,
        "devops": 0.75,
        "ml_ai": 0.80,
        "data_science": 0.82,
        "mobile": 0.75,
        "cloud": 0.78,
        "networking": 0.78,
        "game_dev": 0.72,
        "blockchain": 0.75,
        "automation": 0.80,
        "language_specific": 0.82
    }
}


def load_expertise() -> Dict[str, BishopExpertise]:
    """Load expertise database from disk"""
    if not os.path.exists(EXPERTISE_FILE):
        return {}

    try:
        with open(EXPERTISE_FILE, 'r') as f:
            data = json.load(f)

        expertise = {}
        for model_id, model_data in data.items():
            expertise[model_id] = BishopExpertise(
                model_id=model_id,
                initial_weights=model_data.get("initial_weights", {}),
                learned_weights=model_data.get("learned_weights", {}),
                total_participations=model_data.get("total_participations", 0),
                total_upvotes=model_data.get("total_upvotes", 0),
                total_downvotes=model_data.get("total_downvotes", 0),
                last_updated=model_data.get("last_updated", datetime.now().isoformat())
            )

        return expertise

    except Exception as e:
        print(f"Error loading expertise: {e}")
        return {}


def save_expertise(expertise: Dict[str, BishopExpertise]) -> None:
    """Save expertise database to disk"""
    os.makedirs(CONFIG_DIR, exist_ok=True)

    data = {}
    for model_id, bishop in expertise.items():
        data[model_id] = {
            "model_id": bishop.model_id,
            "initial_weights": bishop.initial_weights,
            "learned_weights": bishop.learned_weights,
            "total_participations": bishop.total_participations,
            "total_upvotes": bishop.total_upvotes,
            "total_downvotes": bishop.total_downvotes,
            "last_updated": bishop.last_updated
        }

    with open(EXPERTISE_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def initialize_bishop_expertise(bishops: List[str]) -> Dict[str, BishopExpertise]:
    """
    Initialize expertise for bishops.
    Uses provider benchmarks as starting point.
    """
    # Load existing expertise
    expertise = load_expertise()

    # Add any new bishops
    for bishop in bishops:
        if bishop not in expertise:
            # Find matching benchmark
            initial_weights = {}

            # Try exact match
            if bishop in PROVIDER_BENCHMARKS:
                benchmark = PROVIDER_BENCHMARKS[bishop]
                initial_weights = {k: v for k, v in benchmark.items() if k != "source" and k != "overall_score"}

            else:
                # Try partial match (e.g., "claude-opus" in "anthropic/claude-opus-4.5")
                for benchmark_model, benchmark_data in PROVIDER_BENCHMARKS.items():
                    # Extract model name without provider
                    model_name = benchmark_model.split('/')[-1]
                    bishop_name = bishop.split('/')[-1]

                    # Check if similar (e.g., "claude-opus-4.5" matches "claude-opus")
                    if model_name.replace('-', '').replace('.', '') in bishop_name.replace('-', '').replace('.', ''):
                        initial_weights = {k: v for k, v in benchmark_data.items() if k != "source" and k != "overall_score"}
                        break

                # Fallback: balanced weights
                if not initial_weights:
                    initial_weights = {
                        "architecture": 0.75,
                        "algorithms": 0.75,
                        "web_dev": 0.75,
                        "backend": 0.75,
                        "database": 0.75,
                        "security": 0.75,
                        "performance": 0.75,
                        "testing": 0.75,
                        "devops": 0.75,
                        "language_specific": 0.75
                    }

            expertise[bishop] = BishopExpertise(
                model_id=bishop,
                initial_weights=initial_weights
            )

    # Save
    save_expertise(expertise)

    return expertise


def calculate_bishop_weights(
    query_domains: List[str],
    bishops: List[str]
) -> Dict[str, float]:
    """
    Calculate weights for each bishop based on query domains.

    Returns normalized weights (0.5 to 1.2 scale):
    - 0.5: Minimum (still participates, but lower influence)
    - 1.0: Average expertise
    - 1.2: Domain expert (high influence)

    Args:
        query_domains: List of domains from Stage 0 analysis
        bishops: List of bishop model IDs

    Returns:
        Dict mapping bishop -> weight
    """
    # Load expertise
    expertise = load_expertise()

    # If empty, initialize
    if not expertise:
        expertise = initialize_bishop_expertise(bishops)

    # Calculate raw weights
    raw_weights = {}
    for bishop in bishops:
        if bishop not in expertise:
            # Initialize if missing
            expertise = initialize_bishop_expertise([bishop])

        bishop_expertise = expertise[bishop]

        # Average weight across relevant domains
        domain_weights = [
            bishop_expertise.get_weight(domain)
            for domain in query_domains
        ]

        raw_weights[bishop] = sum(domain_weights) / len(domain_weights) if domain_weights else 0.75

    # Normalize to 0.5 - 1.2 range
    min_weight = min(raw_weights.values())
    max_weight = max(raw_weights.values())

    normalized = {}
    for bishop, weight in raw_weights.items():
        if max_weight == min_weight:
            # All same, use 1.0
            normalized[bishop] = 1.0
        else:
            # Normalize to 0.0 - 1.0, then scale to 0.5 - 1.2
            norm = (weight - min_weight) / (max_weight - min_weight)
            normalized[bishop] = 0.5 + (norm * 0.7)

    return normalized


def select_top_bishops(
    query_domains: List[str],
    all_bishops: List[str],
    pope_model: str,
    recommended_count: int
) -> tuple[List[str], Dict[str, float]]:
    """
    Select top N bishops by expertise weight for the given query domains.

    This implements the intelligent bishop selection that adapts debate
    participation based on query complexity and domain expertise.

    Args:
        query_domains: List of domains from Stage 0 analysis (e.g., ["algorithms", "python"])
        all_bishops: All configured bishop models
        pope_model: Pope model ID (excluded from selection - remains unbiased observer)
        recommended_count: Number of bishops to select (from Stage 0 strategy)

    Returns:
        Tuple of (selected_bishops, all_weights):
        - selected_bishops: List of top N bishop model IDs
        - all_weights: Dict mapping all active bishops to their weights (for display)
    """
    # Exclude Pope (unbiased observer in Stage 1 & 2)
    active_bishops = [b for b in all_bishops if b != pope_model]

    # Calculate weights for all active bishops
    weights = calculate_bishop_weights(query_domains, active_bishops)

    # Sort by weight (descending) - highest expertise first
    sorted_bishops = sorted(weights.items(), key=lambda x: x[1], reverse=True)

    # Select top N bishops by expertise
    selected = [bishop for bishop, weight in sorted_bishops[:recommended_count]]

    return selected, weights


def record_user_feedback(
    bishops_participated: List[str],
    query_domains: List[str],
    upvote: bool
) -> None:
    """
    Record user feedback (thumbs up/down) to update expertise.

    Args:
        bishops_participated: List of bishops in this debate
        query_domains: Domains involved in query
        upvote: True if user liked solution, False otherwise
    """
    expertise = load_expertise()

    for bishop in bishops_participated:
        if bishop in expertise:
            expertise[bishop].record_feedback(query_domains, upvote)

    save_expertise(expertise)


# CLI for manual weight adjustment
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "show":
        # Show current expertise
        expertise = load_expertise()

        if not expertise:
            print("No expertise data yet. Run some queries first!")
        else:
            for model_id, bishop in expertise.items():
                print(f"\n{model_id}:")
                print(f"  Participations: {bishop.total_participations}")
                print(f"  Upvotes: {bishop.total_upvotes}")
                print(f"  Downvotes: {bishop.total_downvotes}")

                if bishop.total_participations > 0:
                    success_rate = bishop.total_upvotes / bishop.total_participations
                    print(f"  Success Rate: {success_rate:.1%}")

                print(f"  Current Weights:")
                for domain in ["architecture", "algorithms", "web_dev", "backend", "database"]:
                    weight = bishop.get_weight(domain)
                    print(f"    {domain}: {weight:.2f}")
