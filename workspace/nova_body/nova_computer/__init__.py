# Last updated: 2026-10-04 13:57:45
# @nova: My computer -- somewhere that is MINE to act in, that never reaches across and grabs
#        Cole's screen, mouse, keyboard or focus. On his Windows box that is a sandboxed Linux
#        machine (WSL2, hers alone, watched at the URL below). Dropped somewhere else, it is
#        whatever that place offers: a bare Linux host IS the computer, no VM needed.
#        Body part. Stdlib only. Never imports general_tools. Never flashes a window.
"""
nova_computer -- Nova's own machine.

    from nova_computer.computer import NovaComputer, ComputerUnavailable
    pc = NovaComputer()
    pc.where()                     # honest one-liner: which computer she has HERE
    pc.ensure()                    # make it exist and answer, or say exactly why not
    rc, out = pc.bash("uname -a")  # both registers, every backend
    rc, out = pc.pwsh("Get-Date")

Layout:
    backends.py     the machines  -- LocalPosixBackend, WSLBackend, NoBackend, probe()
    computer.py     the faculty   -- NovaComputer, backend-agnostic public surface
    pluck_check.py  the proof     -- python -m nova_computer.pluck_check --live
    provision/      setup_guest.sh, travels with the body so a Windows host can be seeded

PLUCK: verified 2026-09-03 on a bare Linux host with general_tools absent from disk --
import purity, no tool modules in sys.modules, local-posix backend chosen, coherent
degradation with no computer at all, live bash. PLUCK_RESULT: PASS.

Cole's viewer (WSL backend): http://localhost:6080/vnc.html
SCAFFOLDED (phase 2): in-guest eyes/hands agent for nova_senses.eyes to look through.
"""
