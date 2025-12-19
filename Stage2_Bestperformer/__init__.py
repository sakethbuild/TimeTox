"""
Stage2_Bestperformer: Two-Stage LLM Pipeline for Time-Toxic Days Extraction

This pipeline achieved 100% clinical accuracy (±3 days) on 20 synthetic schedules.
"""

from .pipeline import run_pipeline, load_ground_truth, compute_metrics

__all__ = ['run_pipeline', 'load_ground_truth', 'compute_metrics']

