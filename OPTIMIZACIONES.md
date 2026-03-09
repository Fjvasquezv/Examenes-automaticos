# Análisis de Optimizaciones del Flujo de Trabajo

**Fecha de análisis:** 6 de marzo de 2026  
**Estado actual:** Sistema operando en vivo con 40 estudiantes concurrentes en Introducción (11:40–12:20)

---

## I. Diagnóstico Actual

### Fortalezas existentes ✅
- **Persistencia robusta**: Retry con backoff exponencial en Google Sheets (5 intentos max)
- **Preflight validación**: Script operacional que valida todo antes de lanzar examen
- **Administración remota**: Panel admin en Streamlit para publicar config + banks a GitHub
- **Arquitectura modular**: Separación clara entre config_loader, exam_logic, question_manager, persistence
- **Adaptatividad**: CAT (Computerized Adaptive Testing) con IRT simplificado
- **Control de distribución**: Blueprint pedagógico con objetivos/mínimos/máximos por categoría

### Puntos vulnerables ⚠️
1. **Monolito único** → Todo en app.py (1656 líneas), UI + lógica + admin mezcladas
2. **Sin caché de preguntas** → QuestionManager recarga bancos completos por cada estudiante
3. **Estado en Streamlit session** → Rebot ante re-run pierde estado parcialmente; depende de Google Sheets
4. **Sin logging centralizado** → Errores solo en stderr; difícil auditar post-mortem
5. **Admin panel manual** → Seleccionar período, examen, etc. requiere clicks repetitivos
6. **Sin monitoreo en vivo** → No hay dashboard de estudiantes activos, tasa de error, latencia
7. **Configuración dispersa** → Instrucciones en 3+ archivos (disponibilidad, examen config, instrucciones.json)
8. **Sin rate limiting** → Múltiples estudiantes podrían saturar Google Sheets aunque haya retry/backoff
9. **Serialización JSON pesada** → `_serializar_estado_exam_logic()` crea strings grandes para cada actualización
10. **Sin optimización de lectura** → Cada estudiante recarga el mismo examen config desde disco

---

## II. Optimizaciones Propuestas (Priorizadas)

### **FASE 1: Impacto Crítico (Implementar antes del próximo examen)**

#### 1.1 **Caché de Bancos de Preguntas en Memoria**
**Problema:** Cada nueva sesión de estudiante carga todos los bancos JSON desde disco.  
**Solución:** Implementar caché global con TTL de 1 hora.
```python
# En app.py, al inicio
@st.cache_resource(ttl=3600)
def cargar_bancos_cached(periodo: str):
    """Carga bancos una sola vez por hora para todos los usuarios"""
    config = ConfigLoader().load_config(...)
    return QuestionManager(bancos_preguntas=config['bancos_preguntas'])
```
**Impacto:** ↓ 200-500ms por estudiante | ↓ I/O disco | ↓ CPU  
**Riesgo:** Bajo | Es cacheable porque los bancos no cambian durante el examen  
**Esfuerzo:** 15 minutos

---

#### 1.2 **Rate Limiter para Google Sheets API**
**Problema:** Sin límite de QPS, 40 usuarios podrían generar 40 escrituras simultáneas.  
**Solución:** Cola de prioridad (thread-safe) en DataPersistence.
```python
# En data_persistence.py
from queue import PriorityQueue, Queue
import threading

class DataPersistence:
    def __init__(self, config):
        self.cola_escritura = Queue(maxsize=200)
        self.worker_thread = threading.Thread(
            target=self._worker_persistencia, daemon=True
        )
        self.worker_thread.start()
    
    def _worker_persistencia(self):
        """Thread dedicado que escribe a Google Sheets a ~2 QPS max"""
        while True:
            codigo_est, funcion, args = self.cola_escritura.get()
            try:
                funcion(*args)
                time.sleep(0.5)  # Rate limit: máx 2 escrituras/segundo
            except Exception as e:
                # Reintentar o alertar
                pass
    
    def actualizar_progreso_no_bloqueante(self, codigo_est, **progreso):
        """Encola actualización en lugar de hacerla sincrónica"""
        self.cola_escritura.put(
            (codigo_est, self._actualizar_en_sheet, (codigo_est, progreso))
        )
```
**Impacto:** ↓ errores 429 | ↓ latencia de UI (no espera Google Sheets) | ✅ mejor UX  
**Riesgo:** Bajo | Fallback a guardado sincrónico si falla queue  
**Esfuerzo:** 45 minutos

