# tasa_bcv.py - Scraper defensivo de la tasa BCV
import requests
from bs4 import BeautifulSoup
from datetime import datetime

def obtener_tasa_bcv():
    """
    Obtiene la tasa oficial USD/BCV desde el sitio web del BCV.
    Retorna un diccionario: {'fecha': 'YYYY-MM-DD', 'tasa': float, 'fuente': 'bcv.org.ve'}
    o None si falla.
    """
    try:
        url = "https://www.bcv.org.ve/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15, verify=False)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, "html.parser")
        
        # El BCV coloca la tasa del dólar en un div con id="dolar"
        dolar_div = soup.find("div", id="dolar")
        if not dolar_div:
            return None
        
        # Buscamos el valor dentro del div
        valor_span = dolar_div.find("div", class_="col-sm-6 col-xs-6 centrado")
        if not valor_span:
            return None
        
        # Normalizamos: "92,50" -> 92.50
        tasa_texto = valor_span.get_text(strip=True).replace(",", ".")
        tasa = float(tasa_texto)
        
        return {
            "fecha": datetime.now().strftime("%Y-%m-%d"),
            "tasa": tasa,
            "fuente": "bcv.org.ve"
        }
    except Exception as e:
        print(f"Error al obtener tasa BCV: {e}")
        return None
