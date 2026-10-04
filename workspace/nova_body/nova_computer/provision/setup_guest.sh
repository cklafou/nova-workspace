#!/usr/bin/env bash
# @nova: Provision Nova's guest desktop, browser compatibility and intentionally enabled Windows access.
# Nova's computer - guest provisioning (Phase 1). Written by Claude, 2026-09-03.
# Run as root INSIDE the Ubuntu-24.04 WSL distro:
#   wsl -d Ubuntu-24.04 -u root -- bash /mnt/c/Users/lafou/Project_Nova/workspace/nova_body/nova_computer/provision/setup_guest.sh
# Idempotent: safe to re-run. Log: /var/log/nova_setup.log
set -uo pipefail
exec > >(tee -a /var/log/nova_setup.log) 2>&1
echo "==== nova setup $(date) ===="
if [ "$(id -u)" != 0 ]; then echo "ERROR: run as root (add -u root)"; exit 1; fi
export DEBIAN_FRONTEND=noninteractive

echo "--- base packages ---"
apt-get update -y
apt-get install -y xfce4 xfce4-goodies dbus-x11 tigervnc-standalone-server novnc websockify \
  python3-pip python3-venv python3-xlib scrot xdotool wget curl git nano htop \
  || { echo "ERROR: base packages failed"; exit 1; }
apt-get install -y firefox || echo "WARN: firefox install failed - a browser can be added later"

echo "--- PowerShell 7 (so she has BOTH pwsh and bash) ---"
if ! command -v pwsh >/dev/null 2>&1; then
  . /etc/os-release
  wget -q "https://packages.microsoft.com/config/ubuntu/${VERSION_ID}/packages-microsoft-prod.deb" -O /tmp/msprod.deb \
    && dpkg -i /tmp/msprod.deb && apt-get update -y && apt-get install -y powershell \
    || echo "WARN: pwsh install failed (non-fatal, retry later)"
fi

echo "--- user: nova ---"
if ! id -u nova >/dev/null 2>&1; then useradd -m -s /bin/bash nova; fi
# 2026-09-03: on this image "nova" already existed as a SYSTEM user (uid 115) whose passwd
# home was /var/lib/nova, while her whole desktop lives in /home/nova -- WSL then tried to
# chdir into a directory that did not exist on every single command. Pin her home.
systemctl stop nova-vnc nova-novnc 2>/dev/null; pkill -u nova 2>/dev/null; sleep 1
usermod -d /home/nova nova || echo 'WARN: usermod refused - her processes still running'
mkdir -p /home/nova && chown -R nova:nova /home/nova