---

#### 1.3 **Logging Centralizado con Contexto**
**Problema:** Errores solo en stderr; imposible auditar quién falló, cuándo, por qué.  
**Solución:** Logger con rotación a archivo + streaming a Google Sheets (tabla separada).
```python
# Crear utils/exam_logger.py
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

class ExamLogger:
    def __init__(self, spreadsheet_id, hoja_logs="Logs"):
        self.logger = logging.getLogger("examen_adaptativo")
        handler = logging.FileHandler(f"logs/examen_{datetime.now():%Y%m%d_%H%M%S}.log")
        handler.setFormatter(
            logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
        )
        self.logger.addHandler(handler)
        self.spreadsheet_id = spreadsheet_id
    
    def registrar_evento(self, tipo: str, codigo_est: str, mensaje: str, datos_extra: dict = None):
        """Registra eventos de examen (inicio, error, timeout, finalización)"""
        entrada = {
            'timestamp': datetime.now(ZoneInfo("America/Bogota")),
            'tipo': tipo,
            'codigo_estudiante': codigo_est,
            'mensaje': mensaje,
            'usuario_agent': st.session_state.get('user_agent', 'desconocido'),
            'datos_extra': json.dumps(datos_extra or {})
        }
        # Escribir a archivo local
        self.logger.info(f"{tipo} | {codigo_est} | {mensaje}")
        # Escribir a Google Sheets tabla Logs
        # ...
```
**Impacto:** 🔍 Debuggabilidad post-mortem | ✅ Cumplimiento auditoría  
**Riesgo:** Bajo | Logging asíncrono no bloquea examen  
**Esfuerzo:** 1 hora

---

#### 1.4 **Dashboard Operacional en Tiempo Real**
**Problema:** Staff no ve actualmente cuántos estudiantes están en examen, tasa de error, latencia.  
**Solución:** Tab adicional en admin panel que actualiza cada 5s.
```python
# En app.py, agregar tab en admin_panel()
if tab == "Monitoreo 📊":
    col1, col2, col3 = st.columns(3)
    
    with col1:
        estudiantes_activos = contar_en_curso(spreadsheet_id, periodo)
        st.metric("Activos ahora", estudiantes_activos, f"+{estudiantes_activos//10}")
    
    with col2:
        tasa_completacion = calcular_completacion(spreadsheet_id, periodo)
        st.metric("Completación", f"{tasa_completacion:.1f}%")
    
    with col3:
        latencia_prom = calcular_latencia_promedio(spreadsheet_id)
        st.metric("Latencia API", f"{latencia_prom:.0f}ms")
    
    st.plotly_chart(grafico_progreso_en_vivo(spreadsheet_id, periodo), use_container_width=True)
    
    st.subheader("Estudiantes Activos")
    df_activos = obtener_estudiantes_activos(spreadsheet_id, periodo)
    st.dataframe(df_activos, use_container_width=True)
    
    # Auto-refresh cada 5 segundos
    st.rerun()
```
**Impacto:** 👀 Visibilidad operacional | ⚡ Detección rápida de anomalías | 🚨 Alertas proactivas  
**Riesgo:** Bajo | Es UI solo, no impacta lógica examen  
**Esfuerzo:** 1.5 horas

---

### **FASE 2: Mejoras Operacionales (Después de examen actual)**

#### 2.1 **Preflight Automático Antes de Abrir Examen**
**Problema:** Preflight_exam.py requiere CLI; staff podría olvidar ejecutarlo.  
**Solución:** Botón en UI admin que valida antes de activar período.
```python
# En _admin_panel_operacion(), agregar:
if st.button("🧪 Validar Examen Antes de Activar"):
    resultado = ejecutar_preflight_desde_ui(periodo_seleccionado)
    if resultado['ok']:
        st.success(f"✅ {resultado['mensaje']} ({resultado['total_preguntas']} preguntas)")
        if st.button("✅ Activar Período"):
            actualizar_disponibilidad_inicio(periodo)
            st.success("Período abierto!")
    else:
        st.error(f"❌ {resultado['error']}")
        st.info(f"Detalles: {resultado['detalles']}")
```
**Impacto:** 🛡️ Previene exámenes sin bancos | ✅ UX mejorada (no requiere terminal)  
**Riesgo:** Bajo  
**Esfuerzo:** 30 minutos

