#!/usr/bin/env python3
"""
DCTimer: Red Team Time Synchronization Tool

Synchronizes system or process time with a Domain Controller (DC) or NTP server.

Author: MAAYTHM (https://github.com/MAAYTHM)
"""

import argparse
import os
import sys
import platform
import subprocess
import shutil
import time
import signal
import threading
import shlex
from datetime import datetime, timezone

try:
    import ntplib
except ImportError:
    print("[-] ntplib is required. Install with: pip install ntplib")
    sys.exit(1)

DEFAULT_NTP_PORT = 123
DEFAULT_NTP_SERVERS = ["pool.ntp.org", "time.nist.gov", "time.google.com"]
BACKUP_SUFFIX = ".dctimer.bak"
VERBOSE = False
QUIET = False
COLORLESS = False

NTP_TIME_holder = None
Setting_time = None
ntp_lock = threading.Lock()

def get_virtual_ntp_time():
    with ntp_lock:
        if NTP_TIME_holder is None or Setting_time is None:
            return None
        offset = datetime.now(timezone.utc) - Setting_time
        return NTP_TIME_holder + offset

def update_ntp_reference(new_ntp_time):
    global NTP_TIME_holder, Setting_time
    with ntp_lock:
        NTP_TIME_holder = new_ntp_time
        Setting_time = datetime.now(timezone.utc)

class Colors:
    RED = ''
    GREEN = ''
    YELLOW = ''
    BLUE = ''
    PURPLE = ''
    CYAN = ''
    BOLD = ''
    END = ''
    MAGENTA = ''
    @staticmethod
    def enable():
        Colors.RED = '\033[91m'
        Colors.GREEN = '\033[92m'
        Colors.YELLOW = '\033[93m'
        Colors.BLUE = '\033[94m'
        Colors.PURPLE = '\033[95m'
        Colors.CYAN = '\033[96m'
        Colors.BOLD = '\033[1m'
        Colors.MAGENTA = '\033[35m'
        Colors.END = '\033[0m'
    @staticmethod
    def disable():
        Colors.RED = Colors.GREEN = Colors.YELLOW = Colors.BLUE = Colors.PURPLE = Colors.CYAN = Colors.BOLD = Colors.END = Colors.MAGENTA = ''

def log(message, level="INFO", color=""):
    if QUIET:
        return
    timestamp = datetime.now().strftime("%H:%M:%S")
    if color:
        print(f"{color}[{timestamp}] {level}: {message}{Colors.END}")
    else:
        print(f"[{timestamp}] {level}: {message}")

def verbose_log(message, level="INFO"):
    if not VERBOSE or QUIET:
        return
    color = {
        "INFO": Colors.BLUE,
        "WARNING": Colors.YELLOW,
        "ERROR": Colors.RED,
        "SUCCESS": Colors.GREEN,
        "CMD": Colors.MAGENTA + Colors.BOLD
    }.get(level, Colors.BLUE)
    log(message, f"VERBOSE-{level}", color)

def error_log(message):
    if QUIET:
        return
    log(message, "ERROR", Colors.RED)

def success_log(message):
    if QUIET:
        return
    log(message, "SUCCESS", Colors.GREEN)

def warning_log(message):
    if QUIET:
        return
    log(message, "WARNING", Colors.YELLOW)

def info_log(message):
    if QUIET:
        return
    log(message, "INFO", Colors.BLUE)

def is_linux():
    return sys.platform.startswith("linux")

def is_root():
    return os.geteuid() == 0 if hasattr(os, "geteuid") else False

