"""
nova_senses -- Nova Perception Package
Import directly:
    from nova_senses.eyes import NovaEyes
    from nova_senses.proprioception import NovaExplorer
    from nova_senses.vision import NovaVision
"""
# No wildcard imports -- eyes.py imports from nova_senses.proprioception and
# nova_senses.vision, which causes a circular import if loaded here at
# package init time. Always import submodules directly.