---

#### 2.2 **Configuración Centralizada (Un Único Archivo)**
**Problema:** Configuración dispersa en 4+ archivos (disponibilidad, examen config, instrucciones, bancos).  
**Solución:** Crear `config/examenes/<Asignatura>/examen_completo.json` que incluya todo.
```json
{
  "metadata": {...},
  "parametros": {...},
  "disponibilidad": {
    "periodos": [{"nombre": "QUIZZ 1", "inicio": "2026-03-06 11:40", "fin": "2026-03-06 12:20", ...}]
  },
  "instrucciones": {...},
  "descripcion": {...},
  "bancos_preguntas": [...]
}
```
**Impacto:** 📋 Menor confusión | ✅ Versioning atomic (un archivo = una versión examen)  
**Riesgo:** Bajo | Mantener retrocompatibilidad por 1 mes  
**Esfuerzo:** 2 horas (requiere actualizar ConfigLoader + app.py)

---

#### 2.3 **Validación de Integridad de Bancos en GitHub**
**Problema:** Admin puede publicar banco con estructura incorrecta; no se detecta hasta runtime.  
**Solución:** GitHub Action que corre `preflight_exam.py + validators.py` en cada push.
```yaml
# .github/workflows/validate_exams.yml
name: Validar Exámenes
on: [push]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install -r requirements.txt
      - run: python utils/preflight_exam.py --todos_periodos
      - run: python utils/validate_question_banks.py
```
**Impacto:** 🚫 Bloquea push de config inválida | ✅ Calidad garantizada  
**Riesgo:** Bajo | Solo rechaza si falla validación  
**Esfuerzo:** 45 minutos

---

#### 2.4 **Resiliencia: Fallback a Caché Local**
**Problema:** Si Google Sheets está down, estudiantes pierden acceso al examen.  
**Solución:** Guardar últimas 100 actualizaciones en SQLite local; sincronizar cuando Sheet vuelva.
```python
# En data_persistence.py
import sqlite3

class DataPersistenceWithFallback:
    def __init__(self, config):
        self.cache_local = sqlite3.connect(':memory:', check_same_thread=False)
        self.cache_local.execute('''
            CREATE TABLE progreso_buffer (
                codigo_est TEXT, pregunta INT, correctas INT, timestamp REAL
            )
        ''')
    
    def guardar_progreso(self, codigo_est, pregunta, correctas):
        """Intenta Google Sheets; si falla, cachea localmente"""
        try:
            self._escritura_sheets(...)
        except Exception as e:
            # Fallback: escribir SQLite
            self.cache_local.execute(
                'INSERT INTO progreso_buffer VALUES (?, ?, ?, ?)',
                (codigo_est, pregunta, correctas, time.time())
            )
            st.warning("⚠️ Guardando offline; sincronizará cuando vuelva conexión")
            # Reintentar en background
            self._reintento_fondo()
```
**Impacto:** 🔄 Examen no colapsa si Google Sheets se cae | ✅ Garantía de integridad datos  
**Riesgo:** Bajo | Sincronización es idempotente  
**Esfuerzo:** 2 horas

---

### **FASE 3: Optimizaciones a Mediano Plazo (Siguiente trimestre)**

#### 3.1 **Separación Frontend/Backend (Condicional)**
**Problema:** Monolito actual hace difícil escalar a 200+ estudiantes, deployar independientemente.  
**Solución:** Desacoplar si se alcanza 100+ concurrentes en próximo semestre.
- Backend: FastAPI (exam_logic + question_manager + data_persistence)
- Frontend: Streamlit (UI) llamando APIs
- Beneficio: Backend escalable horizontalmente (múltiples instancias); Frontend sin estado
- **Decisión actual:** NO hacer ahora; revisitar en Q2 2026

