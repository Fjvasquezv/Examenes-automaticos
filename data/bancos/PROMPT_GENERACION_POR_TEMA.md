# Plantilla oficial: generación de bancos por tema (compatibles con el sistema)

Usa esta plantilla con cualquier LLM para generar bancos listos para cargar en el sistema adaptativo.

## 1) Qué necesita SÍ o SÍ un banco para funcionar

Cada pregunta debe cumplir este esquema mínimo:
- `id` (string único)
- `dificultad` (entero de 1 a 5)
- `categoria` (string, debe coincidir con el tema)
- `pregunta` (string)
- `opciones` (objeto con claves `a`, `b`, `c`, `d`)
- `respuesta_correcta` (una sola: `a`/`b`/`c`/`d`)
- `explicacion` (string)
- `tipo` (`texto` recomendado)

Reglas críticas de aceptación:
- IDs únicos en todo el banco (sin duplicados).
- JSON válido (sin comentarios, sin texto fuera del JSON).
- `respuesta_correcta` debe existir dentro de `opciones`.
- `categoria` debe ser exactamente el tema esperado (mismo texto).
- Cantidad total del banco debe ser suficiente para el mínimo del examen.

## 2) Prompt listo para copiar/pegar

Eres un diseñador instruccional experto en evaluación adaptativa para estudiantes de primer semestre.

Genera preguntas de selección múltiple por tema para un banco de preguntas con calidad de evaluación real.

### Contexto
- Asignatura: {{ASIGNATURA}}
- Temas a cubrir: {{TEMAS_LISTA}}
- Total de preguntas: {{TOTAL_PREGUNTAS}}
- Distribución por dificultad (1-5): {{DISTRIBUCION_DIFICULTAD}}
- Nivel del público: {{NIVEL_PUBLICO}} (por defecto: primer semestre)
- Idioma: Español
- Prefijo de IDs: {{PREFIJO}}

### Reglas obligatorias
1. Cada pregunta debe pertenecer a un tema de `{{TEMAS_LISTA}}` usando `categoria` exacta.
2. Usa `dificultad` entera entre 1 y 5.
3. Genera exactamente 4 opciones (`a`, `b`, `c`, `d`) y una sola respuesta correcta.
4. Evita preguntas ambiguas, triviales o con dos respuestas plausibles.
5. Usa distractores realistas (errores típicos del nivel).
6. Balancea la posición de la respuesta correcta (no concentrarla en una sola letra).
7. No incluyas contenido fuera del alcance del nivel/tema.
8. Devuelve solo JSON válido.

### Escala pedagógica de dificultad
- 1: reconocimiento/definición básica.
- 2: aplicación simple en contexto corto.
- 3: análisis intermedio, comparación o interpretación.
- 4: resolución de problema con varios pasos.
- 5: caso retador con integración de conceptos.

### Formato de salida obligatorio
Devuelve solo una lista JSON, sin markdown ni comentarios, con esta estructura:

[
  {
    "id": "{{PREFIJO}}_001",
    "dificultad": 3,
    "categoria": "{{TEMA}}",
    "pregunta": "Texto de la pregunta.",
    "opciones": {
      "a": "Opción A",
      "b": "Opción B",
      "c": "Opción C",
      "d": "Opción D"
    },
    "respuesta_correcta": "b",
    "explicacion": "Explicación breve, correcta y formativa.",
    "tipo": "texto"
  }
]

### Autoverificación obligatoria antes de responder
- JSON parseable.
- IDs únicos (sin repetidos).
- Dificultad en rango 1-5.
- `categoria` válida (solo temas permitidos).
- 4 opciones por pregunta.
- Una sola correcta por pregunta.

## 3) Checklist operativo antes de usar el banco

1. Guardar archivo en la ruta correcta (`data/bancos/<Asignatura>/<Tema>.json`).
2. Validar estructura:
   - `python utils/validate_question_banks.py --path data/bancos/<Asignatura>`
3. Validar examen completo (periodo/config/bancos/cantidad):
   - `python utils/preflight_exam.py --periodo "<NOMBRE EXACTO DEL PERIODO>"`
4. Solo después de validar, publicar desde UI Admin o push por git.

## 4) Errores frecuentes a evitar

- IDs duplicados entre archivos de distintos temas.
- Categorías escritas distinto al tema configurado (`bancos_por_tema`).
- Preguntas con `respuesta_correcta` que no coincide con opciones.
- Banco editado en el editor pero no guardado en disco.
- JSON con comillas mal cerradas o comas finales inválidas.
