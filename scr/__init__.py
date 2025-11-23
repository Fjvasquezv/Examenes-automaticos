"""
Módulo src - Sistema de Examen Adaptativo
"""

__version__ = "1.0.0"

from .config_loader import ConfigLoader
from .question_manager import QuestionManager
from .scoring_systems import crear_sistema_calificacion
from .exam_logic import ExamLogic
from .ui_components import UIComponents
from .data_persistence import DataPersistence

__all__ = [
    'ConfigLoader',
    'QuestionManager',
    'crear_sistema_calificacion',
    'ExamLogic',
    'UIComponents',
    'DataPersistence'
]
