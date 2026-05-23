"""Checkpoint Semantic Diff — non-authoritative experiment.

Reads a .cerebro/state.json (target project) and computes deterministic token
overlap between the checkpoint text (goal + summary + next_step) and the
registered source file content.  Never writes to .cerebro/, never calls
import-context, never modifies canonical state.
"""
