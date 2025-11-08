# Discord Printer Receiver

A receiver server that connects your thermal printer (or PC simulator) to the Discord Printer Bot. Run this on your Raspberry Pi or PC to receive prints from friends across Discord servers!

## Features

- **Easy Setup** - Simple configuration with environment variables
- **Multiple Connection Types** - USB, Network, or Serial printer support
- **Testing Mode** - Simulator for testing without a physical printer
- **Secure API** - HMAC-signed requests from the bot
- **Automatic Logging** - Tracks all prints with timestamps
- **Production Ready** - Handles errors, timeouts, and reconnection automatically

## Quick Start

### 1. Install Dependencies

```bash
# Clone the repository
git clone <repository-url>
cd Printer-receiver

# Create virtual environment
python -m venv venv

# Activate venv (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r pi_requirements.txt
```

### 2. Run setup wizard (recommended)

Run the guided setup to configure your token and printer connection:

```bash
python pi_server/setup.py
```

This writes `.env` (with `PRINTER_SHARED_SECRET`) and `config.ini` (connection settings). You can still configure manually as below.

### Manual: configure environment

Create a `.env` file in the project root:

```env
# Required (get these from the Discord bot when linking)
PRINTER_SHARED_SECRET=your_shared_secret_here

# Server Configuration
HOST=0.0.0.0
PORT=5000

# Printer Connection is configured in config.ini (see below)

# Advanced: USB write settings (optional)
# PRINTER_WRITE_CHUNK_SIZE=128
# PRINTER_WRITE_CHUNK_DELAY=0.05
```

### 3. Link Your Printer to the Bot

