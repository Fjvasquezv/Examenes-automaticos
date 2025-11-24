"""
Sistema de Examen Adaptativo Modular
Orquestador Principal
"""
import streamlit as st
import sys
from pathlib import Path

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
                    codigo_limpio = codigo.strip().upper()
                    
                    # NUEVO: Verificar si ya tiene un examen en curso
                    try:
                        persistence = DataPersistence(config)
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
            # Procesar respuesta (sin mostrar feedback)
            exam_logic.procesar_respuesta(
                pregunta_obj,
                respuesta_seleccionada,
                opciones_mezcladas
            )
            
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
        st.info("🔄 Calculando estadísticas finales...")
        
        # Calcular estadísticas finales
        stats = exam_logic.calcular_estadisticas_finales()
        
        st.info(f"✅ Estadísticas calculadas: {len(stats.get('detalle_respuestas', []))} respuestas procesadas")
        st.info("🔄 Guardando en Google Sheets...")
        
        # Intentar guardar en Google Sheets
        persistence = DataPersistence(config)
        resultado = persistence.guardar_resultados(
            codigo_estudiante=st.session_state.codigo_estudiante,
            stats=stats
        )
        
        if not resultado:
            st.error("❌ Error: No se pudieron guardar los resultados en Google Sheets.")
            st.error("Por favor, toma captura de pantalla de esta información:")
            st.json({
                'codigo': st.session_state.codigo_estudiante,
                'preguntas': stats['preguntas_respondidas'],
                'correctas': stats['correctas'],
                'nota': stats['nota_final']
            })
            st.stop()
        
        st.success("✅ Resultados guardados exitosamente en Google Sheets")
        
        # Solo si se guardó exitosamente, guardar en session state
        st.session_state.final_stats = stats
        
    except Exception as e:
        st.error(f"❌ Error crítico al procesar resultados: {str(e)}")
        st.error("El examen no se pudo completar. Por favor, contacta al profesor.")
        import traceback
        st.code(traceback.format_exc())
        st.stop()



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
