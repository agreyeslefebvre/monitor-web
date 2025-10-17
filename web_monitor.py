"""
Monitor de disponibilidad web con notificaciones a Microsoft Teams.
Verifica el estado de múltiples URLs y envía alertas cuando no están disponibles.
"""

import sys
import json
import time
from typing import Optional, List
from datetime import datetime
from dataclasses import dataclass

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.common.exceptions import TimeoutException, WebDriverException


# Lista de URLs a monitorear
URLS_TO_MONITOR = [
    "https://centinela.lefebvre.es",
    "https://www.iberley.es/legislacion/codigo-penal-ley-organica-10-1995-23-nov-1948765?ancla=89095#ancla_89095",
    "https://www.juntadeandalucia.es/export/drupaljda/Plan_antifraude_25_05_22_ptg.pdf",
    "https://www.ine.es/daco/daco42/clasificaciones/cnae09/nace11_nace2.pdf",
    "https://www.hacienda.gob.es/DGPatrimonio/junta%20consultiva/informes/informes2021/2021-075instruccionprtr.pdf",
    "https://www.miteco.gob.es/es/ministerio/recuperacion-transformacion-resiliencia/transicion-verde/guiadnshmitecov20_tcm30-528436.pdf",
    "https://sede.agenciatributaria.gob.es/Sede/procedimientos/ZA25.shtml",
    "https://www.igualdadenlaempresa.es/DIE/convocatorias/home.htm",
    "https://www.igualdadenlaempresa.es/asesoramiento/herramientas-igualdad/docs/Herramienta_Registro_Retributivo.xlsx",
    "https://www.mites.gob.es/ficheros/ministerio/Portada/valoracion_puestos/2022.07.19_Herramienta_SVPT.xlsm.zip",
    "https://expinterweb.mites.gob.es/regcon/index.htm",
    "https://www.igualdadenlaempresa.es/asesoramiento/acoso-sexual/docs/Protocolo_Acoso_Sexual_Por_Razon_Sexo_2023.pdf",
    "https://www.mites.gob.es/ficheros/ministerio/Portada/valoracion_puestos/2022.01.18_Herramienta_SVPT.xls",
    "https://www.sepblac.es/es/sujetos-obligados/tramites/comunicacion-de-personas-autorizadas-por-el-representante/",
    "https://www.sepblac.es/es/sujetos-obligados/tramites/propuesta-de-nombramiento-de-representante-ante-el-sepblac/",
    "https://www.sepblac.es/es/sujetos-obligados/tramites/comunicacion-por-indicio/",
    "https://www.interior.gob.es/opencms/ca/servicios-al-ciudadano/tramites-y-gestiones/extranjeria/control-de-fronteras/estados-del-espacio-economico-europeo-eee/",
    "https://apdcat.gencat.cat/es/seu_electronica/",
    "https://ws050.juntadeandalucia.es/vea/faces/vi/procedimientoDetalle.xhtml",
    "https://sedeagpd.gob.es/sede-electronica-web/",
    "https://sedeagpd.gob.es/sede-electronica-web/vistas/formBrechaSeguridad/nbs/procedimientoBrechaSeguridad.jsf",
]


@dataclass
class MonitorResult:
    """Resultado de la verificación de disponibilidad."""
    url: str
    is_available: bool
    message: str
    timestamp: datetime