def run_command(cmd, check=True, capture_output=True, shell=False, env=None, verbose_cmd=True):
    # verbose_cmd: whether to print the command in verbose mode
    if VERBOSE and not QUIET and verbose_cmd:
        if isinstance(cmd, list):
            verbose_log(f"Running command: {Colors.MAGENTA}{' '.join(shlex.quote(str(x)) for x in cmd)}{Colors.END}", level="CMD")
        else:
            verbose_log(f"Running command: {Colors.MAGENTA}{cmd}{Colors.END}", level="CMD")
    try:
        is_string_command = isinstance(cmd, str)
        if env is None:
            env = os.environ.copy()
        result = subprocess.run(
            cmd,
            shell=is_string_command,
            capture_output=capture_output,
            text=True,
            check=check,
            env=env
        )
        if VERBOSE and not QUIET and capture_output and verbose_cmd:
            if result.stdout:
                verbose_log(f"stdout: {result.stdout.strip()}", level="SUCCESS")
            if result.stderr:
                verbose_log(f"stderr: {result.stderr.strip()}", level="WARNING")
        return result
    except subprocess.CalledProcessError as e:
        if not QUIET:
            error_log(f"Command failed: {e}")
        if VERBOSE and not QUIET and hasattr(e, 'stdout') and e.stdout:
            verbose_log(f"Failed command output: {e.stdout}", level="ERROR")
        if VERBOSE and not QUIET and hasattr(e, 'stderr') and e.stderr:
            verbose_log(f"Failed command stderr: {e.stderr}", level="ERROR")
        return None

def backup_file(filepath):
    backup_path = f"{filepath}{BACKUP_SUFFIX}"
    if os.path.exists(backup_path):
        verbose_log(f"Backup already exists: {backup_path}", level="WARNING")
        verbose_log(f"Suggestion: Remove backup or restore before proceeding.", level="INFO")
        return backup_path
    if os.path.exists(filepath):
        try:
            shutil.copy2(filepath, backup_path)
            verbose_log(f"Backed up {filepath} to {backup_path}", level="SUCCESS")
            return backup_path
        except Exception as e:
            verbose_log(f"Failed to backup {filepath}: {e}", level="ERROR")
    else:
        verbose_log(f"Config file {filepath} does not exist; skipping backup.", level="WARNING")
    return None

def restore_file(filepath):
    backup_path = f"{filepath}{BACKUP_SUFFIX}"
    if not os.path.exists(backup_path):
        verbose_log(f"No backup found for {filepath}", level="WARNING")
        verbose_log(f"Suggestion: Check if backup exists or restore manually.", level="INFO")
        return False
    try:
        shutil.copy2(backup_path, filepath)
        os.remove(backup_path)
        verbose_log(f"Restored {filepath} from backup", level="SUCCESS")
        return True
    except Exception as e:
        verbose_log(f"Failed to restore {filepath}: {e}", level="ERROR")
        return False

def get_env_ip():
    return os.environ.get("IP")

def get_local_time():
    return datetime.now()

def get_ntp_time(server, port=123):
    try:
        verbose_log(f"Fetching time from {server}:{port}", level="INFO")
        client = ntplib.NTPClient()
        response = client.request(server, port=port, version=3)
        ntp_time = datetime.fromtimestamp(response.tx_time, tz=timezone.utc)
        local_time = datetime.now(tz=timezone.utc)
        offset = (ntp_time - local_time).total_seconds()
        verbose_log(f"NTP time: {ntp_time}", level="SUCCESS")
        verbose_log(f"Local time: {local_time}", level="INFO")
        verbose_log(f"Offset: {offset:.3f} seconds", level="INFO")
        return {
            'ntp_time': ntp_time,
            'local_time': local_time,
            'offset': offset,
            'tx_time': response.tx_time
        }
    except Exception as e:
        if VERBOSE and not QUIET:
            error_log(f"Failed to fetch NTP time from {server}:{port} - {e}")
        return None

