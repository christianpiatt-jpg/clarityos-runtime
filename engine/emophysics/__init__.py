"""
Emotional Physics Engine for ClarityOS
Implements validated models for pressure, conversion, thresholds, and relational dynamics.
"""

from .pressure import PressureModel
from .conversion import ConversionModel
from .threshold import ThresholdModel
from .relational import RelationalModel
from .state import EmotionalState

__version__ = "1.0.0"
__all__ = [
    "PressureModel",
    "ConversionModel",
    "ThresholdModel",
    "RelationalModel",
    "EmotionalState",
]
