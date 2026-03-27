"""
nova_perception -- Nova Perception Package
Import directly:
    from nova_perception.eyes import NovaEyes
    from nova_perception.explorer import NovaExplorer
    from nova_perception.vision import NovaVision
"""
# No wildcard imports -- eyes.py imports from nova_perception.explorer and
# nova_perception.vision, which causes a circular import if loaded here at
# package init time. Always import submodules directly.
