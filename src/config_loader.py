"""
Cargador de Configuración
Maneja la carga y validación de archivos de configuración JSON
"""
import json
from pathlib import Path
from typing import Dict, Any


class ConfigLoader:
    """Clase para cargar y validar configuraciones de exámenes"""
    
    REQUIRED_KEYS = {
        'metadata': ['nombre_examen', 'asignatura', 'institucion'],
        'parametros': [
            'preguntas_minimas',
            'preguntas_maximas',
            'nivel_inicial',
            'umbral_estabilizacion',
            'ventana_estabilizacion'
        ],
        'sistema_calificacion': ['tipo', 'parametros'],
        'instrucciones': ['titulo', 'descripcion', 'temas'],
        'persistencia': ['metodo', 'spreadsheet_id'],
        'archivo_preguntas': None  # Es un string directo
    }
    
    def __init__(self):
        """Inicializa el cargador de configuración"""
        self.config_path = Path("config")
        self.config_path.mkdir(exist_ok=True)
    
    def load_config(self, config_file: str) -> Dict[str, Any]:
        """
        Carga un archivo de configuración y lo valida
        
        Args:
            config_file: Ruta al archivo de configuración JSON
            
        Returns:
            Dict con la configuración validada
            
        Raises:
            FileNotFoundError: Si el archivo no existe
            ValueError: Si la configuración es inválida
        """
        config_path = Path(config_file)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Archivo de configuración no encontrado: {config_file}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Error al parsear JSON: {str(e)}")
        
        # Validar configuración
        self._validar_config(config)
        
        # Validar que el archivo de preguntas existe
        preguntas_path = Path(config['archivo_preguntas'])
        if not preguntas_path.exists():
            raise FileNotFoundError(
                f"Archivo de preguntas no encontrado: {config['archivo_preguntas']}"
            )
        
        return config
    
    def _validar_config(self, config: Dict[str, Any]) -> None:
        """
        Valida que la configuración tenga todos los campos requeridos
        
        Args:
            config: Diccionario con la configuración
            
        Raises:
            ValueError: Si falta algún campo requerido o los valores son inválidos
        """
        # Validar claves principales
        for key, subkeys in self.REQUIRED_KEYS.items():
            if key not in config:
                raise ValueError(f"Falta la clave requerida: {key}")
            
            # Validar subclaves si existen
            if subkeys is not None:
                for subkey in subkeys:
                    if subkey not in config[key]:
                        raise ValueError(f"Falta la subclave requerida: {key}.{subkey}")
        
        # Validar rangos de parámetros
        params = config['parametros']
        
        if params['preguntas_minimas'] < 1:
            raise ValueError("preguntas_minimas debe ser al menos 1")
        
        if params['preguntas_maximas'] < params['preguntas_minimas']:
            raise ValueError("preguntas_maximas debe ser mayor o igual a preguntas_minimas")
        
        if not (1 <= params['nivel_inicial'] <= 5):
            raise ValueError("nivel_inicial debe estar entre 1 y 5")
        
        if params['umbral_estabilizacion'] <= 0:
            raise ValueError("umbral_estabilizacion debe ser positivo")
        
        if params['ventana_estabilizacion'] < 2:
            raise ValueError("ventana_estabilizacion debe ser al menos 2")
        
        # Validar sistema de calificación
        tipos_validos = ['irt_simplificado', 'elo', 'hibrido']
        if config['sistema_calificacion']['tipo'] not in tipos_validos:
            raise ValueError(
                f"tipo de calificación debe ser uno de: {', '.join(tipos_validos)}"
            )
        
        # Validar método de persistencia
        if config['persistencia']['metodo'] != 'google_sheets':
            raise ValueError("método de persistencia debe ser 'google_sheets'")
    
    def crear_template_config(self, output_file: str = "config/examen_template.json") -> None:
        """
        Crea un archivo de configuración template
        
        Args:
            output_file: Ruta donde guardar el template
        """
        template = {
            "metadata": {
                "nombre_examen": "Examen Adaptativo de [ASIGNATURA]",
                "asignatura": "[NOMBRE DE LA ASIGNATURA]",
                "institucion": "Universidad ECCI"
            },
            "parametros": {
                "preguntas_minimas": 15,
                "preguntas_maximas": 30,
                "nivel_inicial": 3,
                "umbral_estabilizacion": 0.15,
                "ventana_estabilizacion": 3
            },
            "sistema_calificacion": {
                "tipo": "irt_simplificado",
                "parametros": {
                    "max_iteraciones": 10
                }
            },
            "instrucciones": {
                "titulo": "🎓 Examen Adaptativo de [ASIGNATURA]",
                "descripcion": [
                    "Este es un examen adaptativo...",
                    "Las preguntas se ajustan a tu nivel...",
                    "Contesta con honestidad..."
                ],
                "temas": [
                    "Tema 1",
                    "Tema 2",
                    "Tema 3"
                ]
            },
            "persistencia": {
                "metodo": "google_sheets",
                "spreadsheet_id": "TU_SPREADSHEET_ID_AQUI"
            },
            "archivo_preguntas": "data/preguntas_[ASIGNATURA].json"
        }
        
        output_path = Path(output_file)
        output_path.parent.mkdir(exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(template, f, indent=2, ensure_ascii=False)
    
    def validar_archivo_preguntas(self, preguntas_file: str) -> tuple[bool, str]:
        """
        Valida que el archivo de preguntas tenga el formato correcto
        
        Args:
            preguntas_file: Ruta al archivo de preguntas JSON
            
        Returns:
            Tupla (es_valido, mensaje)
        """
        try:
            with open(preguntas_file, 'r', encoding='utf-8') as f:
                preguntas = json.load(f)
            
            if not isinstance(preguntas, list):
                return False, "El archivo debe contener una lista de preguntas"
            
            if len(preguntas) == 0:
                return False, "El archivo no contiene preguntas"
            
            # Validar estructura de cada pregunta
            campos_requeridos = ['id', 'dificultad', 'categoria', 'pregunta', 
                               'opciones', 'respuesta_correcta', 'explicacion']
            
            for i, pregunta in enumerate(preguntas):
                for campo in campos_requeridos:
                    if campo not in pregunta:
                        return False, f"Pregunta {i+1}: falta el campo '{campo}'"
                
                # Validar dificultad
                if not (1 <= pregunta['dificultad'] <= 5):
                    return False, f"Pregunta {i+1}: dificultad debe estar entre 1 y 5"
                
                # Validar opciones
                if not isinstance(pregunta['opciones'], dict):
                    return False, f"Pregunta {i+1}: 'opciones' debe ser un diccionario"
                
                if len(pregunta['opciones']) < 2:
                    return False, f"Pregunta {i+1}: debe tener al menos 2 opciones"
                
                # Validar respuesta correcta
                if pregunta['respuesta_correcta'] not in pregunta['opciones']:
                    return False, f"Pregunta {i+1}: respuesta_correcta no existe en opciones"
            
            return True, f"Archivo válido con {len(preguntas)} preguntas"
            
        except FileNotFoundError:
            return False, f"Archivo no encontrado: {preguntas_file}"
        except json.JSONDecodeError as e:
            return False, f"Error al parsear JSON: {str(e)}"
        except Exception as e:
            return False, f"Error inesperado: {str(e)}"
