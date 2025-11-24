"""
Sistemas de Calificación
Implementa IRT Simplificado, Elo y sistema Híbrido
"""
import math
from typing import Dict, List, Tuple, Any
from abc import ABC, abstractmethod


class ScoringSystem(ABC):
    """Clase base abstracta para sistemas de calificación"""
    
    @abstractmethod
    def calcular_nota(self, respuestas: List[Dict[str, Any]]) -> float:
        """Calcula la nota final basada en las respuestas"""
        pass
    
    @abstractmethod
    def calcular_nota_parcial(self, respuestas: List[Dict[str, Any]]) -> float:
        """Calcula la nota parcial durante el examen"""
        pass
    
    @abstractmethod
    def obtener_estadisticas(self, respuestas: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Obtiene estadísticas adicionales del desempeño"""
        pass


class IRTSimplificado(ScoringSystem):
    """
    Sistema de calificación basado en IRT (Item Response Theory) Simplificado
    
    Estima la habilidad del estudiante (theta) mediante máxima verosimilitud
    y calcula una nota normalizada basada en esta habilidad.
    """
    
    def __init__(self, max_iteraciones: int = 10):
        """
        Inicializa el sistema IRT
        
        Args:
            max_iteraciones: Número máximo de iteraciones para estimar theta
        """
        self.max_iteraciones = max_iteraciones
        self.theta_min = -3.0
        self.theta_max = 3.0
    
    def probabilidad_respuesta_correcta(self, theta: float, dificultad: int) -> float:
        """
        Calcula la probabilidad de respuesta correcta según modelo IRT de 1 parámetro
        
        Args:
            theta: Habilidad del estudiante
            dificultad: Nivel de dificultad de la pregunta (1-5)
            
        Returns:
            Probabilidad entre 0 y 1
        """
        # Normalizar dificultad de escala 1-5 a escala logística (-2 a 2)
        b = (dificultad - 3) * 0.8  # Centro en 3, rango aproximado [-1.6, 1.6]
        
        # Modelo logístico de 1 parámetro
        # P(correcta) = 1 / (1 + exp(-(theta - b)))
        try:
            prob = 1.0 / (1.0 + math.exp(-(theta - b)))
        except OverflowError:
            prob = 1.0 if theta > b else 0.0
        
        return prob
    
    def estimar_theta(self, respuestas: List[Dict[str, Any]]) -> float:
        """
        Estima la habilidad del estudiante usando máxima verosimilitud
        
        Args:
            respuestas: Lista de diccionarios con respuestas y dificultades
            
        Returns:
            Estimación de theta (habilidad)
        """
        if not respuestas:
            return 0.0
        
        # Iniciar con theta = 0 (habilidad promedio)
        theta = 0.0
        
        for _ in range(self.max_iteraciones):
            # Calcular primera y segunda derivada de la log-verosimilitud
            primera_derivada = 0.0
            segunda_derivada = 0.0
            
            for respuesta in respuestas:
                dificultad = respuesta['dificultad']
                correcta = respuesta['correcta']
                
                p = self.probabilidad_respuesta_correcta(theta, dificultad)
                
                # Evitar divisiones por cero
                p = max(0.001, min(0.999, p))
                
                if correcta:
                    primera_derivada += (1 - p)
                    segunda_derivada -= p * (1 - p)
                else:
                    primera_derivada -= p
                    segunda_derivada -= p * (1 - p)
            
            # Evitar división por cero
            if abs(segunda_derivada) < 0.001:
                break
            
            # Actualización Newton-Raphson
            theta_nuevo = theta - (primera_derivada / segunda_derivada)
            
            # Limitar theta a un rango razonable
            theta_nuevo = max(self.theta_min, min(self.theta_max, theta_nuevo))
            
            # Verificar convergencia
            if abs(theta_nuevo - theta) < 0.01:
                theta = theta_nuevo
                break
            
            theta = theta_nuevo
        
        return theta
    
    def theta_a_nota(self, theta: float) -> float:
        """
        Convierte theta a una nota en escala 0-5
        Usa transformación ajustada para permitir alcanzar 5.0
        """
        # Rango efectivo de theta basado en dificultades reales
        theta_min_efectivo = -2.0
        theta_max_efectivo = 2.5
        
        # Limitar theta al rango efectivo
        theta_limitado = max(theta_min_efectivo, min(theta_max_efectivo, theta))
        
        # Transformación lineal al rango 0-5
        nota = ((theta_limitado - theta_min_efectivo) / (theta_max_efectivo - theta_min_efectivo)) * 5.0
        
        return round(max(0.0, min(5.0, nota)), 2)
    
    def calcular_nota(self, respuestas: List[Dict[str, Any]]) -> float:
        """
        Calcula la nota final usando IRT
        
        Args:
            respuestas: Lista de respuestas con dificultad y si fue correcta
            
        Returns:
            Nota entre 0 y 5
        """
        if not respuestas:
            return 0.0
        
        theta = self.estimar_theta(respuestas)
        return self.theta_a_nota(theta)
    
    def calcular_nota_parcial(self, respuestas: List[Dict[str, Any]]) -> float:
        """
        Calcula la nota parcial durante el examen
        
        Args:
            respuestas: Lista de respuestas hasta el momento
            
        Returns:
            Nota parcial entre 0 y 5
        """
        return self.calcular_nota(respuestas)
    
    def obtener_estadisticas(self, respuestas: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Obtiene estadísticas adicionales del IRT
        
        Args:
            respuestas: Lista de respuestas
            
        Returns:
            Diccionario con estadísticas
        """
        if not respuestas:
            return {
                'theta': 0.0,
                'consistencia': 0.0,
                'nivel_habilidad': 'Sin datos'
            }
        
        theta = self.estimar_theta(respuestas)
        
        # Calcular consistencia (qué tan bien se ajustan las respuestas al modelo)
        consistencia = self._calcular_consistencia(respuestas, theta)
        
        # Determinar nivel de habilidad
        if theta < -1.5:
            nivel = 'Básico'
        elif theta < -0.5:
            nivel = 'Fundamental'
        elif theta < 0.5:
            nivel = 'Intermedio'
        elif theta < 1.5:
            nivel = 'Avanzado'
        else:
            nivel = 'Experto'
        
        return {
            'theta': round(theta, 3),
            'consistencia': round(consistencia, 3),
            'nivel_habilidad': nivel
        }
    
    def _calcular_consistencia(self, respuestas: List[Dict[str, Any]], theta: float) -> float:
        """
        Calcula qué tan consistentes son las respuestas con la habilidad estimada
        
        Args:
            respuestas: Lista de respuestas
            theta: Habilidad estimada
            
        Returns:
            Valor entre 0 y 1 (1 = máxima consistencia)
        """
        if not respuestas:
            return 0.0
        
        suma_diferencias = 0.0
        
        for respuesta in respuestas:
            dificultad = respuesta['dificultad']
            correcta = respuesta['correcta']
            
            prob_esperada = self.probabilidad_respuesta_correcta(theta, dificultad)
            resultado_real = 1.0 if correcta else 0.0
            
            # Diferencia absoluta entre esperado y real
            diferencia = abs(prob_esperada - resultado_real)
            suma_diferencias += diferencia
        
        # Consistencia = 1 - (promedio de diferencias)
        consistencia = 1.0 - (suma_diferencias / len(respuestas))
        
        return max(0.0, min(1.0, consistencia))


class SistemaElo(ScoringSystem):
    """
    Sistema de calificación basado en Elo (similar al ajedrez)
    """
    
    def __init__(self, k_factor: float = 32, rating_inicial: float = 1500):
        """
        Inicializa el sistema Elo
        
        Args:
            k_factor: Factor K de Elo (sensibilidad a cambios)
            rating_inicial: Rating inicial del estudiante
        """
        self.k_factor = k_factor
        self.rating_inicial = rating_inicial
    
    def probabilidad_esperada(self, rating_estudiante: float, rating_pregunta: float) -> float:
        """
        Calcula la probabilidad esperada de respuesta correcta
        
        Args:
            rating_estudiante: Rating actual del estudiante
            rating_pregunta: Rating de la pregunta
            
        Returns:
            Probabilidad entre 0 y 1
        """
        return 1.0 / (1.0 + 10 ** ((rating_pregunta - rating_estudiante) / 400))
    
    def dificultad_a_rating(self, dificultad: int) -> float:
        """
        Convierte nivel de dificultad a rating Elo
        
        Args:
            dificultad: Nivel 1-5
            
        Returns:
            Rating Elo
        """
        # Mapear dificultad 1-5 a ratings
        # Nivel 1: 1200, Nivel 3: 1500, Nivel 5: 1800
        return 1200 + (dificultad - 1) * 150
    
    def calcular_rating_final(self, respuestas: List[Dict[str, Any]]) -> float:
        """
        Calcula el rating final del estudiante
        
        Args:
            respuestas: Lista de respuestas
            
        Returns:
            Rating final
        """
        rating = self.rating_inicial
        
        for respuesta in respuestas:
            dificultad = respuesta['dificultad']
            correcta = respuesta['correcta']
            
            rating_pregunta = self.dificultad_a_rating(dificultad)
            prob_esperada = self.probabilidad_esperada(rating, rating_pregunta)
            
            resultado = 1.0 if correcta else 0.0
            rating += self.k_factor * (resultado - prob_esperada)
        
        return rating
    
    def rating_a_nota(self, rating: float) -> float:
        """
        Convierte rating Elo a nota 0-5
        
        Args:
            rating: Rating Elo
            
        Returns:
            Nota entre 0 y 5
        """
        # Rating 1200 → nota 1.0
        # Rating 1500 → nota 3.0
        # Rating 1800 → nota 5.0
        
        if rating < 1200:
            return max(0.0, (rating - 900) / 300)
        elif rating > 1800:
            return min(5.0, 5.0 + (rating - 1800) / 200)
        else:
            # Interpolación lineal entre 1200-1800
            return 1.0 + ((rating - 1200) / 600) * 4.0
    
    def calcular_nota(self, respuestas: List[Dict[str, Any]]) -> float:
        """Calcula la nota final usando Elo"""
        if not respuestas:
            return 0.0
        
        rating = self.calcular_rating_final(respuestas)
        return self.rating_a_nota(rating)
    
    def calcular_nota_parcial(self, respuestas: List[Dict[str, Any]]) -> float:
        """Calcula la nota parcial"""
        return self.calcular_nota(respuestas)
    
    def obtener_estadisticas(self, respuestas: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Obtiene estadísticas del sistema Elo"""
        if not respuestas:
            return {
                'rating': self.rating_inicial,
                'cambio_rating': 0.0
            }
        
        rating_final = self.calcular_rating_final(respuestas)
        cambio = rating_final - self.rating_inicial
        
        return {
            'rating': round(rating_final, 1),
            'cambio_rating': round(cambio, 1)
        }


class SistemaHibrido(ScoringSystem):
    """
    Sistema híbrido que combina IRT y Elo
    """
    
    def __init__(self, peso_irt: float = 0.7, peso_elo: float = 0.3, **kwargs):
        """
        Inicializa el sistema híbrido
        
        Args:
            peso_irt: Peso del componente IRT (0-1)
            peso_elo: Peso del componente Elo (0-1)
            **kwargs: Parámetros adicionales para IRT y Elo
        """
        self.peso_irt = peso_irt
        self.peso_elo = peso_elo
        
        # Normalizar pesos
        suma_pesos = self.peso_irt + self.peso_elo
        if suma_pesos > 0:
            self.peso_irt /= suma_pesos
            self.peso_elo /= suma_pesos
        
        self.irt = IRTSimplificado(**kwargs)
        self.elo = SistemaElo(**kwargs)
    
    def calcular_nota(self, respuestas: List[Dict[str, Any]]) -> float:
        """Calcula la nota combinando IRT y Elo"""
        if not respuestas:
            return 0.0
        
        nota_irt = self.irt.calcular_nota(respuestas)
        nota_elo = self.elo.calcular_nota(respuestas)
        
        return nota_irt * self.peso_irt + nota_elo * self.peso_elo
    
    def calcular_nota_parcial(self, respuestas: List[Dict[str, Any]]) -> float:
        """Calcula la nota parcial"""
        return self.calcular_nota(respuestas)
    
    def obtener_estadisticas(self, respuestas: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Obtiene estadísticas de ambos sistemas"""
        stats_irt = self.irt.obtener_estadisticas(respuestas)
        stats_elo = self.elo.obtener_estadisticas(respuestas)
        
        return {
            **stats_irt,
            **stats_elo,
            'peso_irt': self.peso_irt,
            'peso_elo': self.peso_elo
        }


def crear_sistema_calificacion(config: Dict[str, Any]) -> ScoringSystem:
    """
    Factory para crear el sistema de calificación apropiado
    
    Args:
        config: Configuración del examen
        
    Returns:
        Instancia del sistema de calificación
    """
    tipo = config['sistema_calificacion']['tipo']
    params = config['sistema_calificacion'].get('parametros', {})
    
    if tipo == 'irt_simplificado':
        return IRTSimplificado(**params)
    elif tipo == 'elo':
        return SistemaElo(**params)
    elif tipo == 'hibrido':
        return SistemaHibrido(**params)
    else:
        raise ValueError(f"Sistema de calificación desconocido: {tipo}")
