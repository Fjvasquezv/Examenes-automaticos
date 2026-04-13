# Sistema de Examen Adaptativo Modular

Sistema de exámenes adaptativos (CAT - Computerized Adaptive Testing) implementado con Streamlit, diseñado para evaluación de conocimientos con ajuste dinámico de dificultad.

## 🎯 Características Principales

- **Adaptatividad**: Las preguntas se ajustan al nivel del estudiante en tiempo real
- **Múltiples sistemas de calificación**: IRT Simplificado, Elo, o Híbrido
- **Modularidad completa**: Configuración mediante archivos JSON
- **Persistencia**: Almacenamiento automático en Google Sheets
- **Feedback inmediato**: Explicaciones después de cada respuesta
- **Análisis detallado**: Gráficos de evolución y estadísticas por nivel/categoría
- **Opciones aleatorizadas**: Previene memorización de posiciones

## 📋 Requisitos

- Python 3.8+
- Cuenta de Google Cloud con API de Sheets habilitada
- Service Account configurado

## 🚀 Instalación

### 1. Clonar el repositorio

```bash
git clone <repository-url>
cd examen-adaptativo
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Configurar Google Sheets

1. Crear un proyecto en Google Cloud Console
2. Habilitar Google Sheets API
3. Crear una Service Account
4. Descargar el archivo JSON de credenciales
5. Crear `.streamlit/secrets.toml`:

```toml
[gcp_service_account]
type = "service_account"
project_id = "tu-project-id"
private_key_id = "tu-private-key-id"
private_key = "-----BEGIN PRIVATE KEY-----\ntu-private-key\n-----END PRIVATE KEY-----\n"
client_email = "tu-service-account@tu-project.iam.gserviceaccount.com"
client_id = "tu-client-id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/..."
```

6. Compartir tu Google Sheet con el email de la service account (con permisos de editor)

### 4. Configurar el examen

Edita `config/examen_python.json` según tus necesidades:

```json
{
  "metadata": {
    "nombre_examen": "Tu Examen",
    "asignatura": "Tu Asignatura",
    "institucion": "Tu Institución"
  },
  "parametros": {
    "preguntas_minimas": 15,
    "preguntas_maximas": 30,
    "nivel_inicial": 3,
    "umbral_estabilizacion": 0.15,
    "ventana_estabilizacion": 3
  },
  "sistema_calificacion": {
    "tipo": "irt_simplificado",
    "parametros": {
      "max_iteraciones": 10
    }
  }
}
```

### 5. Crear banco de preguntas

Crea tu archivo `data/preguntas_python.json` siguiendo este formato:

```json
[
  {
    "id": "p001",
    "dificultad": 1,
    "categoria": "Tipos de datos",
    "pregunta": "¿Cuál es el resultado?\n\n```python\nx = 10 // 3\n```",
    "opciones": {
      "a": "3.333",
      "b": "3",
      "c": "4",
      "d": "3.0"
    },
    "respuesta_correcta": "b",
    "explicacion": "El operador // realiza división entera"
  }
]
```

## ▶️ Ejecución

```bash
streamlit run app.py
```

## ✅ Preflight operativo (recomendado antes de cada prueba)

Valida en un solo comando el periodo, config, bancos activos y conteo mínimo real:

```bash
python utils/preflight_exam.py
```

Opciones útiles:

```bash
# Validar un periodo específico por nombre exacto
python utils/preflight_exam.py --periodo "QUIZZ 1 - Introducción a la Tecnología"

# Simular validación para una fecha/hora puntual (formato YYYY-MM-DD HH:MM)
python utils/preflight_exam.py --fecha "2026-03-06 11:50"
```

## 📁 Estructura del Proyecto

```
examen-adaptativo/
├── app.py                          # Orquestador principal
├── requirements.txt                # Dependencias
├── README.md                       # Este archivo
├── .streamlit/
│   └── secrets.toml               # Credenciales (no incluir en repo)
├── config/
│   ├── examen_python.json         # Configuración del examen
│   └── examen_template.json       # Plantilla de configuración
├── data/
│   └── preguntas_python.json      # Banco de preguntas
├── src/
│   ├── __init__.py
│   ├── config_loader.py           # Carga configuraciones
│   ├── question_manager.py        # Gestión de preguntas
│   ├── scoring_systems.py         # Sistemas de calificación
│   ├── exam_logic.py              # Lógica del examen
│   ├── ui_components.py           # Componentes UI
│   └── data_persistence.py        # Google Sheets
└── utils/
    ├── __init__.py
    └── validators.py              # Validaciones
