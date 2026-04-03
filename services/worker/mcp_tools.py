"""Backward-compatible re-export of CodeQueryTools from shared module.

New code should import from shared.code_query_tools directly.
"""
from shared.code_query_tools import CodeQueryTools

__all__ = ["CodeQueryTools"]
