"""
Sistema de Examen Adaptativo Modular
Orquestador Principal
"""
import streamlit as st
import sys
import os

# Agregar directorios al path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, 'src'))
sys.path.append(os.path.join(current_dir, 'utils'))

# Importaciones normales
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
    if 'show_feedback' not in st.session_state:
        st.session_state.show_feedback = False
    if 'last_answer_correct' not in st.session_state:
        st.session_state.last_answer_correct = None
    if 'ultima_explicacion' not in st.session_state:
        st.session_state.ultima_explicacion = None


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


def mostrar_pantalla_inicio(config, ui):
    """Muestra la pantalla de inicio del examen"""
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
                    st.session_state.codigo_estudiante = codigo.strip().upper()
                    st.session_state.exam_started = True
                    st.rerun()
        
        with col_b:
            if st.button("ℹ️ Más información", use_container_width=True):
                st.info("""
                **Características del examen:**
                - ✅ Preguntas adaptadas a tu nivel
                - ✅ Feedback inmediato
                - ✅ Entre 15 y 30 preguntas
                - ✅ Tiempo ilimitado
                - ✅ Calificación basada en IRT
                """)


def ejecutar_examen(config, question_manager, ui):
    """Ejecuta la lógica del examen"""
    
    # Inicializar lógica del examen si es necesario
    if 'exam_logic' not in st.session_state:
        st.session_state.exam_logic = ExamLogic(config, question_manager)
    
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
    
    # Mostrar feedback de la pregunta anterior si existe
    if st.session_state.show_feedback:
        if st.session_state.last_answer_correct:
            st.success("✅ ¡Respuesta correcta!")
        else:
            st.error("❌ Respuesta incorrecta")
        
        if st.session_state.ultima_explicacion:
            with st.expander("💡 Explicación", expanded=True):
                st.info(st.session_state.ultima_explicacion)
        
        st.markdown("---")
    
    # Obtener pregunta actual
    pregunta_obj = exam_logic.obtener_siguiente_pregunta()
    
    if pregunta_obj is None:
        st.session_state.exam_finished = True
        guardar_resultados(config, exam_logic)
        st.rerun()
        return
    
    # Mostrar pregunta
    ui.mostrar_pregunta(
        pregunta_obj,
        numero_pregunta=exam_logic.pregunta_actual + 1
    )
    
    # Opciones de respuesta (aleatorizadas)
    opciones_mezcladas = exam_logic.mezclar_opciones(pregunta_obj['opciones'])
    
    respuesta_seleccionada = st.radio(
        "Seleccione su respuesta:",
        options=list(opciones_mezcladas.keys()),
        format_func=lambda x: f"{x}) {opciones_mezcladas[x]}",
        key=f"respuesta_{exam_logic.pregunta_actual}"
    )
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col2:
        if st.button("✅ Confirmar Respuesta", type="primary", use_container_width=True):
            # Procesar respuesta
            es_correcta = exam_logic.procesar_respuesta(
                pregunta_obj,
                respuesta_seleccionada,
                opciones_mezcladas
            )
            
            # Guardar feedback
            st.session_state.show_feedback = True
            st.session_state.last_answer_correct = es_correcta
            st.session_state.ultima_explicacion = pregunta_obj.get('explicacion', '')
            
            st.rerun()


def guardar_resultados(config, exam_logic):
    """Guarda los resultados del examen en Google Sheets"""
    try:
        # Calcular estadísticas finales
        stats = exam_logic.calcular_estadisticas_finales()
        
        # Guardar en Google Sheets
        persistence = DataPersistence(config)
        persistence.guardar_resultados(
            codigo_estudiante=st.session_state.codigo_estudiante,
            stats=stats
        )
        
        # Guardar stats en session state para mostrar
        st.session_state.final_stats = stats
        
    except Exception as e:
        st.error(f"⚠️ Error al guardar resultados: {str(e)}")
        # Guardar stats localmente aunque falle el guardado
        st.session_state.final_stats = exam_logic.calcular_estadisticas_finales()


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
