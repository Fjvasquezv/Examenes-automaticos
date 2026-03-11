"""
Gestor de Preguntas
Maneja el banco de preguntas y la selección de preguntas por nivel
"""
import json
import random
from pathlib import Path
from typing import List, Dict, Any, Optional


class QuestionManager:
    """Clase para gestionar el banco de preguntas (soporta múltiples bancos)"""

    def __init__(
        self,
        preguntas_file: str = None,
        bancos_preguntas: list = None,
        base_path: str = None,
        preguntas_data: Optional[List[Dict[str, Any]]] = None
    ):
        """
        Inicializa el gestor de preguntas. Permite múltiples bancos (bancos_preguntas) o un solo archivo (preguntas_file).
        Args:
            preguntas_file: Ruta al archivo JSON con las preguntas (legacy)
            bancos_preguntas: Lista de rutas relativas a archivos JSON de bancos
            base_path: Ruta base para los archivos (Path o str). Si None, usa Path.cwd().
        Raises:
            FileNotFoundError: Si algún archivo no existe
            ValueError: Si el formato es inválido
        """
        from pathlib import Path
        self.base_path = Path(base_path) if base_path else Path.cwd()
        self.preguntas_usadas_ids = set()
        self.preguntas = []

        if preguntas_data is not None:
            if not isinstance(preguntas_data, list) or len(preguntas_data) == 0:
                raise ValueError("preguntas_data debe ser una lista no vacía")
            self.preguntas = list(preguntas_data)
        elif bancos_preguntas:
            for archivo in bancos_preguntas:
                ruta = self.base_path / archivo
                self.preguntas.extend(self._cargar_preguntas(ruta))
        elif preguntas_file:
            ruta = self.base_path / preguntas_file
            self.preguntas = self._cargar_preguntas(ruta)
        else:
            raise ValueError("Debe especificar preguntas_file o bancos_preguntas")
        self.preguntas_por_nivel = self._organizar_por_nivel()
    
    def _cargar_preguntas(self, path: Path) -> List[Dict[str, Any]]:
        """
        Carga las preguntas desde un archivo JSON
        Args:
            path: Ruta al archivo JSON
        Returns:
            Lista de diccionarios con las preguntas
        """
        if not path.exists():
            raise FileNotFoundError(f"Archivo de preguntas no encontrado: {path}")
        try:
            with open(path, 'r', encoding='utf-8') as f:
                preguntas = json.load(f)
            if not isinstance(preguntas, list):
                raise ValueError(f"El archivo debe contener una lista de preguntas: {path}")
            if len(preguntas) == 0:
                raise ValueError(f"El archivo no contiene preguntas: {path}")
            return preguntas
        except json.JSONDecodeError as e:
            raise ValueError(f"Error al parsear JSON en {path}: {str(e)}")
    
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
        preguntas_usadas,
        theta: float = None,
        categorias_prioritarias: Optional[set] = None,
        max_desviacion_nivel: int = 4
    ) -> Optional[Dict[str, Any]]:
        """
        Obtiene una pregunta del nivel especificado que no haya sido usada.
        Si theta está disponible, prioriza la pregunta con máxima información
        (dificultad más cercana a la habilidad estimada).
        
        Args:
            nivel: Nivel de dificultad deseado (1-5)
            preguntas_usadas: IDs de preguntas ya usadas (lista o set)
            theta: Habilidad estimada del estudiante (IRT). Si se provee,
                   se usa selección por máxima información.
            categorias_prioritarias: Conjunto opcional de categorías a priorizar.
                 max_desviacion_nivel: Distancia máxima permitida respecto al
                     nivel objetivo al buscar fallback por escasez.
            
        Returns:
            Diccionario con la pregunta o None si no hay preguntas disponibles
        """
        # Asegurar que el nivel esté en rango válido
        nivel = max(1, min(5, nivel))
        max_desviacion_nivel = max(1, min(4, int(max_desviacion_nivel)))
        
        categorias_objetivo = set(categorias_prioritarias) if categorias_prioritarias else None

        def _filtrar_preguntas(lista_preguntas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            salida = [p for p in lista_preguntas if p['id'] not in preguntas_usadas]
            if categorias_objetivo:
                salida = [
                    p for p in salida
                    if p.get('categoria', 'Sin categoría') in categorias_objetivo
                ]
            return salida

        # Obtener preguntas del nivel que no han sido usadas
        preguntas_disponibles = _filtrar_preguntas(self.preguntas_por_nivel[nivel])
        
        # Si no hay preguntas disponibles en este nivel exacto, buscar en niveles cercanos
        if not preguntas_disponibles:
            # Buscar el/los niveles más cercanos disponibles por distancia
            # Distancia 1 primero, luego hasta max_desviacion_nivel
            for distancia in range(1, max_desviacion_nivel + 1):
                candidatos_distancia = []

                nivel_arriba = nivel + distancia
                if nivel_arriba <= 5:
                    candidatos_distancia.extend(
                        _filtrar_preguntas(self.preguntas_por_nivel[nivel_arriba])
                    )

                nivel_abajo = nivel - distancia
                if nivel_abajo >= 1:
                    candidatos_distancia.extend(
                        _filtrar_preguntas(self.preguntas_por_nivel[nivel_abajo])
                    )

                if candidatos_distancia:
                    preguntas_disponibles = candidatos_distancia
                    break
        
        # Si no hay preguntas disponibles en absoluto
        if not preguntas_disponibles:
            # Si hay filtro de categorías, hacer fallback sin filtro
            if categorias_objetivo:
                return self.obtener_pregunta_por_nivel(
                    nivel,
                    preguntas_usadas,
                    theta=theta,
                    categorias_prioritarias=None,
                    max_desviacion_nivel=max_desviacion_nivel
                )
            return None
        
        # Selección por máxima información si theta está disponible
        if theta is not None and len(preguntas_disponibles) > 1:
            # Ordenar por cercanía de la dificultad al theta estimado
            # b = (dificultad - 3) * 0.8 es la escala IRT
            # IMPORTANTE: en empates, aplicar desempate aleatorio para evitar
            # sesgo hacia el primer banco cargado.
            preguntas_ordenadas = sorted(
                preguntas_disponibles,
                key=lambda p: (
                    abs((p['dificultad'] - 3) * 0.8 - theta),
                    random.random()
                )
            )
            # Elegir entre las top 3 para mantener variedad
            top_n = min(3, len(preguntas_ordenadas))
            return random.choice(preguntas_ordenadas[:top_n])
        
        # Sin theta: selección aleatoria
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
    
    def hay_preguntas_disponibles(self, nivel: int, preguntas_usadas) -> bool:
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
