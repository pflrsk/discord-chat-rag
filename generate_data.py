# -*- coding: utf-8 -*-
"""
Generator syntetycznych danych czatu.

Tworzy realistyczną rozmowę grupową (kilku znajomych) rozłożoną w czasie,
podzieloną na kilka wątków tematycznych. Zapisuje wynik do pliku JSON
w formacie zgodnym z eksportem narzędzia DiscordChatExporter, dzięki czemu
aplikacja może wczytywać zarówno te dane, jak i prawdziwy eksport z Discorda.

Dane są w pełni fikcyjne: brak prawdziwych osób i danych osobowych.
Konwersacja jest "scenariuszowa" (a nie losowa), aby streszczenia
i wyszukiwanie semantyczne dawały sensowne, czytelne wyniki na demo.
"""

import json
import os
from datetime import datetime, timedelta

# --- Uczestnicy rozmowy (fikcyjni) -----------------------------------------
AUTHORS = {
    "Ala":    {"id": "1001", "color": "#e74c3c"},
    "Bartek": {"id": "1002", "color": "#3498db"},
    "Celina": {"id": "1003", "color": "#2ecc71"},
    "Darek":  {"id": "1004", "color": "#9b59b6"},
    "Ela":    {"id": "1005", "color": "#f39c12"},
}

messages = []
_counter = [0]


def add(author, content, dt):
    """Dodaje pojedynczą wiadomość do listy."""
    _counter[0] += 1
    messages.append({
        "id": str(2000000 + _counter[0]),
        "type": "Default",
        "timestamp": dt.isoformat() + "+00:00",
        "timestampEdited": None,
        "content": content,
        "author": {
            "id": AUTHORS[author]["id"],
            "name": author,
            "nickname": author,
            "color": AUTHORS[author]["color"],
            "isBot": False,
        },
        "attachments": [],
        "reactions": [],
    })


def thread(start, step_minutes, lines):
    """Dodaje wątek: listę (autor, treść) z rosnącymi znacznikami czasu."""
    t = start
    for author, content in lines:
        add(author, content, t)
        t += timedelta(minutes=step_minutes)


# ===========================================================================
# WATEK 1: Planowanie wyjazdu w gory (18-19 maja)
# ===========================================================================
thread(datetime(2026, 5, 18, 18, 30), 7, [
    ("Ala", "Hej, co myślicie o wspólnym wyjeździe w góry w długi weekend czerwcowy?"),
    ("Bartek", "Jestem za! Bieszczady czy Tatry?"),
    ("Celina", "Ja głosuję za Bieszczadami, w Tatrach będą tłumy."),
    ("Darek", "Bieszczady spoko, mniej ludzi i taniej."),
    ("Ela", "Też wolę Bieszczady. Kiedy dokładnie?"),
    ("Ala", "Myślałam o 6-8 czerwca, sobota-poniedziałek."),
    ("Bartek", "Pasuje mi. Ile osób w sumie jedzie?"),
    ("Celina", "Na razie nas piątka, ale spytam jeszcze Kasię."),
    ("Darek", "Czym jedziemy? Mam auto na 5 osób."),
    ("Ala", "Super, to autem Darka. Dorzucimy się do paliwa."),
])

thread(datetime(2026, 5, 19, 12, 10), 6, [
    ("Ela", "Znalazłam fajne schronisko pod Połoniną Wetlińską, ma wolne miejsca."),
    ("Celina", "Ile za noc?"),
    ("Ela", "Jakieś 70 zł za osobę ze śniadaniem."),
    ("Bartek", "Biorę. Rezerwujemy dwie noce?"),
    ("Ala", "Tak, dwie noce. Ela, zarezerwujesz?"),
    ("Ela", "Jasne, robię rezerwację dzisiaj wieczorem."),
    ("Darek", "Pamiętajcie o porządnych butach, na Połoninie bywa ślisko."),
])

# ===========================================================================
# WATEK 2: Projekt zaliczeniowy z GenSI (20-23 maja)
# ===========================================================================
thread(datetime(2026, 5, 20, 9, 15), 8, [
    ("Bartek", "Słuchajcie, musimy ruszyć z projektem na zaliczenie z GenSI."),
    ("Ala", "Racja, deadline jest 15 czerwca. Mamy temat?"),
    ("Darek", "Może coś z analizą tekstu? Streszczanie albo wyszukiwanie."),
    ("Celina", "A może aplikacja, która streszcza fragmenty rozmów z czatu?"),
    ("Bartek", "O, to jest dobre. Wyszukiwanie semantyczne + streszczanie."),
    ("Ala", "Podoba mi się. Podzielmy się zadaniami."),
    ("Darek", "Ja wezmę embeddingi i wyszukiwanie."),
    ("Celina", "Ja zrobię interfejs w Streamlit."),
    ("Bartek", "Ja ogarnę streszczanie przez API modelu."),
    ("Ala", "To ja biorę dokumentację i dane testowe."),
])

