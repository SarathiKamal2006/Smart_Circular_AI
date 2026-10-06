"""Semantic retrieval.

Preferred stack : Sentence-Transformers (MiniLM) embeddings  +  FAISS inner-product index
                  (blended with TF-IDF for robustness on exact terms such as dates / hall numbers)
Fallback stack  : TF-IDF cosine similarity (scikit-learn) – no model download required.
"""
from __future__ import annotations

import threading

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from .. import config


class Retriever:
    def __init__(self):
        self._lock = threading.Lock()
        self.chunks: list[dict] = []
        self._tfidf = None
        self._tfidf_mat = None
        self._emb = None  # numpy matrix (n, d) normalised
        self._faiss = None
        self._model = None
        self._model_failed = config.EMBEDDINGS_MODE == "tfidf"
        self.backend = "TF-IDF (cosine)"

    # ---------------------------------------------------------- embeddings
    def _load_model(self):
        if self._model is not None or self._model_failed:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            self._model = SentenceTransformer(config.EMBEDDING_MODEL)
        except Exception as e:  # not installed / offline
            print(f"[retriever] sentence-transformers unavailable ({type(e).__name__}); using TF-IDF")
            self._model_failed = True
        return self._model

    def _encode(self, texts: list[str]):
        m = self._load_model()
        if m is None:
            return None
        v = m.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(v, dtype="float32")

    # ------------------------------------------------------------- indexing
    def rebuild(self, chunks: list[dict]) -> None:
        with self._lock:
            self.chunks = chunks
            self._tfidf = self._tfidf_mat = self._emb = self._faiss = None
            if not chunks:
                return
            texts = [c["text"] for c in chunks]
            self._tfidf = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english")
            try:
                self._tfidf_mat = self._tfidf.fit_transform(texts)
            except ValueError:  # empty vocabulary
                self._tfidf = None
            emb = self._encode(texts)
            if emb is not None:
                self._emb = emb
                try:
                    import faiss  # type: ignore

                    idx = faiss.IndexFlatIP(emb.shape[1])
                    idx.add(emb)
                    self._faiss = idx
                    self.backend = "MiniLM embeddings + FAISS"
                except Exception:
                    self.backend = "MiniLM embeddings (numpy)"
            else:
                self.backend = "TF-IDF (cosine)"

    # --------------------------------------------------------------- search
    def _scores(self, query: str) -> np.ndarray:
        n = len(self.chunks)
        sc = np.zeros(n, dtype="float32")
        lex = np.zeros(n, dtype="float32")
        if self._tfidf is not None:
            q = self._tfidf.transform([query])
            lex = (self._tfidf_mat @ q.T).toarray().ravel().astype("float32")
        if self._emb is not None:
            qe = self._encode([query])
            if self._faiss is not None:
                s, i = self._faiss.search(qe, n)
                dense = np.zeros(n, dtype="float32")
                dense[i[0]] = s[0]
            else:
                dense = (self._emb @ qe[0]).astype("float32")
            sc = 0.7 * dense + 0.3 * lex
        else:
            sc = lex
        return sc

    def search(self, query: str, k: int = 4, circular_id: int | None = None) -> list[dict]:
        with self._lock:
            if not self.chunks:
                return []
            sc = self._scores(query)
            order = np.argsort(-sc)
            out = []
            for i in order:
                c = self.chunks[int(i)]
                if circular_id is not None and c["circular_id"] != circular_id:
                    continue
                out.append({**c, "score": float(sc[int(i)])})
                if len(out) >= k:
                    break
            return out

    # ----------------------------------------------- ad-hoc text ranking
    def rank_texts(self, query: str, texts: list[str]) -> list[float]:
        """Similarity of ``query`` to each string (used to pick the best sentences)."""
        if not texts:
            return []
        m = self._load_model()
        if m is not None:
            vecs = self._encode([query] + texts)
            dense = vecs[1:] @ vecs[0]
        else:
            dense = None
        try:
            tf = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True).fit(texts + [query])
            lex = (tf.transform(texts) @ tf.transform([query]).T).toarray().ravel()
        except ValueError:
            lex = np.zeros(len(texts))
        sc = lex if dense is None else 0.7 * dense + 0.3 * lex
        return [float(x) for x in sc]


retriever = Retriever()
