"""
Componentes de Interfaz de Usuario
Maneja todos los elementos visuales con Streamlit
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, Any, List

class UIComponents:
    """Clase para manejar componentes de UI con Streamlit"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Inicializa los componentes de UI
        
        Args:
            config: Configuración del examen
        """
        self.config = config
        self.metadata = config['metadata']
        self.instrucciones = config['instrucciones']
    
    def mostrar_header(self, periodo_activo=None):
        """Muestra el header del examen - Estilo institucional ECCI"""
        periodo_html = ""
        if periodo_activo:
            periodo_html = f"""<span style='color: #003366; font-size: 12px;'>{periodo_activo}</span>"""
        
        st.markdown(f"""
        <div style='background-color: #FFB81C;
             padding: 30px 15px 8px 20px;
             border-bottom: 8px solid #003366;
             margin-bottom: 2px;
             display: flex; justify-content: space-between;'>
            <div style='display: flex; flex-direction: column; justify-content: center;'>
                <span style='color: #003366; font-weight: bold; font-size: 15px; line-height: 1.2;'>
                    {self.metadata['institucion']}
                </span>
                <span style='color: #003366; font-weight: bold; font-size: 12px; line-height: 1.2;'>
                    Facultad de Ingeniería
                </span>
                <span style='color: #003366; font-weight: bold; font-size: 12px; line-height: 1.2;'>
                    Ingeniería Química
                </span>
            </div>
            <div style='display: flex; flex-direction: column; justify-content: center; text-align: center;'>
                <span style='color: #003366; font-weight: bold; font-size: 18px;'>
                    {self.metadata['asignatura']}
                </span>
                {f"<span style='color: #003366; font-weight: bold; font-size: 12px;'>{periodo_activo}</span>" if periodo_activo else ""}
            </div>
            <div style='display: flex; flex-direction: column; justify-content: center; text-align: right;'>
                <span style='color: #003366; font-weight: bold; font-size: 11px;'>
                    Docente
                </span>
                <span style='color: #003366; font-weight: bold; font-size: 13px;'>
                    Prof. Francisco Javier Vásquez V.
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    def mostrar_instrucciones(self):
        """Muestra las instrucciones del examen en dos columnas"""
        instrucciones = self.config.get('instrucciones', {})
        descripcion = self.config.get('descripcion', {})
        
        col1, col2 = st.columns(2)
        
        # Columna izquierda: Descripción del examen
        with col1:
            st.markdown("**📚 Sobre este examen**")
            
            texto = descripcion.get('texto', '')
            if texto:
                st.write(texto)
            
            temas = descripcion.get('temas', [])
            if temas:
                st.markdown("**Temas evaluados:**")
                temas_html = "".join([f"<li>{tema}</li>" for tema in temas])
                st.markdown(f"""
                <ul style='margin: 0; padding-left: 20px; line-height: 1.4;'>
                    {temas_html}
                </ul>
                """, unsafe_allow_html=True)
            
            duracion = descripcion.get('duracion_estimada', '')
            if duracion:
                st.info(f"⏱️ Duración estimada: {duracion}")
        
        # Columna derecha: Instrucciones generales
        with col2:
            titulo = instrucciones.get('titulo', 'Instrucciones')
            st.markdown(f"**📋 {titulo}**")
            
            items = instrucciones.get('items', [])
            if items:
                items_html = "".join([f"<li>✅ {item}</li>" for item in items])
                st.markdown(f"""
                <ul style='margin: 0; padding-left: 20px; line-height: 1.4; list-style: none;'>
                    {items_html}
                </ul>
                """, unsafe_allow_html=True)
            
            advertencias = instrucciones.get('advertencias', [])
            if advertencias:
                adv_html = "".join([f"<li>{adv}</li>" for adv in advertencias])
                st.markdown(f"""
                <div style='background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 10px 15px; border-radius: 4px;'>
                    <strong>⚠️ Advertencias:</strong>
                    <ul style='margin: 5px 0 0 0; padding-left: 20px; line-height: 1.4;'>
                        {adv_html}
                    </ul>
                </div>
                """, unsafe_allow_html=True)
                
    def mostrar_metricas_progreso(
        self,
        codigo: str,
        pregunta_actual: int,
        total_preguntas: int,
        correctas: int,
        incorrectas: int
    ):
        """Muestra métricas de progreso en una barra compacta"""
        total_respondidas = correctas + incorrectas
        porcentaje = (correctas / total_respondidas * 100) if total_respondidas > 0 else 0
        progreso = (pregunta_actual / total_preguntas) * 100
        
        st.markdown(f"""
        <div style='background-color: #f8f9fa; padding: 10px 20px; border-radius: 8px; 
             margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center;
             border: 1px solid #dee2e6;'>
            <span>👤 <strong>{codigo}</strong></span>
            <span>📝 {pregunta_actual}/{total_preguntas}</span>
            <span>✅ {correctas}</span>
            <span>❌ {incorrectas}</span>
            <span>📊 {porcentaje:.0f}%</span>
            <div style='width: 100px; background-color: #e9ecef; border-radius: 4px; height: 8px;'>
                <div style='width: {progreso}%; background-color: #003366; border-radius: 4px; height: 8px;'></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    def mostrar_pregunta(self, pregunta: Dict[str, Any], numero_pregunta: int):
        """Muestra una pregunta en formato tarjeta compacta"""
        dificultad = pregunta['dificultad']
        color = self._get_dificultad_color(dificultad)
        categoria = pregunta.get('categoria', '')
        
        categoria_html = f"<span style='color: #6c757d; margin-right: 15px;'>📂 {categoria}</span>" if categoria else ""
        
        st.markdown(f"""
        <div style='background-color: #ffffff; border: 1px solid #dee2e6; border-radius: 8px; 
             overflow: hidden; margin-bottom: 15px;'>
            <div style='background-color: #f8f9fa; padding: 10px 15px; border-bottom: 1px solid #dee2e6;
                 display: flex; justify-content: space-between; align-items: center;'>
                <span style='font-weight: bold; font-size: 16px;'>Pregunta {numero_pregunta}</span>
                <div>
                    {categoria_html}
                    <span style='background-color: {color}; color: white; padding: 3px 12px; 
                          border-radius: 12px; font-size: 12px;'>Nivel {dificultad}</span>
                </div>
            </div>
            <div style='padding: 20px;'>
                {pregunta['pregunta']}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    def _get_dificultad_color(self, dificultad: int) -> str:
        """Retorna el color según el nivel de dificultad"""
        colores = {
            1: "#dc3545",  # Rojo (básico)
            2: "#ff8c00",  # Naranja
            3: "#ffc107",  # Amarillo (intermedio)
            4: "#90ee90",  # Verde claro
            5: "#28a745"   # Verde (avanzado)
        }
        return colores.get(dificultad, "#9E9E9E")
    
    def mostrar_resultados_finales(self, stats: Dict[str, Any], codigo: str):
        """Muestra los resultados finales del examen"""
        st.balloons()
        
        nota_final = stats['nota_final']
        color_nota = self._get_color_nota(nota_final)
        porcentaje = stats['porcentaje_correctas']
        
        # Header compacto con nota y métricas
        header_html = f"""
        <div style='background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 10px; padding: 20px; margin-bottom: 20px;'>
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <div>
                    <h2 style='margin: 0; color: #333;'>🎉 ¡Examen Completado!</h2>
                    <p style='margin: 5px 0 0 0; color: #666;'>👤 Estudiante: <strong>{codigo}</strong></p>
                </div>
                <div style='display: flex; align-items: center; gap: 30px;'>
                    <div style='text-align: center;'>
                        <div style='background-color: {color_nota}; color: white; font-size: 36px; font-weight: bold; width: 80px; height: 80px; border-radius: 50%; display: flex; align-items: center; justify-content: center;'>{nota_final}</div>
                        <span style='font-size: 12px; color: #666;'>Nota Final</span>
                    </div>
                    <div style='text-align: left; font-size: 14px; color: #555;'>
                        <div>📝 {stats['preguntas_respondidas']} preguntas</div>
                        <div>✅ {stats['correctas']} correctas ({porcentaje:.0f}%)</div>
                        <div>❌ {stats['incorrectas']} incorrectas</div>
                        <div>🎯 Nivel final: {stats['nivel_final']}</div>
                    </div>
                </div>
            </div>
        </div>
        """
        st.markdown(header_html, unsafe_allow_html=True)
        
        # Tabs para organizar contenido
        tab1, tab2, tab3, tab4 = st.tabs(["📈 Evolución", "📝 Retroalimentación", "📊 Análisis", "ℹ️ Detalles"])
        
        with tab1:
            self._mostrar_grafico_evolucion(stats['historial_notas'])
        
        with tab2:
            if 'detalle_respuestas' in stats and stats['detalle_respuestas']:
                for i, detalle in enumerate(stats['detalle_respuestas'], 1):
                    estado = "✅" if detalle['correcta'] else "❌"
                    
                    with st.expander(f"{estado} Pregunta {i} - {detalle['categoria']} (Nivel {detalle['dificultad']})"):
                        st.markdown(f"**{detalle['pregunta']}**")
                        
                        if detalle['correcta']:
                            st.success("Tu respuesta fue correcta")
                        else:
                            st.error(f"Respuesta correcta: {detalle['respuesta_correcta']}")
                        
                        st.info(f"💡 {detalle['explicacion']}")
            else:
                st.info("No hay retroalimentación disponible")
        
        with tab3:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 🎯 Por Nivel de Dificultad")
                self._mostrar_tabla_niveles(stats['stats_por_nivel'])
            
            with col2:
                st.markdown("#### 📂 Por Categoría")
                if stats['stats_por_categoria']:
                    self._mostrar_tabla_categorias(stats['stats_por_categoria'])
                else:
                    st.info("No hay datos por categoría")
        
        with tab4:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 📋 Información del Examen")
                st.write(f"**Razón de terminación:** {stats['razon_terminacion']}")
                st.write(f"**Sistema de calificación:** {self.config['sistema_calificacion']['tipo']}")
            
            with col2:
                st.markdown("#### 🔢 Estadísticas del Sistema")
                self._mostrar_stats_sistema_compacto(stats['stats_sistema'])

    def _mostrar_tabla_niveles(self, stats_por_nivel: Dict[int, Dict[str, Any]]):
        """Muestra tabla compacta de rendimiento por nivel"""
        datos = []
        for nivel in range(1, 6):
            if nivel in stats_por_nivel and stats_por_nivel[nivel]['total'] > 0:
                datos.append({
                    'Nivel': f"Nivel {nivel}",
                    'Total': stats_por_nivel[nivel]['total'],
                    '✅': stats_por_nivel[nivel]['correctas'],
                    '❌': stats_por_nivel[nivel]['incorrectas'],
                    '%': f"{stats_por_nivel[nivel]['porcentaje']:.0f}%"
                })
        
        if datos:
            st.dataframe(pd.DataFrame(datos), hide_index=True, use_container_width=True)
        else:
            st.info("No hay datos disponibles")

    def _mostrar_tabla_categorias(self, stats_por_categoria: Dict[str, Dict[str, Any]]):
        """Muestra tabla compacta de rendimiento por categoría"""
        datos = []
        for cat, stats in stats_por_categoria.items():
            if stats['total'] > 0:
                datos.append({
                    'Categoría': cat,
                    'Total': stats['total'],
                    '✅': stats['correctas'],
                    '❌': stats['incorrectas'],
                    '%': f"{stats['porcentaje']:.0f}%"
                })
        
        if datos:
            st.dataframe(pd.DataFrame(datos), hide_index=True, use_container_width=True)
        else:
            st.info("No hay datos disponibles")

    def _mostrar_stats_sistema_compacto(self, stats_sistema: Dict[str, Any]):
        """Muestra estadísticas del sistema de forma compacta"""
        for key, value in stats_sistema.items():
            if isinstance(value, float):
                st.write(f"**{key}:** {value:.3f}")
            else:
                st.write(f"**{key}:** {value}")
    
    def _get_color_nota(self, nota: float) -> str:
        """Retorna el color según la nota"""
        if nota >= 4.5:
            return "#4CAF50"  # Verde
        elif nota >= 4.0:
            return "#8BC34A"  # Verde claro
        elif nota >= 3.5:
            return "#FFC107"  # Amarillo
        elif nota >= 3.0:
            return "#FF9800"  # Naranja
        else:
            return "#F44336"  # Rojo
    
    def _mostrar_grafico_evolucion(self, historial_notas: List[float]):
        """Muestra gráfico de evolución de la nota"""
        st.markdown("### 📈 Evolución de la Nota")
        
        if not historial_notas:
            st.info("No hay datos de evolución disponibles")
            return
        
        # Crear DataFrame
        df = pd.DataFrame({
            'Pregunta': range(1, len(historial_notas) + 1),
            'Nota': historial_notas
        })
        
        # Crear gráfico con Plotly
        fig = go.Figure()
        
        # Línea de evolución
        fig.add_trace(go.Scatter(
            x=df['Pregunta'],
            y=df['Nota'],
            mode='lines+markers',
            name='Nota',
            line=dict(color='#667eea', width=3),
            marker=dict(size=8)
        ))
        
        # Línea de aprobación (3.0)
        fig.add_hline(
            y=3.0,
            line_dash="dash",
            line_color="red",
            annotation_text="Nota mínima (3.0)",
            annotation_position="right"
        )
        
        # Layout
        fig.update_layout(
            xaxis_title="Número de Pregunta",
            yaxis_title="Nota Estimada",
            yaxis_range=[0, 5.5],
            hovermode='x unified',
            height=400
            margin=dict(t=20, l=50, r=20, b=50)
        )
        
        st.plotly_chart(fig, use_container_width=True)
