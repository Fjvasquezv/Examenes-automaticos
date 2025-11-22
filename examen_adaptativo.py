import streamlit as st
import json
import pandas as pd
from datetime import datetime
import random
import os

# Configuración de la página
st.set_page_config(
    page_title="Examen Adaptativo - Programación",
    page_icon="🎓",
    layout="centered"
)

# Función para cargar preguntas
@st.cache_data
def cargar_preguntas():
    try:
        with open('preguntas.json', 'r', encoding='utf-8') as f:
            preguntas = json.load(f)
            if not isinstance(preguntas, list):
                st.error("❌ Error: El archivo preguntas.json debe contener una lista de preguntas")
                st.stop()
            return preguntas
    except FileNotFoundError:
        st.error("❌ Error: No se encontró el archivo 'preguntas.json'")
        st.info("Asegúrate de que el archivo esté en el mismo directorio que el script")
        st.stop()
    except json.JSONDecodeError as e:
        st.error(f"❌ Error al leer el archivo JSON: {str(e)}")
        st.info("El archivo preguntas.json está mal formateado. Verifica que:")
        st.markdown("""
        - Sea un array JSON válido que comience con `[` y termine con `]`
        - No tenga comas extra al final
        - Todas las comillas estén balanceadas
        - No haya múltiples objetos JSON separados
        """)
        st.stop()
    except Exception as e:
        st.error(f"❌ Error inesperado: {str(e)}")
        st.stop()

# Función para guardar resultados (MEJORADA CON DEBUGGING)
def guardar_resultado(codigo_estudiante, resultados, historial_respuestas):
    """
    Guarda los resultados en CSV incluyendo las preguntas respondidas
    """
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Crear lista de códigos de preguntas respondidas
        preguntas_respondidas = ','.join([r['pregunta_id'] for r in historial_respuestas])
        
        datos = {
            'Fecha': timestamp,
            'Código': codigo_estudiante,
            'Preguntas_Respondidas': resultados['total_preguntas'],
            'Correctas': resultados['correctas'],
            'Incorrectas': resultados['incorrectas'],
            'Nivel_Final': round(resultados['nivel_final'], 2),
            'Nota_Final': round(resultados['nota_final'], 2),
            'Preguntas': preguntas_respondidas
        }
        
        # Guardar en CSV
        archivo = 'resultados_examen.csv'
        df_nuevo = pd.DataFrame([datos])
        
        # Verificar directorio actual
        directorio_actual = os.getcwd()
        ruta_completa = os.path.join(directorio_actual, archivo)
        
        if os.path.exists(archivo):
            df_existente = pd.read_csv(archivo)
            df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
        else:
            df_final = df_nuevo
        
        # Intentar guardar
        df_final.to_csv(archivo, index=False, encoding='utf-8')
        
        # Verificar que se guardó correctamente
        if os.path.exists(archivo):
            tamaño = os.path.getsize(archivo)
            return True, f"✅ Guardado exitoso\n📁 Ruta: {ruta_completa}\n📊 Tamaño: {tamaño} bytes\n📝 Total registros: {len(df_final)}", df_final
        else:
            return False, f"❌ Error: el archivo no se pudo crear en {ruta_completa}", None
            
    except PermissionError:
        return False, f"❌ Error de permisos en: {os.getcwd()}", None
    except Exception as e:
        return False, f"❌ Error al guardar: {type(e).__name__}: {str(e)}", None

# Función para calcular nota estimada
def calcular_nota(nivel_actual, historial_respuestas, usar_promedio_total=False):
    """
    Calcula la nota basándose en el nivel alcanzado y el desempeño
    
    Si usar_promedio_total=True, calcula basándose SOLO en porcentaje de aciertos
    (esto se usa cuando el estudiante llega al máximo sin estabilizar)
    
    Si usar_promedio_total=False (por defecto):
    Nota = (nivel_actual / 5) * 5.0
    Ajuste por desempeño: +/- según porcentaje de aciertos
    """
    if not historial_respuestas:
        return 3.0
    
    # Si llegó al límite sin estabilizar, usar solo promedio total
    if usar_promedio_total:
        total = len(historial_respuestas)
        aciertos = sum(1 for r in historial_respuestas if r['correcta'])
        porcentaje = aciertos / total
        # Convertir a nota: 0% = 0.0, 50% = 2.5, 100% = 5.0
        return porcentaje * 5.0
    
    # Lógica normal cuando se estabilizó
    # Nota base según nivel
    nota_base = (nivel_actual / 5) * 5.0
    
    # Calcular porcentaje de aciertos en las últimas preguntas
    ultimas = historial_respuestas[-min(5, len(historial_respuestas)):]
    aciertos = sum(1 for r in ultimas if r['correcta'])
    porcentaje = aciertos / len(ultimas)
    
    # Ajuste fino según desempeño
    ajuste = (porcentaje - 0.5) * 0.5  # Ajuste de +/- 0.25
    
    nota_final = max(0, min(5.0, nota_base + ajuste))
    return nota_final