#### 3.2 **Persistencia Híbrida (Sheets + PostgreSQL)**
**Problema:** Google Sheets tiene límite ~ 40 millones de celdas; no es OLTP real.  
**Solución:** Usar PostgreSQL para transacciones, Google Sheets para reportes/colaboración.
- Requerimiento: Base datos adicional (ej. AWS RDS micro ~$15/mes)
- **Decisión actual:** Diferir; evaluar en Q2

#### 3.3 **Compresión de Estado Exam Logic**
**Problema:** `_serializar_estado_exam_logic()` crea strings JSON grandes (~3KB por estudiante).  
**Solución:** Usar formato binario comprimido (MessagePack + brotli).
```python
import msgpack
import brotli

def serializar_estado_comprimido(exam_logic):
    payload = {
        'p': exam_logic.pregunta_actual,
        'n': exam_logic.nivel_actual,
        't': exam_logic.theta_actual,
        'c': exam_logic.correctas,
        'i': exam_logic.incorrectas,
        # ... resto de estado
    }
    return brotli.compress(msgpack.packb(payload))  # ~80% más pequeño
```
**Impacto:** ↓ 80% tamaño estado | ↓ ancho banda Google Sheets  
**Riesgo:** Bajo | Encoding solo, no afecta lógica  
**Esfuerzo:** 1 hora

---

## III. Tableau de Mejoras (Resumen Ejecutivo)

| Optimización | Impacto | Esfuerzo | Riesgo | Fase |
|---|---|---|---|---|
| Caché Bancos Preguntas | ⭐⭐⭐⭐⭐ | 15 min | Bajo | 1 |
| Rate Limiter Google Sheets | ⭐⭐⭐⭐ | 45 min | Bajo | 1 |
| Logging Centralizado | ⭐⭐⭐⭐ | 1 h | Bajo | 1 |
| Dashboard Monitoreo Real-Time | ⭐⭐⭐⭐⭐ | 1.5 h | Bajo | 1 |
| Preflight UI Auto | ⭐⭐⭐ | 30 min | Bajo | 2 |
| Configuración Centralizada | ⭐⭐⭐ | 2 h | Bajo | 2 |
| GitHub Actions Validación | ⭐⭐⭐⭐ | 45 min | Bajo | 2 |
| Fallback Cache Local | ⭐⭐⭐⭐⭐ | 2 h | Bajo | 2 |
| Compresión Estado Exam | ⭐⭐⭐ | 1 h | Bajo | 3 |

---

## IV. Recomendación Inmediata

### 🎯 Para hoy (6 de marzo, durante examen activo):
- **Monitorear** via nuevos logs; activar alertas si completación < 50%
- **Dejar corriendo** el preflight_exam.py en segundo plano para validación post-mortem

### 🎯 Para próximos 3 días (post-examen):
1. Implementar **Caché de Bancos** (MÁXIMO impacto, mínimo riesgo)
2. Implementar **Rate Limiter** (previene siguientes fallos)
3. Agregar **Logging** (instrumentación crítica)

### 🎯 Para próximo examen (semana de marzo 13):
4. Implementar **Dashboard Monitoreo**
5. Implementar **Preflight Bot en UI**
6. Agregar **GitHub Actions validación**

### 🎯 Si escalamos a 100+ estudiantes:
- Evaluar separación Frontend/Backend
- Implementar fallback SQLite local + sincronización

---

## V. Implementación: Stack de Cambios Propuestos

### Archivos a crear:
- `utils/exam_logger.py` (~150 líneas)
- `.github/workflows/validate_exams.yml` (~30 líneas)

### Archivos a modificar:
- `src/data_persistence.py` (+100 líneas, rate limiter + fallback)
- `app.py` (+150 líneas, caché + dashboard + monitoreo)
- `src/question_manager.py` (+10 líneas, adaptación caché)

### Configuración:
- `.streamlit/config.toml`: Aumentar timeout a 600s (rate limiter puede ralentizar primeras respuestas)

---

**Próxima acción:** ¿Procedemos con Fase 1 (caché + rate limiter + logging) después examen actual?