1. **Add the bot to your Discord server**: [printerbot.dragnai.dev/add](https://printerbot.dragnai.dev/add)

2. **Get your printer token**:
   - In Discord, DM the bot: `/printer token`
   - The bot will send you your printer's API token

3. **Link your receiver**:
   - Expose your receiver to the internet (see [Exposing Your Receiver](#exposing-your-receiver-to-the-internet) section below)
   - Use the command: `!printer link http://your-url` (or `https://` for Cloudflared)
     - For port forwarding: `http://your-public-ip:port`
     - For Cloudflared: `https://your-tunnel-url.trycloudflare.com`
   - The bot will send a verification code to test the connection
   - Press ✅ on the DM to complete verification

### 4. Run the Server

```bash
python run_pi_server.py
```

Or directly:
```bash
python -m pi_server.app
```

## Configuration

### Environment Variables

**Required:**
- `PRINTER_SHARED_SECRET` - HMAC secret key shared with the Discord bot (received when linking)

**Mode:**
- `TESTING_MODE` - Set to `true` for simulator mode, `false` for real printer

**Server:**
- `HOST` - Bind address (default: `0.0.0.0` for all interfaces)
- `PORT` - Server port (default: `5000`)

**Printer Connection (Production Mode):**
- `PRINTER_IP` - Network printer IP address (e.g., `192.168.1.100`)
- `PRINTER_SERIAL` - Serial port device (e.g., `/dev/ttyUSB0` or `COM3`)

**Security:**
- `PRINTER_SIGNATURE_MAX_AGE` - Maximum age of request signatures in seconds (default: 300)

**Advanced (USB optimization):**
- `PRINTER_WRITE_CHUNK_SIZE` - Chunk size for USB writes (default: 128)
- `PRINTER_WRITE_CHUNK_DELAY` - Delay between chunks in seconds (default: 0.05 on Windows, 0.0 on Linux)

### Connection via config.ini

The setup wizard writes a `config.ini` like:

```
[printer]
connection=usb  # usb|network|serial
# USB:
usb_vendor_id=0x04B8
usb_product_id=0x0202
# Network:
# ip=192.168.1.100
# port=9100
# Serial:
# device=/dev/ttyUSB0
# baudrate=19200
```

## Hardware Setup

### Supported Printers

This receiver is designed for the **TM-T88IV thermal printer** but may work with other ESC/POS compatible printers.

### Connection Types

#### USB Connection (Recommended)

1. Connect printer to your computer via USB
2. On Linux, printer should appear as `/dev/usb/lp0` or similar
3. On Windows, printer will auto-detect via vendor/product IDs
4. No configuration needed - USB is the default

**Troubleshooting USB:**
- If connection fails, check device permissions (Linux)
- Try different USB ports
- Verify printer power is on

#### Network Connection

1. Configure printer's network settings (see printer manual)
2. Note the printer's IP address
3. Set in `.env`: `PRINTER_IP=192.168.1.100`

#### Serial Connection

1. Connect via serial cable
2. Identify serial port:
   - Linux: `/dev/ttyUSB0`, `/dev/ttyACM0`, etc.
   - Windows: `COM1`, `COM3`, etc.
3. Set in `.env`: `PRINTER_SERIAL=/dev/ttyUSB0` (or `COM3` on Windows)

## Exposing Your Receiver to the Internet

For the Discord bot to reach your receiver, it needs to be accessible from the internet. You have two main options:

### Option 1: Port Forwarding (Direct)

Port forward a port on your router to your receiver server.

**Steps:**

1. **Find your local IP address**:
   - Windows: Run `ipconfig` and look for "IPv4 Address"
   - Linux: Run `hostname -I` or `ip addr`
   - Example: `192.168.1.100`

2. **Configure your router**:
   - Access your router's admin panel (usually `192.168.1.1` or `192.168.0.1`)
   - Navigate to "Port Forwarding" or "Virtual Server" settings
   - Create a new rule:
     - **External Port**: Choose any port (e.g., `5000` or `8000`)
     - **Internal IP**: Your receiver's local IP (e.g., `192.168.1.100`)
     - **Internal Port**: `5000` (your receiver's PORT)
     - **Protocol**: TCP
   - Save and apply the rule

3. **Find your public IP**:
   - Visit https://whatismyipaddress.com/ or run `curl ifconfig.me`
   - Note: Your public IP may change if you don't have a static IP

4. **Link your printer**:
   - Use `!printer link http://your-public-ip:external-port`
   - Example: `!printer link http://203.0.113.42:5000`

**Pros:**
- Direct connection, low latency
- Full control over the connection

**Cons:**
- Requires router access
- Exposes your IP address
- May need to update IP if it changes (if not using static IP)
- Less secure (though HMAC signatures help)

**Security Note:** Always set `PRINTER_SHARED_SECRET` in production mode to prevent unauthorized access.

### Option 2: Cloudflared Tunnel (Recommended)

Use Cloudflare Tunnel (formerly Argo Tunnel) to securely expose your receiver without opening ports on your router.

**Steps:**

1. **Install Cloudflared**:
   
   **Windows:**
   ```powershell
   # Download from https://github.com/cloudflare/cloudflared/releases
   # Or using Chocolatey:
   choco install cloudflared
   ```
   
   **Linux:**
   ```bash
   # Download from https://github.com/cloudflare/cloudflared/releases
   # Or using package manager:
   # Debian/Ubuntu
   curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
   sudo dpkg -i cloudflared.deb
   
   # Or extract binary and move to PATH
   ```

2. **Authenticate Cloudflared**:
   ```bash
   cloudflared tunnel login
   ```
   - Opens browser to log in with your Cloudflare account
   - Creates certificate for tunnel access

3. **Run the tunnel** (Simple method for free tier):
   ```bash
   cloudflared tunnel --url http://localhost:5000
   ```
   
   Cloudflared will start and display a URL like:
   ```
   +--------------------------------------------------------------------------------------------+
   |  Your quick Tunnel has been created! Visit it at (it may take some time to be reachable): |
   |  https://printer-receiver-xxxx-xxxx.trycloudflare.com                                      |
   +--------------------------------------------------------------------------------------------+
   ```
   
   **For a permanent tunnel** (recommended for stable URLs):
   
   3a. Create a named tunnel:
   ```bash
   cloudflared tunnel create printer-receiver
   ```
   - Note the tunnel UUID that's displayed
   
   3b. Create config file:
   - **Windows**: `%USERPROFILE%\.cloudflared\config.yml`
   - **Linux**: `~/.cloudflared/config.yml`
   
   ```yaml
   tunnel: <your-tunnel-uuid>
   credentials-file: <path-to-credentials-file>
   
   ingress:
     - service: http://localhost:5000
   ```
   
   3c. Run the named tunnel:
   ```bash
   cloudflared tunnel run printer-receiver
   ```
   
   Or run as a service for auto-start (see Cloudflare docs).

4. **Link your printer**:
   - Copy the URL displayed by Cloudflared
   - Use `!printer link https://your-tunnel-url.trycloudflare.com`
   - Note: Free tier URLs change each time you restart (unless using a named tunnel with domain)

**Pros:**
- No router configuration needed
- More secure (HTTPS, no direct port exposure)
- Works behind NAT/firewalls
- Free option available

**Cons:**
- Requires Cloudflare account
- Free tier gives random URLs (changes on restart)
- Slightly more complex setup
- Domain name required for stable custom URLs (paid feature)

**Note:** For a permanent stable URL, you'll need your own domain and configure it in Cloudflare DNS.

### Which Method Should I Use?

- **Use Port Forwarding if**: You have router access, want a direct connection, and can manage IP changes
- **Use Cloudflared if**: You can't configure your router, want better security, or prefer not to expose your home network directly

Both methods work with the Discord bot's verification system. Choose based on your technical comfort and network situation.

## Controlling the Bot (Discord Commands)

Once your receiver is linked to the bot, you can control it using Discord commands. These commands are executed in Discord servers where the bot is present.

### Basic User Commands

Anyone can send prints to users who have linked printers:

- `!printer help` - Show help menu
- `!printer info` - About the project
- `!printer @username message` - Send a print to someone
- `!printer list` - See who has a linked printer
- `!printer stats` - View top senders/receivers leaderboard
- `!printer selfstats` - View your own printing activity

### Printer Owner Commands

Manage your own linked printer:

**Setup & Linking:**
- `!printer setuphelp` - Show all setup commands
- `!printer link <url>` - Link your printer (e.g., `http://192.168.1.100:5000`)
- `/printer token` - DM your printer's API token
- `!printer unlink` - Unlink your printer
- `!printer test` - Send test print

**Control:**
- `!printer pause <time>` - Pause receiving (e.g., `1h`, `4h`, `7d`)
- `!printer unpause` - Resume receiving prints

**Access Control:**
- `!printer block @user` - Block someone from printing to you
- `!printer unblock @user` - Unblock a user
- `!printer allow @user` - Add to allowlist (if using allowlist mode)
- `!printer unallow @user` - Remove from allowlist

### Flag Commands

Customize your printer and sending preferences:

- `!flags show` - View all your flags
- `!flags show recv` - View receiving flags (printer owners only)
- `!flags show send` - View sending preferences
- `!flags show privacy` - View privacy settings (printer owners only)
- `!flags set key=value` - Set one or more flags
- `!flags reset [category]` - Reset to defaults
- `!flags preset generous` - Apply generous preset (high limits)
- `!flags preset strict` - Apply strict preset (allowlist mode)

**Example Flag Usage:**
```
!flags set recv.max_per_day=-1
!flags set recv.quiet_hours=22:00-07:00
!flags set send.fail_if_paused=true privacy.store_content_days=7
```

#### Receiving Flags (recv.*)

Control who can print to your receiver:

- `recv.max_per_day` - Total prints accepted per day (-1 = unlimited)
- `recv.max_per_sender_day` - Max from one sender per day
- `recv.allowlist_mode` - Only allow allowlisted senders (true/false)
- `recv.quiet_hours` - Snooze window (e.g., "22:00-07:00")
- `recv.retry_policy` - Retry failed jobs (e.g., "3x/5m")
- `recv.queue_max` - Max queued jobs before rejecting
- `recv.print_qr_reply` - Add QR code with job ID (true/false)

#### Sending Flags (send.*)

Control how your prints are sent:

- `send.confirm_dm` - DM confirmation style (always/fail_only/auto)
- `send.default_dither` - Image dithering (floyd/atkinson/none)
- `send.max_width_px` - Raster width limit
- `send.max_len_px` - Raster height limit
- `send.split_long` - Split tall images instead of truncating
- `send.fail_if_paused` - Fail immediately if printer paused

#### Privacy Flags (privacy.*)

Control data retention:

- `privacy.store_content_days` - Days to keep message content (0 = never)
- `privacy.store_meta_days` - Days to keep metadata
- `privacy.show_in_leaderboard` - Show in stats (true/false)

## API Reference

The receiver exposes a REST API that the Discord bot uses to send print jobs.

### POST `/print`

Receive and process a print job.

**Request Headers:**
- `X-Printer-Signature` - HMAC signature (required if `PRINTER_SHARED_SECRET` is set)
- `X-Printer-Timestamp` - Unix timestamp (required if signature enabled)

**Request Body:**
```json
{
  "escpos_data": "<base64 encoded ESC/POS commands>",
  "username": "DiscordUser",
  "user_id": 123456789012345678
}
```

**Response (Success):**
```json
{
  "success": true,
  "message": "Print job sent successfully",
  "image": "<base64 encoded preview>"  // Testing mode only
}
```

**Response (Error):**
```json
{
  "success": false,
  "message": "Error description",
  "error_code": "OUT_OF_PAPER" | "PRINTER_OFFLINE" | "PRINT_FAILED" | "SERVER_ERROR"
}
```

### POST `/verify`

Signed verification without printing.

Request:
```json
{ "nonce": "<string>" }
```

Headers (required):
- `X-Printer-Timestamp`: unix time (seconds)
- `X-Printer-Signature`: HMAC-SHA256 hex of `"{timestamp}.{nonce}"` using `PRINTER_SHARED_SECRET`

Response:
```json
{ "success": true }
```

### GET `/status`

Get current printer/receiver status.

**Response:**
```json
{
  "online": true,
  "mode": "testing" | "production",
  "message": "Status description"
}
```

### GET `/`

Root endpoint - service information.

**Response:**
```json
{
  "service": "Discord Printer API",
  "mode": "testing" | "production",
  "status": "running"
}
```

## Troubleshooting

### Server won't start

**Problem:** Error on startup

**Solutions:**
- Verify `.env` file exists and has required variables
- Check `PRINTER_SHARED_SECRET` is set if `TESTING_MODE=false`
- Ensure port 5000 is not already in use
- Verify virtual environment is activated and dependencies installed

### Can't link printer to bot

**Problem:** Verification fails when linking

**Solutions:**
- Ensure receiver is running (`python run_pi_server.py`)
- Verify receiver is accessible from the internet (or use same network)
- Check firewall allows connections on port 5000
- For local testing, ensure bot's `PRINTER_API_URL` points to your receiver
- Verify `PRINTER_SHARED_SECRET` matches between receiver and bot configuration

### Printer connection fails

**Problem:** "Printer not connected" errors

**Solutions:**
- **USB**: Check printer is powered on and USB cable connected
- **USB**: Verify device permissions on Linux: `sudo usermod -a -G lp $USER` (then log out/in)
- **USB**: Try different USB ports
- **Network**: Verify `PRINTER_IP` is correct and printer is on same network
- **Network**: Test network connectivity: `ping <printer-ip>`
- **Serial**: Verify serial port exists and permissions are correct
- Check printer model compatibility (designed for TM-T88IV)

### USB timeout errors

**Problem:** "USB timeout" errors during printing

**Solutions:**
- Increase delay: `PRINTER_WRITE_CHUNK_DELAY=0.1`
- Try different USB cable (some cables are data-only)
- Check USB port power delivery (some ports may be underpowered)

### Bot shows receiver as offline

**Problem:** Bot reports receiver offline

**Solutions:**
- Verify receiver is running
- Check network connectivity between bot and receiver
- Ensure firewall allows connections on port 5000
- Verify `PRINTER_API_URL` in bot configuration points to correct address
- Check receiver logs for errors

### Signature verification fails

**Problem:** "Invalid signature" or "Missing signature headers" errors

**Solutions:**
- Verify `PRINTER_SHARED_SECRET` matches exactly between receiver and bot
- Check system clock is synchronized (signatures expire after 5 minutes default)
- Ensure bot is sending `X-Printer-Signature` and `X-Printer-Timestamp` headers
- Increase `PRINTER_SIGNATURE_MAX_AGE` if needed (not recommended)

## Project Structure

```
Printer-receiver/
├── pi_server/                    # Receiver server code
│   ├── __init__.py
│   ├── app.py                    # Flask REST API
│   ├── printer_handler.py        # Real printer interface
│   └── simulator.py              # Testing mode simulator
├── print_logs/                   # Auto-created log directory
│   └── print_log.txt             # Print activity log
├── pi_requirements.txt           # Python dependencies
├── run_pi_server.py              # Server startup script
├── .env                          # Configuration (create this)
└── README.md                     # This file
```

## Security

### Important Security Notes

- **Never share** your `PRINTER_SHARED_SECRET` - it authenticates requests from the bot
- **Keep `.env` private** - contains sensitive configuration
- **Use HTTPS/TLS** if exposing receiver to the internet (consider reverse proxy)
- **Firewall rules** - Only allow connections from the Discord bot server if possible
- **Signature verification** - Always enable `PRINTER_SHARED_SECRET` in production

### Request Signing

The receiver verifies all print requests using HMAC-SHA256 signatures:

1. Bot sends request with `X-Printer-Signature` and `X-Printer-Timestamp` headers
2. Receiver reconstructs the signature using shared secret
3. Receives valid requests, rejects invalid ones

This prevents unauthorized print jobs even if your receiver is exposed to the internet.

## Logging

### Print Logs

All print jobs are logged to `print_logs/print_log.txt`:

```
2025-10-22T13:45:30|DiscordUsername|123456789012345678
```

Format: `timestamp|username|user_id`

Logs are automatically rotated and kept for 30 days (older entries are filtered in API responses).

### Server Logs

The receiver prints status information to stdout:
- Connection status
- Print job processing
- Errors and warnings
- Security events

Redirect to file if needed:
```bash
python run_pi_server.py > server.log 2>&1
```

## License

This project is for personal use. Feel free to fork and modify for your own Discord server!

---

Made with thermal paper and sarcasm. Contributions welcome!

