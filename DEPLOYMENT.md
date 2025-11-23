# Guía de Despliegue en Streamlit Cloud

Esta guía te ayudará a desplegar el Sistema de Examen Adaptativo en Streamlit Cloud.

## 📋 Requisitos Previos

1. Cuenta de GitHub
2. Cuenta de Streamlit Cloud (https://streamlit.io/cloud)
3. Cuenta de Google Cloud con API de Sheets habilitada
4. Service Account configurado

## 🔧 Preparación

### 1. Configurar Google Cloud

#### a) Crear Proyecto
1. Ve a https://console.cloud.google.com
2. Crea un nuevo proyecto o selecciona uno existente
3. Anota el `project_id`

#### b) Habilitar APIs
1. En el menú lateral, ve a "APIs y servicios" > "Biblioteca"
2. Busca y habilita:
   - Google Sheets API
   - Google Drive API

#### c) Crear Service Account
1. Ve a "APIs y servicios" > "Credenciales"
2. Click en "Crear credenciales" > "Cuenta de servicio"
3. Dale un nombre (ej: "examen-python")
4. Click en "Crear y continuar"
5. Selecciona el rol "Editor" (o "Propietario" si necesitas más permisos)
6. Click en "Continuar" y luego "Listo"

#### d) Generar clave JSON
1. Click en la service account que acabas de crear
2. Ve a la pestaña "Claves"
3. Click en "Agregar clave" > "Crear clave nueva"
4. Selecciona formato JSON
5. Click en "Crear"
6. Se descargará un archivo JSON - **guárdalo de forma segura**

### 2. Configurar Google Sheet

1. Crea una nueva hoja de cálculo en Google Sheets
2. Copia el ID del spreadsheet de la URL:
   ```
   https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit
   ```
3. Comparte la hoja con el email de la service account (está en el JSON):
   ```
   examen-python@tu-proyecto.iam.gserviceaccount.com
   ```
4. Dale permisos de "Editor"

### 3. Preparar Repositorio

#### a) Subir a GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/TU_REPO.git
git push -u origin main
```

#### b) Actualizar configuración
Edita `config/examen_python.json` y actualiza el `spreadsheet_id`:
```json
{
  "persistencia": {
    "metodo": "google_sheets",
    "spreadsheet_id": "TU_SPREADSHEET_ID_AQUI"
  }
}
```

## 🚀 Despliegue en Streamlit Cloud

### 1. Conectar con GitHub

1. Ve a https://share.streamlit.io
2. Click en "New app"
3. Conecta tu cuenta de GitHub si no lo has hecho
4. Autoriza el acceso a tus repositorios

### 2. Configurar la App

1. Selecciona tu repositorio
2. Selecciona la rama: `main`
3. Archivo principal: `app.py`
4. Click en "Advanced settings..."

### 3. Configurar Secrets

En la sección "Secrets", copia todo el contenido del archivo JSON de la service account:

```toml
[gcp_service_account]
type = "service_account"
project_id = "tu-project-id"
private_key_id = "abc123..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "examen-python@tu-proyecto.iam.gserviceaccount.com"
client_id = "123456789"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/..."
```

⚠️ **IMPORTANTE**: 
- Asegúrate de que `private_key` esté en una sola línea con `\n` para los saltos de línea
- No compartas este archivo ni lo subas a GitHub

### 4. Deploy

1. Click en "Deploy!"
2. Espera a que se complete la instalación (puede tomar varios minutos)
3. Una vez completado, tu app estará disponible en una URL como:
   ```
   https://tu-usuario-tu-repo-abc123.streamlit.app
   ```

## 🔍 Verificación

### Prueba la Aplicación

1. Abre la URL de tu app
2. Ingresa un código de estudiante de prueba
3. Completa algunas preguntas
4. Verifica que los resultados se guarden en Google Sheets

### Revisa los Logs

Si algo no funciona:
1. Click en "Manage app" en Streamlit Cloud
2. Ve a la pestaña "Logs"
3. Busca errores relacionados con Google Sheets o credenciales

## 🐛 Solución de Problemas Comunes

### Error: "Failed to load credentials"

**Causa**: Las credenciales en Secrets no están correctamente formateadas

**Solución**:
1. Verifica que el formato sea TOML válido
2. Asegúrate de que `private_key` esté en una sola línea
3. Verifica que no haya comillas adicionales

### Error: "Permission denied"

**Causa**: La service account no tiene permisos en el spreadsheet

**Solución**:
1. Ve a Google Sheets
2. Click en "Compartir"
3. Agrega el email de la service account
4. Dale permisos de "Editor"

### Error: "Spreadsheet not found"

**Causa**: El SPREADSHEET_ID es incorrecto

**Solución**:
1. Verifica el ID en la URL del spreadsheet
2. Actualiza `config/examen_python.json`
3. Haz commit y push de los cambios

### La app no se actualiza

**Causa**: Los cambios no se reflejan inmediatamente

**Solución**:
1. Ve a "Manage app"
2. Click en "Reboot app"
3. O haz un nuevo commit para forzar redeploy

## 🔄 Actualizar la Aplicación

Para actualizar la app después de hacer cambios:

```bash
git add .
git commit -m "Descripción de los cambios"
git push
```

Streamlit Cloud detectará automáticamente los cambios y redesplegará la app.

## 📊 Monitoreo

### Verificar Uso

1. Ve a "Manage app" en Streamlit Cloud
2. Revisa las métricas de uso
3. Monitorea los logs para errores

### Google Sheets

1. Abre tu spreadsheet
2. Verifica que los resultados se estén guardando correctamente
3. Revisa las columnas y formatos

## 🔒 Seguridad

### Mejores Prácticas

1. **Nunca** incluyas `secrets.toml` en el repositorio
2. **Nunca** hagas commit del JSON de la service account
3. Usa `.gitignore` para proteger archivos sensibles
4. Limita los permisos de la service account al mínimo necesario
5. Cambia las credenciales periódicamente

### Backup

1. Haz backup regular del Google Sheet
2. Exporta los resultados periódicamente
3. Guarda una copia del JSON de la service account de forma segura

## 📞 Soporte

Si encuentras problemas:

1. Revisa los logs en Streamlit Cloud
2. Verifica la documentación de Streamlit: https://docs.streamlit.io
3. Consulta la documentación de Google Sheets API: https://developers.google.com/sheets
4. Contacta al administrador del sistema

## 🎉 ¡Listo!

Tu Sistema de Examen Adaptativo está ahora desplegado y listo para usar. Los estudiantes pueden acceder a través de la URL proporcionada por Streamlit Cloud.

### URL del Examen

Comparte esta URL con tus estudiantes:
```
https://tu-usuario-tu-repo-abc123.streamlit.app
```

### Personalización del Dominio (Opcional)

Si tienes un dominio propio, puedes configurar un CNAME en Streamlit Cloud para usar tu dominio personalizado.
