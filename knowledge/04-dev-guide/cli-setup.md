# CLI Setup Guide

## Installation

### From Source

```bash
cd heiman-agent/cli
pip install -e .
```

Or using uv:

```bash
cd heiman-agent/cli
uv pip install -e .
```

### Verify Installation

```bash
heiman-cli --help
```

## Usage

### Basic Commands

```bash
# Show help
heiman-cli --help

# Show version
heiman-cli version

# Get command-specific help
heiman-cli sensor --help
```

### Authentication

```bash
# Login to Heiman Cloud
heiman-cli account login

# Get current token
heiman-cli account token

# Refresh token
heiman-cli account refresh
```

### Sensor Management

```bash
# List all sensors
heiman-cli device list

# Get sensor details
heiman-cli device get <sensor_id>

# Refresh sensor data
heiman-cli device refresh
```

### Event Management

```bash
# List all events
heiman-cli event list

# Get event details
heiman-cli event get <event_id>

# Acknowledge event
heiman-cli event ack <event_id>
```

### Rule Management

```bash
# List all rules
heiman-cli rule list

# Create a rule
heiman-cli rule create --name "High Temp Alert" --sensor-type TEMPERATURE --operator ">" --value 35

# Update a rule
heiman-cli rule update <rule_id> --enabled false

# Delete a rule
heiman-cli rule delete <rule_id>
```

### Service Management

```bash
# Start service
heiman-cli service start

# Stop service
heiman-cli service stop

# Restart service
heiman-cli service restart

# Check service status
heiman-cli service status

# View logs
heiman-cli service logs

# Kill all processes
heiman-cli service kill
```

### Monitoring

```bash
# Monitor sensor status
heiman-cli monitor sensors

# Monitor events
heiman-cli monitor events

# Monitor system resources
heiman-cli monitor resources

# Monitor rules
heiman-cli monitor rules
```

### Admin Commands

```bash
# Check system status
heiman-cli admin status

# Get system info
heiman-cli admin info

# Get statistics
heiman-cli admin stats --period week

# View logs
heiman-cli admin logs -f

# Cleanup old data
heiman-cli admin cleanup --older-than 30

# Reset system
heiman-cli admin reset --confirm
```

### Configuration

```bash
# Show current configuration
heiman-cli config show

# Get specific config value
heiman-cli config get server.url

# Set config value
heiman-cli config set server.url http://192.168.1.100:1912

# List all available config paths
heiman-cli config list-paths

# Set multiple values at once
heiman-cli config set server.url http://127.0.0.1:1912 server.tls_verify false --no-restart
```

### Diagnostics

```bash
# Run full diagnostics
heiman-cli doctor

# JSON output for scripting
heiman-cli doctor --json
```

## Configuration File

The CLI uses `$HEIMAN_HOME/config.json` for configuration.

### Default Path

- `$HEIMAN_HOME` defaults to `~/.heiman`
- Can be overridden via `HEIMAN_HOME` environment variable

### Config Structure

```json
{
  "debug": false,
  "server": {
    "url": "http://127.0.0.1:1912",
    "token": "",
    "tls_verify": false,
    "python_bin": ""
  }
}
```

### Environment Variables

Environment variables override config file values:

```bash
# Override server URL
export HEIMAN_SERVER__URL=http://192.168.1.100:1912

# Enable debug mode
export HEIMAN_DEBUG=true
```

## Output Formats

### JSON Output (default)

```bash
heiman-cli device list
```

Output:
```json
{"code":0,"message":"success","data":[...]}
```

### Pretty JSON

```bash
heiman-cli device list --pretty
```

Output:
```json
{
  "code": 0,
  "message": "success",
  "data": [...]
}
```

### Table Output

```bash
heiman-cli monitor sensors --pretty
```

Output:
```
ID                               NAME                 TYPE        STATUS      VALUE            LAST_UPDATE
sensor_001                       Kitchen Smoke        SMOKE       NORMAL      15 %             2024-01-15T10:30
sensor_002                       Living Room Temp      TEMPERATURE NORMAL      22.5 °C          2024-01-15T10:30
```

## Scripting Tips

### Extract values with jq

```bash
# Get all sensor IDs
heiman-cli device list --pretty | jq -r '.data[].did'

# Count online sensors
heiman-cli device list --pretty | jq '.data | map(select(.status != "OFFLINE")) | length'

# Get unacknowledged events
heiman-cli event list --pretty | jq '.data.events | map(select(.acknowledged == false))'
```

### Shell integration

```bash
# Check if service is running
if heiman-cli service status --pretty | jq -e '.running' > /dev/null; then
  echo "Service is running"
else
  echo "Service is not running"
fi
```

### Cron jobs

```bash
# Monitor sensors every 5 minutes
*/5 * * * * /path/to/heiman-cli monitor sensors --pretty >> /var/log/heiman_monitor.log

# Cleanup old events daily at 2 AM
0 2 * * * /path/to/heiman-cli admin cleanup --older-than 30 --confirm
```

## Troubleshooting

### CLI not found

```bash
# Ensure installation is in PATH
export PATH="$HOME/.local/bin:$PATH"
```

### Connection refused

```bash
# Check if backend is running
heiman-cli service status

# Start backend if not running
heiman-cli service start
```

### Authentication errors

```bash
# Check token
heiman-cli account token

# Refresh token if expired
heiman-cli account refresh

# Re-authenticate if needed
heiman-cli account login
```

### Permission issues

```bash
# Check config directory permissions
ls -la ~/.heiman

# Fix permissions if needed
chown -R $USER ~/.heiman
```

## Advanced Usage

### Running in foreground

```bash
heiman-cli service start --foreground
```

### Custom Python interpreter

```bash
# Configure Python binary
heiman-cli config set server.python_bin /usr/bin/python3

# Start service with custom Python
heiman-cli service start
```

### Multiple instances

```bash
# Create separate config directory
export HEIMAN_HOME=~/.heiman-instance2

# Initialize and start
heiman-cli config set server.url http://127.0.0.1:1913
heiman-cli service start
```