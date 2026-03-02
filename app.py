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
import unicodedata

# Agregar AMBOS directorios al path
base = Path(__file__).parent
sys.path.insert(0, str(base / "src"))
sys.path.insert(0, str(base / "utils"))

# Importar SIN prefijos
from config_loader import ConfigLoader
from question_manager import QuestionManager
from exam_logic import ExamLogic
from ui_components import UIComponents
from src.data_persistence import DataPersistence
from validators import validate_codigo_estudiante


def _serializar_estado_exam_logic(exam_logic) -> str:
    """Serializa el estado mínimo necesario para restaurar un examen en curso."""
    respuestas_minimas = []
    for r in exam_logic.preguntas_respondidas:
        respuestas_minimas.append({
            'pregunta_id': r.get('pregunta_id', ''),
            'dificultad': r.get('dificultad', 3),
            'categoria': r.get('categoria', 'Sin categoría'),
            'correcta': bool(r.get('correcta', False)),
            'nivel_en_pregunta': r.get('nivel_en_pregunta', 3)
        })

    payload = {
        'pregunta_actual': exam_logic.pregunta_actual,
        'nivel_actual': exam_logic.nivel_actual,
        'theta_actual': exam_logic.theta_actual,
        'correctas': exam_logic.correctas,
        'incorrectas': exam_logic.incorrectas,
        'preguntas_usadas': list(exam_logic.preguntas_usadas),
        'historial_notas': list(exam_logic.historial_notas),
        'categorias_evaluadas': list(exam_logic.categorias_evaluadas),
        'preguntas_respondidas': respuestas_minimas,
    }
    return json.dumps(payload, ensure_ascii=False)


