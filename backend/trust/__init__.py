"""
Trust layer: uncertainty-aware attribution, history reliability, and calibrated
confidence. This package sits *above* attribution/scoring/integrity and consumes
their outputs — it never rewrites them. Its job is to quantify how much the system
should be believed, and to ensure GitSight never implies certainty it does not have.
"""
