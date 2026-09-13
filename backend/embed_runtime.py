import os

from fastembed import TextEmbedding

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_model = None


def embed_query(text: str) -> list[float]:
    global _model
    if _model is None:
        _model = TextEmbedding(model_name=MODEL_NAME)
    return list(_model.embed([text]))[0].tolist()