# Función para verificar estabilización
def verificar_estabilizacion(historial_notas, umbral=0.15):
    """
    Verifica si la nota se ha estabilizado en las últimas 3 preguntas
    """
    if len(historial_notas) < 4:
        return False
    
    ultimas_3 = historial_notas[-3:]
    variacion = max(ultimas_3) - min(ultimas_3)
    
    return variacion < umbral

# Función para seleccionar pregunta
def seleccionar_pregunta(preguntas, nivel, preguntas_usadas):
    """
    Selecciona una pregunta del nivel especificado que no haya sido usada
    """
    candidatas = [p for p in preguntas if p['dificultad'] == nivel and p['id'] not in preguntas_usadas]
    
    # Si no hay preguntas de ese nivel, buscar en nivel cercano
    if not candidatas:
        for offset in [1, -1, 2, -2]:
            nuevo_nivel = nivel + offset
            if 1 <= nuevo_nivel <= 5:
                candidatas = [p for p in preguntas if p['dificultad'] == nuevo_nivel and p['id'] not in preguntas_usadas]
                if candidatas:
                    break
    
    return random.choice(candidatas) if candidatas else None

# Inicializar estado de la sesión
if 'iniciado' not in st.session_state:
    st.session_state.iniciado = False
    st.session_state.codigo_estudiante = ""
    st.session_state.nivel_actual = 3
    st.session_state.pregunta_actual = None
    st.session_state.historial_respuestas = []
    st.session_state.historial_notas = []
    st.session_state.preguntas_usadas = set()
    st.session_state.finalizado = False
    st.session_state.esperando_respuesta = False
    st.session_state.mostrar_feedback = False
    st.session_state.respuesta_correcta = False
    st.session_state.explicacion = ""
    st.session_state.opciones_mezcladas = []
    st.session_state.pregunta_mezclada_id = None
    st.session_state.usar_promedio_final = False
    st.session_state.resultado_guardado = False
    st.session_state.mensaje_guardado = ""

# Pantalla de inicio
if not st.session_state.iniciado:
    st.title("🎓 Examen Adaptativo de Programación en Python")
    st.write("---")
    
    st.markdown("""
    ### Instrucciones:
    
    - El examen se adapta a tu nivel de conocimiento
    - Si respondes correctamente, las preguntas se vuelven más difíciles
    - Si fallas, las preguntas se vuelven más fáciles
    - El examen termina automáticamente cuando tu nota se estabiliza
    - Mínimo 15 preguntas, máximo 30 preguntas
    - **No puedes regresar a preguntas anteriores**
    - Tómate tu tiempo para leer cada pregunta cuidadosamente
    
    **Temas evaluados:**
    1. Tipos de datos y operadores
    2. Control de flujo y funciones
    3. Estructuras de datos (listas, diccionarios, tuplas)
    4. Manejo de excepciones
    5. Programación Orientada a Objetos (POO)
    """)
    
    st.write("---")
    codigo = st.text_input("Ingresa tu código de estudiante:", max_chars=20)
    
    if st.button("Iniciar Examen", type="primary", use_container_width=True):
        if codigo.strip():
            st.session_state.codigo_estudiante = codigo.strip()
            st.session_state.iniciado = True
            st.session_state.preguntas = cargar_preguntas()
            # Seleccionar primera pregunta
            st.session_state.pregunta_actual = seleccionar_pregunta(
                st.session_state.preguntas, 
                st.session_state.nivel_actual,
                st.session_state.preguntas_usadas
            )
            st.session_state.preguntas_usadas.add(st.session_state.pregunta_actual['id'])
            st.session_state.esperando_respuesta = True
            st.rerun()
        else:
            st.error("Por favor ingresa tu código de estudiante")

