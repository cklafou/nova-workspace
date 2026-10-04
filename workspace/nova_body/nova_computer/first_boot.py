# Last updated: 2026-10-04 13:57:45
# @nova: One-shot first boot of her computer, run via RUN_SETUP.cmd. Logs everything.
import json, sys, traceback
sys.stdout.reconfigure(line_buffering=True)
try:
    from nova_computer.computer import NovaComputer, ComputerUnavailable
    pc = NovaComputer()
    print("[1/5] status before:", json.dumps(pc.status()))
    print("[2/5] ensure() - registering/provisioning as needed; this can take many minutes...")
    s = pc.ensure()
    print("[2/5] ensured:", json.dumps(s))
    rc, out = pc.bash("echo hello-from-my-computer && uname -a && whoami")
    print("[3/5] bash check rc=", rc, ":", out)
    rc, out = pc.pwsh("'pwsh alive: ' + $PSVersionTable.PSVersion.ToString()")
    print("[4/5] pwsh check rc=", rc, ":", out)
    rc, out, err = pc._exec_root("cat /root/nova_vnc_password.txt 2>/dev/null")
    print("[5/5] vnc password:", out or "(not set - check provision log)")
    print("DESKTOP VIEWER:", pc.desktop_url)
    print("FIRST_BOOT_RESULT: SUCCESS")
except Exception as e:
    print("FIRST_BOOT_RESULT: FAILED:", e)
    traceback.print_exc()