thread(datetime(2026, 5, 23, 17, 0), 6, [
    ("Ala", "Zrobiłam zestaw danych testowych, syntetyczny czat z timestampami."),
    ("Darek", "Mega, dzięki. Wyszukiwanie semantyczne już mi działa lokalnie."),
    ("Celina", "Interfejs prawie gotowy, dodaję suwaki do wyboru zakresu czasu."),
    ("Bartek", "Streszczanie działa, dodałem tryb awaryjny gdyby nie było klucza API."),
    ("Ala", "Świetnie idziemy. Spotkajmy się w środę żeby to skleić."),
])

# ===========================================================================
# WATEK 3: Urodziny Celiny - organizacja prezentu (24-26 maja)
# ===========================================================================
thread(datetime(2026, 5, 24, 20, 30), 5, [
    ("Ala", "PSST, bez Celiny. Jej urodziny są 30 maja, trzeba ogarnąć prezent."),
    ("Bartek", "Racja! Macie pomysły?"),
    ("Darek", "Mówiła kiedyś, że chce słuchawki bezprzewodowe."),
    ("Ela", "O, dobry pomysł. Zrzutka po 50 zł od osoby?"),
    ("Ala", "Pasuje. Bartek, ogarniesz zakup?"),
    ("Bartek", "Jasne, znajdę dobry model do 250 zł."),
])

thread(datetime(2026, 5, 26, 13, 45), 5, [
    ("Bartek", "Kupiłem słuchawki, te z dobrą redukcją szumów."),
    ("Ela", "Super! Gdzie robimy imprezę urodzinową?"),
    ("Darek", "Może u mnie? Mam duży salon i ogród."),
    ("Ala", "Idealnie. Sobota 30 maja, godzina 18?"),
    ("Ela", "Gra. Ja zrobię tort."),
])

# ===========================================================================
# WATEK 4: Wieczor planszowkowy + luzne rozmowy (27-29 maja)
# ===========================================================================
thread(datetime(2026, 5, 27, 21, 0), 4, [
    ("Darek", "Ktoś chętny na planszówki w piątek wieczorem?"),
    ("Celina", "Ja! Weźmiemy Catana?"),
    ("Bartek", "Catan albo Wsiąść do Pociągu, oba lubię."),
    ("Ela", "Może być Wsiąść do Pociągu, dawno nie grałam."),
    ("Darek", "OK, piątek 20:00 u mnie. Przyniosę przekąski."),
])

thread(datetime(2026, 5, 29, 10, 20), 5, [
    ("Celina", "Ale wczoraj fajny wieczór, wygrałam w pociągi!"),
    ("Bartek", "Miałaś szczęście do długich tras :)"),
    ("Ela", "Rewanż za tydzień, ostrzegam."),
    ("Ala", "Liczę na rewanż. A propos, pogoda na weekend zapowiada się słoneczna."),
    ("Darek", "To dobrze wróży na wyjazd w góry!"),
])

# ===========================================================================
# WATEK 5: Domkniecie spraw (30-31 maja)
# ===========================================================================
thread(datetime(2026, 5, 30, 22, 30), 4, [
    ("Ala", "Wszystkiego najlepszego Celina jeszcze raz! Świetna impreza."),
    ("Celina", "Dziękuję wam bardzo! Słuchawki rewelacja, jak wiedzieliście :)"),
    ("Bartek", "Mały wywiad zrobiliśmy ;)"),
    ("Ela", "Tort też się udał, sama jestem zaskoczona."),
])

thread(datetime(2026, 5, 31, 16, 0), 5, [
    ("Darek", "Przypominam: za tydzień wyjazd. Spakujcie kurtki, w górach chłodno."),
    ("Ela", "Rezerwacja schroniska potwierdzona, dwie noce."),
    ("Ala", "Projekt z GenSI też prawie skończony, zostaje dokumentacja."),
    ("Bartek", "Czyli wszystko pod kontrolą. Dobra robota ekipa!"),
    ("Celina", "Najlepsza ekipa <3"),
])


# ===========================================================================
# Zapis do pliku w formacie DiscordChatExporter (JSON)
# ===========================================================================
def build_export():
    messages.sort(key=lambda m: m["timestamp"])
    return {
        "guild": {"id": "9001", "name": "Ekipa znajomych"},
        "channel": {"id": "9101", "name": "ogólny", "type": "GuildTextChat"},
        "dateRange": {
            "after": messages[0]["timestamp"],
            "before": messages[-1]["timestamp"],
        },
        "messages": messages,
        "messageCount": len(messages),
    }


if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "sample_chat.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(build_export(), f, ensure_ascii=False, indent=2)
    print(f"Zapisano {len(messages)} wiadomosci do: {out_path}")