```

## 🎓 Sistemas de Calificación

### IRT Simplificado (Recomendado)

Modelo de 1 parámetro basado en Item Response Theory. Estima la habilidad del estudiante (theta) y calcula una nota normalizada.

```json
{
  "tipo": "irt_simplificado",
  "parametros": {
    "max_iteraciones": 10
  }
}
```

### Sistema Elo

Basado en el sistema de rating de ajedrez, ajusta el rating del estudiante después de cada pregunta.

```json
{
  "tipo": "elo",
  "parametros": {
    "k_factor": 32,
    "rating_inicial": 1500
  }
}
```

### Sistema Híbrido

Combina IRT (70%) y Elo (30%) para un enfoque balanceado.

```json
{
  "tipo": "hibrido",
  "parametros": {
    "peso_irt": 0.7,
    "peso_elo": 0.3,
    "max_iteraciones": 10,
    "k_factor": 32
  }
}
```

## 📊 Formato de Resultados en Google Sheets

Los resultados se guardan con las siguientes columnas:

- Fecha_Hora
- Codigo_Estudiante
- Preguntas_Respondidas
- Correctas
- Incorrectas
- Porcentaje_Correctas
- Nivel_Final
- Nota_Final
- Preguntas_IDs
- Theta_IRT
- Consistencia_IRT
- Nivel_Habilidad_IRT
- Rating_Elo
- Cambio_Rating_Elo
- Razon_Terminacion
- Sistema_Calificacion

## 🔧 Personalización

### Crear un nuevo examen

1. Copia `config/examen_template.json`
2. Modifica los parámetros según tu asignatura
3. Crea un nuevo banco de preguntas en `data/`
4. Actualiza la referencia en el archivo de configuración

### Agregar preguntas

Las preguntas deben tener:
- **id**: Identificador único (ej: "p001")
- **dificultad**: Nivel 1-5
- **categoria**: Tema o categoría
- **pregunta**: Texto de la pregunta (puede incluir código con ````python`)
- **opciones**: Diccionario con opciones {letra: texto}
- **respuesta_correcta**: Letra de la opción correcta
- **explicacion**: Feedback para el estudiante

### Prompt recomendado para generar preguntas con IA

- Usa el prompt oficial en [data/bancos/PROMPT_GENERACION_POR_TEMA.md](data/bancos/PROMPT_GENERACION_POR_TEMA.md).
- Está alineado con la lógica adaptativa del proyecto (dificultad 1-5, por tema).
- Está optimizado para estudiantes de **primer semestre** y exige salida en JSON compatible.

## 🎯 Criterios de Terminación

El examen termina cuando:

1. Se alcanza el máximo de preguntas (30 por defecto)
2. Se cumple el mínimo (15) Y la nota se estabiliza (variación < 0.15 en últimas 3 preguntas)
3. No hay más preguntas disponibles en el banco

## 📈 Análisis de Resultados

El sistema proporciona:

- **Nota final**: Escala 0-5 basada en el sistema de calificación
- **Gráfico de evolución**: Muestra cómo cambió la nota durante el examen
- **Análisis por nivel**: Desempeño en cada nivel de dificultad
- **Análisis por categoría**: Fortalezas y debilidades por tema
- **Estadísticas del sistema**: Theta, consistencia, rating, etc.

## ⚠️ Consideraciones Importantes

1. **Banco de preguntas**: Asegúrate de tener suficientes preguntas en cada nivel (mínimo 3-5 por nivel)
2. **Seguridad**: Nunca incluyas el archivo `secrets.toml` en control de versiones
3. **Permisos**: La service account debe tener permisos de editor en el Google Sheet
4. **Testing**: Prueba el examen antes de usar en producción

## 🔒 Seguridad de cliente (modo no invasivo)

El sistema incluye una capa de hardening en navegador, sin permisos de sistema operativo:

- Pantalla completa (best effort)
- Bloqueo de copiar/pegar/cortar y menu contextual
- Bloqueo de atajos comunes de inspeccion/busqueda/guardar/imprimir
- Deteccion de perdida de foco o cambio de pestana con alertas visuales
- Advertencia al intentar cerrar/recargar la pagina

Configuracion opcional por examen en el JSON:

```json
"seguridad_cliente": {
  "habilitado": true,
  "fullscreen_obligatorio": true,
  "bloquear_copiar_pegar": true,
  "bloquear_menu_contexto": true,
  "bloquear_seleccion_texto": true,
  "bloquear_atajos_comunes": true,
  "detectar_perdida_foco": true,
  "advertir_salida_pestana": true,
  "mensaje_disuasion": "Modo examen activo. Evite cambiar de pestana o usar atajos no permitidos.",
  "max_alertas_en_pantalla": 3
}
```

Importante: esta capa disuade y reduce riesgo, pero no reemplaza un entorno kiosk/lockdown browser cuando se requiere alta seguridad.

## 🐛 Solución de Problemas

### Error: ModuleNotFoundError en Streamlit Cloud

Si ves un error como `ModuleNotFoundError: No module named 'src'` al desplegar:

**Solución 1**: Verifica la estructura de archivos
```bash
# Asegúrate de que existan estos archivos:
src/__init__.py
utils/__init__.py
```

**Solución 2**: Haz commit y push de todos los archivos
```bash
git add .
git commit -m "Fix module imports"
git push
```

**Solución 3**: Reboot la app en Streamlit Cloud
1. Ve a "Manage app"
2. Click en "⋮" (menú)
3. Selecciona "Reboot app"

### Error al conectar con Google Sheets

- Verifica que las credenciales en `secrets.toml` sean correctas
- Confirma que la service account tenga permisos en el Sheet
- Verifica que el SPREADSHEET_ID sea correcto

### No se cargan las preguntas

- Verifica el formato JSON del archivo de preguntas
- Confirma que la ruta en la configuración sea correcta
- Revisa que todas las preguntas tengan los campos requeridos

### El examen no termina

- Revisa los parámetros de estabilización
- Verifica que haya suficientes preguntas en el banco
- Ajusta `umbral_estabilizacion` si es necesario

## 📝 Licencia

Este proyecto está desarrollado para uso académico en Universidad ECCI.

## 👤 Autor

Sistema desarrollado para el Programa de Ingeniería Química - Universidad ECCI

## 📧 Contacto

Para soporte o preguntas, contactar al administrador del sistema.
