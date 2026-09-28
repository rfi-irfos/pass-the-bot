from __future__ import annotations

from collections import OrderedDict

from sentence_transformers import SentenceTransformer, util

# extract_soft_skills calls best_match once per (sentence, soft-skill entry)
# pair, so the same sentence text is re-submitted once per entry. Bound the
# cache instead of using an unbounded dict like _phrase_cache: unlike the
# curated, fixed anchor-phrase lists, sentence text is arbitrary per-request
# resume/posting content on a long-lived Embedder singleton, so caching it
# forever would leak memory over the life of the process.
_SENTENCE_CACHE_SIZE = 512


class Embedder:
    """Thin wrapper around a small local sentence-embedding model. No network
    calls at inference time once the model is cached locally; no generative
    model involved, so results are deterministic for a fixed model + input.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = SentenceTransformer(model_name)
        self._phrase_cache: dict[tuple[str, ...], object] = {}
        self._sentence_cache: OrderedDict[str, object] = OrderedDict()

    def _encode_phrases(self, phrases: list[str]):
        key = tuple(phrases)
        cached = self._phrase_cache.get(key)
        if cached is None:
            cached = self._model.encode(phrases, convert_to_tensor=True)
            self._phrase_cache[key] = cached
        return cached

    def _encode_sentence(self, text: str):
        cached = self._sentence_cache.get(text)
        if cached is not None:
            self._sentence_cache.move_to_end(text)
            return cached
        embedding = self._model.encode(text, convert_to_tensor=True)
        self._sentence_cache[text] = embedding
        if len(self._sentence_cache) > _SENTENCE_CACHE_SIZE:
            self._sentence_cache.popitem(last=False)
        return embedding

    def best_match(
        self, text: str, phrases: list[str], cache_phrases: bool = True
    ) -> tuple[str, float]:
        """Score `text` against every phrase in `phrases` and return the
        best-matching (phrase, score) pair.

        `cache_phrases` controls whether `phrases` is routed through the
        unbounded `_phrase_cache`. Leave it at the default (True) for
        curated, fixed anchor-phrase lists (e.g. extract_soft_skills),
        where the same small set of phrases is re-submitted across many
        calls and caching saves real work. Pass False when `phrases` is
        arbitrary per-request text (e.g. matcher.match_open_requirements
        passing in the resume's own sentences) -- caching that would grow
        `_phrase_cache` unboundedly for the life of a long-lived Embedder
        singleton, the same leak `_sentence_cache`'s bounded LRU exists to
        avoid for the "text" side of this call.
        """
        text_emb = self._encode_sentence(text)
        if cache_phrases:
            phrase_embs = self._encode_phrases(phrases)
        else:
            phrase_embs = self._model.encode(phrases, convert_to_tensor=True)
        scores = util.cos_sim(text_emb, phrase_embs)[0]
        best_idx = int(scores.argmax())
        return phrases[best_idx], float(scores[best_idx])
