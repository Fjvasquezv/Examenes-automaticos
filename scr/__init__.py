"""
Módulo src - Sistema de Examen Adaptativo
"""

__version__ = "1.0.0"
__author__ = "Sistema de Examen Adaptativo"

from .config_loader import ConfigLoader
from .question_manager import QuestionManager
from .scoring_systems import (
    ScoringSystem,
    IRTSimplificado,
    SistemaElo,
    SistemaHibrido,
    crear_sistema_calificacion
)
from .exam_logic import ExamLogic
from .ui_components import UIComponents
from .data_persistence import DataPersistence

__all__ = [
    'ConfigLoader',
    'QuestionManager',
    'ScoringSystem',
    'IRTSimplificado',
    'SistemaElo',
    'SistemaHibrido',
    'crear_sistema_calificacion',
    'ExamLogic',
    'UIComponents',
    'DataPersistence'
]