def print_cross_platform_tips(server, port, time_info):
    if QUIET:
        return
    system = platform.system()
    print(f"\n{Colors.YELLOW}=== Cross-Platform Time Sync Information ==={Colors.END}")
    print(f"Target Server: {server}:{port}")
    print(f"Server Time: {time_info['ntp_time']}")
    print(f"Local Time: {time_info['local_time']}")
    print(f"Offset: {time_info['offset']:.3f} seconds")
    if system == "Windows":
        print(f"\n{Colors.CYAN}Windows Manual Sync:{Colors.END}")
        print(f"1. Run as Administrator:")
        print(f"   w32tm /config /manualpeerlist:\"{server}\" /syncfromflags:manual")
        print(f"   w32tm /resync")
        print(f"2. Or use GUI: Date & Time Settings > Additional date, time, & regional settings")
    elif system == "Darwin":
        print(f"\n{Colors.CYAN}macOS Manual Sync:{Colors.END}")
        print(f"1. System Preferences > Date & Time")
        print(f"2. Uncheck 'Set date and time automatically'")
        print(f"3. Manually set to: {time_info['ntp_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"4. Or use terminal: sudo sntp -sS {server}")
    print(f"\n{Colors.RED}OPSEC Note:{Colors.END} Manual time changes may be logged by the system")

# =========================
# Technique Classes
# =========================

class TimeSyncTechnique:
    def __init__(self, name, number, supports_custom_port=False, needs_config=False, needs_service=False, supports_shell=False):
        self.name = name
        self.number = number
        self.supports_custom_port = supports_custom_port
        self.needs_config = needs_config
        self.needs_service = needs_service
        self.supports_shell = supports_shell
        self.active = False
        self.last_error = None
    def is_available(self): raise NotImplementedError
    def sync_time(self, server, port=123): raise NotImplementedError
    def reset(self): pass

class NTPDateTechnique(TimeSyncTechnique):
    def __init__(self):
        super().__init__("ntpdate", 1, supports_custom_port=False, needs_config=False, needs_service=False, supports_shell=False)
    def is_available(self):
        if shutil.which("ntpdate") is None:
            self.last_error = "ntpdate not found in PATH"
            return False
        if not is_linux():
            self.last_error = "ntpdate is only supported on Linux"
            return False
        return True
    def sync_time(self, server, port=123):
        try:
            result = run_command(["timedatectl", "set-ntp", "off"], check=False, capture_output=True, verbose_cmd=True)
            if result is not None and result.returncode != 0:
                warning_log("Could not disable system NTP: " + (result.stderr.strip() if result.stderr else "Unknown error"))
                warning_log("Note: The ntpdate technique is temporary and system time may be reset at any time by the OS or background services.")
        except Exception as e:
            warning_log(f"Could not disable system NTP: {e}")
            warning_log("Note: The ntpdate technique is temporary and system time may be reset at any time by the OS or background services.")
        if not is_root():
            self.last_error = "Root required for ntpdate"
            return False
        if port != 123:
            self.last_error = "ntpdate does not support custom ports"
        result = run_command(["ntpdate", "-u", server], capture_output=True, verbose_cmd=True)
        if result is None or result.returncode != 0:
            if result and result.stderr and "System has not been booted with systemd" in result.stderr:
                self.last_error = "Systemd is not available (container or minimal OS). Technique not supported."
            else:
                self.last_error = "ntpdate command failed"
            return False
        self.active = True
        return True
    def reset(self):
        run_command(["timedatectl", "set-ntp", "true"], check=False, capture_output=True, verbose_cmd=True)

class NTPDTechnique(TimeSyncTechnique):
    def __init__(self):
        super().__init__("ntpd", 2, supports_custom_port=False, needs_config=True, needs_service=True, supports_shell=True)
        self.config_file = "/etc/ntp.conf"
    def is_available(self):
        if shutil.which("ntpd") is None:
            self.last_error = "ntpd not found in PATH"
            return False
        if not is_linux():
            self.last_error = "ntpd is only supported on Linux"
            return False
        return True
    def sync_time(self, server, port=123):
        if not is_root():
            self.last_error = "Root required for ntpd"
            return False
        if port != 123:
            self.last_error = "ntpd does not support custom ports"
        backup_file(self.config_file)
        conf_content = f"server {server} iburst\n"
        try:
            with open(self.config_file, "w") as f:
                f.write(conf_content)
        except Exception as e:
            self.last_error = f"Failed to write ntpd config: {e}"
            return False
        # Run the actual service commands and check for errors
        result1 = run_command(["systemctl", "restart", "ntp"], capture_output=True, verbose_cmd=True)
        if result1 is None or result1.returncode != 0:
            self.last_error = "systemctl restart ntp failed"
            return False
        result2 = run_command(["systemctl", "enable", "ntp"], capture_output=True, verbose_cmd=True)
        if result2 is None or result2.returncode != 0:
            self.last_error = "systemctl enable ntp failed"
            return False
        self.active = True
        return True
    def reset(self):
        run_command(["timedatectl", "set-ntp", "true"], check=False, capture_output=True, verbose_cmd=True)
        restore_file(self.config_file)

class SystemdTimesyncTechnique(TimeSyncTechnique):
    def __init__(self):
        super().__init__("systemd-timesyncd", 3, supports_custom_port=False, needs_config=True, needs_service=True, supports_shell=True)
        self.config_file = "/etc/systemd/timesyncd.conf"
    def is_available(self):
        if not os.path.exists("/lib/systemd/systemd-timesyncd"):
            self.last_error = "systemd-timesyncd not found"
            return False
        if not is_linux():
            self.last_error = "systemd-timesyncd is only supported on Linux"
            return False
        return True
    def sync_time(self, server, port=123):
        if not is_root():
            self.last_error = "Root required for systemd-timesyncd"
            return False
        if port != 123:
            self.last_error = "systemd-timesyncd does not support custom ports"
        backup_file(self.config_file)
        config_content = f"[Time]\nNTP={server}\nFallbackNTP={' '.join(DEFAULT_NTP_SERVERS)}\n"
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w') as f:
                f.write(config_content)
        except Exception as e:
            self.last_error = f"Failed to write timesyncd config: {e}"
            return False
        # Run the actual service commands and check for errors
        result1 = run_command(["systemctl", "enable", "systemd-timesyncd"], capture_output=True, verbose_cmd=True)
        if result1 is None or result1.returncode != 0:
            self.last_error = "systemctl enable systemd-timesyncd failed"
            return False
        result2 = run_command(["systemctl", "restart", "systemd-timesyncd"], capture_output=True, verbose_cmd=True)
        if result2 is None or result2.returncode != 0:
            self.last_error = "systemctl restart systemd-timesyncd failed"
            return False
        result3 = run_command(["timedatectl", "set-ntp", "true"], capture_output=True, verbose_cmd=True)
        if result3 is None or result3.returncode != 0:
            self.last_error = "timedatectl set-ntp true failed"
            return False
        self.active = True
        return True
    def reset(self):
        run_command(["timedatectl", "set-ntp", "true"], check=False, capture_output=True, verbose_cmd=True)
        restore_file(self.config_file)

class OpenNTPDTechnique(TimeSyncTechnique):
    def __init__(self):
        super().__init__("openntpd", 4, supports_custom_port=False, needs_config=True, needs_service=True, supports_shell=True)
        self.config_file = "/etc/openntpd/ntpd.conf"
    def is_available(self):
        if not shutil.which("ntpd") or not os.path.exists("/etc/openntpd"):
            self.last_error = "openntpd not found"
            return False
        if not is_linux():
            self.last_error = "openntpd is only supported on Linux"
            return False
        return True
    def sync_time(self, server, port=123):
        if not is_root():
            self.last_error = "Root required for openntpd"
            return False
        if port != 123:
            self.last_error = "openntpd does not support custom ports"
        backup_file(self.config_file)
        config_content = f"servers {server}\n"
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w') as f:
                f.write(config_content)
        except Exception as e:
            self.last_error = f"Failed to write openntpd config: {e}"
            return False
        # Run the actual service commands and check for errors
        result1 = run_command(["systemctl", "restart", "openntpd"], capture_output=True, verbose_cmd=True)
        if result1 is None or result1.returncode != 0:
            self.last_error = "systemctl restart openntpd failed"
            return False
        result2 = run_command(["systemctl", "enable", "openntpd"], capture_output=True, verbose_cmd=True)
        if result2 is None or result2.returncode != 0:
            self.last_error = "systemctl enable openntpd failed"
            return False
        self.active = True
        return True
    def reset(self):
        run_command(["timedatectl", "set-ntp", "true"], check=False, capture_output=True, verbose_cmd=True)
        restore_file(self.config_file)

class DynamicDateLoopTechnique(TimeSyncTechnique):
    def __init__(self):
        super().__init__("Dynamic Date Loop", 5, supports_custom_port=True, needs_config=False, needs_service=False, supports_shell=True)
        self._reset_needed = False
    def is_available(self):
        if not is_linux():
            self.last_error = "Dynamic Date Loop is only supported on Linux"
            return False
        if not is_root():
            self.last_error = "Root required for Dynamic Date Loop"
            return False
        return True
    def sync_time(self, server, port=123):
        vntp = get_virtual_ntp_time()
        if not vntp:
            self.last_error = "No virtual NTP time available"
            return False
        timestamp = int(vntp.timestamp())
        result = run_command(["date", "-s", f"@{timestamp}"], capture_output=True, verbose_cmd=True)
        if result is None or result.returncode != 0:
            self.last_error = "date command failed"
            return False
        self.active = True
        self._reset_needed = True
        return True
    def reset(self):
        if self._reset_needed:
            run_command(["timedatectl", "set-ntp", "true"], check=False, capture_output=True, verbose_cmd=True)
            self._reset_needed = False

class FaketimeTechnique(TimeSyncTechnique):
    def __init__(self):
        super().__init__("faketime", 6, supports_custom_port=True, needs_config=False, needs_service=False, supports_shell=True)
        self.faketime_str = None
    def is_available(self):
        if shutil.which("faketime") is None:
            self.last_error = "faketime not found in PATH"
            return False
        return True
    def sync_time(self, server, port=123):
        vntp = get_virtual_ntp_time()
        if not vntp:
            self.last_error = "No virtual NTP time available"
            return False
        self.faketime_str = f"@{int(vntp.timestamp())}"
        self.active = True
        return True
    def reset(self):
        pass

# =========================
# DCTimer Class and Main Entrypoint
# =========================
class DCTimer:
    def __init__(self):
        self.techniques = [
            NTPDateTechnique(), NTPDTechnique(), SystemdTimesyncTechnique(),
            OpenNTPDTechnique(), DynamicDateLoopTechnique(), FaketimeTechnique()
        ]
        self.active_technique = None
        self.failed_techniques = []

    def get_target_ip(self, args):
        if args.ip: return args.ip
        ip = get_env_ip()
        if ip: return ip
        error_log("No DC/NTP server IP specified. Use -i or set IP environment variable.")
        sys.exit(1)

    def validate_port(self, port):
        if not (1 <= port <= 65535):
            error_log(f"Invalid port {port}. Must be between 1 and 65535")
            sys.exit(1)
        return port

    def try_techniques(self, server, port, technique_num=None):
        self.failed_techniques = []
        if technique_num == 7:
            error_log("Technique 7 (Python monkey-patch) is not currently supported. This feature will be added in a future update.")
            sys.exit(1)
        techniques_to_try = self.techniques if technique_num is None else [self.techniques[technique_num-1]]
        for tech in techniques_to_try:
            if tech.is_available():
                verbose_log(f"Trying technique {tech.number}: {tech.name}", level="INFO")
                if tech.sync_time(server, port):
                    self.active_technique = tech
                    return True
                else:
                    # Container/Non-systemd detection
                    if tech.last_error and "System has not been booted with systemd" in tech.last_error:
                        if VERBOSE and not QUIET:
                            warning_log("This command cannot run in a container or system without systemd (such as many Docker containers).")
                            warning_log("Techniques 1, 2, 3, 4, 5, and 7 do not work in container-like systems.")
                    elif tech.last_error:
                        verbose_log(f"Technique {tech.number} {tech.name} failed: {tech.last_error}", level="WARNING")
                    self.failed_techniques.append((tech, tech.last_error or "Unknown error"))
            else:
                if tech.last_error and "System has not been booted with systemd" in tech.last_error:
                    if VERBOSE and not QUIET:
                        warning_log("This command cannot run in a container or system without systemd (such as many Docker containers).")
                        warning_log("Techniques 1, 2, 3, 4, 5, and 7 do not work in container-like systems.")
                elif tech.last_error:
                    verbose_log(f"Technique {tech.number} {tech.name} not available: {tech.last_error}", level="WARNING")
                self.failed_techniques.append((tech, tech.last_error or "Not available"))
        return False

    def print_failure_matrix(self):
        if QUIET:
            return
        print("\nTechnique Failure Summary:")
        print(f"{'No.':<4} {'Technique Name':<22} {'Reason'}")
        print("-"*60)
        for tech, reason in self.failed_techniques:
            print(f"{tech.number:<4} {tech.name:<22} {reason}")

    def print_success(self):
        if QUIET:
            return
        tech = self.active_technique
        print(f"Used Technique {tech.number}: {tech.name}")

    def reset_all(self):
        if not is_linux():
            error_log("Reset functionality is only available on Linux")
            return
        if not is_root():
            error_log("Root privileges required for reset")
            return
        info_log("Performing universal time sync reset (timedatectl set-ntp true)...")
        run_command(["timedatectl", "set-ntp", "true"], check=False, capture_output=not QUIET)
        info_log("Synchronizing with public NTP server (ntpdate pool.ntp.org)...")
        run_command(["ntpdate", "pool.ntp.org"], check=False, capture_output=not QUIET)
        success_log("Universal time sync restored (timedatectl set-ntp true; ntpdate pool.ntp.org).")
        if not QUIET:
            print("\nAdditional notes for manual restoration:")
            print("  - If you used ntpd: consider restoring /etc/ntp.conf from backup.")
            print("  - If you used openntpd: consider restoring /etc/openntpd/ntpd.conf from backup.")
            print("  - If you used systemd-timesyncd: consider restoring /etc/systemd/timesyncd.conf.")
            print("  - For faketime: no reset needed.")
            print("  - For Dynamic Date Loop: system time should be reset by universal restore.")
            print("  - For ntpdate: system time should be reset by universal restore.")
            print("  - Technique 7 (Python monkey-patch) is not currently supported.")

    def execute_command(self, command, server, port, technique_num=None):
        try:
            if not self.try_techniques(server, port, technique_num):
                self.print_failure_matrix()
                if not QUIET:
                    error_log("Time synchronization failed. No technique succeeded.")
                sys.exit(1)
            else:
                self.print_success()

            tech = self.active_technique
            # Handle faketime wrapping
            if isinstance(tech, FaketimeTechnique):
                if tech.faketime_str:
                    try:
                        cmd_args = shlex.split(command)
                        cmd_list = ["faketime", tech.faketime_str] + cmd_args
                        if VERBOSE and not QUIET:
                            verbose_log(f"Running command: {Colors.MAGENTA}{' '.join(shlex.quote(arg) for arg in cmd_list)}{Colors.END}", level="CMD")
                        result = subprocess.run(cmd_list, env=os.environ.copy(), capture_output=True, text=True)
                        if QUIET:
                            if result.stdout:
                                print(result.stdout, end="")
                            if result.stderr:
                                print(result.stderr, end="", file=sys.stderr)
                        else:
                            if result.stdout:
                                print(result.stdout, end="")
                            if result.stderr:
                                print(result.stderr, end="", file=sys.stderr)
                                if "faketime: Running specified command failed: No such file or directory" in result.stderr and VERBOSE:
                                    verbose_log("Note: This faketime error often means the command you provided is invalid or not found. Please check your command.", level="WARNING")
                            if result.returncode != 0 and not QUIET:
                                error_log(f"Command failed with exit code {result.returncode}")
                        return result.returncode
                    except Exception as e:
                        if VERBOSE and not QUIET:
                            error_log(f"Error executing command with faketime: {e}")
                        if not QUIET:
                            error_log("Failed to execute command with faketime.")
                        return 1
                else:
                    if not QUIET:
                        error_log("Faketime string not set. Cannot run command.")
                    return 1
            else:
                try:
                    if VERBOSE and not QUIET:
                        verbose_log(f"Running command: {Colors.MAGENTA}{command}{Colors.END}", level="CMD")
                    result = subprocess.run(command, shell=True, env=os.environ.copy(), capture_output=True, text=True)
                    if QUIET:
                        if result.stdout:
                            print(result.stdout, end="")
                        if result.stderr:
                            print(result.stderr, end="", file=sys.stderr)
                    else:
                        if result.stdout:
                            print(result.stdout, end="")
                        if result.stderr:
                            print(result.stderr, end="", file=sys.stderr)
                        if result.returncode != 0 and not QUIET:
                            error_log(f"Command failed with exit code {result.returncode}")
                    return result.returncode
                except Exception as e:
                    if VERBOSE and not QUIET:
                        error_log(f"Error executing command: {e}")
                    if not QUIET:
                        error_log("Failed to execute command.")
                    return 1
        finally:
            if self.active_technique:
                self.active_technique.reset()

    def shell_mode(self, shell_name=None, technique_num=None, server=None, port=None):
        if not is_linux():
            error_log("Shell mode is only supported on Linux/Unix.")
            sys.exit(1)
        shell_path = shell_name
        if not shell_path:
            shell_path = os.environ.get("SHELL", "/bin/bash")
        elif shell_path in ("bash", "zsh", "sh"):
            shell_path = shutil.which(shell_path) or shell_path
        if not shell_path or not os.path.exists(shell_path):
            error_log(f"Could not find shell: {shell_name or '$SHELL'}")
            sys.exit(1)
        if technique_num == 7:
            error_log("Technique 7 (Python monkey-patch) is not currently supported. This feature will be added in a future update.")
            sys.exit(1)
        if not self.try_techniques(server, port, technique_num):
            self.print_failure_matrix()
            error_log("Time synchronization failed. No technique succeeded.")
            sys.exit(1)
        else:
            self.print_success()
        tech = self.active_technique
        if isinstance(tech, FaketimeTechnique) and tech.faketime_str:
            cmd_list = ["faketime", tech.faketime_str, shell_path]
            if VERBOSE and not QUIET:
                verbose_log(f"Launching shell: {Colors.MAGENTA}{' '.join(shlex.quote(arg) for arg in cmd_list)}{Colors.END}", level="CMD")
            subprocess.run(cmd_list, env=os.environ.copy())
        else:
            if VERBOSE and not QUIET:
                verbose_log(f"Launching shell: {Colors.MAGENTA}{shell_path}{Colors.END}", level="CMD")
            subprocess.run([shell_path], env=os.environ.copy())
        if self.active_technique:
            self.active_technique.reset()

def signal_handler(signum, frame):
    if not QUIET:
        print(f"\n{Colors.YELLOW}Interrupted by user{Colors.END}")
    sys.exit(0)

def print_help():
    script_name = "DCTimer.py"
    print(f"\033[1mDCTimer: Red Team Time Synchronization Tool\033[0m")
    print("Synchronize system or process time with a Domain Controller (DC) or NTP server.")
    print()
    print("="*20 + " USAGE " + "="*20)
    print(f"\033[96m{script_name} -i <IP> [OPTIONS] [COMMAND...]\033[0m")
    print()
    print("="*19 + " OPTIONS " + "="*19)
    print(f"  \033[1m-i, --ip IP\033[0m\t\tDC/NTP server IP address (or use 'IP' env var).")
    print(f"  \033[1m-p, --port PORT\033[0m\t\tUDP port for NTP queries (Default: 123).")
    print(f"  \033[1m-t, --technique TECH\033[0m\tForce a specific time sync technique (1-6).")
    print(f"  \033[1m-q, --quiet\033[0m\t\tQuiet mode: only print command output.")
    print(f"  \033[1m-s, --shell [SHELL]\033[0m\tQuick shell mode: open DC-synced shell (bash, zsh, sh, or $SHELL).")
    print(f"  \033[1m--colorless\033[0m\t\t\tDisable colored output (for piping).")
    print(f"  \033[1m--reset\033[0m\t\t\tReset all applied time changes (Linux only, requires root).")
    print(f"  \033[1m-v, --verbose\033[0m\t\tEnable verbose output for debugging.")
    print(f"  \033[1m-h, --help\033[0m\t\tShow this help message and exit.")
    print()
    print("="*18 + " TECHNIQUES " + "="*17)
    print("  1: ntpdate\t\t(System-wide, one-shot, requires root)")
    print("  2: ntpd\t\t\t(System-wide, persistent service, requires root)")
    print("  3: systemd-timesyncd\t(System-wide, persistent service, requires root)")
    print("  4: openntpd\t\t(System-wide, persistent service, requires root)")
    print("  5: Dynamic Date Loop\t(System-wide, persistent loop, requires root)")
    print("  6: faketime\t\t(Process-level, for specific commands, no root needed)")
    print("  7: Python monkey-patch\t(NOT SUPPORTED YET - future update)")
    print()
    print("="*19 + " EXAMPLES " + "="*18)
    print(f"\033[92m# Run 'date' and print only the output\033[0m")
    print(f"  {script_name} -i $ip -q date")
    print(f"\n\033[92m# Open a bash shell with DC-synced time\033[0m")
    print(f"  {script_name} -i $ip -s bash")
    print(f"\n\033[92m# Force use of ntpdate (T1) and run a command with verbose output\033[0m")
    print(f"  sudo {script_name} -i $ip -t 1 -v \"nxc ldap dc.$host -u $user -p $pass -k -d $host\"")
    print()

def main():
    global VERBOSE, QUIET, COLORLESS
    parser = argparse.ArgumentParser(description='DCTimer', add_help=False)
    parser.add_argument('-i', '--ip', help='DC/NTP server IP address')
    parser.add_argument('-p', '--port', type=int, default=DEFAULT_NTP_PORT, help='NTP port')
    parser.add_argument('-t', '--technique', type=int, choices=range(1, 8), help='Force a technique (1-7)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('-q', '--quiet', action='store_true', help='Quiet mode')
    parser.add_argument('--colorless', action='store_true', help='Disable colored output')
    parser.add_argument('--reset', action='store_true', help='Reset time changes')
    parser.add_argument('-s', '--shell', nargs='?', const=True, help='Quick shell mode: open DC-synced shell (bash, zsh, sh, or $SHELL)')
    parser.add_argument('-h', '--help', action='store_true', help='Show help')
    args, remaining = parser.parse_known_args()

    VERBOSE = args.verbose
    QUIET = args.quiet
    COLORLESS = args.colorless

    if COLORLESS:
        Colors.disable()
    else:
        Colors.enable()

    if args.help:
        print_help()
        sys.exit(0)

    dctimer = DCTimer()

    if args.reset:
        dctimer.reset_all()
        sys.exit(0)

    port = dctimer.validate_port(args.port)
    server = dctimer.get_target_ip(args)

    ntp_info = get_ntp_time(server, port)
    if not ntp_info:
        if not QUIET:
            error_log("Failed to fetch initial NTP time. Exiting.")
        sys.exit(1)

    update_ntp_reference(ntp_info['ntp_time'])

    if not is_linux():
        if not QUIET:
            warning_log("Full automation only available on Linux")
            print_cross_platform_tips(server, port, ntp_info)
        sys.exit(0)

    if args.shell is not None:
        shell_name = None
        if isinstance(args.shell, str) and args.shell != "True":
            shell_name = args.shell
        dctimer.shell_mode(shell_name, args.technique, server, port)
        sys.exit(0)

    command_str = ' '.join(remaining) if remaining else None

    if not command_str:
        if not QUIET:
            error_log("No command provided. Please specify a command to run.")
        sys.exit(1)

    retcode = dctimer.execute_command(command_str, server, port, args.technique)
    sys.exit(retcode if retcode is not None else 1)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    main()

