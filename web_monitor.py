"""
Monitor de disponibilidad web con notificaciones a Microsoft Teams.
Verifica el estado de una URL y envía alertas cuando no está disponible.
"""

import sys
import json
from typing import Tuple, Optional
from datetime import datetime
from dataclasses import dataclass

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.common.exceptions import TimeoutException, WebDriverException


@dataclass
class MonitorResult:
    """Resultado de la verificación de disponibilidad."""
    is_available: bool
    message: str
    timestamp: datetime


class WebMonitor:
    """Monitor de disponibilidad de sitios web."""
    
    TIMEOUT_SECONDS = 30
    
    def __init__(self, url: str, teams_webhook_url: str):
        """
        Inicializa el monitor de disponibilidad web.
        
        Args:
            url: URL del sitio web a monitorear
            teams_webhook_url: URL del webhook de Microsoft Teams para notificaciones
        """
        self.url = url
        self.teams_webhook_url = teams_webhook_url
        self._driver: Optional[WebDriver] = None
    
    def _setup_driver(self) -> WebDriver:
        """
        Configura y retorna el driver de Chrome en modo headless.
        
        Returns:
            WebDriver configurado
        """
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(self.TIMEOUT_SECONDS)
        
        return driver
    
    def check_availability(self) -> MonitorResult:
        """
        Verifica si el sitio web está disponible.
        
        Returns:
            MonitorResult con el estado y detalles de la verificación
        """
        timestamp = datetime.now()
        
        print(f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] Verificando {self.url}...")
        
        try:
            self._driver.get(self.url)
            
            if self._driver.title:
                message = f"Web disponible. Título: '{self._driver.title}'"
                print(f"✓ {message}")
                print(f"  URL actual: {self._driver.current_url}")
                return MonitorResult(True, message, timestamp)
            else:
                message = "Web cargada pero sin título"
                print(f"✗ {message}")
                return MonitorResult(False, message, timestamp)
        
        except TimeoutException:
            message = f"Timeout: La web no responde (más de {self.TIMEOUT_SECONDS}s)"
            print(f"✗ {message}")
            return MonitorResult(False, message, timestamp)
        
        except WebDriverException as e:
            message = f"Error de conexión: {str(e)[:200]}"
            print(f"✗ {message}")
            return MonitorResult(False, message, timestamp)
        
        except Exception as e:
            message = f"Error inesperado: {str(e)[:200]}"
            print(f"✗ {message}")
            return MonitorResult(False, message, timestamp)
    
    def _build_teams_card(self, result: MonitorResult) -> dict:
        """
        Construye el mensaje adaptativo para Microsoft Teams.
        
        Args:
            result: Resultado de la verificación
            
        Returns:
            Diccionario con el formato de MessageCard para Teams
        """
        timestamp_str = result.timestamp.strftime('%d/%m/%Y %H:%M:%S')
        
        if result.is_available:
            theme_color = "00FF00"
            title = "✅ Centinela Lefebvre - Disponible"
            summary = "La web está funcionando correctamente"
            status = "✅ DISPONIBLE"
        else:
            theme_color = "FF0000"
            title = "🚨 ALERTA - Centinela Lefebvre Caída"
            summary = "⚠️ La web NO está disponible"
            status = "❌ NO DISPONIBLE"
        
        return {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": summary,
            "themeColor": theme_color,
            "title": title,
            "sections": [{
                "activityTitle": "Monitor Automático de Disponibilidad",
                "activitySubtitle": f"Verificación realizada el {timestamp_str}",
                "facts": [
                    {"name": "🌐 URL:", "value": self.url},
                    {"name": "📊 Estado:", "value": status},
                    {"name": "ℹ️ Detalles:", "value": result.message},
                    {"name": "⏰ Hora:", "value": timestamp_str}
                ],
                "markdown": True
            }],
            "potentialAction": [{
                "@type": "OpenUri",
                "name": "🔗 Abrir Centinela",
                "targets": [{"os": "default", "uri": self.url}]
            }]
        }
    
    def send_teams_notification(self, result: MonitorResult) -> bool:
        """
        Envía notificación a Microsoft Teams.
        
        Args:
            result: Resultado de la verificación a notificar
            
        Returns:
            True si la notificación se envió correctamente, False en caso contrario
        """
        card = self._build_teams_card(result)
        
        try:
            response = requests.post(
                self.teams_webhook_url,
                headers={'Content-Type': 'application/json'},
                data=json.dumps(card),
                timeout=10
            )
            
            if response.status_code == 200:
                print("✓ Notificación enviada a Teams correctamente")
                return True
            else:
                print(f"✗ Error al enviar a Teams: {response.status_code}")
                print(f"  Respuesta: {response.text}")
                return False
        
        except requests.exceptions.RequestException as e:
            print(f"✗ Error al enviar notificación: {str(e)}")
            return False
    
    def run(self, notify_on_success: bool = False) -> int:
        """
        Ejecuta el monitoreo completo.
        
        Args:
            notify_on_success: Si es True, envía notificación también cuando la web funciona
            
        Returns:
            Código de salida: 0 si la web está disponible, 1 si no lo está
        """
        try:
            self._driver = self._setup_driver()
            result = self.check_availability()
            
            # Enviar notificación según configuración
            should_notify = not result.is_available or notify_on_success
            
            if should_notify:
                self.send_teams_notification(result)
            else:
                print("✓ Web OK - No se envía notificación (solo se notifican fallos)")
            
            return 0 if result.is_available else 1
        
        except Exception as e:
            error_message = f"Error crítico en el sistema de monitoreo: {str(e)}"
            print(f"✗ {error_message}")
            
            # Intentar notificar el error crítico
            try:
                error_result = MonitorResult(False, error_message, datetime.now())
                self.send_teams_notification(error_result)
            except Exception:
                pass  # Si falla la notificación, no hay mucho más que hacer
            
            return 1
        
        finally:
            self._cleanup()
    
    def _cleanup(self) -> None:
        """Limpia los recursos utilizados."""
        if self._driver:
            try:
                self._driver.quit()
                print("Driver de Chrome cerrado")
            except Exception as e:
                print(f"Advertencia: Error al cerrar el driver: {e}")


def main() -> int:
    """
    Función principal del script.
    
    Returns:
        Código de salida del programa
    """
    # Configuración por defecto
    default_url = "https://centinela.lefebvre.es"
    
    # Obtener parámetros de línea de comandos
    url = sys.argv[1] if len(sys.argv) > 1 else default_url
    webhook = sys.argv[2] if len(sys.argv) > 2 else ""
    
    if not webhook:
        print("ERROR: No se proporcionó URL del webhook de Teams")
        print("Uso: python web_monitor.py [URL] TEAMS_WEBHOOK")
        return 1
    
    # Mostrar información de la ejecución
    print("=" * 70)
    print("MONITOR DE DISPONIBILIDAD WEB")
    print("=" * 70)
    print(f"URL a verificar: {url}")
    print("=" * 70)
    print()
    
    # Ejecutar monitoreo
    monitor = WebMonitor(url, webhook)
    exit_code = monitor.run(notify_on_success=False)
    
    # Mostrar resultado final
    print()
    print("=" * 70)
    status = "✅ Web funcionando correctamente" if exit_code == 0 else "❌ Web NO disponible"
    print(f"RESULTADO: {status}")
    print("=" * 70)
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
