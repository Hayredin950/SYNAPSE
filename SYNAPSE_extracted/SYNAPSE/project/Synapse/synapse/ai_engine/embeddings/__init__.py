"""
ai_engine.embeddings
~~~~~~~~~~~~~~~~~~~~
Vector embedding generation for SYNAPSE — Phase 2.3.

Public API:
    get_embedder()          — Returns the singleton SynapseEmbedder instance.
    embed_text(text)        — Embed a single string → list[float].
    embed_batch(texts)      — Embed a list of strings → list[list[float]].
"""

from .embedder import SynapseEmbedder, embed_batch, embed_text, get_embedder

__all__ = ["SynapseEmbedder", "embed_text", "embed_batch", "get_embedder"]
