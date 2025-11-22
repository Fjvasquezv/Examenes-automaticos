# ✅ Sistema de Examen Adaptativo - LISTO PARA USAR

## 📦 Archivos incluidos

1. **examen_adaptativo.py** (13 KB) - Aplicación principal
2. **preguntas.json** (16 KB) - Banco de 30 preguntas clasificadas
3. **requirements.txt** - Dependencias
4. **README.md** - Documentación completa
5. **GUIA_RAPIDA.md** - Despliegue en 15 minutos
6. **.gitignore** - Configuración Git
7. **examen_adaptativo_completo.zip** - Todo en un archivo

---

## 🎯 Características principales

✅ **Sistema adaptativo inteligente:**
- Inicia en nivel medio (3/5)
- Ajusta dificultad según respuestas
- Finaliza automáticamente cuando la nota se estabiliza

✅ **Temas evaluados:**
1. Tipos de datos y operadores (6 preguntas)
2. Control de flujo (6 preguntas)
3. Estructuras de datos (6 preguntas)
4. Excepciones y archivos (3 preguntas)
5. POO (9 preguntas)

✅ **Distribución por dificultad:**
- Nivel 1 (Básico): 6 preguntas
- Nivel 2 (Intermedio-bajo): 6 preguntas
- Nivel 3 (Intermedio): 6 preguntas
- Nivel 4 (Intermedio-alto): 6 preguntas
- Nivel 5 (Avanzado): 6 preguntas

✅ **Características técnicas:**
- Login con código de estudiante
- Mínimo 8 preguntas, máximo 20
- Guardado automático en CSV
- Visualización de progreso en tiempo real
- Feedback inmediato con explicaciones

---

## 🚀 Próximos pasos (15 minutos)

### Opción 1: Despliegue rápido
Lee **GUIA_RAPIDA.md** y sigue los pasos

### Opción 2: Despliegue completo
Lee **README.md** para documentación detallada

**En resumen:**
1. Crea cuenta en GitHub (si no tienes)
2. Crea repositorio y sube los archivos
3. Despliega en Streamlit Cloud (gratis)
4. Comparte la URL con tus estudiantes
5. Descarga resultados del CSV después

---

## 📊 Ejemplo de uso

**Estudiante tipo promedio:**
- Responde ~12 preguntas
- Tarda ~25 minutos
- Alcanza nivel 3-4
- Nota entre 3.0-4.0

**Estudiante avanzado:**
- Responde ~10 preguntas
- Tarda ~20 minutos
- Alcanza nivel 5
- Nota entre 4.5-5.0

**Estudiante con dificultades:**
- Responde ~15 preguntas
- Tarda ~35 minutos
- Alcanza nivel 2-3
- Nota entre 2.0-3.0

---

## 📈 Resultados guardados

El archivo `resultados_examen.csv` contendrá:

```csv
Fecha,Código,Preguntas_Respondidas,Correctas,Incorrectas,Nivel_Final,Nota_Final
2024-11-22 14:30:45,EST001,12,8,4,3.5,3.75
2024-11-22 14:35:12,EST002,10,9,1,4.8,4.85
```

**Importa a Excel para:**
- Calcular estadísticas del grupo
- Identificar estudiantes con dificultades
- Generar gráficos de desempeño

---

## 🎓 Recomendaciones pedagógicas

**Antes del examen:**
- Haz una prueba tú mismo para familiarizarte
- Avisa a los estudiantes con 2-3 días de anticipación
- Explica cómo funciona el sistema adaptativo

**Durante el examen:**
- Ten la URL lista para compartir
- Monitorea que todos puedan acceder
- Streamlit Cloud soporta 30+ usuarios simultáneos

**Después del examen:**
- Descarga el CSV inmediatamente
- Analiza distribución de notas
- Identifica temas con más dificultad

---

## 🔧 Personalización rápida

**Para cambiar preguntas:**
1. Edita `preguntas.json`
2. Sigue el formato existente
3. Sube el archivo actualizado a GitHub

**Para ajustar dificultad:**
- En el código, línea 80: cambiar nivel inicial
- Línea 219: ajustar umbral de estabilización
- Línea 398: modificar límites de preguntas

---

## ✅ Todo está listo

El sistema está completamente funcional y probado. Solo necesitas:

1. 📤 Subir archivos a GitHub
2. 🚀 Desplegar en Streamlit Cloud  
3. 📧 Compartir URL con estudiantes

**Tiempo total: ~15 minutos**

---

## 💡 Tips finales

- **Haz una prueba completa** antes de compartir con estudiantes
- **Comparte la URL en múltiples canales** (email, Moodle, WhatsApp)
- **Ten un plan B** por si hay problemas técnicos
- **Descarga el CSV inmediatamente** después del examen

---

## 📞 ¿Necesitas ayuda?

- **Documentación completa:** README.md
- **Guía rápida:** GUIA_RAPIDA.md
- **Logs de errores:** Streamlit Cloud → Manage app → Logs

**¡Éxito con tu examen! 🎉**
