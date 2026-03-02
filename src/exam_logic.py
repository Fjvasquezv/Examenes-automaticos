"""
Lógica del Examen Adaptativo
Implementa la lógica CAT (Computerized Adaptive Testing)
"""
import random
from typing import Dict, List, Any, Optional

from question_manager import QuestionManager
from scoring_systems import crear_sistema_calificacion


class ExamLogic:
    """Clase que implementa la lógica del examen adaptativo"""
    
    def __init__(self, config: Dict[str, Any], question_manager: QuestionManager):
        """
        Inicializa la lógica del examen
        
        Args:
            config: Configuración del examen
            question_manager: Gestor de preguntas
        """
        self.config = config
        self.question_manager = question_manager
        
        # Parámetros del examen
        self.preguntas_minimas = config['parametros']['preguntas_minimas']
        self.preguntas_maximas = config['parametros']['preguntas_maximas']
        self.nivel_inicial = config['parametros']['nivel_inicial']
        self.umbral_estabilizacion = config['parametros']['umbral_estabilizacion']
        self.ventana_estabilizacion = config['parametros']['ventana_estabilizacion']
        
        # Sistema de calificación
        self.scoring_system = crear_sistema_calificacion(config)
        
        # Estado del examen
        self.nivel_actual = self.nivel_inicial
        self.pregunta_actual = 0
        self.correctas = 0
        self.incorrectas = 0
        self.preguntas_respondidas = []
        self.historial_notas = []
        self.preguntas_usadas = []
        self.preguntas_usadas_set = set()
        
        # Estimación de habilidad
        # Alinear theta inicial con el nivel inicial para mantener coherencia
        self.theta_actual = (self.nivel_inicial - 3) * 0.8
        # Evitar saltos bruscos de nivel entre preguntas consecutivas
        self.max_cambio_nivel_por_pregunta = 1
        self.categorias_evaluadas = set()
        
        # Pregunta actual
        self.pregunta_actual_obj = None
        self.opciones_mezcladas_actual = None
    
    def obtener_siguiente_pregunta(self) -> Optional[Dict[str, Any]]:
        """
        Obtiene la siguiente pregunta basada en el nivel actual y theta estimado.
        Usa selección por máxima información cuando theta está disponible.
        
        Returns:
            Diccionario con la pregunta o None si no hay más preguntas
        """
        pregunta = self.question_manager.obtener_pregunta_por_nivel(
            self.nivel_actual,
            self.preguntas_usadas_set,
            theta=self.theta_actual
        )
        
        if pregunta is None:
            return None
        
        # Guardar pregunta actual
        self.pregunta_actual_obj = pregunta
        self.preguntas_usadas.append(pregunta['id'])
        self.preguntas_usadas_set.add(pregunta['id'])
        
        return pregunta
    
    def mezclar_opciones(self, opciones: Dict[str, str]) -> Dict[str, str]:
        """
        Mezcla las opciones de respuesta aleatoriamente
        
        Args:
            opciones: Diccionario con opciones originales
            
        Returns:
            Diccionario con opciones mezcladas
        """
        # Crear lista de pares (clave, valor)
        items = list(opciones.items())
        
        # Mezclar los valores pero mantener las claves ordenadas
        valores = [v for k, v in items]
        random.shuffle(valores)
        
        # Crear nuevo diccionario con claves ordenadas y valores mezclados
        claves_ordenadas = sorted(opciones.keys())
        opciones_mezcladas = {k: v for k, v in zip(claves_ordenadas, valores)}
        
        # Guardar opciones mezcladas actuales
        self.opciones_mezcladas_actual = opciones_mezcladas
        
        return opciones_mezcladas
    
    def procesar_respuesta(
        self,
        pregunta: Dict[str, Any],
        respuesta_seleccionada: str,
        opciones_mezcladas: Dict[str, str]
    ) -> bool:
        """
        Procesa la respuesta del estudiante
        
        Args:
            pregunta: Diccionario con la pregunta
            respuesta_seleccionada: Letra de la opción seleccionada
            opciones_mezcladas: Opciones mezcladas mostradas
            
        Returns:
            True si la respuesta es correcta
        """
        # Determinar cuál era la respuesta correcta original
        respuesta_correcta_original = pregunta['respuesta_correcta']
        texto_correcto = pregunta['opciones'][respuesta_correcta_original]
        
        # Ver si el texto seleccionado coincide con el texto correcto
        texto_seleccionado = opciones_mezcladas[respuesta_seleccionada]
        es_correcta = (texto_seleccionado == texto_correcto)
        
        # Actualizar contadores
        if es_correcta:
            self.correctas += 1
        else:
            self.incorrectas += 1
        
        # Guardar respuesta con TODOS los detalles para retroalimentación final
        respuesta_info = {
            'pregunta_id': pregunta['id'],
            'dificultad': pregunta['dificultad'],
            'categoria': pregunta.get('categoria', 'Sin categoría'),
            'correcta': es_correcta,
            'nivel_en_pregunta': self.nivel_actual,
            # NUEVO: Guardar detalles para retroalimentación
            'pregunta_texto': pregunta['pregunta'],
            'respuesta_correcta_texto': texto_correcto,
            'respuesta_estudiante_texto': texto_seleccionado,
            'explicacion': pregunta.get('explicacion', 'Sin explicación disponible')
        }
        self.preguntas_respondidas.append(respuesta_info)
        
        # Calcular nota actual
        nota_actual = self.scoring_system.calcular_nota_parcial(self.preguntas_respondidas)
        self.historial_notas.append(nota_actual)
        
        # Actualizar nivel basado en el modelo estadístico (no reglas ad-hoc)
        self._actualizar_nivel_desde_modelo()
        
        # Registrar categoría evaluada
        self.categorias_evaluadas.add(pregunta.get('categoria', 'Sin categoría'))
        
        # Incrementar contador de pregunta
        self.pregunta_actual += 1
        
        return es_correcta
    
    def _actualizar_nivel_desde_modelo(self):
        """
        Actualiza el nivel de dificultad basándose en la estimación
        del modelo estadístico (theta en IRT, rating en Elo).
        Elimina aleatoriedad: el nivel se deriva directamente del modelo.
        
        Nota: Requiere mínimo 4 respuestas para evitar inestabilidad con pocas muestras.
        Con < 4 respuestas, theta es demasiado volátil y puede causar saltos de nivel erráticos.
        """
        if len(self.preguntas_respondidas) < 4:
            return  # Necesita al menos 4 respuestas para estimación estable
        
        nivel_estimado = self.nivel_actual
        stats = self.scoring_system.obtener_estadisticas(self.preguntas_respondidas)
        
        if 'theta' in stats:
            # IRT: mapear theta a nivel usando la escala de dificultad del modelo
            self.theta_actual = stats['theta']
            nivel_estimado = self._theta_a_nivel(self.theta_actual)
        elif 'rating' in stats:
            # Elo: mapear rating [1200-1800] a nivel [1-5]
            rating = stats['rating']
            nivel_estimado = max(1, min(5, round((rating - 1050) / 150)))
        else:
            # Fallback: proporción de correctas
            ratio = self.correctas / len(self.preguntas_respondidas)
            nivel_estimado = max(1, min(5, round(ratio * 4) + 1))

        # Aplicar amortiguación: como máximo ±1 nivel por pregunta
        delta = nivel_estimado - self.nivel_actual
        if delta > self.max_cambio_nivel_por_pregunta:
            delta = self.max_cambio_nivel_por_pregunta
        elif delta < -self.max_cambio_nivel_por_pregunta:
            delta = -self.max_cambio_nivel_por_pregunta

        self.nivel_actual = max(1, min(5, self.nivel_actual + delta))
    
    @staticmethod
    def _theta_a_nivel(theta: float) -> int:
        """
        Convierte theta IRT a nivel de dificultad 1-5.
        Usa la misma escala que el modelo: b = (nivel - 3) * 0.8
        
        Mapeo: theta -1.6→1, -0.8→2, 0.0→3, 0.8→4, 1.6→5
        """
        nivel = round(theta / 0.8 + 3)
        return max(1, min(5, nivel))
    
    @staticmethod
    def _calcular_pendiente(valores: list) -> float:
        """
        Calcula la pendiente de una serie de valores (regresión lineal simple).
        Usada para verificar convergencia en el criterio de terminación.
        
        Returns:
            Pendiente de la recta. Cercana a 0 indica estabilización.
        """
        n = len(valores)
        if n < 2:
            return float('inf')
        
        x_mean = (n - 1) / 2.0
        y_mean = sum(valores) / n
        
        numerador = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(valores))
        denominador = sum((i - x_mean) ** 2 for i in range(n))
        
        if denominador == 0:
            return 0.0
        
        return numerador / denominador
    
    def debe_terminar_examen(self) -> bool:
        """
        Determina si el examen debe terminar
        
        Returns:
            True si el examen debe terminar
        """
        # Si no se han respondido preguntas aún
        if self.pregunta_actual == 0:
            return False
        
        # Si se alcanzó el máximo de preguntas
        if self.pregunta_actual >= self.preguntas_maximas:
            return True
        
        # Si no se ha alcanzado el mínimo, continuar
        if self.pregunta_actual < self.preguntas_minimas:
            return False
        
        # Verificar cobertura mínima de categorías antes de permitir terminación
        categorias_disponibles = len(self.question_manager.obtener_categorias())
        categorias_minimas = min(3, categorias_disponibles)
        if len(self.categorias_evaluadas) < categorias_minimas:
            return False
        
        # Verificar estabilización de la nota (rango + pendiente)
        if len(self.historial_notas) >= self.ventana_estabilizacion:
            ultimas_notas = self.historial_notas[-self.ventana_estabilizacion:]
            
            # Calcular rango de variación
            max_nota = max(ultimas_notas)
            min_nota = min(ultimas_notas)
            variacion = max_nota - min_nota
            
            # Terminar si la variación es pequeña Y la nota converge (pendiente ≈ 0)
            if variacion <= self.umbral_estabilizacion:
                pendiente = self._calcular_pendiente(ultimas_notas)
                if abs(pendiente) < 0.1:
                    return True
        
        # Verificar si no hay más preguntas disponibles
        if not self.question_manager.hay_preguntas_disponibles(
            self.nivel_actual,
            self.preguntas_usadas_set
        ):
            # Intentar otros niveles
            hay_preguntas = False
            for nivel in range(1, 6):
                if self.question_manager.hay_preguntas_disponibles(nivel, self.preguntas_usadas_set):
                    hay_preguntas = True
                    break
            
            if not hay_preguntas:
                return True
        
        return False
    
    def calcular_estadisticas_finales(self) -> Dict[str, Any]:
        """
        Calcula las estadísticas finales del examen
        
        Returns:
            Diccionario con estadísticas completas
        """
        # Nota final
        nota_final = self.scoring_system.calcular_nota(self.preguntas_respondidas)
        
        # Estadísticas del sistema de calificación
        stats_sistema = self.scoring_system.obtener_estadisticas(self.preguntas_respondidas)
        
        # Estadísticas por nivel de dificultad
        stats_por_nivel = self._calcular_stats_por_nivel()
        
        # Estadísticas por categoría
        stats_por_categoria = self._calcular_stats_por_categoria()
        
        # Progresión de dificultad
        niveles_progresion = [r['nivel_en_pregunta'] for r in self.preguntas_respondidas]
        
        # NUEVO: Preparar detalle de respuestas para retroalimentación
        detalle_respuestas = []
        for respuesta in self.preguntas_respondidas:
            detalle_respuestas.append({
                'pregunta': respuesta.get('pregunta_texto', f"Pregunta {respuesta.get('pregunta_id', '')}"),
                'categoria': respuesta.get('categoria', 'Sin categoría'),
                'dificultad': respuesta.get('dificultad', 3),
                'correcta': bool(respuesta.get('correcta', False)),
                'respuesta_correcta': respuesta.get('respuesta_correcta_texto', 'No disponible'),
                'respuesta_estudiante': respuesta.get('respuesta_estudiante_texto', 'No disponible'),
                'explicacion': respuesta.get('explicacion', 'Sin explicación disponible')
            })
        
        return {
            'preguntas_respondidas': len(self.preguntas_respondidas),
            'correctas': self.correctas,
            'incorrectas': self.incorrectas,
            'porcentaje_correctas': (self.correctas / len(self.preguntas_respondidas) * 100) 
                                    if self.preguntas_respondidas else 0,
            'nota_final': round(nota_final, 2),
            'nivel_final': self.nivel_actual,
            'historial_notas': [round(n, 2) for n in self.historial_notas],
            'stats_sistema': stats_sistema,
            'stats_por_nivel': stats_por_nivel,
            'stats_por_categoria': stats_por_categoria,
            'niveles_progresion': niveles_progresion,
            'preguntas_ids': [r['pregunta_id'] for r in self.preguntas_respondidas],
            'razon_terminacion': self._obtener_razon_terminacion(),
            'detalle_respuestas': detalle_respuestas  # NUEVO
        }
    
    def _calcular_stats_por_nivel(self) -> Dict[int, Dict[str, Any]]:
        """
        Calcula estadísticas por nivel de dificultad
        
        Returns:
            Diccionario con stats por nivel
        """
        stats = {}
        
        for nivel in range(1, 6):
            respuestas_nivel = [
                r for r in self.preguntas_respondidas
                if r['dificultad'] == nivel
            ]
            
            if respuestas_nivel:
                correctas_nivel = sum(1 for r in respuestas_nivel if r['correcta'])
                total_nivel = len(respuestas_nivel)
                
                stats[nivel] = {
                    'total': total_nivel,
                    'correctas': correctas_nivel,
                    'incorrectas': total_nivel - correctas_nivel,
                    'porcentaje': round(correctas_nivel / total_nivel * 100, 1)
                }
            else:
                stats[nivel] = {
                    'total': 0,
                    'correctas': 0,
                    'incorrectas': 0,
                    'porcentaje': 0
                }
        
        return stats
    
    def _calcular_stats_por_categoria(self) -> Dict[str, Dict[str, Any]]:
        """
        Calcula estadísticas por categoría
        
        Returns:
            Diccionario con stats por categoría
        """
        stats = {}
        
        # Agrupar por categoría
        for respuesta in self.preguntas_respondidas:
            categoria = respuesta['categoria']
            
            if categoria not in stats:
                stats[categoria] = {
                    'total': 0,
                    'correctas': 0,
                    'incorrectas': 0
                }
            
            stats[categoria]['total'] += 1
            if respuesta['correcta']:
                stats[categoria]['correctas'] += 1
            else:
                stats[categoria]['incorrectas'] += 1
        
        # Calcular porcentajes
        for categoria in stats:
            if stats[categoria]['total'] > 0:
                stats[categoria]['porcentaje'] = round(
                    stats[categoria]['correctas'] / stats[categoria]['total'] * 100, 1
                )
            else:
                stats[categoria]['porcentaje'] = 0
        
        return stats
    
    def _obtener_razon_terminacion(self) -> str:
        """
        Determina la razón por la que terminó el examen
        
        Returns:
            Descripción de la razón
        """
        if self.pregunta_actual >= self.preguntas_maximas:
            return "Máximo de preguntas alcanzado"
        
        if len(self.historial_notas) >= self.ventana_estabilizacion:
            ultimas_notas = self.historial_notas[-self.ventana_estabilizacion:]
            variacion = max(ultimas_notas) - min(ultimas_notas)
            
            if variacion <= self.umbral_estabilizacion:
                pendiente = self._calcular_pendiente(ultimas_notas)
                if abs(pendiente) < 0.1:
                    return "Nota estabilizada"
        
        return "Sin preguntas disponibles"
    
    def obtener_resumen_pregunta_actual(self) -> Dict[str, Any]:
        """
        Obtiene un resumen del estado en la pregunta actual
        
        Returns:
            Diccionario con información resumida
        """
        return {
            'numero_pregunta': self.pregunta_actual + 1,
            'nivel_actual': self.nivel_actual,
            'correctas': self.correctas,
            'incorrectas': self.incorrectas,
            'nota_actual': round(self.historial_notas[-1], 2) if self.historial_notas else 0.0
        }
