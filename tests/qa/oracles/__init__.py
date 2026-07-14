"""Independently-written closed-form oracles for the D226 QA harness.

HARD RULE (structurally enforced by ``tests/qa/test_spotcheck.py``):
no module in this package may import ``regolith.harness.models`` or
``feldspar`` -- every formula here is written fresh from the cited
source, never by calling or copying the model under test.
"""
