from __future__ import annotations

from sentence_transformers import SentenceTransformer, util


class Embedder:
    """Thin wrapper around a small local sentence-embedding model. No network
    calls at inference time once the model is cached locally; no generative
    model involved, so results are deterministic for a fixed model + input.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = SentenceTransformer(model_name)

    def best_match(self, text: str, phrases: list[str]) -> tuple[str, float]:
        text_emb = self._model.encode(text, convert_to_tensor=True)
        phrase_embs = self._model.encode(phrases, convert_to_tensor=True)
        scores = util.cos_sim(text_emb, phrase_embs)[0]
        best_idx = int(scores.argmax())
        return phrases[best_idx], float(scores[best_idx])
