"""Configuración del agente. Las claves y la URL de la base vienen del entorno (.env o GitHub Secrets)."""
import os

CLIENTE = "estudiojuridicorios"  # Etapa 7: pasa a la tabla clientes
MODELO_ESTRATEGA = os.getenv("MODELO_ESTRATEGA", "claude-sonnet-5-5")

# Poco volumen: 1 clic de diferencia ya es ±100 %. Lo que queda por debajo no se reporta.
# Calibrados con la semana al 23/10/2026: 21 clics en total; 4 de 8 páginas cambian 3 clics o más
# y ninguna consulta nueva pasa de 2 impresiones.
UMBRAL_CLICS = 3        # diferencia mínima de clics de una página entre semanas
UMBRAL_IMPRESIONES = 5  # impresiones mínimas de una consulta nueva en la semana
MAX_POR_TIPO = 5        # tope de oportunidades de CTR y de consultas nuevas

# Sin dominio verificado, Resend solo deja mandar desde esta dirección y a la cuenta dueña de la clave.
REMITENTE = "Observatorio SEO <onboarding@resend.dev>"