def _restaurar_estado_exam_logic(exam_logic, progreso: dict) -> bool:
    """Restaura el estado de exam_logic desde una fila EN_CURSO de Sheets."""
    try:
        estado_json = progreso.get('Estado_JSON', '')

        if estado_json:
            estado = json.loads(estado_json)
            exam_logic.pregunta_actual = int(estado.get('pregunta_actual', 0))
            exam_logic.nivel_actual = max(1, min(5, int(estado.get('nivel_actual', exam_logic.nivel_actual))))
            exam_logic.theta_actual = float(estado.get('theta_actual', exam_logic.theta_actual))
            exam_logic.correctas = int(estado.get('correctas', 0))
            exam_logic.incorrectas = int(estado.get('incorrectas', 0))
            exam_logic.preguntas_usadas = list(estado.get('preguntas_usadas', []))
            exam_logic.preguntas_usadas_set = set(exam_logic.preguntas_usadas)
            exam_logic.historial_notas = list(estado.get('historial_notas', []))
            exam_logic.categorias_evaluadas = set(estado.get('categorias_evaluadas', []))
            exam_logic.preguntas_respondidas = list(estado.get('preguntas_respondidas', []))
            return True

        exam_logic.pregunta_actual = int(progreso.get('Preguntas_Respondidas', 0) or 0)
        exam_logic.correctas = int(progreso.get('Correctas', 0) or 0)
        exam_logic.incorrectas = int(progreso.get('Incorrectas', 0) or 0)
        exam_logic.nivel_actual = max(1, min(5, int(progreso.get('Nivel_Final', exam_logic.nivel_actual) or exam_logic.nivel_actual)))
        theta_val = progreso.get('Theta_IRT', '')
        if theta_val not in ('', None):
            exam_logic.theta_actual = float(theta_val)

        preguntas_ids = progreso.get('Preguntas_IDs', '')
        exam_logic.preguntas_usadas = [p.strip() for p in preguntas_ids.split(',') if p.strip()]
        exam_logic.preguntas_usadas_set = set(exam_logic.preguntas_usadas)

        nota = progreso.get('Nota_Final', '')
        if nota not in ('', None):
            exam_logic.historial_notas = [float(nota)]

        return True
    except Exception:
        return False


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
        page_title="Sistema de Exámenes - ECCI",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    # Reducir espacio superior de Streamlit
    st.markdown("""
    <style>
        .block-container {
            padding-top: 1rem;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Inicializar session state
    inicializar_session_state()
    
    # ============================================
    # VERIFICAR DISPONIBILIDAD Y OBTENER EXAMEN
    # ============================================
    disponible, config, mensaje, periodos = verificar_disponibilidad()
    
    if not disponible:
        # Mostrar pantalla de "no disponible"
        st.title("🎓 Sistema de Exámenes")
        st.error("⏰ No hay exámenes disponibles en este momento")
        st.warning(f"📅 {mensaje}")
        
        # Mostrar hora actual
        zona = ZoneInfo("America/Bogota")
        ahora = datetime.now(zona)
        st.info(f"🕐 Hora actual: {ahora.strftime('%d/%m/%Y %H:%M')} (Colombia)")
        
        # Mostrar calendario
        if periodos:
            st.markdown("### 📆 Próximos exámenes programados")
            for p in periodos:
                inicio = datetime.strptime(p['inicio'], "%Y-%m-%d %H:%M")
                if inicio > ahora.replace(tzinfo=None):
                    st.write(f"📝 **{p.get('nombre', 'Examen')}:** {p['inicio']} → {p['fin']}")
        return
    
    # ============================================
    # EXAMEN DISPONIBLE - CONTINUAR NORMALMENTE
    # ============================================
    try:
        # Cargar banco(s) de preguntas (multi-banco o legacy)
        base_path = Path(__file__).parent
        if 'bancos_preguntas' in config:
            question_manager = QuestionManager(
                bancos_preguntas=config['bancos_preguntas'],
                base_path=base_path
            )
        else:
            question_manager = QuestionManager(
                preguntas_file=config['archivo_preguntas'],
                base_path=base_path
            )
        
        # Inicializar componentes
        ui = UIComponents(config)
        
        # Verificar que hay suficientes preguntas
        total_preguntas = len(question_manager.preguntas)
        if total_preguntas < config['parametros']['preguntas_minimas']:
            st.error(f"⚠️ Error: El banco tiene {total_preguntas} preguntas, "
                    f"se necesitan al menos {config['parametros']['preguntas_minimas']}")
            return
        
        # Mostrar header con nombre del examen
        ui.mostrar_header(periodo_activo=mensaje)
        
        # Flujo principal
        if not st.session_state.exam_started:
            mostrar_pantalla_inicio(config, ui)
        elif st.session_state.exam_finished:
            mostrar_resultados(config, ui)
        else:
            ejecutar_examen(config, question_manager, ui)
            
    except FileNotFoundError as e:
        st.error(f"❌ Error: No se encontró archivo.\n{str(e)}")
    except Exception as e:
        st.error(f"❌ Error inesperado: {str(e)}")
        st.exception(e)

def verificar_disponibilidad():
    """
    Verifica qué examen está disponible según el calendario.
    Retorna: (disponible, examen_config, mensaje, periodos)
    """
    # Cargar archivo de disponibilidad
    try:
        ruta_disponibilidad = Path(__file__).parent / "config" / "disponibilidad.json"
        with open(ruta_disponibilidad, 'r', encoding='utf-8') as f:
            disponibilidad = json.load(f)
    except FileNotFoundError:
        return False, None, "No se encontró archivo de disponibilidad", None
    
    # Si no está habilitado, no hay exámenes disponibles
    if not disponibilidad.get('habilitado', False):
        return False, None, "Sistema de exámenes deshabilitado", None
    
    # Configurar zona horaria
    zona = ZoneInfo(disponibilidad.get('zona_horaria', 'America/Bogota'))
    ahora = datetime.now(zona)
    
    periodos = disponibilidad.get('periodos', [])
    if not periodos:
        return False, None, "No hay periodos configurados", None
    
    # Buscar si estamos DENTRO de algún periodo
    for periodo in periodos:
        inicio = datetime.strptime(periodo['inicio'], "%Y-%m-%d %H:%M").replace(tzinfo=zona)
        fin = datetime.strptime(periodo['fin'], "%Y-%m-%d %H:%M").replace(tzinfo=zona)
        
        if inicio <= ahora <= fin:
            # ✅ Estamos dentro de un periodo válido - cargar config del examen
            examen_id = periodo.get('examen', '')
            examen_slug = unicodedata.normalize('NFKD', examen_id).encode('ascii', 'ignore').decode('ascii').lower()
            ruta_examen = Path(__file__).parent / "config" / "examenes" / f"{examen_slug}.json"
            
            try:
                with open(ruta_examen, 'r', encoding='utf-8') as f:
                    config_examen = json.load(f)
                
                # Validar configuración del examen
                loader = ConfigLoader(base_path=Path(__file__).parent)
                loader.validar_config_dict(config_examen)
                
                config_examen['_examen_id'] = examen_slug  # Guardar ID para referencia
                
                # Cargar instrucciones desde archivo separado
                ruta_instrucciones = Path(__file__).parent / "config" / "instrucciones.json"
                try:
                    with open(ruta_instrucciones, 'r', encoding='utf-8') as f2:
                        instrucciones = json.load(f2)
                except FileNotFoundError:
                    instrucciones = {"titulo": "Instrucciones", "items": [], "advertencias": []}
                
                # Combinar con descripción del examen
                config_examen['instrucciones'] = instrucciones
                config_examen['instrucciones']['descripcion'] = config_examen.get('descripcion', {})
                return True, config_examen, periodo.get('nombre', 'Examen activo'), periodos
            except FileNotFoundError as e:
                return False, None, f"Error en examen '{examen_id}': {str(e)}", periodos
            except ValueError as e:
                return False, None, f"Configuración inválida para '{examen_id}': {str(e)}", periodos
    
    # ❌ NO estamos en ningún periodo - buscar el próximo
    proximos = []
    for periodo in periodos:
        inicio = datetime.strptime(periodo['inicio'], "%Y-%m-%d %H:%M").replace(tzinfo=zona)
        if inicio > ahora:
            proximos.append((inicio, periodo))
    
    if proximos:
        proximos.sort(key=lambda x: x[0])
        proximo = proximos[0][1]
        mensaje = f"Próximo examen: {proximo.get('nombre', '')} - {proximo['inicio']}"
    else:
        mensaje = "No hay exámenes programados"
    
    return False, None, mensaje, periodos


def mostrar_pantalla_inicio(config, ui):
    """Muestra la pantalla de inicio del examen"""
    
    # Mostrar instrucciones
    ui.mostrar_instrucciones()
    
    st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
    st.markdown("##### 📝 Comencemos por tú código (ARCA)")

    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        codigo = st.text_input(
            "Código de estudiante:",
            placeholder="Ejemplo: 12345678",
            max_chars=20,
            key="input_codigo",
            label_visibility="collapsed"
        )
    
    with col2:
        if st.button("🚀 Comenzar Examen", type="primary", use_container_width=True):
            if not codigo:
                st.error("⚠️ Por favor ingrese su código de estudiante")
            elif not validate_codigo_estudiante(codigo):
                st.error("⚠️ Código inválido. Debe contener solo números y letras")
            else:
                codigo_limpio = codigo.strip().upper()
                
                try:
                    persistence = DataPersistence(config)
                    if persistence.verificar_examen_completado(codigo_limpio):
                        st.error("⚠️ Ya completaste este examen anteriormente.")
                        st.info("💡 Solo se permite un intento por estudiante.")
                        return
                    progreso = persistence.obtener_progreso_en_curso(codigo_limpio)
                    if progreso:
                        autorizado = str(progreso.get('Autorizado_Continuar', 'NO')).strip().upper() in ('SI', 'SÍ', 'YES', 'TRUE', '1')
                        if not autorizado:
                            st.error("🔒 Tienes un examen en curso bloqueado para reanudación.")
                            st.info("🧑‍🏫 Solicita autorización docente. En Google Sheets, cambia la columna 'Autorizado_Continuar' a 'SI' en tu fila EN_CURSO.")
                            return

                        st.info("🔄 Se detectó un examen en curso autorizado. Restaurando progreso...")
                        st.session_state.codigo_estudiante = codigo_limpio
                        st.session_state.exam_started = True
                        st.session_state.exam_finished = False
                        st.session_state.current_question_index = int(progreso.get('Preguntas_Respondidas', 0) or 0)
                        st.session_state.respuestas = []
                        st.session_state.notas_historicas = []
                        st.session_state.preguntas_usadas = progreso.get('Preguntas_IDs', '').split(',') if progreso.get('Preguntas_IDs') else []
                        st.session_state.progreso_a_restaurar = progreso
                        st.rerun()
                        return
                except Exception as e:
                    st.warning(f"⚠️ Error al verificar progreso: {e}")
                st.session_state.codigo_estudiante = codigo_limpio
                st.session_state.exam_started = True
                st.rerun()
    
    with col3:
        with st.expander("ℹ️ Más información"):
            st.write(f"""
            **{config['metadata']['asignatura']}**
            - ✅ Preguntas adaptadas a tu nivel
            - ✅ Entre {config['parametros']['preguntas_minimas']} y {config['parametros']['preguntas_maximas']} preguntas
            - ✅ Calificación basada en IRT
            """)

def ejecutar_examen(config, question_manager, ui):
    """Ejecuta la lógica del examen"""
    
    # Inicializar lógica del examen si es necesario
    if 'exam_logic' not in st.session_state:
        st.session_state.exam_logic = ExamLogic(config, question_manager)
        progreso = st.session_state.pop('progreso_a_restaurar', None)

        if progreso:
            restaurado = _restaurar_estado_exam_logic(st.session_state.exam_logic, progreso)
            if not restaurado:
                st.warning("⚠️ No se pudo restaurar completamente el estado. Se continuará con estado parcial.")
        else:
            try:
                persistence = DataPersistence(config)
                persistence.guardar_inicio_examen(st.session_state.codigo_estudiante)
            except Exception as e:
                st.warning(f"⚠️ No se pudo guardar el inicio del examen: {e}")
    
    exam_logic = st.session_state.exam_logic
    
    # Verificar si el examen debe terminar
    if exam_logic.debe_terminar_examen():
        st.session_state.exam_finished = True
        guardar_resultados(config, exam_logic)
        st.rerun()
        return
    
    # Mostrar métricas de progreso
    ui.mostrar_metricas_progreso(
        codigo=st.session_state.codigo_estudiante,
        pregunta_actual=exam_logic.pregunta_actual + 1,
        total_preguntas=config['parametros']['preguntas_maximas'],
        correctas=exam_logic.correctas,
        incorrectas=exam_logic.incorrectas
    )
    
    # Obtener pregunta actual
    pregunta_key = f"pregunta_actual_{exam_logic.pregunta_actual}"
    opciones_key = f"opciones_pregunta_{exam_logic.pregunta_actual}"
    
    if pregunta_key not in st.session_state:
        pregunta_obj = exam_logic.obtener_siguiente_pregunta()
        
        if pregunta_obj is None:
            st.session_state.exam_finished = True
            guardar_resultados(config, exam_logic)
            st.rerun()
            return
        
        st.session_state[pregunta_key] = pregunta_obj
        st.session_state[opciones_key] = exam_logic.mezclar_opciones(pregunta_obj['opciones'])
    
    pregunta_obj = st.session_state[pregunta_key]
    opciones_mezcladas = st.session_state[opciones_key]
    
    # Layout dos columnas
    col_pregunta, col_opciones = st.columns([3, 2])
    
    with col_pregunta:
        dificultad = pregunta_obj['dificultad']
        color = ui._get_dificultad_color(dificultad)
        categoria = pregunta_obj.get('categoria', '')
        categoria_html = f"<span style='color: #6c757d;'>📂 {categoria}</span>" if categoria else ""
        
        # Header de la tarjeta
        html_header = f"<div style='background-color: #ffffff; border: 1px solid #dee2e6; border-radius: 8px 8px 0 0; overflow: hidden;'><div style='background-color: #f8f9fa; padding: 10px 15px; border-bottom: 1px solid #dee2e6; display: flex; justify-content: space-between; align-items: center;'><span style='font-weight: bold;'>Pregunta {exam_logic.pregunta_actual + 1}</span><div>{categoria_html}<span style='background-color: {color}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px; margin-left: 10px;'>Nivel {dificultad}</span></div></div></div>"
        st.markdown(html_header, unsafe_allow_html=True)
        
        # Contenido de la pregunta (separado para que el código se renderice bien)
        st.markdown(pregunta_obj['pregunta'])
    
    with col_opciones:
        html_header = "<div style='background-color: #f8f9fa; padding: 8px 15px; border: 1px solid #dee2e6; border-radius: 8px 8px 0 0; border-bottom: none;'><span style='font-weight: bold; color: #495057;'>Seleccione su respuesta:</span></div>"
        st.markdown(html_header, unsafe_allow_html=True)
        
        respuesta_seleccionada = st.radio(
            "Respuesta:",
            options=list(opciones_mezcladas.keys()),
            format_func=lambda x: f"{x}) {opciones_mezcladas[x]}",
            key=f"respuesta_{exam_logic.pregunta_actual}",
            label_visibility="collapsed"
        )
        
        if st.button("🚀 Confirmar Respuesta", type="primary", use_container_width=True):
            exam_logic.procesar_respuesta(
                pregunta_obj,
                respuesta_seleccionada,
                opciones_mezcladas
            )
            
            if pregunta_key in st.session_state:
                del st.session_state[pregunta_key]
            if opciones_key in st.session_state:
                del st.session_state[opciones_key]
            
            try:
                persistence = DataPersistence(config)
                persistence.actualizar_progreso_examen(
                    st.session_state.codigo_estudiante,
                    exam_logic.pregunta_actual,
                    exam_logic.correctas,
                    exam_logic.incorrectas,
                    nivel_actual=exam_logic.nivel_actual,
                    nota_actual=exam_logic.historial_notas[-1] if exam_logic.historial_notas else 0.0,
                    preguntas_ids=exam_logic.preguntas_usadas,
                    theta_actual=exam_logic.theta_actual,
                    estado_json=_serializar_estado_exam_logic(exam_logic)
                )
            except:
                pass
            
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
