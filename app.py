# -*- coding: utf-8 -*-
"""
Aplikacja webowa (Streamlit): wyszukiwanie i streszczanie fragmentów rozmów.

Uruchomienie:
    streamlit run app.py

Przepływ:
  1. Wczytaj historię rozmowy (dane przykładowe lub wgrany plik JSON / eksport Discorda).
  2. Wpisz prompt (czego szukasz) i/lub wybierz zakres czasu (od–do).
  3. Aplikacja wyszukuje semantycznie pasujące wiadomości, buduje spójny
     fragment i streszcza go za pomocą GenSI (lub trybu awaryjnego).
"""

import os
import json
from datetime import datetime, time

# Wczytanie pliku .env (jeśli istnieje) - wygodne ustawianie kluczy API.
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import streamlit as st

from data_loader import load_messages, load_messages_from_dict
from search import (ConversationSearch, messages_to_transcript,
                    messages_to_numbered_transcript)
import summarizer
from summarizer import summarize, answer_question, extract_citation_indices

st.set_page_config(page_title="Streszczacz rozmów (GenSI)", page_icon="💬", layout="wide")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
SAMPLE_PATH = os.path.join(DATA_DIR, "sample_chat.json")


@st.cache_resource(show_spinner="Buduję indeks (embeddingi)...")
def get_search_index(messages_json, engine_pref):
    """Buduje i cache'uje wyszukiwarkę. Klucz cache = treść danych + silnik."""
    data = json.loads(messages_json)
    messages = load_messages_from_dict(data)
    return ConversationSearch(messages, prefer=engine_pref), messages


# ---------------------------------------------------------------------------
# Pasek boczny - konfiguracja
# ---------------------------------------------------------------------------
st.sidebar.title("Konfiguracja")

source = st.sidebar.radio(
    "Źródło danych",
    ["(wybierz źródło)", "Dane przykładowe", "Wgraj plik JSON / eksport Discorda",
     "Pobierz z Discorda (bot)"],
)

raw_json = None
if source == "Dane przykładowe":
    if os.path.exists(SAMPLE_PATH):
        with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
            raw_json = f.read()
    else:
        st.sidebar.error("Brak pliku z danymi przykładowymi. Uruchom: python generate_data.py")
elif source == "Wgraj plik JSON / eksport Discorda":
    up = st.sidebar.file_uploader("Plik JSON", type=["json"])
    if up is not None:
        raw_json = up.read().decode("utf-8")
elif source == "Pobierz z Discorda (bot)":
    # Pobieranie bezpośrednio z Discorda przez API (bot).
    token = st.sidebar.text_input(
        "Token bota", type="password",
        value=os.environ.get("DISCORD_BOT_TOKEN", ""),
        help="Bot musi być na serwerze i mieć: Wyświetlanie kanałów, Czytanie historii czatu.",
    )
    channel_id = st.sidebar.text_input(
        "ID kanału",
        help="Discord → Ustawienia → Zaawansowane → Tryb developera, "
             "potem prawy klik na kanał → Kopiuj ID kanału.",
    )
    if st.sidebar.button("Pobierz z Discorda"):
        try:
            from discord_fetch import fetch_as_dict
            with st.spinner("Pobieram wiadomości z Discorda..."):
                data = fetch_as_dict(channel_id.strip(), token.strip())
            st.session_state["discord_json"] = json.dumps(data)
            st.sidebar.success(f"Pobrano {data['messageCount']} wiadomości.")
        except Exception as e:
            st.sidebar.error(f"Błąd pobierania: {e}")
    raw_json = st.session_state.get("discord_json")

engine_pref = st.sidebar.selectbox(
    "Silnik wyszukiwania (embeddingi)",
    ["auto", "tfidf", "keyword"],
    help="auto = spróbuj modelu semantycznego (sentence-transformers), "
         "z fallbackiem do TF-IDF i pokrycia słów.",
)

sum_pref = st.sidebar.selectbox(
    "Silnik streszczania (GenSI)",
    ["auto", "gemini", "anthropic", "openai", "extractive"],
    help="auto = użyj API jeśli ustawiono klucz, inaczej tryb awaryjny.",
)

