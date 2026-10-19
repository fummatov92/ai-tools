# 🖥️ System & Resource Audit (`sys` module)

The `sys` module provides 0-token system diagnostics, port monitoring, disk breakdown, and Docker container auditing.

## Commands

### 1. General System Health
```bash
ai-tool sys status
```
Returns CPU load average, RAM usage/free space, and primary disk statistics in JSON format.

### 2. Disk Storage Breakdown
```bash
ai-tool sys storage
ai-tool sys storage --path /home/user/project --depth 2
```
Scans directories and outputs size allocation per folder with percentage shares.

### 3. Port Range Scanner
```bash
ai-tool sys ports --start 8000 --end 9000
```
Audits listening TCP/UDP ports, detecting open sockets and bound processes.

### 4. Rootless Docker Containers
```bash
ai-tool sys docker
```
Lists user Docker containers without requiring sudo privileges.

### 5. Audit Log Inspector
```bash
ai-tool sys logs --limit 10
ai-tool sys last-run
```
Inspects all local operations executed by the CLI with millisecond durations and exit codes.
