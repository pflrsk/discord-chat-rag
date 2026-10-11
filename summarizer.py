# -*- coding: utf-8 -*-
"""
Moduł generatywny (GenSI): streszczanie oraz odpowiadanie na pytania.

Dwie funkcje publiczne:
  summarize(...)        -- streszcza fragment rozmowy,
  answer_question(...)  -- odpowiada na pytanie na podstawie fragmentu i podaje
                           numery wiadomości źródłowych (cytaty), w duchu RAG.

Wybór silnika (degradacja łagodna):
1. API LLM - Google Gemini (GEMINI_API_KEY), Anthropic (ANTHROPIC_API_KEY)
   lub OpenAI (OPENAI_API_KEY).
2. Tryb awaryjny - bez żadnego klucza. Streszczanie: ekstrakcyjne (najważniejsze
   wiadomości). Q&A: zwraca najbardziej powiązane wiadomości jako podpowiedź.

Zmienne środowiskowe (opcjonalne):
  GEMINI_API_KEY,    GEMINI_MODEL    (domyślnie gemini-2.5-flash)
  ANTHROPIC_API_KEY, ANTHROPIC_MODEL (domyślnie claude-sonnet-4-6)
  OPENAI_API_KEY,    OPENAI_MODEL    (domyślnie gpt-4o-mini)
"""

import os
import re


# ---------------------------------------------------------------------------
# Prompty systemowe
# ---------------------------------------------------------------------------
SUMMARY_SYSTEM_PROMPT = (
    "Jesteś asystentem, który zwięźle streszcza fragmenty rozmów. "
    "Piszesz po polsku, rzeczowo i neutralnie. Nie zmyślasz informacji "
    "spoza transkryptu."
)

QA_SYSTEM_PROMPT = (
    "Jesteś asystentem, który odpowiada na pytania WYŁĄCZNIE na podstawie "
    "podanego, ponumerowanego fragmentu rozmowy. Piszesz po polsku, rzeczowo. "
    "Po każdej informacji w odpowiedzi podajesz numery wiadomości źródłowych "
    "w nawiasach kwadratowych, np. [2] albo [2, 5]. Jeśli odpowiedzi nie ma "
    "w transkrypcie, napisz to wprost i nie zmyślaj."
)


def _build_summary_prompt(transcript, user_query=None):
    instr = (
        "Streść poniższy fragment rozmowy. Podaj:\n"
        "1. Krótkie streszczenie (2-4 zdania).\n"
        "2. Najważniejsze ustalenia/fakty w punktach.\n"
        "3. Ewentualne zadania do wykonania (kto, co), jeśli występują.\n"
    )
    if user_query:
        instr += (
            f"\nUżytkownik szukał informacji na temat: \"{user_query}\". "
            "Zwróć szczególną uwagę na ten wątek.\n"
        )
    return f"{instr}\n--- TRANSKRYPT ---\n{transcript}\n--- KONIEC ---"


def _build_qa_prompt(numbered_transcript, question):
    return (
        "Odpowiedz na pytanie użytkownika na podstawie poniższego, "
        "ponumerowanego fragmentu rozmowy. W odpowiedzi cytuj źródła, podając "
        "numery wiadomości w nawiasach kwadratowych (np. [3] lub [3, 7]). "
        "Jeśli w transkrypcie nie ma odpowiedzi, napisz to wprost.\n\n"
        f"PYTANIE: {question}\n\n"
        f"--- FRAGMENT (ponumerowany) ---\n{numbered_transcript}\n--- KONIEC ---"
    )


