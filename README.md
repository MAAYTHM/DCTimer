# DCTimer

**Red Team Time Synchronization Tool**  
Author: [MAAYTHM](https://github.com/MAAYTHM)

## Overview

DCTimer is a flexible tool for synchronizing your system or process time with a Domain Controller (DC) or NTP server. It is designed for red teamers, penetration testers, and advanced system administrators who need precise time control for operations, testing, or evasion scenarios.

DCTimer supports both system-level and process-level time manipulation techniques, provides robust reset/cleanup capabilities, and offers clear, script-friendly output modes.

## Features

- **One-shot command execution or shell with DC/NTP-synced time**
- **Multiple techniques**: system-wide and process-level (see below)
- **Universal reset**: Restores system time and configuration safely
- **Quick shell mode**: Instantly open a DC-synced shell
- **Verbose and quiet modes**: For debugging or script/pipeline use
- **Colorless output option**: For clean logs and piping
- **Technique auto-selection or forced mode**
- **Clear error handling and guidance**
- **Compatible with Linux/Unix systems**

## Installation

1. **Install Python 3** (if not already present).
2. **Install required Python package:**
   ```
   pip install ntplib
   ```
3. **Download or clone this repository and make the script executable:**
   ```
   chmod +x DCTimer.py
   ```

## Usage

### Basic Syntax

```
./DCTimer.py -i <NTP/DC_IP> [OPTIONS] [COMMAND...]
```

### Common Examples

- **Run a command with DC-synced time:**
  ```
  ./DCTimer.py -i 10.10.10.1 date
  ```

- **Force use of faketime (technique 6):**
  ```
  ./DCTimer.py -i 10.10.10.1 -t 6 date
  ```

- **Open a shell with DC-synced time (uses $SHELL by default):**
  ```
  ./DCTimer.py -i 10.10.10.1 --shell
  ```

- **Open a bash shell with DC-synced time:**
  ```
  ./DCTimer.py -i 10.10.10.1 --shell bash
  ```

- **Quiet mode for scripting/pipelines:**
  ```
  ./DCTimer.py -i 10.10.10.1 -q date
  ```

- **Universal reset after system-level changes:**
  ```
  sudo ./DCTimer.py --reset
  ```

## Command-Line Options

| Option                  | Description                                                         |
|-------------------------|---------------------------------------------------------------------|
| `-i`, `--ip`            | DC/NTP server IP address (or use `IP` environment variable)         |
| `-p`, `--port`          | UDP port for NTP queries (default: 123)                             |
| `-t`, `--technique`     | Force a specific technique (1-6; see below)                         |
| `-q`, `--quiet`         | Quiet mode: only print command output                               |
| `-s`, `--shell [SHELL]` | Quick shell mode: open DC-synced shell (bash, zsh, sh, or $SHELL)   |
| `--colorless`           | Disable colored output (for piping/logs)                            |
| `--reset`               | Reset all applied time changes (Linux only, requires root)          |
| `-v`, `--verbose`       | Enable verbose output for debugging                                 |
| `-h`, `--help`          | Show help message and exit                                          |

## Techniques

| No. | Name                | Description                                                | Requires Root | System-wide | Works in Containers |
|-----|---------------------|-----------------------------------------------------------|:------------:|:-----------:|:-------------------:|
| 1   | ntpdate             | One-shot system time sync (ntpdate -u <server>)           | Yes          | Yes         | No                  |
| 2   | ntpd                | Persistent system NTP daemon                              | Yes          | Yes         | No                  |
| 3   | systemd-timesyncd   | Systemd-based time sync                                   | Yes          | Yes         | No                  |
| 4   | openntpd            | OpenNTPD daemon                                           | Yes          | Yes         | No                  |
| 5   | Dynamic Date Loop   | Sets system time in a loop                                | Yes          | Yes         | No                  |
| 6   | faketime            | Process-level time faking (faketime '@<timestamp>' <cmd>) | No           | No          | Yes                 |
| 7   | Python monkey-patch | **Not supported yet   future update**                      | No           | No          | No                  |

## Manual Technique Commands

### Technique 1: ntpdate

- **Sync:**  
  ```
  sudo timedatectl set-ntp off
  sudo ntpdate -u <server>
  ```
- **Reset:**  
  ```
  sudo timedatectl set-ntp true
  sudo ntpdate pool.ntp.org
  ```

### Technique 2: ntpd

- **Sync:**  
  - Edit `/etc/ntp.conf` to set `server <ip> iburst`
  - Restart daemon:
    ```
    sudo systemctl restart ntp
    sudo systemctl enable ntp
    ```
- **Reset:**  
  ```
  sudo timedatectl set-ntp true
  sudo ntpdate pool.ntp.org
  # Restore /etc/ntp.conf if needed
  ```

### Technique 3: systemd-timesyncd

- **Sync:**  
  - Edit `/etc/systemd/timesyncd.conf` to set `[Time] NTP=<ip>`
  - Restart daemon:
    ```
    sudo systemctl restart systemd-timesyncd
    sudo timedatectl set-ntp true
    ```
- **Reset:**  
  ```
  sudo timedatectl set-ntp true
  sudo ntpdate pool.ntp.org
  # Restore /etc/systemd/timesyncd.conf if needed
  ```

### Technique 4: openntpd

- **Sync:**  
  - Edit `/etc/openntpd/ntpd.conf` to set `servers <ip>`
  - Restart daemon:
    ```
    sudo systemctl restart openntpd
    sudo systemctl enable openntpd
    ```
- **Reset:**  
  ```
  sudo timedatectl set-ntp true
  sudo ntpdate pool.ntp.org
  # Restore /etc/openntpd/ntpd.conf if needed
  ```

### Technique 5: Dynamic Date Loop

- **Sync:**  
  ```
  sudo date -s @<timestamp>
  ```
- **Reset:**  
  ```
  sudo timedatectl set-ntp true
  sudo ntpdate pool.ntp.org
  ```

### Technique 6: faketime

- **Sync:**  
  ```
  faketime '@<timestamp>' <cmd>
  ```
- **Reset:**  
  No reset needed.

## Universal Reset

For all system-level techniques, the following universal reset is recommended:

```
sudo timedatectl set-ntp true
sudo ntpdate pool.ntp.org
```

Additionally, restore any modified config files if you used ntpd, openntpd, or systemd-timesyncd.

## Methodology Flow

Below is a typical workflow for DCTimer:

1. **Fetch NTP/DC time** from the specified server.
2. **Apply selected technique** (auto or forced) to sync time.
3. **Run user command or shell** in the chosen time context.
4. **Reset system time** (if system-level technique used) after command/shell exits.

## Public NTP Servers

Some reliable public NTP servers for testing:

- pool.ntp.org
- time.nist.gov (129.6.15.28)
- time.google.com (216.239.35.0)
- time.cloudflare.com (162.159.200.1)

## Compatibility and Limitations

- **Linux/Unix only** (tested on modern distributions).
- **System-override techniques** (1, 2, 3, 4, 5) do not work in containers or systems without systemd (e.g., many Docker containers).
- **Process-level technique (6)** works in containers.
- **Technique 7 (Python monkey-patch)** is not currently supported.
- **If you see**  
  `"System has not been booted with systemd as init system (PID 1). Can't operate."`  
  this means you are running in a container or system without systemd.

## Security & OPSEC Notes

- **System-override techniques** change the system time for all shells and applications on the OS, not just the shell or process launched by DCTimer.
- Use **process-level techniques** (like faketime) when you need isolation.
- Always perform a universal reset after using system-level techniques.

## Troubleshooting

- If a command fails with  
  `faketime: Running specified command failed: No such file or directory`  
  it usually means your command is invalid or not found.
- For systemd errors or failures in containers, use process-level techniques or run on a full Linux system.

## Thanks & Recognitions

DCTimer would not be possible without the contributions of the open-source community and the maintainers of the following tools and libraries:

### Core Tools & Dependencies

- **faketime**  
  - A powerful utility for faking the system time for a given process, widely used for process-level time manipulation on Linux.
  - Project: [libfaketime on GitHub](https://github.com/wolfcw/libfaketime)

- **ntpdate**  
  - A classic tool for one-shot synchronization of the system clock with an NTP server.
  - Part of the NTP reference implementation (ntp.org) and also available in NTPsec.

- **ntpd / NTPsec**  
  - The traditional NTP daemon for continuous time synchronization.
  - NTPsec is a secure, modernized fork of the original NTP daemon.
  - Project: [NTPsec](https://docs.ntpsec.org/latest/)

- **systemd-timesyncd**  
  - A modern, lightweight NTP client integrated with systemd for system time synchronization.
  - Documentation: [systemd-timesyncd man page](https://www.freedesktop.org/software/systemd/man/systemd-timesyncd.service.html)

- **openntpd**  
  - An OpenBSD-originated NTP daemon focused on simplicity and security.
  - Project: [OpenNTPD Portable](https://openntpd.org/portable.html)

- **ntplib (Python library)**  
  - A Python module used for querying NTP servers and retrieving time in scripts.
  - Project: [ntplib on PyPI](https://pypi.org/project/ntplib/)

### Platform & System Utilities

- **date**  
  - The standard Unix command-line utility for displaying and setting the system date and time.

- **systemctl / timedatectl**  
  - Systemd utilities for managing services and system time settings.

- **bash, zsh, sh**  
  - Standard Unix shells used for launching interactive sessions.

### Acknowledgments

- Thanks to the maintainers and contributors of all the above projects for their dedication to open-source software.
- Special appreciation to the Linux, BSD, and Python communities for providing robust, well-documented system tools and libraries.

**Note:**  
DCTimer is a glue tool that leverages these utilities to provide a unified, user-friendly interface for red teamers and system administrators. Please refer to the documentation of each tool for licensing, advanced usage, and security considerations.

## Contributing

Pull requests, issues, and feedback are welcome!  
See [MAAYTHM](https://maaythm.github.io/maaythm/) for contact.

## License

MIT License