# If an existing account kept a nonstandard home, Snap Firefox needs its real
# parent registered. Preserve other homedirs; do not move account data to fix a browser.
# snapd >= 2.59: https://snapcraft.io/docs/explanation/how-snaps-work/home-outside-home/
nova_home=$(getent passwd nova | cut -d: -f6)
case "$nova_home" in
  /home/*) ;;  # Snap already supports ordinary /home users.
  /*)
    if command -v snap >/dev/null 2>&1; then
      nova_home_parent=$(dirname "$nova_home")
      nova_snap_homes=$(snap get system homedirs 2>/dev/null || true)
      if [ "$nova_home_parent" != / ]; then
        case ",$nova_snap_homes," in
          *",$nova_home_parent,"*) ;;
          *) snap set system homedirs="${nova_snap_homes:+$nova_snap_homes,}$nova_home_parent" \
               || echo 'WARN: Snap home configuration failed; check firefox --version before using the browser' ;;
        esac
      fi
    fi
    ;;
esac
usermod -aG sudo nova
echo 'nova ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/nova
chmod 440 /etc/sudoers.d/nova

echo "--- VNC desktop for user nova ---"
install -d -m 700 -o nova -g nova /home/nova/.vnc
if [ ! -f /home/nova/.vnc/passwd ]; then
  VNCPASS=$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 12)
  echo "$VNCPASS" | vncpasswd -f > /home/nova/.vnc/passwd
  chmod 600 /home/nova/.vnc/passwd; chown nova:nova /home/nova/.vnc/passwd
  echo "$VNCPASS" > /root/nova_vnc_password.txt; chmod 600 /root/nova_vnc_password.txt
  echo ">>> VNC PASSWORD (also saved in /root/nova_vnc_password.txt): $VNCPASS"
else
  echo "VNC password already set - see /root/nova_vnc_password.txt"
fi
cat > /home/nova/.vnc/xstartup <<'XS'
#!/bin/sh
unset SESSION_MANAGER DBUS_SESSION_BUS_ADDRESS
exec startxfce4
XS
chmod +x /home/nova/.vnc/xstartup; chown nova:nova /home/nova/.vnc/xstartup

echo "--- services (VNC + noVNC web viewer) ---"
cat > /etc/systemd/system/nova-vnc.service <<'UNIT'
[Unit]
Description=Nova desktop (TigerVNC :1)
After=network.target

[Service]
Type=simple
User=nova
Environment=HOME=/home/nova
WorkingDirectory=/home/nova
# WSLg mounts /tmp/.X11-unix read-only. Give this service its own writable X1
# socket directory; the host's WSLg X0 mount stays intact. External guest clients
# can still use X1's authenticated abstract Unix socket.
RuntimeDirectory=nova-x11
RuntimeDirectoryMode=1777
BindPaths=/run/nova-x11:/tmp/.X11-unix
ExecStartPre=-/usr/bin/tigervncserver -kill :1
# A killed VNC server leaves .Xauthority-c/-l and /tmp/.X1-lock behind; xauth then blocks
# ("timeout in locking authority file") and :5901 never binds. Clear them every start.
ExecStartPre=-/bin/rm -f /home/nova/.Xauthority-c /home/nova/.Xauthority-l /tmp/.X1-lock /tmp/.X11-unix/X1
ExecStart=/usr/bin/tigervncserver :1 -geometry 1600x900 -depth 24 -localhost yes -fg
Restart=on-failure

[Install]
WantedBy=multi-user.target
UNIT
cat > /etc/systemd/system/nova-novnc.service <<'UNIT'
[Unit]
Description=Nova desktop viewer (noVNC on port 6080)
After=nova-vnc.service

[Service]
Type=simple
ExecStart=/usr/bin/websockify --web=/usr/share/novnc 6080 localhost:5901
Restart=on-failure

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable nova-vnc nova-novnc

echo "--- sandbox hardening (/etc/wsl.conf) - takes effect after wsl --terminate ---"
cat > /etc/wsl.conf <<CONF
[boot]
systemd=true

[user]
default=nova

# 2026-09-04, Cole's decision: her computer is HIS computer seen through her own environment.
# Whole drive read-write; metadata gives real Linux permissions on Windows files.
# (This replaced the 09-02 sealed sandbox on purpose - the safety net is snapshots now.)
[automount]
enabled=true
root=/mnt/
options="metadata,uid=$(id -u nova),gid=$(id -g nova),umask=22,fmask=11"
mountFsTab=true

# Full interop: any Windows program is callable from her shell.
# Note: a Windows GUI app launched from here renders on COLE'S desktop and takes his focus.
# Her own Linux apps run on her X display and never do.
[interop]
enabled=true
appendWindowsPath=true

[network]
hostname=nova-computer
CONF

echo "nova-computer provisioned $(date -Iseconds)" > /etc/nova-computer

echo "--- landing dir: WSL must always have a real cwd to chdir into ---"
mkdir -p /var/lib/nova && chown nova:nova /var/lib/nova

echo "--- drop folder: the ONE shared path with the host ---"
mkdir -p /mnt/drop
grep -q '/mnt/drop' /etc/fstab 2>/dev/null \
  || echo "C:/Users/lafou/Project_Nova/NovaDrop /mnt/drop drvfs defaults,nofail,uid=$(id -u nova),gid=$(id -g nova) 0 0" >> /etc/fstab

cp -f "$0" /root/setup_guest.sh 2>/dev/null || true
echo "==== DONE. Next steps: exit this shell, then on Windows:"
echo "  wsl --terminate Ubuntu-24.04     (applies the sandbox)"
echo "  wsl -d Ubuntu-24.04              (boots her computer; keep the window open)"
echo "  browser -> http://localhost:6080/vnc.html  (her desktop; password above)"
