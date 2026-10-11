# -*- coding: utf-8 -*-
"""
Zaludnianie kanału Discord realistyczną rozmową przez WEBHOOK.

Skrypt odtwarza rozmowę z pliku data/sample_chat.json na Twoim kanale,
wysyłając każdą wiadomość przez webhooka pod nazwą jej autora (Ala, Bartek...).
Dzięki temu na serwerze pojawia się wieloosobowo wyglądająca konwersacja,
którą można potem wyeksportować i wczytać do aplikacji.

WAŻNE: używaj wyłącznie na WŁASNYM serwerze/kanale. Webhook to oficjalny
mechanizm Discorda - to NIE jest self-bot ani scraping.

Ograniczenie: Discord ustawia znacznik czasu w momencie wysłania, więc
wszystkie wiadomości dostaną czas "teraz" (nie da się ich antydatować przez
webhooka). Do demonstracji filtra czasu lepiej nadaje się plik syntetyczny.

Jak zdobyć URL webhooka:
  Kanał -> Edytuj kanał -> Integracje -> Webhooki -> Nowy webhook -> Kopiuj URL.

Uruchomienie (Windows cmd):
  set WEBHOOK_URL=https://discord.com/api/webhooks/...
  python discord_seed.py

albo podając URL jako argument:
  python discord_seed.py https://discord.com/api/webhooks/...
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error

DELAY_SECONDS = 1.0  # odstęp między wiadomościami (ochrona przed limitem)


def get_webhook_url():
    if len(sys.argv) > 1 and sys.argv[1].startswith("http"):
        return sys.argv[1].strip()
    url = os.environ.get("WEBHOOK_URL", "").strip()
    if url:
        return url
    # awaryjnie: plik webhook.txt obok skryptu
    path = os.path.join(os.path.dirname(__file__), "webhook.txt")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""


def post_message(url, username, content):
    """Wysyła jedną wiadomość przez webhooka. Obsługuje limit (429)."""
    payload = json.dumps({
        "username": username,
        "content": content,
        # nie pinguj nikogo, nawet gdyby w treści było @ktoś
        "allowed_mentions": {"parse": []},
    }).encode("utf-8")

    while True:
        req = urllib.request.Request(
            url, data=payload,
            headers={
                "Content-Type": "application/json",
                # Bez User-Agent Cloudflare blokuje request (błąd 1010).
                "User-Agent": "conv-summarizer-seed/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                resp.read()
            return True
        except urllib.error.HTTPError as e:
            if e.code == 429:  # przekroczony limit - poczekaj i powtórz
                try:
                    info = json.loads(e.read().decode("utf-8"))
                    retry = float(info.get("retry_after", 2))
                except Exception:
                    retry = 2.0
                print(f"  [limit] czekam {retry:.1f}s...")
                time.sleep(retry + 0.3)
                continue
            print(f"  [błąd HTTP {e.code}] {e.read().decode('utf-8', 'ignore')[:200]}")
            return False
        except Exception as e:
            print(f"  [błąd] {e}")
            return False


def main():
    url = get_webhook_url()
    if not url:
        print("BŁĄD: brak URL webhooka.")
        print("Ustaw zmienną:  set WEBHOOK_URL=https://discord.com/api/webhooks/...")
        print("lub podaj jako argument:  python discord_seed.py <URL>")
        sys.exit(1)

    data_path = os.path.join(os.path.dirname(__file__), "data", "sample_chat.json")
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    messages = data["messages"]

    print(f"Wysyłam {len(messages)} wiadomości na kanał...")
    ok = 0
    for i, m in enumerate(messages, 1):
        author = m["author"]["name"]
        content = m["content"]
        if post_message(url, author, content):
            ok += 1
            print(f"  {i:>3}/{len(messages)}  {author}: {content[:50]}")
        time.sleep(DELAY_SECONDS)

    print(f"\nGotowe. Wysłano {ok}/{len(messages)} wiadomości.")
    print("Teraz możesz wyeksportować kanał do JSON i wczytać go w aplikacji.")


if __name__ == "__main__":
    main()
