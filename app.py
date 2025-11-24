"""
Sistema de Examen Adaptativo Modular
Orquestador Principal
"""
import streamlit as st
import sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json

# Agregar AMBOS directorios al path
base = Path(__file__).parent
sys.path.insert(0, str(base / "src"))
sys.path.insert(0, str(base / "utils"))

# Importar SIN prefijos
from config_loader import ConfigLoader
from question_manager import QuestionManager
from exam_logic import ExamLogic
from ui_components import UIComponents
from data_persistence import DataPersistence
from validators import validate_codigo_estudiante


def inicializar_session_state():
    """Inicializa las variables de session state necesarias"""
    if 'exam_started' not in st.session_state:
        st.session_state.exam_started = False
    if 'exam_finished' not in st.session_state:
        st.session_state.exam_finished = False
    if 'codigo_estudiante' not in st.session_state:
        st.session_state.codigo_estudiante = None
    if 'current_question_index' not in st.session_state:
        st.session_state.current_question_index = 0
    if 'respuestas' not in st.session_state:
        st.session_state.respuestas = []
    if 'notas_historicas' not in st.session_state:
        st.session_state.notas_historicas = []
    if 'preguntas_usadas' not in st.session_state:
        st.session_state.preguntas_usadas = []


def main():
    """Función principal de la aplicación"""
    
    # Configuración de la página
    st.set_page_config(
        page_title="Examen Adaptativo",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # Inicializar session state
    inicializar_session_state()
    
    try:
        # Cargar configuración
        config_loader = ConfigLoader()
        config = config_loader.load_config("config/examen_python.json")
        
        # Cargar banco de preguntas
        question_manager = QuestionManager(config['archivo_preguntas'])
        
        # Inicializar componentes
        ui = UIComponents(config)
        
        # Verificar que hay suficientes preguntas
        total_preguntas = len(question_manager.preguntas)
        if total_preguntas < config['parametros']['preguntas_minimas']:
            st.error(f"⚠️ Error: El banco de preguntas tiene {total_preguntas} preguntas, "
                    f"pero se necesitan al menos {config['parametros']['preguntas_minimas']}")
            return
        
        # Mostrar header
        ui.mostrar_header()
        
        # Flujo principal de la aplicación
        if not st.session_state.exam_started:
            # Pantalla de inicio
            mostrar_pantalla_inicio(config, ui)
            
        elif st.session_state.exam_finished:
            # Pantalla de resultados
            mostrar_resultados(config, ui)
            
        else:
            # Examen en progreso
            ejecutar_examen(config, question_manager, ui)
            
    except FileNotFoundError as e:
        st.error(f"❌ Error: No se encontró el archivo de configuración.\n{str(e)}")
    except Exception as e:
        st.error(f"❌ Error inesperado: {str(e)}")
        st.exception(e)


def verificar_disponibilidad(config):
    """
    Verifica si el examen está disponible según el calendario.
    Solo está disponible DENTRO de las franjas horarias definidas.
    """
    # Cargar archivo de disponibilidad
    try:
        ruta_disponibilidad = Path(__file__).parent / "config" / "disponibilidad.json"
        with open(ruta_disponibilidad, 'r', encoding='utf-8') as f:
            disponibilidad = json.load(f)
    except FileNotFoundError:
        # Si no existe el archivo, permitir siempre
        return True, "", None
    
    # Si no está habilitado, permitir siempre
    if not disponibilidad.get('habilitado', False):
        return True, "", None
    
    # Configurar zona horaria
    zona = ZoneInfo(disponibilidad.get('zona_horaria', 'America/Bogota'))
    ahora = datetime.now(zona)
    
    # Obtener periodos
    periodos = disponibilidad.get('periodos', [])
    if not periodos:
        return True, "", None
    
    # Buscar si estamos DENTRO de algún periodo
    for periodo in periodos:
        inicio = datetime.strptime(periodo['inicio'], "%Y-%m-%d %H:%M").replace(tzinfo=zona)
        fin = datetime.strptime(periodo['fin'], "%Y-%m-%d %H:%M").replace(tzinfo=zona)
        
        if inicio <= ahora <= fin:
            # ✅ Estamos dentro de un periodo válido
            return True, periodo.get('nombre', 'Examen activo'), periodos
    
    # ❌ NO estamos en ningún periodo - buscar el próximo para informar
    proximos = []
    for periodo in periodos:
        inicio = datetime.strptime(periodo['inicio'], "%Y-%m-%d %H:%M").replace(tzinfo=zona)
        if inicio > ahora:
            proximos.append((inicio, periodo))
    
    if proximos:
        proximos.sort(key=lambda x: x[0])
        proximo = proximos[0][1]
        mensaje = f"Próxima disponibilidad: {proximo.get('nombre', '')} - {proximo['inicio']}"
    else:
        # Todos los periodos ya pasaron
        mensaje = "No hay periodos de disponibilidad programados"
    
    # Siempre retorna False si no estamos dentro de un periodo
    return False, mensaje, periodos

def mostrar_pantalla_inicio(config, ui):
    """Muestra la pantalla de inicio del examen"""
    
    # ============================================
    # VERIFICAR DISPONIBILIDAD SEGÚN CALENDARIO
    # ============================================
    disponible, mensaje, periodos = verificar_disponibilidad(config)
    
    if not disponible:
        st.error("⏰ El examen no está disponible en este momento")
        st.warning(f"📅 {mensaje}")
        
        # Mostrar hora actual
        zona = ZoneInfo("America/Bogota")
        ahora = datetime.now(zona)
        st.info(f"🕐 Hora actual: {ahora.strftime('%d/%m/%Y %H:%M')} (Colombia)")
        
        # Mostrar calendario de disponibilidad
        if periodos:
            st.markdown("### 📆 Calendario de disponibilidad")
            for p in periodos:
                st.write(f"**{p.get('nombre', 'Periodo')}:** {p['inicio']} → {p['fin']}")
        
        # Detener aquí - NO mostrar el formulario de inicio
        return
    
    # Si hay un periodo activo, mostrar mensaje
    if mensaje:
        st.success(f"✅ {mensaje}")
    
    # ============================================
    # PANTALLA DE INICIO NORMAL
    # ============================================
    
    # Mostrar instrucciones
    ui.mostrar_instrucciones()
    
    st.markdown("---")
    
    # Formulario de inicio
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("### 📝 Para comenzar")
        
        codigo = st.text_input(
            "Ingrese su código de estudiante:",
            placeholder="Ejemplo: 12345678",
            max_chars=20,
            key="input_codigo"
        )
        
        col_a, col_b = st.columns(2)
        
        with col_a:
            if st.button("🚀 Comenzar Examen", type="primary", use_container_width=True):
                if not codigo:
                    st.error("⚠️ Por favor ingrese su código de estudiante")
                elif not validate_codigo_estudiante(codigo):
                    st.error("⚠️ Código inválido. Debe contener solo números y letras")
                else:
                    codigo_limpio = codigo.strip().upper()
                    
                    # Verificaciones de seguridad
                    try:
                        persistence = DataPersistence(config)
                        
                        # 1. Verificar si ya completó el examen
                        if persistence.verificar_examen_completado(codigo_limpio):
                            st.error("⚠️ Ya completaste este examen anteriormente.")
                            st.info("💡 Solo se permite un intento por estudiante. Si crees que esto es un error, contacta al profesor.")
                            return
                        
                        # 2. Verificar si tiene un examen en curso
                        if persistence.verificar_examen_en_curso(codigo_limpio):
                            st.error("⚠️ Ya tienes un examen en curso. No puedes iniciar otro hasta terminar el actual.")
                            st.info("💡 Si refrescaste la página por accidente, contacta al profesor.")
                            return
                    except:
                        pass  # Si falla la verificación, permitir continuar
                    
                    st.session_state.codigo_estudiante = codigo_limpio
                    st.session_state.exam_started = True
                    st.rerun()
        
        with col_b:
            if st.button("ℹ️ Más información", use_container_width=True):
                st.info("""
                **Características del examen:**
                - ✅ Preguntas adaptadas a tu nivel
                - ✅ Entre 15 y 30 preguntas
                - ✅ Tiempo sugerido: 1:45 horas
                - ✅ Calificación basada en IRT
                """)

def ejecutar_examen(config, question_manager, ui):
    """Ejecuta la lógica del examen"""
    
    # Inicializar lógica del examen si es necesario
    if 'exam_logic' not in st.session_state:
        st.session_state.exam_logic = ExamLogic(config, question_manager)
        # NUEVO: Guardar inicio del examen
        try:
            persistence = DataPersistence(config)
            persistence.guardar_inicio_examen(st.session_state.codigo_estudiante)
        except:
            pass  # Si falla, continuar igual
    
    exam_logic = st.session_state.exam_logic
    
    # Verificar si el examen debe terminar
    if exam_logic.debe_terminar_examen():
        st.session_state.exam_finished = True
        guardar_resultados(config, exam_logic)
        st.rerun()
        return
    
    # Mostrar métricas
    ui.mostrar_metricas_progreso(
        codigo=st.session_state.codigo_estudiante,
        pregunta_actual=exam_logic.pregunta_actual + 1,
        total_preguntas=config['parametros']['preguntas_maximas'],
        correctas=exam_logic.correctas,
        incorrectas=exam_logic.incorrectas
    )
    
    # Obtener pregunta actual - GUARDAR en session_state para que no cambie
    pregunta_key = f"pregunta_actual_{exam_logic.pregunta_actual}"
    opciones_key = f"opciones_pregunta_{exam_logic.pregunta_actual}"
    
    # Si no existe la pregunta guardada, obtenerla y guardarla
    if pregunta_key not in st.session_state:
        pregunta_obj = exam_logic.obtener_siguiente_pregunta()
        
        if pregunta_obj is None:
            st.session_state.exam_finished = True
            guardar_resultados(config, exam_logic)
            st.rerun()
            return
        
        # Guardar pregunta en session_state
        st.session_state[pregunta_key] = pregunta_obj
        
        # Mezclar y guardar opciones JUNTO con la pregunta
        st.session_state[opciones_key] = exam_logic.mezclar_opciones(pregunta_obj['opciones'])
    
    # Usar pregunta y opciones guardadas (NO cambiarán aunque Streamlit re-ejecute)
    pregunta_obj = st.session_state[pregunta_key]
    opciones_mezcladas = st.session_state[opciones_key]
    
    # Mostrar pregunta
    ui.mostrar_pregunta(
        pregunta_obj,
        numero_pregunta=exam_logic.pregunta_actual + 1
    )
    
    respuesta_seleccionada = st.radio(
        "Seleccione su respuesta:",
        options=list(opciones_mezcladas.keys()),
        format_func=lambda x: f"{x}) {opciones_mezcladas[x]}",
        key=f"respuesta_{exam_logic.pregunta_actual}"
    )
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col2:
        if st.button("✅ Confirmar Respuesta", type="primary", use_container_width=True):
            # Procesar respuesta (sin mostrar feedback)
            exam_logic.procesar_respuesta(
                pregunta_obj,
                respuesta_seleccionada,
                opciones_mezcladas
            )
            
            # IMPORTANTE: Limpiar pregunta Y opciones guardadas para la siguiente
            if pregunta_key in st.session_state:
                del st.session_state[pregunta_key]
            if opciones_key in st.session_state:
                del st.session_state[opciones_key]
            
            # NUEVO: Actualizar progreso en Google Sheets
            try:
                persistence = DataPersistence(config)
                persistence.actualizar_progreso_examen(
                    st.session_state.codigo_estudiante,
                    exam_logic.pregunta_actual,
                    exam_logic.correctas,
                    exam_logic.incorrectas
                )
            except:
                pass  # Si falla, continuar igual
            
            st.rerun()
def guardar_resultados(config, exam_logic):
    """Guarda los resultados del examen en Google Sheets"""
    try:
        # 1. PRIMERO: Calcular estadísticas
        stats = exam_logic.calcular_estadisticas_finales()
        
        # 2. SEGUNDO: Guardar en session_state INMEDIATAMENTE (antes de cualquier st.write)
        st.session_state.final_stats = stats
        
        # 3. TERCERO: Ahora sí guardar en Sheets (con mensajes)
        st.info("🔄 Guardando resultados en Google Sheets...")
        
        persistence = DataPersistence(config)
        resultado = persistence.guardar_resultados(
            codigo_estudiante=st.session_state.codigo_estudiante,
            stats=stats
        )
        
        if resultado:
            st.success("✅ Resultados guardados exitosamente")
        else:
            st.warning("⚠️ Los resultados se muestran pero hubo un problema al guardar en Sheets")
        
    except Exception as e:
        st.error(f"⚠️ Error al guardar en Sheets: {str(e)}")
        # Los resultados se mostrarán igual porque ya están en session_state



def mostrar_resultados(config, ui):
    """Muestra los resultados finales del examen"""
    
    if 'final_stats' not in st.session_state:
        st.error("❌ Error: No se encontraron resultados del examen")
        return
    
    stats = st.session_state.final_stats
    
    # Mostrar resultados
    ui.mostrar_resultados_finales(
        stats=stats,
        codigo=st.session_state.codigo_estudiante
    )
    
    # Botón para reiniciar
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🔄 Realizar otro examen", type="primary", use_container_width=True):
            # Limpiar session state
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


if __name__ == "__main__":
    main()
