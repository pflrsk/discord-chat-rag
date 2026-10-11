# -*- coding: utf-8 -*-
"""
Moduł wyszukiwania semantycznego + filtrowania po czasie.

Sednem jest zamiana każdej wiadomości na wektor (embedding) i porównywanie
go z wektorem zapytania użytkownika za pomocą podobieństwa kosinusowego.
Dzięki temu wyszukiwanie działa "po znaczeniu", a nie tylko po słowach
(np. zapytanie "gdzie nocujemy" trafi w wiadomość o rezerwacji schroniska).

Strategia wyboru silnika embeddingów (degradacja łagodna):
1. sentence-transformers (model wielojęzyczny)  -> najlepsza jakość, lokalnie, za darmo
2. TF-IDF (scikit-learn)                          -> lekki fallback, bez pobierania modelu
3. proste pokrycie słów (bez zależności)          -> ostateczny fallback

Filtr czasu zawęża zbiór wiadomości do zakresu [start, end] PRZED rankingiem.
"""

from datetime import datetime
import math
import re


# ---------------------------------------------------------------------------
# Silniki embeddingów
# ---------------------------------------------------------------------------
class _SentenceTransformerEngine:
    name = "sentence-transformers (semantyczny, wielojęzyczny)"

    def __init__(self, model_name="paraphrase-multilingual-MiniLM-L12-v2"):
        from sentence_transformers import SentenceTransformer  # import leniwy
        import numpy as np
        self._np = np
        self.model = SentenceTransformer(model_name)

    def fit(self, texts):
        self._emb = self.model.encode(texts, normalize_embeddings=True,
                                      convert_to_numpy=True)

    def query_scores(self, query):
        q = self.model.encode([query], normalize_embeddings=True,
                              convert_to_numpy=True)[0]
        return (self._emb @ q)  # podobieństwo kosinusowe (wektory znormalizowane)


class _TfidfEngine:
    name = "TF-IDF (fallback, scikit-learn)"

    def __init__(self):
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        self._cos = cosine_similarity
        self.vectorizer = TfidfVectorizer()

    def fit(self, texts):
        self._matrix = self.vectorizer.fit_transform(texts)

    def query_scores(self, query):
        qv = self.vectorizer.transform([query])
        return self._cos(qv, self._matrix)[0]


class _KeywordEngine:
    """Ostateczny fallback bez żadnych zależności - pokrycie słów (Jaccard)."""
    name = "pokrycie słów (fallback bez bibliotek)"

    @staticmethod
    def _tokens(text):
        return set(re.findall(r"\w+", text.lower()))

    def fit(self, texts):
        self._sets = [self._tokens(t) for t in texts]

    def query_scores(self, query):
        q = self._tokens(query)
        scores = []
        for s in self._sets:
            if not q or not s:
                scores.append(0.0)
            else:
                inter = len(q & s)
                union = len(q | s)
                scores.append(inter / union if union else 0.0)
        return scores


def _build_engine(prefer="auto"):
    """Tworzy najlepszy dostępny silnik embeddingów."""
    order = []
    if prefer in ("auto", "semantic"):
        order = ["st", "tfidf", "keyword"]
    elif prefer == "tfidf":
        order = ["tfidf", "keyword"]
    elif prefer == "keyword":
        order = ["keyword"]

    for kind in order:
        try:
            if kind == "st":
                return _SentenceTransformerEngine()
            if kind == "tfidf":
                return _TfidfEngine()
            if kind == "keyword":
                return _KeywordEngine()
        except Exception:
            continue
    return _KeywordEngine()


# ---------------------------------------------------------------------------
# Główna klasa wyszukiwarki
# ---------------------------------------------------------------------------
class ConversationSearch:
    def __init__(self, messages, prefer="auto"):
        """messages: lista słowników z data_loader.load_messages()."""
        self.messages = messages
        self.engine = _build_engine(prefer)
        self.engine_name = self.engine.name
        self._texts = [f"{m['author']}: {m['content']}" for m in messages]
        if self._texts:
            self.engine.fit(self._texts)

    # --- filtr czasu -------------------------------------------------------
    def _in_range(self, m, start, end):
        if start is not None and m["timestamp"] < start:
            return False
        if end is not None and m["timestamp"] > end:
            return False
        return True

    def filter_by_time(self, start=None, end=None):
        """Zwraca indeksy wiadomości mieszczących się w zakresie czasu."""
        return [i for i, m in enumerate(self.messages) if self._in_range(m, start, end)]

    # --- wyszukiwanie ------------------------------------------------------
    def search(self, query, start=None, end=None, top_k=5):
        """
        Zwraca listę dopasowań: [{index, message, score}] posortowaną malejąco.
        Najpierw zawęża zakres czasu, potem rankuje semantycznie wg zapytania.
        """
        candidates = self.filter_by_time(start, end)
        if not candidates:
            return []
        if not query or not query.strip():
            # Brak zapytania => zwracamy po prostu fragment z zakresu czasu (chronologicznie).
            return [{"index": i, "message": self.messages[i], "score": None}
                    for i in candidates]

        scores = self.engine.query_scores(query)
        ranked = sorted(candidates, key=lambda i: float(scores[i]), reverse=True)
        top = ranked[:top_k]
        return [{"index": i, "message": self.messages[i], "score": float(scores[i])}
                for i in top]

    # --- budowa spójnego fragmentu ----------------------------------------
    def build_fragment(self, hit_indices, context=2, start=None, end=None):
        """
        Z listy trafień buduje spójny fragment rozmowy: dla każdego trafienia
        dokłada `context` wiadomości przed i po (kontekst), scala nakładające
        się przedziały i zwraca wiadomości w kolejności chronologicznej.
        Wynik jest dodatkowo przycięty do zakresu czasu [start, end].
        """
        if not hit_indices:
            return []
        n = len(self.messages)
        keep = set()
        for idx in hit_indices:
            lo = max(0, idx - context)
            hi = min(n - 1, idx + context)
            for j in range(lo, hi + 1):
                keep.add(j)
        ordered = sorted(keep)
        return [self.messages[j] for j in ordered if self._in_range(self.messages[j], start, end)]


def messages_to_transcript(messages):
    """Zamienia listę wiadomości na czytelny transkrypt tekstowy."""
    lines = []
    for m in messages:
        ts = m["timestamp"].strftime("%Y-%m-%d %H:%M")
        lines.append(f"[{ts}] {m['author']}: {m['content']}")
    return "\n".join(lines)


def messages_to_numbered_transcript(messages):
    """Transkrypt z numerami wiadomości (1, 2, 3...) do cytowania w trybie Q&A."""
    lines = []
    for i, m in enumerate(messages, 1):
        ts = m["timestamp"].strftime("%Y-%m-%d %H:%M")
        lines.append(f"[{i}] ({ts}) {m['author']}: {m['content']}")
    return "\n".join(lines)


if __name__ == "__main__":
    import os
    from data_loader import load_messages
    p = os.path.join(os.path.dirname(__file__), "data", "sample_chat.json")
    msgs = load_messages(p)
    s = ConversationSearch(msgs, prefer="auto")
    print("Silnik:", s.engine_name)
    hits = s.search("gdzie będziemy spać podczas wyjazdu", top_k=3)
    for h in hits:
        sc = f"{h['score']:.3f}" if h["score"] is not None else "-"
        print(f"  [{sc}] {h['message']['author']}: {h['message']['content']}")
