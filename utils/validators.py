"""
Validadores
Funciones de validación para diferentes datos del sistema
"""
import re
from typing import Any, Dict, List


def validate_codigo_estudiante(codigo: str) -> bool:
    """
    Valida que el código de estudiante sea válido
    
    Args:
        codigo: Código del estudiante
        
    Returns:
        True si es válido
    """
    if not codigo:
        return False
    
    # Eliminar espacios
    codigo = codigo.strip()
    
    # Debe tener al menos 4 caracteres
    if len(codigo) < 4:
        return False
    
    # Solo debe contener letras, números, guiones y guiones bajos
    if not re.match(r'^[a-zA-Z0-9_-]+$', codigo):
        return False
    
    return True


def validate_respuesta(respuesta: str, opciones: Dict[str, str]) -> bool:
    """
    Valida que una respuesta sea válida
    
    Args:
        respuesta: Letra de la opción seleccionada
        opciones: Diccionario con las opciones disponibles
        
    Returns:
        True si la respuesta es válida
    """
    if not respuesta:
        return False
    
    return respuesta in opciones


def validate_nivel(nivel: int) -> bool:
    """
    Valida que un nivel sea válido
    
    Args:
        nivel: Nivel de dificultad
        
    Returns:
        True si es válido (1-5)
    """
    return isinstance(nivel, int) and 1 <= nivel <= 5


def validate_nota(nota: float) -> bool:
    """
    Valida que una nota sea válida
    
    Args:
        nota: Nota a validar
        
    Returns:
        True si es válida (0-5)
    """
    return isinstance(nota, (int, float)) and 0 <= nota <= 5


def validate_pregunta_estructura(pregunta: Dict[str, Any]) -> tuple[bool, str]:
    """
    Valida que una pregunta tenga la estructura correcta
    
    Args:
        pregunta: Diccionario con la pregunta
        
    Returns:
        Tupla (es_valida, mensaje_error)
    """
    campos_requeridos = [
        'id',
        'dificultad',
        'categoria',
        'pregunta',
        'opciones',
        'respuesta_correcta',
        'explicacion'
    ]
    
    # Verificar campos requeridos
    for campo in campos_requeridos:
        if campo not in pregunta:
            return False, f"Falta el campo requerido: {campo}"
    
    # Validar ID
    if not isinstance(pregunta['id'], str) or not pregunta['id']:
        return False, "ID debe ser un string no vacío"
    
    # Validar dificultad
    if not validate_nivel(pregunta['dificultad']):
        return False, "Dificultad debe ser un entero entre 1 y 5"
    
    # Validar categoría
    if not isinstance(pregunta['categoria'], str) or not pregunta['categoria']:
        return False, "Categoría debe ser un string no vacío"
    
    # Validar pregunta
    if not isinstance(pregunta['pregunta'], str) or not pregunta['pregunta']:
        return False, "Pregunta debe ser un string no vacío"
    
    # Validar opciones
    if not isinstance(pregunta['opciones'], dict):
        return False, "Opciones debe ser un diccionario"
    
    if len(pregunta['opciones']) < 2:
        return False, "Debe haber al menos 2 opciones"
    
    for key, value in pregunta['opciones'].items():
        if not isinstance(key, str) or not isinstance(value, str):
            return False, "Las claves y valores de opciones deben ser strings"
        if not key or not value:
            return False, "Las claves y valores de opciones no pueden estar vacíos"
    
    # Validar respuesta correcta
    if pregunta['respuesta_correcta'] not in pregunta['opciones']:
        return False, "La respuesta correcta debe existir en las opciones"
    
    # Validar explicación
    if not isinstance(pregunta['explicacion'], str):
        return False, "Explicación debe ser un string"
    
    return True, "Pregunta válida"


