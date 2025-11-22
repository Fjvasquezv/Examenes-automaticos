# Examen Adaptativo de Programación en Python

Sistema de evaluación adaptativa que ajusta la dificultad de las preguntas según el desempeño del estudiante en tiempo real.

## Características

- ✅ Examen adaptativo con 5 niveles de dificultad
- 📊 Evaluación automática con nota final
- 🔐 Sistema de identificación por código de estudiante
- 💾 Guardado automático de resultados en CSV
- 📈 Visualización de progreso en tiempo real
- 🎯 Criterio de parada inteligente (nota estabilizada)

## Temas evaluados

1. Tipos de datos y operadores
2. Control de flujo y funciones
3. Estructuras de datos (listas, diccionarios, tuplas)
4. Manejo de excepciones y archivos
5. Programación Orientada a Objetos (POO)

## Archivos del proyecto

```
examen_adaptativo/
│
├── examen_adaptativo.py    # Aplicación principal
├── preguntas.json          # Banco de 30 preguntas clasificadas por dificultad
├── requirements.txt        # Dependencias del proyecto
└── README.md              # Este archivo
```

## Instalación local (opcional)

Si quieres probarlo localmente antes de desplegarlo:

```bash
# 1. Clona o descarga los archivos
# 2. Instala las dependencias
pip install -r requirements.txt

# 3. Ejecuta la aplicación
streamlit run examen_adaptativo.py
```

La aplicación se abrirá en tu navegador en `http://localhost:8501`

## Despliegue en Streamlit Cloud (RECOMENDADO)

### Paso 1: Crear cuenta en GitHub (si no tienes)

1. Ve a https://github.com
2. Regístrate con tu email
3. Confirma tu cuenta

### Paso 2: Crear repositorio en GitHub

1. Inicia sesión en GitHub
2. Haz clic en el botón "+" en la esquina superior derecha
3. Selecciona "New repository"
4. Configura:
   - **Repository name:** `examen-adaptativo-python`
   - **Description:** "Sistema de examen adaptativo para programación"
   - **Visibility:** Private (para que solo tú tengas acceso)
5. Haz clic en "Create repository"

### Paso 3: Subir archivos al repositorio

**Opción A: Interfaz web (más fácil)**

1. En tu repositorio nuevo, haz clic en "uploading an existing file"
2. Arrastra y suelta estos 3 archivos:
   - `examen_adaptativo.py`
   - `preguntas.json`
   - `requirements.txt`
3. Escribe un mensaje de commit: "Subir examen adaptativo"
4. Haz clic en "Commit changes"

**Opción B: Usando Git (si sabes usar la terminal)**

```bash
# En la carpeta con tus archivos
git init
git add .
git commit -m "Subir examen adaptativo"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/examen-adaptativo-python.git
git push -u origin main
```

### Paso 4: Desplegar en Streamlit Cloud

1. Ve a https://streamlit.io/cloud
2. Haz clic en "Sign up" y usa tu cuenta de GitHub
3. Una vez dentro, haz clic en "New app"
4. Configura:
   - **Repository:** Selecciona `examen-adaptativo-python`
   - **Branch:** main
   - **Main file path:** `examen_adaptativo.py`
5. Haz clic en "Deploy!"

⏰ El despliegue toma 2-3 minutos

### Paso 5: Obtener la URL del examen

Una vez desplegado, Streamlit te dará una URL como:
```
https://tu-usuario-examen-adaptativo-python-xxxxx.streamlit.app
```

**¡Comparte esta URL con tus estudiantes!**

## Uso del sistema

### Para estudiantes

1. Abrir la URL del examen
2. Ingresar su código de estudiante
3. Hacer clic en "Iniciar Examen"
4. Responder las preguntas
5. Ver resultados al finalizar

### Para el docente

#### Descargar resultados

Los resultados se guardan automáticamente en `resultados_examen.csv` en el servidor.

**Para descargar los resultados:**

1. Ve a tu repositorio en GitHub
2. Haz clic en `resultados_examen.csv` (aparecerá después de que los estudiantes empiecen a hacer el examen)
3. Haz clic en "Download" o "Raw" y guarda el archivo
4. Abre el CSV en Excel o Google Sheets para ver los resultados

