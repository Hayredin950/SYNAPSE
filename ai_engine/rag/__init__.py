"""
SYNAPSE RAG (Retrieval-Augmented Generation) Pipeline
Phase 3.1 — LangChain + pgvector + Google Gemini + local sentence-transformers

Imports are lazy to avoid loading heavy ML dependencies at Django startup.
Use get_rag_pipeline() as the primary entry point.
"""


def get_rag_pipeline(*args, **kwargs):
    """Lazy entry point — imports RAGPipeline only when first called."""
    from .pipeline import get_rag_pipeline as _get

    return _get(*args, **kwargs)


def __getattr__(name):
    """Lazy attribute access for the public symbols."""
    _map = {
        "SynapseRetriever": ("ai_engine.rag.retriever", "SynapseRetriever"),
        "SynapseRAGChain": ("ai_engine.rag.chain", "SynapseRAGChain"),
        "ConversationMemoryManager": (
            "ai_engine.rag.memory",
            "ConversationMemoryManager",
        ),
        "RAGPipeline": ("ai_engine.rag.pipeline", "RAGPipeline"),
        # Allow direct module access (needed for patch("ai_engine.rag.pipeline", ...))
        "pipeline": ("ai_engine.rag.pipeline", None),
        "retriever": ("ai_engine.rag.retriever", None),
        "chain": ("ai_engine.rag.chain", None),
        "memory": ("ai_engine.rag.memory", None),
    }
    if name in _map:
        import importlib

        module_path, cls_name = _map[name]
        mod = importlib.import_module(module_path)
        # If cls_name is None, return the module itself (for submodule access)
        return mod if cls_name is None else getattr(mod, cls_name)
    raise AttributeError(f"module 'ai_engine.rag' has no attribute {name!r}")


__all__ = [
    "SynapseRetriever",
    "SynapseRAGChain",
    "ConversationMemoryManager",
    "RAGPipeline",
    "get_rag_pipeline",
]