def validate_config_estructura(config: Dict[str, Any]) -> tuple[bool, str]:
    """
    Valida que la configuración tenga la estructura correcta
    
    Args:
        config: Diccionario con la configuración
        
    Returns:
        Tupla (es_valida, mensaje_error)
    """
    # Verificar secciones principales
    secciones_requeridas = [
        'metadata',
        'parametros',
        'sistema_calificacion',
        'persistencia'
    ]
    
    for seccion in secciones_requeridas:
        if seccion not in config:
            return False, f"Falta la sección requerida: {seccion}"

    # Arquitectura modular: exigir bancos_preguntas
    if 'bancos_preguntas' not in config:
        return False, "Debe existir 'bancos_preguntas' (arquitectura modular)"

    if not isinstance(config['bancos_preguntas'], list) or len(config['bancos_preguntas']) == 0:
        return False, "bancos_preguntas debe ser una lista no vacía"

    if 'archivo_preguntas' in config:
        return False, "'archivo_preguntas' no está permitido en arquitectura modular"
    
    # Validar metadata
    campos_metadata = ['nombre_examen', 'asignatura', 'institucion']
    for campo in campos_metadata:
        if campo not in config['metadata']:
            return False, f"Falta en metadata: {campo}"
    
    # Validar parámetros
    campos_parametros = [
        'preguntas_minimas',
        'preguntas_maximas',
        'nivel_inicial',
        'umbral_estabilizacion',
        'ventana_estabilizacion'
    ]
    for campo in campos_parametros:
        if campo not in config['parametros']:
            return False, f"Falta en parámetros: {campo}"
    
    # Validar rangos
    params = config['parametros']
    
    if params['preguntas_minimas'] < 1:
        return False, "preguntas_minimas debe ser al menos 1"
    
    if params['preguntas_maximas'] < params['preguntas_minimas']:
        return False, "preguntas_maximas debe ser >= preguntas_minimas"
    
    if not validate_nivel(params['nivel_inicial']):
        return False, "nivel_inicial debe estar entre 1 y 5"
    
    if params['umbral_estabilizacion'] <= 0:
        return False, "umbral_estabilizacion debe ser positivo"
    
    if params['ventana_estabilizacion'] < 2:
        return False, "ventana_estabilizacion debe ser al menos 2"
    
    # Validar sistema de calificación
    if 'tipo' not in config['sistema_calificacion']:
        return False, "Falta tipo en sistema_calificacion"
    
    tipos_validos = ['irt_simplificado', 'elo', 'hibrido']
    if config['sistema_calificacion']['tipo'] not in tipos_validos:
        return False, f"Tipo de sistema debe ser uno de: {', '.join(tipos_validos)}"
    
    # Validar persistencia
    if 'metodo' not in config['persistencia']:
        return False, "Falta método en persistencia"
    
    if config['persistencia']['metodo'] != 'google_sheets':
        return False, "Método de persistencia debe ser 'google_sheets'"
    
    if 'spreadsheet_id' not in config['persistencia']:
        return False, "Falta spreadsheet_id en persistencia"
    
    return True, "Configuración válida"


def validate_respuestas_lista(respuestas: List[Dict[str, Any]]) -> tuple[bool, str]:
    """
    Valida que una lista de respuestas tenga la estructura correcta
    
    Args:
        respuestas: Lista de diccionarios con respuestas
        
    Returns:
        Tupla (es_valida, mensaje_error)
    """
    if not isinstance(respuestas, list):
        return False, "Respuestas debe ser una lista"
    
    campos_requeridos = ['pregunta_id', 'dificultad', 'correcta']
    
    for i, respuesta in enumerate(respuestas):
        if not isinstance(respuesta, dict):
            return False, f"Respuesta {i+1} debe ser un diccionario"
        
        for campo in campos_requeridos:
            if campo not in respuesta:
                return False, f"Respuesta {i+1}: falta el campo {campo}"
        
        # Validar tipos
        if not isinstance(respuesta['pregunta_id'], str):
            return False, f"Respuesta {i+1}: pregunta_id debe ser string"
        
        if not validate_nivel(respuesta['dificultad']):
            return False, f"Respuesta {i+1}: dificultad debe estar entre 1 y 5"
        
        if not isinstance(respuesta['correcta'], bool):
            return False, f"Respuesta {i+1}: correcta debe ser booleano"
    
    return True, "Lista de respuestas válida"


def sanitize_texto(texto: str, max_length: int = None) -> str:
    """
    Limpia un texto eliminando caracteres peligrosos
    
    Args:
        texto: Texto a limpiar
        max_length: Longitud máxima opcional
        
    Returns:
        Texto limpio
    """
    if not isinstance(texto, str):
        return ""
    
    # Eliminar espacios extras
    texto = texto.strip()
    
    # Limitar longitud si se especifica
    if max_length and len(texto) > max_length:
        texto = texto[:max_length]
    
    return texto


def validate_spreadsheet_id(spreadsheet_id: str) -> bool:
    """
    Valida que un spreadsheet ID tenga el formato correcto
    
    Args:
        spreadsheet_id: ID del spreadsheet de Google
        
    Returns:
        True si es válido
    """
    if not isinstance(spreadsheet_id, str):
        return False
    
    # Un spreadsheet ID típicamente tiene 44 caracteres y contiene letras, números, guiones y guiones bajos
    if len(spreadsheet_id) < 20:
        return False
    
    if not re.match(r'^[a-zA-Z0-9_-]+$', spreadsheet_id):
        return False
    
    return True


