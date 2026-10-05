# Last updated: 2026-10-05 21:33:05
# @nova: Nova's model updater: finds newer dense models, installs them with rollback, and trains LoRAs for installed models.
"""Model updater for Nova (a general tool, not a body part).

Entry points:
  check.start_background_check()   lightweight check at each Nova Chat start
  api.create_router(...)           FastAPI routes for the Nova Chat notification and widget
  python -m nova_updater ...       command line for tests and agents

Nothing in this package downloads a model or spends money unless a person confirms it.
"""
__version__ = "1.0.0"
