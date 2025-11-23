# Guía para Expandir el Banco de Preguntas

Esta guía te ayudará a expandir tu banco de preguntas de 75 a 120 preguntas de manera estructurada y balanceada.

## 📊 Estado Actual

- **Preguntas actuales**: 75
- **Meta**: 120 preguntas
- **Preguntas faltantes**: 45

## 🎯 Distribución Recomendada por Nivel

Para mantener un banco balanceado, se recomienda la siguiente distribución:

| Nivel | Preguntas Objetivo | Descripción |
|-------|-------------------|-------------|
| 1 | 24 preguntas | Básico - Conceptos fundamentales |
| 2 | 24 preguntas | Fundamental - Aplicación simple |
| 3 | 24 preguntas | Intermedio - Múltiples conceptos |
| 4 | 24 preguntas | Avanzado - Resolución de problemas |
| 5 | 24 preguntas | Experto - Casos complejos |

## 📚 Distribución por Categoría

Asegúrate de cubrir estas categorías de manera equilibrada:

### 1. Tipos de datos (12 preguntas)
- **Nivel 1**: int, float, str, bool básicos
- **Nivel 2**: Conversiones de tipos
- **Nivel 3**: Tipos complejos (None, bytes)
- **Nivel 4-5**: Edge cases, comportamiento avanzado

