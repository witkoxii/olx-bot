"""
iPhone Alert - Bot Telegram monitorujący OLX
Wysyła powiadomienia o nowych ogłoszeniach iPhone w Twojej okolicy.
"""

import os
import time
import json
import requests
from datetime import datetime

# Serwer keep-alive dla UptimeRobot (działanie 24/7)
try:
    from keep_alive import keep_alive
    MA_KEEP_ALIVE = True
except ImportError:
    MA_KEEP_ALIVE = False

# ════════════════════════════════════════════════════════════
#  KONFIGURACJA - zmień pod siebie
# ════════════════════════════════════════════════════════════

# Token i chat ID (najlepiej trzymać w Secrets na Replit - patrz instrukcja)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8782928178:AAE8R0hmcN5C2X7X37sVjlC_gbIECIMTa9M")
CHAT_ID = os.environ.get("CHAT_ID", "7717339730")

# Ustawienia wyszukiwania
SZUKAJ = "iphone"          # czego szukać
MIASTO = "warszawa"        # miasto (małymi literami, bez polskich znaków: lodz, krakow, wroclaw)
PROMIEN_KM = 30            # promień w km: 0, 5, 10, 15, 30, 50, 75, 100, 150
CENA_MAX = 0               # maksymalna cena w zł (0 = bez limitu)
CENA_MIN = 0               # minimalna cena w zł (0 = bez limitu, pomaga odfiltrować akcesoria)

# Jak często sprawdzać (w sekundach). 300 = co 5 minut
INTERWAL = 300

# ════════════════════════════════════════════════════════════
#  KOD BOTA
# ════════════════════════════════════════════════════════════

PLIK_WIDZIANE = "widziane.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
                  "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 "
                  "Mobile/15E148 Safari/604.1",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pl-PL,pl;q=0.9",
}

# OLX kategoria: telefony Apple iPhone
KATEGORIA_ID = 1707


def wczytaj_widziane():
    """Wczytuje listę już wysłanych ogłoszeń."""
    try:
        with open(PLIK_WIDZIANE, "r") as f:
            return set(json.load(f))
    except Exception:
        return set()


def zapisz_widziane(widziane):
    """Zapisuje listę wysłanych ogłoszeń."""
    try:
        with open(PLIK_WIDZIANE, "w") as f:
            json.dump(list(widziane)[-2000:], f)  # trzymaj ostatnie 2000
    except Exception as e:
        print(f"Błąd zapisu: {e}")


def wyslij_telegram(tekst, zdjecie_url=None):
    """Wysyła wiadomość na Telegram (z opcjonalnym zdjęciem)."""
    try:
        if zdjecie_url:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
            dane = {
                "chat_id": CHAT_ID,
                "photo": zdjecie_url,
                "caption": tekst,
                "parse_mode": "HTML",
            }
        else:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            dane = {
                "chat_id": CHAT_ID,
                "text": tekst,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            }
        r = requests.post(url, data=dane, timeout=20)
        if not r.ok:
            # Jeśli zdjęcie nie działa, spróbuj bez zdjęcia
            if zdjecie_url:
                return wyslij_telegram(tekst, None)
            print(f"Telegram błąd: {r.text}")
        return r.ok
    except Exception as e:
        print(f"Błąd wysyłania: {e}")
        return False


def pobierz_oferty():
    """Pobiera ogłoszenia z oficjalnego API OLX."""
    params = {
        "offset": 0,
        "limit": 40,
        "query": SZUKAJ,
        "category_id": KATEGORIA_ID,
        "sort_by": "created_at:desc",  # najnowsze pierwsze
    }

    # Filtr ceny
    if CENA_MIN > 0:
        params["filter_float_price:from"] = CENA_MIN
    if CENA_MAX > 0:
        params["filter_float_price:to"] = CENA_MAX

    # Lokalizacja - OLX API używa city_id, ale query z miastem też działa
    if MIASTO:
        params["city"] = MIASTO
    if PROMIEN_KM > 0:
        params["distance"] = PROMIEN_KM

    try:
        r = requests.get(
            "https://www.olx.pl/api/v1/offers/",
            params=params,
            headers=HEADERS,
            timeout=20,
        )
        if not r.ok:
            print(f"OLX API błąd: {r.status_code}")
            return []
        dane = r.json()
        return dane.get("data", [])
    except Exception as e:
        print(f"Błąd pobierania OLX: {e}")
        return []