# Pantalla de examen
elif st.session_state.iniciado and not st.session_state.finalizado:
    # Header con información
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Estudiante", st.session_state.codigo_estudiante)
    with col2:
        st.metric("Pregunta", f"{len(st.session_state.historial_respuestas) + 1}")
    with col3:
        correctas = sum(1 for r in st.session_state.historial_respuestas if r['correcta'])
        st.metric("Correctas", f"{correctas}/{len(st.session_state.historial_respuestas)}")
    
    st.write("---")
    
    # Mostrar pregunta actual
    if st.session_state.pregunta_actual and st.session_state.esperando_respuesta:
        pregunta = st.session_state.pregunta_actual
        
        # Aleatorizar opciones si no se ha hecho aún para esta pregunta
        if 'opciones_mezcladas' not in st.session_state or st.session_state.pregunta_mezclada_id != pregunta['id']:
            # Crear lista de tuplas (clave, texto)
            opciones_lista = list(pregunta['opciones'].items())
            # Mezclar aleatoriamente
            random.shuffle(opciones_lista)
            # Guardar el orden mezclado
            st.session_state.opciones_mezcladas = opciones_lista
            st.session_state.pregunta_mezclada_id = pregunta['id']
        
        # Mostrar la pregunta
        st.markdown(f"### Pregunta {len(st.session_state.historial_respuestas) + 1}")
        st.markdown(f"**Nivel de dificultad:** {'⭐' * pregunta['dificultad']}")
        st.write(pregunta['pregunta'])
        
        # Mostrar opciones en orden aleatorizado
        respuesta_seleccionada = st.radio(
            "Selecciona tu respuesta:",
            options=[clave for clave, _ in st.session_state.opciones_mezcladas],
            format_func=lambda x: dict(st.session_state.opciones_mezcladas)[x],
            key=f"radio_{pregunta['id']}"
        )
        
        # Botón para confirmar respuesta
        if st.button("Confirmar Respuesta", type="primary", use_container_width=True):
            es_correcta = respuesta_seleccionada == pregunta['respuesta_correcta']
            
            # Registrar respuesta
            st.session_state.historial_respuestas.append({
                'pregunta_id': pregunta['id'],
                'nivel': pregunta['dificultad'],
                'correcta': es_correcta
            })
            
            # Ajustar nivel
            if es_correcta:
                st.session_state.nivel_actual = min(5, st.session_state.nivel_actual + 1)
            else:
                st.session_state.nivel_actual = max(1, st.session_state.nivel_actual - 1)
            
            # Calcular nota actual
            nota_actual = calcular_nota(st.session_state.nivel_actual, st.session_state.historial_respuestas)
            st.session_state.historial_notas.append(nota_actual)
            
            # Preparar feedback
            st.session_state.respuesta_correcta = es_correcta
            st.session_state.explicacion = pregunta.get('explicacion', '')
            st.session_state.esperando_respuesta = False
            st.session_state.mostrar_feedback = True
            st.rerun()
    
    # Mostrar feedback
    elif st.session_state.mostrar_feedback:
        if st.session_state.respuesta_correcta:
            st.success("✅ ¡Respuesta correcta!")
        else:
            st.error("❌ Respuesta incorrecta")
        
        if st.session_state.explicacion:
            with st.expander("📝 Explicación", expanded=True):
                st.write(st.session_state.explicacion)
        
        # Verificar condiciones de finalización
        debe_finalizar = False
        razon_finalizacion = ""
        
        if len(st.session_state.historial_respuestas) >= 30:
            debe_finalizar = True
            # Verificar si se estabilizó antes de llegar al máximo
            if verificar_estabilizacion(st.session_state.historial_notas):
                razon_finalizacion = "Se alcanzó el número máximo de preguntas (30)"
                st.session_state.usar_promedio_final = False
            else:
                razon_finalizacion = "Se alcanzó el número máximo de preguntas sin estabilización"
                st.session_state.usar_promedio_final = True
        elif len(st.session_state.historial_respuestas) >= 15:  # CAMBIADO DE 8 A 15
            if verificar_estabilizacion(st.session_state.historial_notas):
                debe_finalizar = True
                razon_finalizacion = "Tu nota se ha estabilizado"
                st.session_state.usar_promedio_final = False
        
        if debe_finalizar:
            st.info(f"🎯 {razon_finalizacion}")
            if st.button("Ver Resultados Finales", type="primary", use_container_width=True):
                st.session_state.finalizado = True
                st.rerun()
        else:
            if st.button("Siguiente Pregunta ➡️", type="primary", use_container_width=True):
                # Seleccionar siguiente pregunta
                siguiente = seleccionar_pregunta(
                    st.session_state.preguntas,
                    st.session_state.nivel_actual,
                    st.session_state.preguntas_usadas
                )
                
                if siguiente:
                    st.session_state.pregunta_actual = siguiente
                    st.session_state.preguntas_usadas.add(siguiente['id'])
                    st.session_state.esperando_respuesta = True
                    st.session_state.mostrar_feedback = False
                    st.rerun()
                else:
                    st.session_state.finalizado = True
                    st.rerun()