with st.sidebar.expander("Status kluczy API"):
    st.write("Google Gemini:", "ustawiony" if (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")) else "brak")
    st.write("Anthropic:", "ustawiony" if os.environ.get("ANTHROPIC_API_KEY") else "brak")
    st.write("OpenAI:", "ustawiony" if os.environ.get("OPENAI_API_KEY") else "brak")
    st.caption("Bez klucza działa tryb awaryjny (ekstrakcyjny).")


# ---------------------------------------------------------------------------
# Strona główna
# ---------------------------------------------------------------------------
st.title("Streszczacz fragmentów rozmów")
st.caption("Wyszukiwanie semantyczne + streszczanie (GenSI) historii czatu. "
           "Projekt zaliczeniowy.")

if not raw_json:
    st.markdown(
        """
        ### Jak zacząć

        To narzędzie do **przeszukiwania, streszczania i odpytywania** historii
        rozmów z serwera Discord z użyciem generatywnej sztucznej inteligencji.

        **Co potrafi:**
        - **wyszukiwanie semantyczne**: znajduje wiadomości po znaczeniu, nie tylko po słowach,
        - **streszczanie**: zwięzłe podsumowanie wybranego wątku lub zakresu czasu,
        - **pytanie i odpowiedź z cytatami**: odpowiada na pytania i wskazuje wiadomości źródłowe.

        **Aby zacząć**, wybierz źródło danych w panelu po lewej:
        *Dane przykładowe* (gotowa rozmowa demonstracyjna), wgranie pliku JSON
        albo pobranie kanału prosto z Discorda.
        """
    )
    st.stop()

try:
    search, messages = get_search_index(raw_json, engine_pref)
except Exception as e:
    st.error(f"Nie udało się wczytać danych: {e}")
    st.stop()

if not messages:
    st.warning("Wczytano 0 wiadomości - sprawdź format pliku.")
    st.stop()

t_min = messages[0]["timestamp"]
t_max = messages[-1]["timestamp"]

# Pasek informacyjny
c1, c2, c3, c4 = st.columns(4)
c1.metric("Wiadomości", len(messages))
c2.metric("Uczestnicy", len({m["author"] for m in messages}))
c3.metric("Od", t_min.strftime("%Y-%m-%d"))
c4.metric("Do", t_max.strftime("%Y-%m-%d"))
st.caption(f"Silnik wyszukiwania: **{search.engine_name}**")

st.divider()

# --- Formularz zapytania ---------------------------------------------------
tryb = st.radio(
    "Tryb działania",
    ["Streszczenie", "Pytanie i odpowiedź (z cytatami)"],
    horizontal=True,
)
qa_mode = tryb.startswith("Pytanie")

left, right = st.columns([2, 1])

with left:
    if qa_mode:
        query = st.text_input(
            "Zadaj pytanie o rozmowę",
            placeholder="np. ile kosztuje nocleg i kto go rezerwuje?",
        )
    else:
        query = st.text_input(
            "Temat do streszczenia (opcjonalnie)",
            placeholder="np. wyjazd w góry - zostaw puste, aby streścić całość",
            help="Z tematem: streszczamy dopasowany fragment (wyszukiwanie "
                 "semantyczne). Bez tematu: streszczamy cały wybrany zakres.",
        )

with right:
    top_k = st.slider("Liczba trafień", 1, 15, 5)
    context = st.slider("Kontekst (wiadomości wokół trafienia)", 0, 5, 2)

use_time = st.checkbox("Ogranicz do zakresu czasu (od–do)", value=False)
start_dt = end_dt = None
if use_time:
    d1, d2 = st.columns(2)
    with d1:
        sd = st.date_input("Data od", value=t_min.date(),
                           min_value=t_min.date(), max_value=t_max.date())
        sti = st.time_input("Godzina od", value=time(0, 0))
    with d2:
        ed = st.date_input("Data do", value=t_max.date(),
                           min_value=t_min.date(), max_value=t_max.date())
        eti = st.time_input("Godzina do", value=time(23, 59))
    start_dt = datetime.combine(sd, sti)
    end_dt = datetime.combine(ed, eti)

go = st.button("Odpowiedz" if qa_mode else "Streść", type="primary")

# --- Wyniki ----------------------------------------------------------------
if go:
    if qa_mode and not (query and query.strip()):
        st.warning("Wpisz pytanie, aby uzyskać odpowiedź.")
        st.stop()

    hits = search.search(query, start=start_dt, end=end_dt, top_k=top_k)
    if not hits:
        st.warning("Brak wiadomości pasujących do zapytania / zakresu czasu.")
        st.stop()

    # Buduj spójny fragment (z kontekstem) lub, gdy brak promptu, cały zakres czasu.
    if query and query.strip():
        fragment = search.build_fragment([h["index"] for h in hits],
                                         context=context, start=start_dt, end=end_dt)
    else:
        fragment = [h["message"] for h in hits]

    transcript = messages_to_transcript(fragment)

    if qa_mode:
        # --- Tryb pytanie-odpowiedź z cytatami ---
        numbered = messages_to_numbered_transcript(fragment)
        tab1, tab2, tab3 = st.tabs(["Odpowiedź", "Cytaty", "Fragment"])

        with tab1:
            with st.spinner("Szukam odpowiedzi (GenSI)..."):
                answer, engine_used = answer_question(fragment, numbered,
                                                      query, prefer=sum_pref)
            st.success(f"Silnik odpowiedzi: {engine_used}")
            if summarizer.LAST_ERROR:
                st.error(f"Błąd wywołania API: {summarizer.LAST_ERROR}")
            st.markdown(answer)

        with tab2:
            cited = extract_citation_indices(answer)
            if not cited:
                st.info("Model nie wskazał konkretnych numerów wiadomości.")
            else:
                st.write("Wiadomości przytoczone w odpowiedzi:")
                for n in cited:
                    if 1 <= n <= len(fragment):
                        m = fragment[n - 1]
                        ts = m["timestamp"].strftime("%Y-%m-%d %H:%M")
                        st.markdown(f"> **[{n}] {m['author']}** · `{ts}`  \n> {m['content']}")

        with tab3:
            st.write(f"Spójny fragment ({len(fragment)} wiadomości):")
            st.code(numbered, language=None)
    else:
        # --- Tryb streszczenia ---
        tab1, tab2, tab3 = st.tabs(["Streszczenie", "Trafienia", "Fragment"])

        with tab1:
            with st.spinner("Streszczam fragment (GenSI)..."):
                summary, engine_used = summarize(fragment, transcript,
                                                 user_query=query or None, prefer=sum_pref)
            st.success(f"Silnik streszczania: {engine_used}")
            if summarizer.LAST_ERROR:
                st.error(f"Błąd wywołania API: {summarizer.LAST_ERROR}")
            st.markdown(summary)

        with tab2:
            st.write(f"Znaleziono {len(hits)} najlepiej pasujących wiadomości:")
            for h in hits:
                m = h["message"]
                sc = f"{h['score']:.3f}" if h["score"] is not None else "-"
                ts = m["timestamp"].strftime("%Y-%m-%d %H:%M")
                st.markdown(f"**[{sc}]** `{ts}` **{m['author']}**: {m['content']}")

        with tab3:
            st.write(f"Spójny fragment ({len(fragment)} wiadomości):")
            st.code(transcript, language=None)