class WebMonitor:
    """Monitor de disponibilidad de sitios web."""
    
    TIMEOUT_SECONDS = 45  # Aumentado para webs lentas
    FILE_TIMEOUT = 15
    
    def __init__(self, teams_webhook_url: str):
        """
        Inicializa el monitor de disponibilidad web.
        
        Args:
            teams_webhook_url: URL del webhook de Microsoft Teams para notificaciones
        """
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
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--disable-blink-features=AutomationControlled')
        
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(self.TIMEOUT_SECONDS)
        
        return driver
    
    def _check_file_url(self, url: str) -> MonitorResult:
        """
        Verifica archivos descargables (PDF, Excel, ZIP).
        
        Args:
            url: URL del archivo
            
        Returns:
            MonitorResult con el estado
        """
        timestamp = datetime.now()
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Referer': 'https://www.google.com/'
        }
        
        try:
            # Primero intentar con HEAD
            response = requests.head(
                url, 
                timeout=self.FILE_TIMEOUT, 
                allow_redirects=True,
                headers=headers,
                verify=True
            )
            
            if response.status_code == 200:
                message = f"Archivo disponible (HEAD: {response.status_code})"
                print(f"  ✓ {message}")
                return MonitorResult(url, True, message, timestamp)
            
            # Si HEAD falla, intentar con GET
            response = requests.get(
                url,
                timeout=self.FILE_TIMEOUT,
                allow_redirects=True,
                headers=headers,
                stream=True,  # No descargar todo, solo verificar
                verify=True
            )
            
            if response.status_code == 200:
                message = f"Archivo disponible (GET: {response.status_code})"
                print(f"  ✓ {message}")
                return MonitorResult(url, True, message, timestamp)
            else:
                message = f"Error HTTP {response.status_code}"
                print(f"  ✗ {message}")
                return MonitorResult(url, False, message, timestamp)
                
        except requests.exceptions.Timeout:
            message = f"Timeout al acceder al archivo (>{self.FILE_TIMEOUT}s)"
            print(f"  ✗ {message}")
            return MonitorResult(url, False, message, timestamp)
            
        except requests.exceptions.SSLError as e:
            message = f"Error SSL: {str(e)[:80]}"
            print(f"  ✗ {message}")
            return MonitorResult(url, False, message, timestamp)
            
        except requests.exceptions.RequestException as e:
            message = f"Error de conexión: {str(e)[:80]}"
            print(f"  ✗ {message}")
            return MonitorResult(url, False, message, timestamp)
    
    def _check_web_url(self, url: str) -> MonitorResult:
        """
        Verifica páginas web con Selenium.
        
        Args:
            url: URL de la página
            
        Returns:
            MonitorResult con el estado
        """
        timestamp = datetime.now()
        
        try:
            self._driver.get(url)
            time.sleep(3)  # Esperar a que cargue JavaScript
            
            # Obtener título de la página
            title = self._driver.title
            current_url = self._driver.current_url
            
            # Verificar si hay errores evidentes
            page_source = self._driver.page_source.lower()
            
            # Indicadores de error más específicos
            critical_errors = [
                '404 not found',
                '500 internal server error',
                '503 service unavailable',
                'page not found',
                'página no encontrada'
            ]
            
            if any(error in page_source[:1000] for error in critical_errors):
                message = "Página con error crítico detectado"
                print(f"  ✗ {message}")
                return MonitorResult(url, False, message, timestamp)
            
            # Si llegó aquí y tiene título, está OK
            if title and len(title) > 0:
                message = f"Web disponible - '{title[:50]}'"
                print(f"  ✓ {message}")
                return MonitorResult(url, True, message, timestamp)
            else:
                # Incluso sin título, si cargó algo, podría estar OK
                if len(page_source) > 100:
                    message = "Web disponible (sin título)"
                    print(f"  ✓ {message}")
                    return MonitorResult(url, True, message, timestamp)
                else:
                    message = "Web sin contenido"
                    print(f"  ✗ {message}")
                    return MonitorResult(url, False, message, timestamp)
        
        except TimeoutException:
            message = f"Timeout al cargar página (>{self.TIMEOUT_SECONDS}s)"
            print(f"  ⚠️ {message}")
            # Para webs muy lentas, considerarlo como warning pero no error crítico
            return MonitorResult(url, False, message, timestamp)
        
        except WebDriverException as e:
            error_str = str(e)[:100]
            message = f"Error de navegador: {error_str}"
            print(f"  ✗ {message}")
            return MonitorResult(url, False, message, timestamp)
        
        except Exception as e:
            message = f"Error inesperado: {str(e)[:100]}"
            print(f"  ✗ {message}")
            return MonitorResult(url, False, message, timestamp)
    
    def check_url(self, url: str) -> MonitorResult:
        """
        Verifica si una URL específica está disponible.
        
        Args:
            url: URL a verificar
            
        Returns:
            MonitorResult con el estado y detalles de la verificación
        """
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Verificando: {url}")
        
        # Detectar tipo de contenido por extensión
        file_extensions = ('.pdf', '.xlsx', '.xls', '.xlsm', '.zip', '.doc', '.docx')
        
        if url.lower().endswith(file_extensions):
            return self._check_file_url(url)
        else:
            return self._check_web_url(url)
    
    def _build_teams_card(self, failed_urls: List[MonitorResult], total: int) -> dict:
        """
        Construye el mensaje adaptativo para Microsoft Teams.
        
        Args:
            failed_urls: Lista de URLs que fallaron
            total: Total de URLs verificadas
            
        Returns:
            Diccionario con el formato de MessageCard para Teams
        """
        timestamp_str = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        failed_count = len(failed_urls)
        success_count = total - failed_count
        
        # Construir lista de URLs caídas
        facts = [
            {"name": "📊 Total verificadas:", "value": str(total)},
            {"name": "✅ Disponibles:", "value": str(success_count)},
            {"name": "❌ No disponibles:", "value": str(failed_count)},
            {"name": "⏰ Hora verificación:", "value": timestamp_str},
            {"name": "", "value": ""}  # Separador
        ]
        
        # Añadir detalles de cada URL caída (máximo 8 para no saturar Teams)
        for i, result in enumerate(failed_urls[:8], 1):
            url_short = result.url[:65] + "..." if len(result.url) > 65 else result.url
            facts.append({
                "name": f"🔴 URL {i}:",
                "value": f"{url_short}\n💬 {result.message}"
            })
        
        if failed_count > 8:
            facts.append({
                "name": "⚠️ Nota:",
                "value": f"Y {failed_count - 8} URL(s) más con problemas. Ver logs en GitHub Actions."
            })
        
        return {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": f"⚠️ {failed_count} de {total} URLs no disponibles",
            "themeColor": "FF0000",
            "title": f"🚨 ALERTA - {failed_count} URL(s) con Problemas",
            "sections": [{
                "activityTitle": "Monitor Automático de Disponibilidad",
                "activitySubtitle": f"Verificación realizada el {timestamp_str}",
                "facts": facts,
                "markdown": True
            }],
            "potentialAction": [{
                "@type": "OpenUri",
                "name": "📋 Ver logs completos",
                "targets": [{
                    "os": "default",
                    "uri": "https://github.com/agreyeslefebvre/monitor-web/actions"
                }]
            }]
        }
    
    def _build_success_card(self, total: int) -> dict:
        """Construye mensaje de éxito para Teams."""
        timestamp_str = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        
        return {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": f"✅ Todas las URLs funcionan correctamente",
            "themeColor": "00FF00",
            "title": "✅ Monitor - Todo Correcto",
            "sections": [{
                "activityTitle": "Monitor Automático de Disponibilidad",
                "activitySubtitle": f"Verificación realizada el {timestamp_str}",
                "facts": [
                    {"name": "📊 URLs verificadas:", "value": str(total)},
                    {"name": "✅ Estado:", "value": "Todas disponibles"},
                    {"name": "⏰ Hora:", "value": timestamp_str}
                ],
                "markdown": True
            }]
        }
    
    def send_teams_notification(self, card: dict) -> bool:
        """
        Envía notificación a Microsoft Teams.
        
        Args:
            card: Diccionario con el mensaje a enviar
            
        Returns:
            True si la notificación se envió correctamente
        """
        try:
            response = requests.post(
                self.teams_webhook_url,
                headers={'Content-Type': 'application/json'},
                data=json.dumps(card),
                timeout=10
            )
            
            if response.status_code in [200, 202]:
                print("\n✓ Notificación enviada a Teams correctamente")
                return True
            else:
                print(f"\n✗ Error al enviar a Teams: {response.status_code}")
                print(f"   Respuesta: {response.text[:200]}")
                return False
        
        except requests.exceptions.RequestException as e:
            print(f"\n✗ Error al enviar notificación: {str(e)}")
            return False
    
    def run(self, urls: List[str], notify_on_success: bool = False) -> int:
        """
        Ejecuta el monitoreo de todas las URLs.
        
        Args:
            urls: Lista de URLs a verificar
            notify_on_success: Si True, notifica también cuando todo funciona
            
        Returns:
            Código de salida: 0 si todo OK, 1 si hay fallos
        """
        try:
            self._driver = self._setup_driver()
            
            print("="*70)
            print(f"Verificando {len(urls)} URLs...")
            print("="*70)
            
            results = []
            for i, url in enumerate(urls, 1):
                print(f"\n[{i}/{len(urls)}]", end=" ")
                result = self.check_url(url)
                results.append(result)
                time.sleep(1)  # Pausa entre verificaciones
            
            # Filtrar URLs que fallaron
            failed_urls = [r for r in results if not r.is_available]
            
            print("\n" + "="*70)
            print(f"RESUMEN: {len(failed_urls)} fallos de {len(urls)} URLs")
            print("="*70)
            
            # Mostrar resumen de fallos
            if failed_urls:
                print("\n❌ URLs con problemas:")
                for result in failed_urls:
                    print(f"  - {result.url}")
                    print(f"    └─ {result.message}")
            
            # Enviar notificación
            if failed_urls:
                card = self._build_teams_card(failed_urls, len(urls))
                self.send_teams_notification(card)
                return 1
            else:
                print("\n✅ Todas las URLs funcionan correctamente")
                if notify_on_success:
                    card = self._build_success_card(len(urls))
                    self.send_teams_notification(card)
                return 0
        
        except Exception as e:
            print(f"\n✗ Error crítico: {str(e)}")
            import traceback
            traceback.print_exc()
            return 1
        
        finally:
            self._cleanup()
    
    def _cleanup(self) -> None:
        """Limpia los recursos utilizados."""
        if self._driver:
            try:
                self._driver.quit()
                print("\nDriver de Chrome cerrado")
            except Exception as e:
                print(f"\nAdvertencia: Error al cerrar el driver: {e}")


def main() -> int:
    """Función principal del script."""
    
    webhook = sys.argv[1] if len(sys.argv) > 1 else ""
    
    if not webhook:
        print("ERROR: No se proporcionó URL del webhook de Teams")
        print("Uso: python web_monitor.py TEAMS_WEBHOOK")
        return 1
    
    print("="*70)
    print("MONITOR DE DISPONIBILIDAD WEB - VERIFICACIÓN MASIVA")
    print("="*70)
    print(f"Total de URLs a verificar: {len(URLS_TO_MONITOR)}")
    print(f"Timeout webs: {WebMonitor.TIMEOUT_SECONDS}s")
    print(f"Timeout archivos: {WebMonitor.FILE_TIMEOUT}s")
    print("="*70)
    
    monitor = WebMonitor(webhook)
    exit_code = monitor.run(URLS_TO_MONITOR, notify_on_success=False)
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())


