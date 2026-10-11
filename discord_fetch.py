# -*- coding: utf-8 -*-
"""
Bezpośrednie pobieranie wiadomości z kanału Discord przez oficjalne API (REST).

Zastępuje ręczny eksport DiscordChatExporterem: bot z uprawnieniami
"Wyświetlanie kanałów" i "Czytanie historii czatu" pobiera całą historię
kanału i zwraca ją w formacie zgodnym z resztą aplikacji.

Korzysta z oficjalnego API przez bota (nie self-bota ani scrapingu). Bot musi być
dodany do serwera i mieć dostęp do danego kanału.

Jak zdobyć ID kanału:
  Discord -> Ustawienia -> Zaawansowane -> włącz "Tryb developera".
  Następnie kliknij kanał prawym przyciskiem -> "Kopiuj ID kanału".

Użycie z linii poleceń:
  set DISCORD_BOT_TOKEN=...        (Windows cmd)
  python discord_fetch.py <ID_kanalu>            -> zapis do data/discord_export.json
  python discord_fetch.py <ID_kanalu> plik.json  -> zapis do wskazanego pliku
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error

API = "https://discord.com/api/v10"
HEADERS_UA = "conv-summarizer/1.0"


def _get(url, token):
    """Pojedyncze żądanie GET do API Discorda z obsługą limitu (429)."""
    while True:
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bot {token}",
            "User-Agent": HEADERS_UA,  # bez tego Cloudflare blokuje (błąd 1010)
        })
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:  # limit zapytań - poczekaj i powtórz
                try:
                    retry = float(json.loads(e.read().decode("utf-8")).get("retry_after", 2))
                except Exception:
                    retry = 2.0
                time.sleep(retry + 0.3)
                continue
            body = e.read().decode("utf-8", "ignore")[:300]
            if e.code == 401:
                raise RuntimeError("Nieprawidłowy token bota (401).")
            if e.code == 403:
                raise RuntimeError("Bot nie ma dostępu do tego kanału (403) - "
                                   "sprawdź uprawnienia: Wyświetlanie kanałów, "
                                   "Czytanie historii czatu.")
            if e.code == 404:
                raise RuntimeError("Nie znaleziono kanału (404) - sprawdź ID kanału.")
            raise RuntimeError(f"Błąd API Discorda ({e.code}): {body}")


def fetch_raw_messages(channel_id, token, max_messages=5000):
    """Pobiera surowe wiadomości z kanału (z paginacją). Zwraca listę obiektów API."""
    out = []
    before = None
    while len(out) < max_messages:
        url = f"{API}/channels/{channel_id}/messages?limit=100"
        if before:
            url += f"&before={before}"
        batch = _get(url, token)
        if not batch:
            break
        out.extend(batch)
        before = batch[-1]["id"]  # API zwraca od najnowszych; idziemy wstecz
        if len(batch) < 100:
            break
        time.sleep(0.3)
    return out


def to_export_dict(channel_id, raw_messages):
    """Konwertuje surowe wiadomości API do formatu zgodnego z data_loader."""
    msgs = []
    for m in raw_messages:
        content = (m.get("content") or "").strip()
        if not content:
            continue  # pomijamy wpisy systemowe / bez treści
        a = m.get("author", {}) or {}
        name = a.get("global_name") or a.get("username") or "?"
        msgs.append({
            "id": m.get("id"),
            "type": "Default",
            "timestamp": m.get("timestamp"),
            "content": content,
            "author": {"name": name, "nickname": name},
        })
    msgs.sort(key=lambda x: x["timestamp"] or "")
    return {
        "channel": {"id": str(channel_id)},
        "messages": msgs,
        "messageCount": len(msgs),
    }


def fetch_as_dict(channel_id, token, max_messages=5000):
    """Pobiera kanał i zwraca gotowy słownik (do bezpośredniego użycia w aplikacji)."""
    if not token:
        raise RuntimeError("Brak tokenu bota.")
    if not channel_id:
        raise RuntimeError("Brak ID kanału.")
    raw = fetch_raw_messages(channel_id, token, max_messages=max_messages)
    return to_export_dict(channel_id, raw)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Użycie: python discord_fetch.py <ID_kanalu> [plik_wyjsciowy.json]")
        print("Token podaj w zmiennej DISCORD_BOT_TOKEN.")
        sys.exit(1)

    token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        print("BŁĄD: ustaw token: set DISCORD_BOT_TOKEN=...")
        sys.exit(1)

    channel_id = sys.argv[1].strip()
    out_path = sys.argv[2] if len(sys.argv) > 2 else \
        os.path.join(os.path.dirname(__file__), "data", "discord_export.json")

    print(f"Pobieram wiadomości z kanału {channel_id}...")
    data = fetch_as_dict(channel_id, token)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Zapisano {data['messageCount']} wiadomości do: {out_path}")