# Pantalla de resultados finales
else:
    st.title("📊 Resultados del Examen")
    st.write("---")
    
    # Calcular estadísticas finales
    total_preguntas = len(st.session_state.historial_respuestas)
    correctas = sum(1 for r in st.session_state.historial_respuestas if r['correcta'])
    incorrectas = total_preguntas - correctas
    nivel_final = st.session_state.nivel_actual
    
    # Calcular nota final según el método apropiado
    if st.session_state.usar_promedio_final:
        # Usar promedio total (cuando llegó a 30 sin estabilizar)
        nota_final = calcular_nota(
            nivel_final,
            st.session_state.historial_respuestas,
            usar_promedio_total=True
        )
        metodo_calculo = "promedio total"
    else:
        # Usar última nota estabilizada
        nota_final = st.session_state.historial_notas[-1] if st.session_state.historial_notas else 0
        metodo_calculo = "nivel alcanzado"
    
    # Guardar resultados (solo una vez)
    if not st.session_state.resultado_guardado:
        resultados = {
            'total_preguntas': total_preguntas,
            'correctas': correctas,
            'incorrectas': incorrectas,
            'nota_final': nota_final,
            'nivel_final': nivel_final
        }
        exito, mensaje, df = guardar_resultado(
            st.session_state.codigo_estudiante, 
            resultados,
            st.session_state.historial_respuestas
        )
        st.session_state.resultado_guardado = True
        st.session_state.mensaje_guardado = mensaje
        
        # MOSTRAR MENSAJE TEMPORAL DE DEBUG (Puedes comentar esto en producción)
        if exito:
            st.success(mensaje)
        else:
            st.error(mensaje)
            # Intentar crear en directorio home del usuario
            try:
                home_dir = os.path.expanduser("~")
                archivo_alt = os.path.join(home_dir, "resultados_examen.csv")
                if df is not None:
                    df.to_csv(archivo_alt, index=False, encoding='utf-8')
                    st.warning(f"Se guardó en ubicación alternativa: {archivo_alt}")
            except:
                st.error("No se pudo guardar en ninguna ubicación")
    
    # Mostrar métricas principales
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Nota Final", f"{nota_final:.2f}")
    with col2:
        st.metric("Nivel Alcanzado", f"{nivel_final}/5")
    with col3:
        st.metric("Correctas", f"{correctas}/{total_preguntas}")
    with col4:
        porcentaje = (correctas / total_preguntas * 100) if total_preguntas > 0 else 0
        st.metric("% Aciertos", f"{porcentaje:.1f}%")
    
    st.write("---")
    
    # Mostrar método de cálculo si fue por promedio
    if st.session_state.usar_promedio_final:
        st.info(f"ℹ️ Nota calculada por {metodo_calculo} de respuestas correctas ({correctas}/{total_preguntas} = {correctas/total_preguntas*100:.1f}%)")
    
    # Análisis de desempeño
    st.subheader("📈 Análisis de Desempeño")
    
    # Gráfico de evolución de nota
    if st.session_state.historial_notas:
        df_notas = pd.DataFrame({
            'Pregunta': range(1, len(st.session_state.historial_notas) + 1),
            'Nota Estimada': st.session_state.historial_notas
        })
        st.line_chart(df_notas.set_index('Pregunta'))
    
    # Desempeño por nivel
    st.subheader("📊 Desempeño por Nivel de Dificultad")
    niveles_data = {}
    for respuesta in st.session_state.historial_respuestas:
        nivel = respuesta['nivel']
        if nivel not in niveles_data:
            niveles_data[nivel] = {'total': 0, 'correctas': 0}
        niveles_data[nivel]['total'] += 1
        if respuesta['correcta']:
            niveles_data[nivel]['correctas'] += 1
    
    for nivel in sorted(niveles_data.keys()):
        data = niveles_data[nivel]
        porcentaje = (data['correctas'] / data['total'] * 100) if data['total'] > 0 else 0
        st.write(f"**Nivel {nivel}:** {data['correctas']}/{data['total']} correctas ({porcentaje:.0f}%)")
    
    st.write("---")
    
    # Mensaje final
    if nota_final >= 4.5:
        st.success("🎉 ¡Excelente desempeño! Dominas muy bien los conceptos de programación.")
    elif nota_final >= 3.5:
        st.success("✅ ¡Buen trabajo! Tienes una base sólida en programación.")
    elif nota_final >= 3.0:
        st.info("📚 Aprobado. Te recomiendo repasar algunos conceptos para mejorar tu dominio.")
    else:
        st.warning("📖 Te sugerimos dedicar más tiempo a practicar y repasar los conceptos fundamentales.")
    
    st.info("✅ Tus resultados han sido guardados automáticamente.")
    
    if st.button("Cerrar", type="primary"):
        st.balloons()