def wyciagnij_info(oferta):
    """Wyciąga potrzebne dane z ogłoszenia."""
    tytul = oferta.get("title", "Bez tytułu")
    url = oferta.get("url", "")
    id_oferty = str(oferta.get("id", ""))

    # Cena
    cena = "Cena nieznana"
    for param in oferta.get("params", []):
        if param.get("key") == "price":
            wartosc = param.get("value", {})
            cena = wartosc.get("label", "Cena nieznana")
            break

    # Stan (nowy/używany)
    stan = ""
    for param in oferta.get("params", []):
        if param.get("key") == "state":
            stan = param.get("value", {}).get("label", "")
            break

    # Lokalizacja
    lokalizacja = ""
    loc = oferta.get("location", {})
    if loc:
        miasto = loc.get("city", {}).get("name", "")
        lokalizacja = miasto

    # Data dodania
    data = oferta.get("created_time", "")
    try:
        if data:
            dt = datetime.fromisoformat(data.replace("Z", "+00:00"))
            data = dt.strftime("%H:%M")
    except Exception:
        data = ""

    # Zdjęcie
    zdjecie = None
    foty = oferta.get("photos", [])
    if foty:
        link = foty[0].get("link", "")
        # OLX używa {width}x{height} w URL
        zdjecie = link.replace("{width}", "600").replace("{height}", "450")

    return {
        "id": id_oferty,
        "tytul": tytul,
        "cena": cena,
        "stan": stan,
        "lokalizacja": lokalizacja,
        "data": data,
        "url": url,
        "zdjecie": zdjecie,
    }


def formatuj_wiadomosc(info):
    """Tworzy ładną wiadomość na Telegram."""
    linie = [f"📱 <b>{info['tytul']}</b>"]
    linie.append(f"💰 <b>{info['cena']}</b>")
    if info["stan"]:
        linie.append(f"📦 Stan: {info['stan']}")
    if info["lokalizacja"]:
        linie.append(f"📍 {info['lokalizacja']}")
    if info["data"]:
        linie.append(f"🕐 Dodano: {info['data']}")
    linie.append(f"\n🔗 <a href=\"{info['url']}\">Zobacz ogłoszenie na OLX</a>")
    return "\n".join(linie)


def sprawdz():
    """Główna funkcja - sprawdza nowe ogłoszenia."""
    widziane = wczytaj_widziane()
    oferty = pobierz_oferty()

    if not oferty:
        print(f"[{datetime.now():%H:%M:%S}] Brak wyników (lub błąd API)")
        return

    nowe = 0
    for oferta in oferty:
        info = wyciagnij_info(oferta)
        if not info["id"] or info["id"] in widziane:
            continue

        # Filtr ceny min (dodatkowy, na wypadek gdyby API nie odfiltrowało)
        widziane.add(info["id"])
        wiadomosc = formatuj_wiadomosc(info)
        if wyslij_telegram(wiadomosc, info["zdjecie"]):
            nowe += 1
            print(f"[{datetime.now():%H:%M:%S}] Wysłano: {info['tytul']} - {info['cena']}")
            time.sleep(1)  # nie spamuj Telegrama za szybko

    zapisz_widziane(widziane)
    if nowe == 0:
        print(f"[{datetime.now():%H:%M:%S}] Sprawdzono {len(oferty)} ofert, brak nowych")
    else:
        print(f"[{datetime.now():%H:%M:%S}] Wysłano {nowe} nowych ogłoszeń!")


def main():
    print("=" * 50)
    print("  iPhone Alert - Bot OLX uruchomiony!")
    print(f"  Szukam: {SZUKAJ} | Miasto: {MIASTO} (+{PROMIEN_KM}km)")
    print(f"  Sprawdzam co {INTERWAL // 60} min")
    print("=" * 50)

    # Uruchom serwer keep-alive (dla UptimeRobot)
    if MA_KEEP_ALIVE:
        keep_alive()
        print("Serwer keep-alive uruchomiony na porcie 8080")

    # Wiadomość startowa
    wyslij_telegram(
        f"🤖 <b>Bot uruchomiony!</b>\n\n"
        f"Szukam: <b>{SZUKAJ}</b>\n"
        f"📍 {MIASTO.capitalize()} (+{PROMIEN_KM} km)\n"
        f"🕐 Sprawdzam co {INTERWAL // 60} min\n\n"
        f"Pierwsze ogłoszenia traktuję jako 'już widziane', "
        f"żeby nie zasypać Cię starymi. Powiadomienia przyjdą "
        f"przy <b>nowych</b> ogłoszeniach. 🔔"
    )

    # Pierwsza inicjalizacja - oznacz obecne oferty jako widziane (bez wysyłania)
    widziane = wczytaj_widziane()
    if not widziane:
        print("Pierwsze uruchomienie - oznaczam obecne oferty jako widziane...")
        oferty = pobierz_oferty()
        for oferta in oferty:
            info = wyciagnij_info(oferta)
            if info["id"]:
                widziane.add(info["id"])
        zapisz_widziane(widziane)
        print(f"Oznaczono {len(widziane)} ofert. Czekam na nowe...")

    # Główna pętla
    while True:
        try:
            sprawdz()
        except Exception as e:
            print(f"Błąd w pętli: {e}")
        time.sleep(INTERWAL)


if __name__ == "__main__":
    main()
