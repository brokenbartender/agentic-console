from __future__ import annotations


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


def estimate_cost(tokens_in: int, tokens_out: int, input_per_million: float, output_per_million: float) -> float:
    cost_in = (tokens_in / 1_000_000.0) * input_per_million
    cost_out = (tokens_out / 1_000_000.0) * output_per_million
    return cost_in + cost_out
