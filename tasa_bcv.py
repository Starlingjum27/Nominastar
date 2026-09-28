# tasa_bcv.py - Scraper robusto de la tasa BCV con fallback a API pública
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import time

def obtener_tasa_bcv():
    """
    Obtiene la tasa oficial USD/BCV desde el sitio web del BCV.
    Si falla, intenta con una API pública de respaldo.
    Retorna dict: {'fecha': 'YYYY-MM-DD', 'tasa': float, 'fuente': '...'}
    o None si todo falla.
    """
    # --- INTENTO 1: Scraping directo del BCV ---
    resultado = _scrapear_bcv()
    if resultado:
        return resultado

    # --- INTENTO 2: API pública de respaldo ---
    resultado = _consultar_api_respaldo()
    if resultado:
        return resultado

    return None


def _scrapear_bcv():
    """Intenta obtener la tasa directamente del sitio del BCV."""
    url = "https://www.bcv.org.ve/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    }

    # Reintentos por si la red falla momentáneamente
    for intento in range(3):
        try:
            response = requests.get(url, headers=headers, timeout=20, verify=False)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # El BCV coloca la tasa del dólar en un div con id="dolar"
            dolar_div = soup.find("div", id="dolar")
            if not dolar_div:
                continue

            # El valor está dentro de un <strong> dentro del div
            valor_strong = dolar_div.find("strong")
            if not valor_strong:
                # Fallback: buscar por la clase específica
                valor_span = dolar_div.find("div", class_="col-sm-6 col-xs-6 centrado")
                if valor_span:
                    valor_strong = valor_span

            if not valor_strong:
                continue

            # Normalizar: "857,0100" -> 857.01
            valor_texto = valor_strong.get_text(strip=True)
            valor_limpio = valor_texto.replace(",", ".")

            # Validar que sea un número
            if re.match(r"^\d+(\.\d+)?$", valor_limpio):
                tasa = float(valor_limpio)
                if tasa > 0:
                    return {
                        "fecha": datetime.now().strftime("%Y-%m-%d"),
                        "tasa": tasa,
                        "fuente": "bcv.org.ve"
                    }

        except requests.exceptions.RequestException as e:
            print(f"Intento {intento + 1} falló: {e}")
            if intento < 2:
                time.sleep(2 ** intento)  # Espera 1s, luego 2s

    return None


def _consultar_api_respaldo():
    """
    Consulta una API pública de respaldo si el scraping del BCV falla.
    Usa AllRatesToday que sirve los mismos datos oficiales del BCV.
    """
    try:
        url = "https://allratestoday.com/api/v1/central-bank/bcv/latest"
        params = {"source": "USD", "target": "VES"}
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()

        data = response.json()
        # La API devuelve algo como: {"rate": 857.01, "rate_date": "2026-09-28", ...}
        tasa = data.get("rate")
        fecha = data.get("rate_date", datetime.now().strftime("%Y-%m-%d"))

        if tasa and float(tasa) > 0:
            return {
                "fecha": fecha,
                "tasa": float(tasa),
                "fuente": "api.respaldo (allratestoday)"
            }
    except Exception as e:
        print(f"API de respaldo falló: {e}")

    return None
