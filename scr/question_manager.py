"""
Gestor de Preguntas
Maneja el banco de preguntas y la selección de preguntas por nivel
"""
import json
import random
from pathlib import Path
from typing import List, Dict, Any, Optional


class QuestionManager:
    """Clase para gestionar el banco de preguntas"""
    
    def __init__(self, preguntas_file: str):
        """
        Inicializa el gestor de preguntas
        
        Args:
            preguntas_file: Ruta al archivo JSON con las preguntas
            
        Raises:
            FileNotFoundError: Si el archivo no existe
            ValueError: Si el formato es inválido
        """
        self.preguntas_file = Path(preguntas_file)
        self.preguntas = self._cargar_preguntas()
        self.preguntas_por_nivel = self._organizar_por_nivel()
        self.preguntas_usadas_ids = set()
    
    def _cargar_preguntas(self) -> List[Dict[str, Any]]:
        """
        Carga las preguntas desde el archivo JSON
        
        Returns:
            Lista de diccionarios con las preguntas
        """
        if not self.preguntas_file.exists():
            raise FileNotFoundError(f"Archivo de preguntas no encontrado: {self.preguntas_file}")
        
        try:
            with open(self.preguntas_file, 'r', encoding='utf-8') as f:
                preguntas = json.load(f)
            
            if not isinstance(preguntas, list):
                raise ValueError("El archivo debe contener una lista de preguntas")
            
            if len(preguntas) == 0:
                raise ValueError("El archivo no contiene preguntas")
            
            return preguntas
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Error al parsear JSON: {str(e)}")
    
    def _organizar_por_nivel(self) -> Dict[int, List[Dict[str, Any]]]:
        """
        Organiza las preguntas por nivel de dificultad
        
        Returns:
            Diccionario con nivel como clave y lista de preguntas como valor
        """
        preguntas_por_nivel = {1: [], 2: [], 3: [], 4: [], 5: []}
        
        for pregunta in self.preguntas:
            nivel = pregunta.get('dificultad', 3)
            if 1 <= nivel <= 5:
                preguntas_por_nivel[nivel].append(pregunta)
        
        return preguntas_por_nivel
    
    def obtener_pregunta_por_nivel(
        self, 
        nivel: int, 
        preguntas_usadas: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Obtiene una pregunta aleatoria del nivel especificado que no haya sido usada
        
        Args:
            nivel: Nivel de dificultad deseado (1-5)
            preguntas_usadas: Lista de IDs de preguntas ya usadas
            
        Returns:
            Diccionario con la pregunta o None si no hay preguntas disponibles
        """
        # Asegurar que el nivel esté en rango válido
        nivel = max(1, min(5, nivel))
        
        # Obtener preguntas del nivel que no han sido usadas
        preguntas_disponibles = [
            p for p in self.preguntas_por_nivel[nivel]
            if p['id'] not in preguntas_usadas
        ]
        
        # Si no hay preguntas disponibles en este nivel exacto, buscar en niveles cercanos
        if not preguntas_disponibles:
            # Intentar niveles adyacentes
            for offset in [1, -1, 2, -2]:
                nivel_alternativo = nivel + offset
                if 1 <= nivel_alternativo <= 5:
                    preguntas_disponibles = [
                        p for p in self.preguntas_por_nivel[nivel_alternativo]
                        if p['id'] not in preguntas_usadas
                    ]
                    if preguntas_disponibles:
                        break
        
        # Si aún no hay preguntas disponibles, buscar en cualquier nivel
        if not preguntas_disponibles:
            preguntas_disponibles = [
                p for p in self.preguntas
                if p['id'] not in preguntas_usadas
            ]
        
        # Si no hay preguntas disponibles en absoluto
        if not preguntas_disponibles:
            return None
        
        # Seleccionar una pregunta aleatoria
        return random.choice(preguntas_disponibles)
    
    def obtener_pregunta_por_id(self, pregunta_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene una pregunta específica por su ID
        
        Args:
            pregunta_id: ID de la pregunta
            
        Returns:
            Diccionario con la pregunta o None si no existe
        """
        for pregunta in self.preguntas:
            if pregunta['id'] == pregunta_id:
                return pregunta
        return None
    
    def obtener_estadisticas_banco(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas del banco de preguntas
        
        Returns:
            Diccionario con estadísticas
        """
        categorias = {}
        for pregunta in self.preguntas:
            categoria = pregunta.get('categoria', 'Sin categoría')
            categorias[categoria] = categorias.get(categoria, 0) + 1
        
        return {
            'total_preguntas': len(self.preguntas),
            'preguntas_por_nivel': {
                nivel: len(preguntas) 
                for nivel, preguntas in self.preguntas_por_nivel.items()
            },
            'categorias': categorias,
            'niveles_disponibles': [
                nivel for nivel, preguntas in self.preguntas_por_nivel.items()
                if len(preguntas) > 0
            ]
        }
    
    def validar_cobertura_niveles(self, preguntas_minimas: int) -> Dict[str, Any]:
        """
        Valida que haya suficientes preguntas en cada nivel
        
        Args:
            preguntas_minimas: Cantidad mínima de preguntas requeridas para el examen
            
        Returns:
            Diccionario con el resultado de la validación
        """
        niveles_insuficientes = []
        
        for nivel in range(1, 6):
            cantidad = len(self.preguntas_por_nivel[nivel])
            # Asumimos que necesitamos al menos preguntas_minimas/5 por nivel
            minimo_recomendado = max(3, preguntas_minimas // 5)
            
            if cantidad < minimo_recomendado:
                niveles_insuficientes.append({
                    'nivel': nivel,
                    'actual': cantidad,
                    'recomendado': minimo_recomendado
                })
        
        es_valido = len(niveles_insuficientes) == 0
        
        return {
            'es_valido': es_valido,
            'total_preguntas': len(self.preguntas),
            'niveles_insuficientes': niveles_insuficientes,
            'mensaje': 'Cobertura adecuada' if es_valido else 'Algunos niveles tienen pocas preguntas'
        }
    
    def obtener_preguntas_por_categoria(self, categoria: str) -> List[Dict[str, Any]]:
        """
        Obtiene todas las preguntas de una categoría específica
        
        Args:
            categoria: Nombre de la categoría
            
        Returns:
            Lista de preguntas de la categoría
        """
        return [
            p for p in self.preguntas
            if p.get('categoria', '').lower() == categoria.lower()
        ]
    
    def obtener_categorias(self) -> List[str]:
        """
        Obtiene la lista de todas las categorías disponibles
        
        Returns:
            Lista de categorías únicas
        """
        categorias = set()
        for pregunta in self.preguntas:
            categoria = pregunta.get('categoria', 'Sin categoría')
            categorias.add(categoria)
        return sorted(list(categorias))
    
    def reiniciar_preguntas_usadas(self):
        """Reinicia el conjunto de preguntas usadas"""
        self.preguntas_usadas_ids.clear()
    
    def marcar_pregunta_usada(self, pregunta_id: str):
        """
        Marca una pregunta como usada
        
        Args:
            pregunta_id: ID de la pregunta
        """
        self.preguntas_usadas_ids.add(pregunta_id)
    
    def hay_preguntas_disponibles(self, nivel: int, preguntas_usadas: List[str]) -> bool:
        """
        Verifica si hay preguntas disponibles en un nivel
        
        Args:
            nivel: Nivel de dificultad
            preguntas_usadas: Lista de IDs de preguntas ya usadas
            
        Returns:
            True si hay preguntas disponibles
        """
        nivel = max(1, min(5, nivel))
        preguntas_disponibles = [
            p for p in self.preguntas_por_nivel[nivel]
            if p['id'] not in preguntas_usadas
        ]
        return len(preguntas_disponibles) > 0
