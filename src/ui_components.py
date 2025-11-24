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
                <span style='color: #003366; font-size: 12px; line-height: 1.2;'>
                    Facultad de Ingeniería
                </span>
                <span style='color: #003366; font-size: 12px; line-height: 1.2;'>
                    Ingeniería Química
                </span>
            </div>
            <div style='display: flex; flex-direction: column; justify-content: center; text-align: center;'>
                <span style='color: #003366; font-weight: bold; font-size: 14px;'>
                    {self.metadata['asignatura']}
                </span>
                {f"<span style='color: #003366; font-size: 12px;'>{periodo_activo}</span>" if periodo_activo else ""}
            </div>
            <div style='display: flex; flex-direction: column; justify-content: center; text-align: right;'>
                <span style='color: #003366; font-size: 11px;'>
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
                st.markdown("**⚠️ Advertencias:**")
                for adv in advertencias:
                    st.warning(adv)
                
    def mostrar_metricas_progreso(
        self,
        codigo: str,
        pregunta_actual: int,
        total_preguntas: int,
        correctas: int,
        incorrectas: int
    ):
        """
        Muestra métricas de progreso durante el examen
        
        Args:
            codigo: Código del estudiante
            pregunta_actual: Número de pregunta actual
            total_preguntas: Total de preguntas máximas
            correctas: Número de respuestas correctas
            incorrectas: Número de respuestas incorrectas
        """
        # Información del estudiante
        st.markdown(f"""
        <div style='background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 20px;'>
            <p style='margin: 0; font-size: 18px;'><strong>👤 Estudiante:</strong> {codigo}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Métricas en columnas
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "📝 Pregunta",
                f"{pregunta_actual}/{total_preguntas}"
            )
        
        with col2:
            st.metric(
                "✅ Correctas",
                correctas,
                delta=None
            )
        
        with col3:
            st.metric(
                "❌ Incorrectas",
                incorrectas,
                delta=None
            )
        
        with col4:
            total_respondidas = correctas + incorrectas
            porcentaje = (correctas / total_respondidas * 100) if total_respondidas > 0 else 0
            st.metric(
                "📊 Aciertos",
                f"{porcentaje:.1f}%"
            )
        
        # Barra de progreso
        progreso = pregunta_actual / total_preguntas
        st.progress(progreso)
        
        st.markdown("---")
    
    def mostrar_pregunta(self, pregunta: Dict[str, Any], numero_pregunta: int):
        """
        Muestra una pregunta
        
        Args:
            pregunta: Diccionario con la pregunta
            numero_pregunta: Número de la pregunta
        """
        # Encabezado de la pregunta
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.markdown(f"### 📌 Pregunta {numero_pregunta}")
        
        with col2:
            # Badge de dificultad
            dificultad = pregunta['dificultad']
            color = self._get_dificultad_color(dificultad)
            st.markdown(f"""
            <div style='text-align: right;'>
                <span style='background-color: {color}; color: white; padding: 5px 15px; 
                      border-radius: 20px; font-weight: bold;'>
                    Nivel {dificultad}
                </span>
            </div>
            """, unsafe_allow_html=True)
        
        # Categoría
        if 'categoria' in pregunta:
            st.caption(f"📂 Categoría: {pregunta['categoria']}")
        
        # Pregunta
        st.markdown("---")
        st.markdown(pregunta['pregunta'])
        st.markdown("---")
    
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
        """
        Muestra los resultados finales del examen
        
        Args:
            stats: Diccionario con estadísticas finales
            codigo: Código del estudiante
        """
        # Título
        st.balloons()
        st.markdown("## 🎉 ¡Examen Completado!")
        st.markdown(f"**Estudiante:** {codigo}")
        st.markdown("---")
        
        # Nota final destacada
        nota_final = stats['nota_final']
        color_nota = self._get_color_nota(nota_final)
        
        st.markdown(f"""
        <div style='text-align: center; padding: 30px; background: linear-gradient(135deg, {color_nota}20 0%, {color_nota}40 100%);
             border-radius: 15px; margin: 20px 0; border: 3px solid {color_nota};'>
            <h1 style='color: {color_nota}; font-size: 72px; margin: 0;'>{nota_final}</h1>
            <p style='font-size: 24px; color: #555; margin: 10px 0 0 0;'>Nota Final (sobre 5.0)</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Métricas generales
        st.markdown("### 📊 Resumen General")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Total de Preguntas",
                stats['preguntas_respondidas']
            )
        
        with col2:
            st.metric(
                "Respuestas Correctas",
                stats['correctas'],
                delta=f"{stats['porcentaje_correctas']:.1f}%"
            )
        
        with col3:
            st.metric(
                "Respuestas Incorrectas",
                stats['incorrectas']
            )
        
        with col4:
            st.metric(
                "Nivel Final",
                stats['nivel_final']
            )
        
        st.markdown("---")
        
        # NUEVO: Retroalimentación detallada de cada pregunta
        if 'detalle_respuestas' in stats:
            st.markdown("### 📝 Retroalimentación Detallada")
            
            for i, detalle in enumerate(stats['detalle_respuestas'], 1):
                with st.expander(f"Pregunta {i} - {'✅ Correcta' if detalle['correcta'] else '❌ Incorrecta'}"):
                    st.markdown(f"**Pregunta:** {detalle['pregunta']}")
                    st.markdown(f"**Categoría:** {detalle['categoria']} | **Dificultad:** Nivel {detalle['dificultad']}")
                    
                    if detalle['correcta']:
                        st.success("✅ Tu respuesta fue correcta")
                    else:
                        st.error("❌ Tu respuesta fue incorrecta")
                        st.info(f"**Respuesta correcta:** {detalle['respuesta_correcta']}")
                    
                    st.markdown("**💡 Explicación:**")
                    st.info(detalle['explicacion'])
            
            st.markdown("---")
        
        # Gráfico de evolución de la nota
        self._mostrar_grafico_evolucion(stats['historial_notas'])
        
        # Análisis por nivel de dificultad
        self._mostrar_analisis_por_nivel(stats['stats_por_nivel'])
        
        # Análisis por categoría
        if stats['stats_por_categoria']:
            self._mostrar_analisis_por_categoria(stats['stats_por_categoria'])
        
        # Estadísticas del sistema de calificación
        self._mostrar_stats_sistema(stats['stats_sistema'])
        
        # Información adicional
        with st.expander("ℹ️ Información adicional"):
            st.write(f"**Razón de terminación:** {stats['razon_terminacion']}")
            st.write(f"**Sistema de calificación:** {self.config['sistema_calificacion']['tipo']}")
            
            if 'niveles_progresion' in stats:
                st.write("**Progresión de niveles:**")
                st.line_chart(stats['niveles_progresion'])
    
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
            title="Evolución de la Nota Durante el Examen",
            xaxis_title="Número de Pregunta",
            yaxis_title="Nota Estimada",
            yaxis_range=[0, 5.5],
            hovermode='x unified',
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    def _mostrar_analisis_por_nivel(self, stats_por_nivel: Dict[int, Dict[str, Any]]):
        """Muestra análisis por nivel de dificultad"""
        st.markdown("### 🎯 Análisis por Nivel de Dificultad")
        
        # Crear DataFrame
        data = []
        for nivel in range(1, 6):
            if nivel in stats_por_nivel and stats_por_nivel[nivel]['total'] > 0:
                data.append({
                    'Nivel': f"Nivel {nivel}",
                    'Total': stats_por_nivel[nivel]['total'],
                    'Correctas': stats_por_nivel[nivel]['correctas'],
                    'Incorrectas': stats_por_nivel[nivel]['incorrectas'],
                    'Porcentaje': stats_por_nivel[nivel]['porcentaje']
                })
        
        if not data:
            st.info("No hay datos por nivel disponibles")
            return
        
        df = pd.DataFrame(data)
        
        # Mostrar tabla
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.dataframe(
                df[['Nivel', 'Total', 'Correctas', 'Incorrectas', 'Porcentaje']],
                hide_index=True,
                use_container_width=True
            )
        
        with col2:
            # Gráfico de barras
            fig = px.bar(
                df,
                x='Nivel',
                y='Porcentaje',
                text='Porcentaje',
                title='Porcentaje de Aciertos por Nivel',
                color='Porcentaje',
                color_continuous_scale='RdYlGn',
                range_color=[0, 100]
            )
            
            fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
            fig.update_layout(height=300, showlegend=False)
            
            st.plotly_chart(fig, use_container_width=True)
    
    def _mostrar_analisis_por_categoria(self, stats_por_categoria: Dict[str, Dict[str, Any]]):
        """Muestra análisis por categoría"""
        st.markdown("### 📚 Análisis por Categoría")
        
        # Crear DataFrame
        data = []
        for categoria, stats in stats_por_categoria.items():
            data.append({
                'Categoría': categoria,
                'Total': stats['total'],
                'Correctas': stats['correctas'],
                'Incorrectas': stats['incorrectas'],
                'Porcentaje': stats['porcentaje']
            })
        
        df = pd.DataFrame(data)
        df = df.sort_values('Porcentaje', ascending=False)
        
        # Mostrar tabla
        st.dataframe(
            df,
            hide_index=True,
            use_container_width=True
        )
        
        # Gráfico de barras horizontales
        fig = px.bar(
            df,
            y='Categoría',
            x='Porcentaje',
            orientation='h',
            text='Porcentaje',
            title='Desempeño por Categoría',
            color='Porcentaje',
            color_continuous_scale='RdYlGn',
            range_color=[0, 100]
        )
        
        fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        fig.update_layout(height=max(300, len(df) * 40), showlegend=False)
        
        st.plotly_chart(fig, use_container_width=True)
    
    def _mostrar_stats_sistema(self, stats_sistema: Dict[str, Any]):
        """Muestra estadísticas del sistema de calificación"""
        st.markdown("### 🔬 Estadísticas del Sistema de Calificación")
        
        cols = st.columns(len(stats_sistema))
        
        for i, (key, value) in enumerate(stats_sistema.items()):
            with cols[i]:
                # Formatear nombre de la métrica
                nombre_metrica = key.replace('_', ' ').title()
                
                # Formatear valor
                if isinstance(value, float):
                    valor_formateado = f"{value:.3f}"
                else:
                    valor_formateado = str(value)
                
                st.metric(nombre_metrica, valor_formateado)
