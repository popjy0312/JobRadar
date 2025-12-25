"""
Recruit - Job posting monitoring system
"""

__version__ = "1.0.0"
__author__ = "Recruit Project"

from .parser import get_parser
from .matcher import JobMatcher
from .notifier import Notifier
from .scheduler import JobScheduler

__all__ = [
    'get_parser',
    'JobMatcher',
    'Notifier',
    'JobScheduler',
]