# ---------------------------------------------------------------------------
# Wywołania dostawców API (generyczne: system + treść użytkownika -> tekst)
# ---------------------------------------------------------------------------
def _call_gemini(system, user):
    from google import genai
    from google.genai import types
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    client = genai.Client()  # czyta GEMINI_API_KEY lub GOOGLE_API_KEY
    cfg = dict(system_instruction=system, max_output_tokens=2000, temperature=0.3)
    # Wyłączenie "myślenia" w modelach 2.5 - inaczej zjada limit tokenów wyjścia.
    try:
        cfg["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
    except Exception:
        pass
    resp = client.models.generate_content(
        model=model, contents=user,
        config=types.GenerateContentConfig(**cfg),
    )
    return resp.text


def _call_anthropic(system, user):
    import anthropic
    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    client = anthropic.Anthropic()  # czyta ANTHROPIC_API_KEY
    msg = client.messages.create(
        model=model, max_tokens=1200, system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def _call_openai(system, user):
    from openai import OpenAI
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAI()  # czyta OPENAI_API_KEY
    resp = client.chat.completions.create(
        model=model, max_tokens=1200,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content


_PROVIDERS = {
    "gemini":    (_call_gemini,    "Google Gemini API (GenSI)"),
    "anthropic": (_call_anthropic, "Anthropic API (GenSI)"),
    "openai":    (_call_openai,    "OpenAI API (GenSI)"),
}


def _available():
    return {
        "gemini": bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")),
        "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "openai": bool(os.environ.get("OPENAI_API_KEY")),
    }


# Ostatni błąd wywołania API (do wyświetlenia w aplikacji, gdy włączy się tryb awaryjny).
LAST_ERROR = None


def _generate(system, user, prefer):
    """Próbuje wygenerować tekst dostępnym modelem. Zwraca (tekst, nazwa) lub (None, None)."""
    global LAST_ERROR
    LAST_ERROR = None
    has = _available()
    if prefer == "auto":
        order = [p for p in ("gemini", "anthropic", "openai") if has[p]]
    elif prefer in _PROVIDERS:
        order = [prefer] if has[prefer] else []
    else:  # "extractive" lub nieznane
        order = []

    for p in order:
        func, name = _PROVIDERS[p]
        try:
            return func(system, user), name
        except Exception as e:
            LAST_ERROR = f"{name}: {type(e).__name__}: {e}"
            continue
    return None, None


# ---------------------------------------------------------------------------
# Tryb awaryjny (bez API)
# ---------------------------------------------------------------------------
_STOPWORDS = set("""
i oraz a ale lub albo że to się na w z do od za po o u co jak kto gdzie kiedy
czy nie tak jest są być mam masz ma mamy macie mają ja ty on ona ono my wy oni
mnie ci mu jej nas was im ten ta to te ten tym tej tego dla bez przy nad pod
już tylko też także bardzo może można żeby bo więc no ok hej
""".split())


def _tokenize(text):
    return [w for w in re.findall(r"\w+", text.lower()) if w not in _STOPWORDS and len(w) > 2]


def _rank_messages(messages, query=None, max_points=6):
    """Zwraca indeksy najistotniejszych wiadomości metodą częstości słów."""
    freq = {}
    for m in messages:
        for w in _tokenize(m["content"]):
            freq[w] = freq.get(w, 0) + 1
    if query:
        for w in _tokenize(query):
            freq[w] = freq.get(w, 0) + 5
    scored = []
    for idx, m in enumerate(messages):
        toks = _tokenize(m["content"])
        if not toks:
            continue
        score = sum(freq.get(w, 0) for w in toks) / (len(toks) ** 0.5)
        scored.append((score, idx))
    scored.sort(reverse=True)
    return sorted(i for _, i in scored[:max_points])


def _summarize_extractive(messages, user_query=None, max_points=6, deliberate=False):
    if not messages:
        return "Brak wiadomości do streszczenia w wybranym zakresie."
    chosen = _rank_messages(messages, user_query, max_points)
    authors = sorted({m["author"] for m in messages})
    t0 = messages[0]["timestamp"].strftime("%Y-%m-%d %H:%M")
    t1 = messages[-1]["timestamp"].strftime("%Y-%m-%d %H:%M")
    naglowek = ("STRESZCZENIE (tryb ekstrakcyjny)" if deliberate
                else "STRESZCZENIE (tryb awaryjny - ekstrakcyjne, bez API LLM)")
    lines = [naglowek, ""]
    lines.append(f"Zakres: {t0} – {t1} | Liczba wiadomości: {len(messages)} | "
                 f"Uczestnicy: {', '.join(authors)}")
    if user_query:
        lines.append(f"Szukany wątek: {user_query}")
    lines.append("")
    lines.append("Najważniejsze fragmenty:")
    for idx in chosen:
        m = messages[idx]
        ts = m["timestamp"].strftime("%m-%d %H:%M")
        lines.append(f"  • [{ts}] {m['author']}: {m['content']}")
    if not deliberate:
        lines.append("")
        lines.append("(Aby uzyskać pełne streszczenie generatywne, ustaw klucz API, np. zmienną GEMINI_API_KEY.)")
    return "\n".join(lines)


def _answer_extractive(messages, question, max_points=5, deliberate=False):
    if not messages:
        return "Brak wiadomości do analizy w wybranym zakresie."
    chosen = _rank_messages(messages, question, max_points)
    if deliberate:
        lines = ["ODPOWIEDŹ (tryb ekstrakcyjny)", ""]
        lines.append("Tryb ekstrakcyjny nie generuje pełnej odpowiedzi - poniżej "
                     "wiadomości najbardziej powiązane z pytaniem:")
    else:
        lines = ["ODPOWIEDŹ (tryb awaryjny - bez API LLM)", ""]
        lines.append("Nie można wygenerować odpowiedzi bez modelu językowego. "
                     "Poniżej wiadomości najbardziej powiązane z pytaniem:")
    lines.append("")
    for idx in chosen:
        m = messages[idx]
        ts = m["timestamp"].strftime("%m-%d %H:%M")
        lines.append(f"  • [{idx + 1}] [{ts}] {m['author']}: {m['content']}")
    if not deliberate:
        lines.append("")
        lines.append("(Aby uzyskać pełną odpowiedź z cytatami, ustaw klucz API, np. zmienną GEMINI_API_KEY.)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Funkcje publiczne
# ---------------------------------------------------------------------------
def summarize(messages, transcript, user_query=None, prefer="auto"):
    """Zwraca (tekst_streszczenia, nazwa_silnika). prefer: auto|gemini|anthropic|openai|extractive."""
    if prefer == "extractive":
        return _summarize_extractive(messages, user_query, deliberate=True), \
            "Tryb ekstrakcyjny (wybrany)"
    text, engine = _generate(SUMMARY_SYSTEM_PROMPT,
                             _build_summary_prompt(transcript, user_query), prefer)
    if text is not None:
        return text, engine
    return _summarize_extractive(messages, user_query), "Tryb awaryjny (ekstrakcyjny)"


def answer_question(messages, numbered_transcript, question, prefer="auto"):
    """
    Odpowiada na pytanie na podstawie fragmentu. Zwraca (tekst_odpowiedzi, nazwa_silnika).
    Odpowiedź zawiera numery wiadomości źródłowych w nawiasach [n] (do wyświetlenia cytatów).
    """
    if prefer == "extractive":
        return _answer_extractive(messages, question, deliberate=True), \
            "Tryb ekstrakcyjny (wybrany)"
    text, engine = _generate(QA_SYSTEM_PROMPT,
                             _build_qa_prompt(numbered_transcript, question), prefer)
    if text is not None:
        return text, engine
    return _answer_extractive(messages, question), "Tryb awaryjny (ekstrakcyjny)"


def extract_citation_indices(answer_text):
    """Wyciąga z odpowiedzi numery cytatów, np. z '[2]' i '[2, 5]'. Zwraca posortowaną listę intów."""
    nums = set()
    for group in re.findall(r"\[([\d,\s]+)\]", answer_text):
        for part in group.split(","):
            part = part.strip()
            if part.isdigit():
                nums.add(int(part))
    return sorted(nums)


if __name__ == "__main__":
    from data_loader import load_messages
    from search import ConversationSearch, messages_to_numbered_transcript
    p = os.path.join(os.path.dirname(__file__), "data", "sample_chat.json")
    msgs = load_messages(p)
    s = ConversationSearch(msgs, prefer="tfidf")
    q = "ile kosztuje nocleg i kto rezerwuje?"
    hits = s.search(q, top_k=5)
    frag = s.build_fragment([h["index"] for h in hits], context=2)
    nt = messages_to_numbered_transcript(frag)
    ans, engine = answer_question(frag, nt, q, prefer="extractive")
    print("Silnik:", engine)
    print(ans)
    print("Cytaty:", extract_citation_indices(ans))
