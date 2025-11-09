"""
Learning module for intelligent test data generation

This module provides functionality for:
- Pattern extraction from successful test runs
- Learning data relationships between endpoints
- Smart test data generation based on learned patterns
- Baseline tracking and regression detection
"""

from apitest.learning.pattern_extractor import PatternExtractor
from apitest.learning.data_generator import SmartDataGenerator

__all__ = ['PatternExtractor', 'SmartDataGenerator']