### 2. Operadores y expresiones (12 preguntas)
- **Nivel 1**: Operadores aritméticos básicos (+, -, *, /)
- **Nivel 2**: Operadores especiales (//, %, **)
- **Nivel 3**: Operadores lógicos y de comparación
- **Nivel 4-5**: Precedencia y expresiones complejas

### 3. Estructuras de control (15 preguntas)
- **Nivel 1**: if básico
- **Nivel 2**: if-elif-else
- **Nivel 3**: for loops básicos
- **Nivel 4**: while loops, break, continue
- **Nivel 5**: Nested loops, lógica compleja

### 4. Funciones (15 preguntas)
- **Nivel 1**: Definición y llamado básico
- **Nivel 2**: Parámetros y return
- **Nivel 3**: Argumentos por defecto
- **Nivel 4**: *args, **kwargs
- **Nivel 5**: Lambda, decoradores, closures

### 5. Listas y tuplas (15 preguntas)
- **Nivel 1**: Creación y acceso básico
- **Nivel 2**: Slicing, métodos básicos
- **Nivel 3**: Métodos avanzados (sort, extend, etc.)
- **Nivel 4**: List comprehension simple
- **Nivel 5**: List comprehension avanzada

### 6. Diccionarios (12 preguntas)
- **Nivel 1**: Creación y acceso
- **Nivel 2**: Métodos básicos (get, keys, values)
- **Nivel 3**: Métodos avanzados (update, items)
- **Nivel 4**: Dictionary comprehension
- **Nivel 5**: Diccionarios anidados, defaultdict

### 7. Strings (12 preguntas)
- **Nivel 1**: Concatenación, indexación
- **Nivel 2**: Slicing, métodos básicos
- **Nivel 3**: Format, métodos avanzados
- **Nivel 4**: f-strings, expresiones regulares básicas
- **Nivel 5**: Manipulación compleja

### 8. POO (12 preguntas)
- **Nivel 1**: Conceptos básicos de clases
- **Nivel 2**: __init__, self
- **Nivel 3**: Métodos, atributos de clase
- **Nivel 4**: Herencia, super()
- **Nivel 5**: Métodos especiales, polimorfismo

### 9. Manejo de excepciones (9 preguntas)
- **Nivel 2**: Try-except básico
- **Nivel 3**: Múltiples excepciones
- **Nivel 4**: Finally, else
- **Nivel 5**: Excepciones personalizadas, context managers

### 10. Archivos y módulos (6 preguntas)
- **Nivel 3**: Lectura básica de archivos
- **Nivel 4**: Escritura, modos de apertura
- **Nivel 5**: Context managers, módulos

## 🔨 Plantilla para Crear Preguntas

### Nivel 1 - Básico
```json
{
  "id": "p076",
  "dificultad": 1,
  "categoria": "Tipos de datos",
  "pregunta": "¿Qué tipo de dato es `42` en Python?",
  "opciones": {
    "a": "str",
    "b": "float",
    "c": "int",
    "d": "bool"
  },
  "respuesta_correcta": "c",
  "explicacion": "42 es un número entero (int). No tiene punto decimal, por lo que no es float."
}
```

### Nivel 2 - Fundamental
```json
{
  "id": "p077",
  "dificultad": 2,
  "categoria": "Operadores",
  "pregunta": "¿Cuál es el resultado?\n\n```python\nprint(10 % 3)\n```",
  "opciones": {
    "a": "3",
    "b": "1",
    "c": "3.33",
    "d": "0"
  },
  "respuesta_correcta": "b",
  "explicacion": "El operador % (módulo) devuelve el resto de la división. 10 dividido entre 3 es 3 con resto 1."
}
```

### Nivel 3 - Intermedio
```json
{
  "id": "p078",
  "dificultad": 3,
  "categoria": "Listas",
  "pregunta": "¿Qué devuelve este código?\n\n```python\nlista = [1, 2, 3, 4, 5]\nprint(lista[1:4])\n```",
  "opciones": {
    "a": "[1, 2, 3]",
    "b": "[2, 3, 4]",
    "c": "[2, 3, 4, 5]",
    "d": "[1, 2, 3, 4]"
  },
  "respuesta_correcta": "b",
  "explicacion": "El slicing [1:4] toma elementos desde el índice 1 (incluido) hasta el 4 (excluido), resultando en [2, 3, 4]."
}
```

### Nivel 4 - Avanzado
```json
{
  "id": "p079",
  "dificultad": 4,
  "categoria": "Funciones",
  "pregunta": "¿Qué imprime este código?\n\n```python\ndef func(*args):\n    return sum(args)\n\nprint(func(1, 2, 3, 4))\n```",
  "opciones": {
    "a": "10",
    "b": "(1, 2, 3, 4)",
    "c": "Error",
    "d": "[1, 2, 3, 4]"
  },
  "respuesta_correcta": "a",
  "explicacion": "*args permite recibir un número variable de argumentos como tupla. sum() suma todos los elementos: 1+2+3+4 = 10."
}
```

### Nivel 5 - Experto
```json
{
  "id": "p080",
  "dificultad": 5,
  "categoria": "Comprensión de listas",
  "pregunta": "¿Cuál es el resultado?\n\n```python\nmatriz = [[1,2,3], [4,5,6], [7,8,9]]\nresultado = [x for fila in matriz for x in fila if x % 2 == 0]\nprint(resultado)\n```",
  "opciones": {
    "a": "[2, 4, 6, 8]",
    "b": "[1, 3, 5, 7, 9]",
    "c": "[[2], [4, 6], [8]]",
    "d": "[2, 4, 5, 6, 8]"
  },
  "respuesta_correcta": "a",
  "explicacion": "La comprensión recorre cada fila de la matriz, luego cada elemento, y filtra los pares. Los números pares son 2, 4, 6 y 8."
}
```

## ✅ Lista de Verificación para Cada Pregunta

Antes de agregar una pregunta, verifica:

- [ ] ID único (p001-p120)
- [ ] Nivel de dificultad apropiado (1-5)
- [ ] Categoría asignada
- [ ] Pregunta clara y concisa
- [ ] Código formateado con ````python` si aplica
- [ ] 4 opciones de respuesta
- [ ] Una respuesta correcta claramente identificable
- [ ] Explicación detallada y educativa
- [ ] Sin ambigüedades
- [ ] Ortografía y gramática correctas

## 📝 Consejos para Crear Buenas Preguntas

### 1. Claridad
- Usa lenguaje preciso
- Evita ambigüedades
- Sé específico en lo que preguntas

### 2. Código
- Usa ejemplos concisos
- Formatea correctamente
- Asegúrate de que el código sea ejecutable

### 3. Opciones
- Haz las opciones incorrectas plausibles
- Evita opciones obviamente incorrectas
- No uses "Todas las anteriores" o "Ninguna de las anteriores"

### 4. Explicaciones
- Explica por qué la respuesta correcta es correcta
- Menciona por qué las otras opciones son incorrectas
- Proporciona contexto adicional cuando sea útil

### 5. Dificultad Progresiva
- **Nivel 1**: Conocimiento directo, definiciones
- **Nivel 2**: Aplicación simple, un concepto
- **Nivel 3**: Múltiples conceptos, análisis
- **Nivel 4**: Resolución de problemas, síntesis
- **Nivel 5**: Casos complejos, optimización

## 🔄 Proceso de Expansión

### Fase 1: Preguntas 76-90 (15 preguntas)
Enfócate en:
- Completar las categorías con menos preguntas
- Balancear los niveles 1-3

### Fase 2: Preguntas 91-105 (15 preguntas)
Enfócate en:
- Niveles 4-5
- Categorías avanzadas (POO, excepciones)

### Fase 3: Preguntas 106-120 (15 preguntas)
Enfócate en:
- Llenar huecos en la distribución
- Asegurar balance entre categorías
- Revisar y refinar

## 🧪 Validación

Después de agregar las preguntas, valida el banco:

```python
import json

# Cargar preguntas
with open('data/preguntas_python.json', 'r', encoding='utf-8') as f:
    preguntas = json.load(f)

# Estadísticas
niveles = {}
categorias = {}

for p in preguntas:
    nivel = p['dificultad']
    categoria = p['categoria']
    
    niveles[nivel] = niveles.get(nivel, 0) + 1
    categorias[categoria] = categorias.get(categoria, 0) + 1

print(f"Total de preguntas: {len(preguntas)}")
print("\nDistribución por nivel:")
for nivel in sorted(niveles.keys()):
    print(f"  Nivel {nivel}: {niveles[nivel]} preguntas")

print("\nDistribución por categoría:")
for cat in sorted(categorias.keys()):
    print(f"  {cat}: {categorias[cat]} preguntas")
```

## 📊 Plantilla de Seguimiento

Usa esta tabla para hacer seguimiento de tu progreso:

| ID | Nivel | Categoría | Status | Notas |
|----|-------|-----------|--------|-------|
| p076 | 1 | Tipos de datos | ✅ | Completada |
| p077 | 2 | Operadores | ⏳ | En progreso |
| p078 | 3 | Listas | ⬜ | Pendiente |
| ... | ... | ... | ... | ... |

## 🎯 Meta Final

Al completar las 120 preguntas, deberías tener:

- ✅ 24 preguntas por cada nivel (1-5)
- ✅ Cobertura balanceada de todas las categorías
- ✅ Progresión clara de dificultad
- ✅ Explicaciones detalladas en todas las preguntas
- ✅ Banco validado y sin errores

## 📞 Soporte

Si necesitas ayuda para crear preguntas:
1. Revisa los ejemplos en `data/preguntas_ejemplo.json`
2. Consulta la documentación de Python
3. Usa casos de uso reales de tus clases
4. Pide feedback a otros docentes

¡Buena suerte expandiendo tu banco de preguntas! 🚀