**Columnas del CSV:**
- `Fecha`: Timestamp de cuando se completó el examen
- `Código`: Código del estudiante
- `Preguntas_Respondidas`: Número total de preguntas
- `Correctas`: Preguntas respondidas correctamente
- `Incorrectas`: Preguntas respondidas incorrectamente
- `Nivel_Final`: Nivel de dificultad alcanzado (1-5)
- `Nota_Final`: Nota final sobre 5.0

## Cómo funciona el algoritmo adaptativo

1. **Inicio:** Todos los estudiantes empiezan en nivel 3 (medio)
2. **Ajuste:** 
   - Si responde correctamente → sube 1 nivel (máximo 5)
   - Si responde incorrectamente → baja 1 nivel (mínimo 1)
3. **Nota:** Se calcula basándose en:
   - Nivel actual alcanzado
   - Porcentaje de aciertos en últimas 5 preguntas
4. **Finalización:** El examen termina cuando:
   - La nota se estabiliza (variación < 0.15 en últimas 3 preguntas) Y
   - Ha respondido mínimo 8 preguntas
   - O ha respondido 20 preguntas (máximo)

## Personalizar el banco de preguntas

El archivo `preguntas.json` contiene 30 preguntas. Para agregar más:

```json
{
  "id": "p031",
  "dificultad": 3,
  "categoria": "Categoría",
  "pregunta": "¿Texto de la pregunta con código si es necesario?",
  "opciones": {
    "a": "Opción A",
    "b": "Opción B",
    "c": "Opción C",
    "d": "Opción D"
  },
  "respuesta_correcta": "a",
  "explicacion": "Explicación de la respuesta correcta"
}
```

**Niveles de dificultad:**
- 1: Básico (tipos de datos, operadores simples)
- 2: Intermedio-bajo (control de flujo, listas básicas)
- 3: Intermedio (funciones, diccionarios, excepciones)
- 4: Intermedio-alto (POO básica, conceptos avanzados)
- 5: Avanzado (POO avanzada, herencia, métodos especiales)

## Configuración avanzada

### Ajustar parámetros del examen

En `examen_adaptativo.py`, puedes modificar:

```python
# Línea ~80 - Nivel inicial
st.session_state.nivel_actual = 3  # Cambiar a 1, 2, 4 o 5

# Línea ~219 - Umbral de estabilización
def verificar_estabilizacion(historial_notas, umbral=0.15):
    # Reducir umbral = más preguntas antes de estabilizar
    # Aumentar umbral = menos preguntas

# Línea ~398 - Límites de preguntas
if len(st.session_state.historial_respuestas) >= 20:  # Máximo
elif len(st.session_state.historial_respuestas) >= 8:  # Mínimo
```

## Solución de problemas

### No aparece resultados_examen.csv

- El archivo se crea después de que el primer estudiante completa el examen
- Refresca la página del repositorio en GitHub

### Estudiantes reportan errores

1. Revisa los logs en Streamlit Cloud:
   - Ve a tu app en Streamlit Cloud
   - Haz clic en "Manage app" → "Logs"
2. Verifica que todos los archivos estén subidos correctamente

### Actualizar el examen después de desplegado

1. Modifica los archivos localmente
2. Súbelos a GitHub (reemplazando los anteriores)
3. Streamlit Cloud se actualizará automáticamente en 1-2 minutos

## Estadísticas del sistema

- ⏱️ Tiempo promedio por pregunta: 2-3 minutos
- 📊 Preguntas promedio por estudiante: 10-15
- ⏰ Duración total del examen: 20-40 minutos
- 👥 Capacidad: 30+ estudiantes simultáneos (Streamlit Cloud gratuito)

## Soporte

Para preguntas o problemas:
- Revisa los logs en Streamlit Cloud
- Verifica que el formato JSON de las preguntas sea correcto
- Asegúrate de que los estudiantes usen navegadores actualizados

## Licencia

Uso libre para fines educativos.

---

**Creado con ❤️ para Universidad ECCI**
**Profesor: Francisco**
**Curso: Programación y Algoritmos - Ingeniería Química**
