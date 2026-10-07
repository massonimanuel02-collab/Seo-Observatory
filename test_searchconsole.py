"""
Observatorio SEO - Prueba de conexión
Verifica que la cuenta de servicio tenga acceso a Search Console.
Si funciona, imprime los sitios disponibles y su nivel de permiso.
"""

from google.oauth2 import service_account
from googleapiclient.discovery import build

# Autenticación con la cuenta de servicio (permiso de solo lectura)
credenciales = service_account.Credentials.from_service_account_file(
    "credenciales.json",
    scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
)

# Cliente de la API de Search Console
servicio = build("searchconsole", "v1", credentials=credenciales)

# Lista los sitios a los que la cuenta tiene acceso
sitios = servicio.sites().list().execute()
print(sitios)