def validate_pregunta_estructura_v1_compatible(pregunta: Dict[str, Any]) -> tuple[bool, List[str], List[str]]:
    """
    Valida una pregunta contra el esquema compatible con el motor actual
    y permite extensiones opcionales (ej. soporte de imagen futuro).

    Requeridos (compatibilidad runtime):
      id, dificultad, categoria, pregunta, opciones(dict), respuesta_correcta

    Opcionales:
      explicacion, tipo, imagen, imagen_caption, imagen_ancho,
      imagen_generator_id, imagen_params

    Returns:
        (es_valida, errores, advertencias)
    """
    errores: List[str] = []
    advertencias: List[str] = []

    if not isinstance(pregunta, dict):
        return False, ["La pregunta debe ser un diccionario"], []

    campos_requeridos = [
        'id',
        'dificultad',
        'categoria',
        'pregunta',
        'opciones',
        'respuesta_correcta'
    ]

    for campo in campos_requeridos:
        if campo not in pregunta:
            errores.append(f"Falta campo requerido: {campo}")

    # Tipos/campos básicos
    if 'id' in pregunta and (not isinstance(pregunta['id'], str) or not pregunta['id'].strip()):
        errores.append("id debe ser string no vacío")

    if 'dificultad' in pregunta and not validate_nivel(pregunta['dificultad']):
        errores.append("dificultad debe ser entero entre 1 y 5")

    if 'categoria' in pregunta and (not isinstance(pregunta['categoria'], str) or not pregunta['categoria'].strip()):
        errores.append("categoria debe ser string no vacío")

    if 'pregunta' in pregunta and (not isinstance(pregunta['pregunta'], str) or not pregunta['pregunta'].strip()):
        errores.append("pregunta debe ser string no vacío")

    # Opciones esperadas por runtime actual
    if 'opciones' in pregunta:
        opciones = pregunta['opciones']
        if not isinstance(opciones, dict):
            errores.append("opciones debe ser un diccionario (ej. {'a': '...', 'b': '...'})")
        else:
            if len(opciones) < 2:
                errores.append("opciones debe tener al menos 2 entradas")
            for key, value in opciones.items():
                if not isinstance(key, str) or not key.strip():
                    errores.append("cada clave de opciones debe ser string no vacío")
                    break
                if not isinstance(value, str) or not value.strip():
                    errores.append("cada valor de opciones debe ser string no vacío")
                    break

    if 'respuesta_correcta' in pregunta:
        if not isinstance(pregunta['respuesta_correcta'], str) or not pregunta['respuesta_correcta'].strip():
            errores.append("respuesta_correcta debe ser string no vacío")
        elif isinstance(pregunta.get('opciones'), dict) and pregunta['respuesta_correcta'] not in pregunta['opciones']:
            errores.append("respuesta_correcta debe existir como clave en opciones")

    # Extensiones opcionales
    if 'explicacion' in pregunta and not isinstance(pregunta['explicacion'], str):
        errores.append("explicacion debe ser string")

    if 'tipo' in pregunta and pregunta['tipo'] not in ['texto', 'imagen']:
        advertencias.append("tipo recomendado: 'texto' o 'imagen'")

    if 'imagen' in pregunta and (not isinstance(pregunta['imagen'], str) or not pregunta['imagen'].strip()):
        errores.append("imagen debe ser string no vacío cuando se incluya")

    if 'imagen_caption' in pregunta and not isinstance(pregunta['imagen_caption'], str):
        errores.append("imagen_caption debe ser string")

    if 'imagen_ancho' in pregunta:
        ancho = pregunta['imagen_ancho']
        if not ((isinstance(ancho, int) and ancho > 0) or ancho == 'auto'):
            errores.append("imagen_ancho debe ser entero positivo o 'auto'")

    if 'imagen_generator_id' in pregunta and (
        not isinstance(pregunta['imagen_generator_id'], str) or not pregunta['imagen_generator_id'].strip()
    ):
        errores.append("imagen_generator_id debe ser string no vacío")

    if 'imagen_params' in pregunta and not isinstance(pregunta['imagen_params'], dict):
        errores.append("imagen_params debe ser un diccionario")

    if pregunta.get('tipo') == 'imagen':
        if not pregunta.get('imagen') and not pregunta.get('imagen_generator_id'):
            advertencias.append("tipo='imagen' pero no se definió imagen ni imagen_generator_id")

    es_valida = len(errores) == 0
    return es_valida, errores, advertencias


def validate_banco_preguntas_v1_compatible(preguntas: List[Dict[str, Any]]) -> tuple[bool, List[str], List[str]]:
    """
    Valida una lista de preguntas para compatibilidad con el runtime actual,
    detectando errores de esquema e IDs duplicados.

    Returns:
        (es_valido, errores, advertencias)
    """
    errores: List[str] = []
    advertencias: List[str] = []

    if not isinstance(preguntas, list):
        return False, ["El banco debe ser una lista de preguntas"], []

    if len(preguntas) == 0:
        return False, ["El banco está vacío"], []

    ids_vistos = set()
    ids_duplicados = set()

    for idx, pregunta in enumerate(preguntas, start=1):
        es_valida, errs, warns = validate_pregunta_estructura_v1_compatible(pregunta)

        for err in errs:
            errores.append(f"Pregunta #{idx}: {err}")
        for warn in warns:
            advertencias.append(f"Pregunta #{idx}: {warn}")

        pregunta_id = pregunta.get('id') if isinstance(pregunta, dict) else None
        if isinstance(pregunta_id, str) and pregunta_id:
            if pregunta_id in ids_vistos:
                ids_duplicados.add(pregunta_id)
            ids_vistos.add(pregunta_id)

        if not es_valida:
            continue

    if ids_duplicados:
        errores.append(f"IDs duplicados detectados: {', '.join(sorted(ids_duplicados))}")

    return len(errores) == 0, errores, advertencias
