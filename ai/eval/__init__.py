"""Evaluation harness — ground-truth labels, scoring, and artifact diagnostics.

This package is the measurement layer for the processing pipeline. Nothing in
here is imported by the pipeline itself; it only reads pipeline output (from
PostgreSQL) and compares it against hand-labelled ground truth.

Entry point:  python -m eval.cli --help   (run from the ai/ directory)
"""
