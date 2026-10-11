# -*- coding: utf-8 -*-
"""
Moduł ładowania danych.

Wczytuje historię rozmowy z pliku JSON do wspólnej, prostej struktury:
listy słowników o kluczach: id, author, content, timestamp (obiekt datetime).

Obsługiwane formaty:
1. DiscordChatExporter (klucz "messages" z polami author.name / content / timestamp)
   - to także format naszych danych syntetycznych.
2. Format prosty: lista obiektów {author, content, timestamp}.

Dzięki temu aplikacja działa na danych testowych ORAZ na prawdziwym
eksporcie z Discorda bez zmian w kodzie.
"""

import json
from datetime import datetime
from dateutil import parser as date_parser


def _parse_ts(value):
    """Zamienia różne formaty znacznika czasu na obiekt datetime (bez strefy)."""
    if isinstance(value, datetime):
        dt = value
    else:
        dt = date_parser.parse(str(value))
    # Ujednolicamy do czasu naiwnego (bez strefy) dla prostoty porównań.
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt


def load_messages_from_dict(data):
    """Przyjmuje sparsowany JSON (dict lub list) i zwraca listę wiadomości."""
    raw = []
    if isinstance(data, dict) and "messages" in data:
        raw = data["messages"]
    elif isinstance(data, list):
        raw = data
    else:
        raise ValueError("Nieobsługiwany format danych: oczekiwano listy lub obiektu z kluczem 'messages'.")

    out = []
    for i, m in enumerate(raw):
        # Autor: format Discord (author.name/nickname) lub prosty (author jako tekst).
        author = "?"
        a = m.get("author")
        if isinstance(a, dict):
            author = a.get("nickname") or a.get("name") or a.get("username") or "?"
        elif isinstance(a, str):
            author = a

        content = (m.get("content") or "").strip()
        ts_value = m.get("timestamp") or m.get("time") or m.get("date")
        if not content or ts_value is None:
            continue  # pomijamy puste wiadomości i systemowe wpisy bez treści

        out.append({
            "id": str(m.get("id", i)),
            "author": author,
            "content": content,
            "timestamp": _parse_ts(ts_value),
        })

    out.sort(key=lambda x: x["timestamp"])
    return out


def load_messages(path):
    """Wczytuje wiadomości z pliku JSON pod podaną ścieżką."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return load_messages_from_dict(data)


if __name__ == "__main__":
    import os
    p = os.path.join(os.path.dirname(__file__), "data", "sample_chat.json")
    msgs = load_messages(p)
    print(f"Wczytano {len(msgs)} wiadomosci.")
    print("Zakres:", msgs[0]["timestamp"], "->", msgs[-1]["timestamp"])
    for m in msgs[:3]:
        print(f"  [{m['timestamp']}] {m['author']}: {m['content'][:50]}")
