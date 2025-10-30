import os
import sys
import platform
from pathlib import Path
import configparser
import socket

try:
    from dotenv import set_key
except Exception:
    set_key = None

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / '.env'
INI_PATH = PROJECT_ROOT / 'config.ini'


def print_header():
    print('=' * 60)
    print('Discord Printer Receiver - Setup Wizard')
    print('=' * 60)


def detect_os():
    return platform.system().lower()


def guide_driver_setup(os_name: str):
    print('\nPrinter driver/setup guidance:')
    if os_name == 'windows':
        print('- Windows detected. If using a TM-T88IV over USB, install libusbK driver (Zadig).')
        print('  Steps: Open Zadig → Options > List All Devices → select printer → install libusbK.')
    elif os_name == 'linux':
        print('- Linux/Raspberry Pi detected. Ensure user has permissions for USB/serial devices.')
        print('  For USB: add user to plugdev/dialout groups if required; unplug/replug the printer.')
    elif os_name == 'darwin':
        print('- macOS detected. USB printers may require additional permissions; network is often simpler.')
    else:
        print('- Unknown OS. Proceed with manual configuration.')


def prompt_connection_type():
    print('\nSelect printer connection method:')
    print('  1) USB')
    print('  2) Network (IP)')
    print('  3) Serial')
    choice = input('Enter choice [1/2/3]: ').strip() or '1'
    return {'1': 'usb', '2': 'network', '3': 'serial'}.get(choice, 'usb')


def prompt_usb_params():
    print('\nUSB setup (press Enter to skip/keep defaults):')
    vid = input('Vendor ID (hex, e.g. 0x04b8 for Epson): ').strip()
    pid = input('Product ID (hex): ').strip()
    return vid, pid


def prompt_network_params():
    print('\nNetwork setup:')
    ip = input('Printer IP or hostname: ').strip()
    port = input('Port [9100]: ').strip() or '9100'
    return ip, port


def prompt_serial_params():
    print('\nSerial setup:')
    device = input('Serial device (e.g. COM3 or /dev/ttyUSB0): ').strip()
    baud = input('Baudrate [19200]: ').strip() or '19200'
    return device, baud


def write_env(secret: str):
    # Ensure .env exists
    if not ENV_PATH.exists():
        ENV_PATH.write_text('', encoding='utf-8')
    # Append or set key
    line = f'PRINTER_SHARED_SECRET={secret}\n'
    if set_key:
        # Use python-dotenv helper when available
        set_key(str(ENV_PATH), 'PRINTER_SHARED_SECRET', secret)
    else:
        # Fallback naive write
        contents = ENV_PATH.read_text(encoding='utf-8')
        if 'PRINTER_SHARED_SECRET=' in contents:
            # Replace existing
            new_lines = []
            for l in contents.splitlines():
                if l.startswith('PRINTER_SHARED_SECRET='):
                    new_lines.append(line.strip())
                else:
                    new_lines.append(l)
            ENV_PATH.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')
        else:
            with ENV_PATH.open('a', encoding='utf-8') as f:
                f.write(line)


def write_ini(connection: str, params: dict):
    cfg = configparser.ConfigParser()
    if INI_PATH.exists():
        cfg.read(INI_PATH)
    if 'printer' not in cfg:
        cfg['printer'] = {}
    cfg['printer']['connection'] = connection
    for k, v in params.items():
        if v:
            cfg['printer'][k] = str(v)
    with INI_PATH.open('w', encoding='utf-8') as f:
        cfg.write(f)


def main():
    print_header()

    os_name = detect_os()
    print(f'Detected OS: {os_name}')
    guide_driver_setup(os_name)

    # Exposure guidance BEFORE token prompt
    print('\nHow will you expose this receiver to the bot?')
    print('  1) Port Forwarding (router)')
    print('  2) Cloudflared Quick Tunnel (free, temporary URL)')
    print('  3) Cloudflared Named Tunnel (stable URL on your domain)')
    choice = input('Enter choice [1/2/3]: ').strip() or '2'

    local_ip = get_local_ip() or '127.0.0.1'
    print(f'\nDetected local IP: http://{local_ip}:5000')

    if choice == '1':
        show_port_forwarding_steps(local_ip)
    elif choice == '3':
        show_cloudflared_named_tunnel_steps()
    else:
        show_cloudflared_quick_tunnel_steps()

    print('\nLink your receiver in Discord:')
    print('  1) Run /printer link <your exposed URL from the step above>')
    print('  2) Use /printer token and copy the token shown to you')
    secret = input('Paste your printer API token here: ').strip()
    while not secret:
        secret = input('Token cannot be empty. Paste your token: ').strip()

    # Save secret to .env
    write_env(secret)
    print(f'Wrote PRINTER_SHARED_SECRET to {ENV_PATH}')

    # Connection configuration
    conn = prompt_connection_type()
    params = {}
    if conn == 'usb':
        vid, pid = prompt_usb_params()
        params = {
            'usb_vendor_id': vid,
            'usb_product_id': pid,
        }
    elif conn == 'network':
        ip, port = prompt_network_params()
        params = {'ip': ip, 'port': port}
    else:
        device, baud = prompt_serial_params()
        params = {'device': device, 'baudrate': baud}

    write_ini(conn, params)
    print(f'Wrote connection config to {INI_PATH}')

    print('\nNext steps:')
    print('- Start the receiver: python run_pi_server.py')
    print('- In Discord, press ✅ on the DM to trigger verification')
    print('- After verification, the bot will send a test print automatically')
    print('\nOptional: Install autostart from the scripts directory after the first successful run.')


if __name__ == '__main__':
    main()

# Helpers
def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return '127.0.0.1'

def show_port_forwarding_steps(local_ip: str):
    print('\nPort Forwarding (Direct)')
    print('- Log into your router and add a port forward:')
    print('  External Port -> Internal IP -> Internal Port 5000 (TCP)')
    print(f'  Internal IP should be this device: {local_ip}')
    print('- Find your public IP at: https://ifconfig.me or your router status page')
    print('- Link in Discord using your public IP and port, e.g.:')
    print('  !printer link http://<public-ip>:<external-port>')
    print('- Keep PRINTER_SHARED_SECRET private; signatures protect your endpoint but do not skip firewalling if possible')

def show_cloudflared_quick_tunnel_steps():
    print('\nCloudflared Quick Tunnel (free)')
    print('- Install cloudflared: https://github.com/cloudflare/cloudflared/releases')
    print('- Run:')
    print('  cloudflared tunnel --url http://localhost:5000')
    print('- Copy the shown https://<random>.trycloudflare.com URL')
    print('- Link in Discord: !printer link <that URL>')
    print('- Note: URL changes when you restart; use Named Tunnel for a stable URL')

def show_cloudflared_named_tunnel_steps():
    print('\nCloudflared Named Tunnel (stable, with your domain)')
    print('- Requires a Cloudflare account and a domain managed in Cloudflare DNS')
    print('- Steps:')
    print('  1) cloudflared tunnel login')
    print('  2) cloudflared tunnel create printer-receiver')
    print('  3) Create ~/.cloudflared/config.yml with:')
    print('     tunnel: <your-tunnel-uuid>')
    print('     credentials-file: <path-to-credentials-file>')
    print('     ingress:')
    print('       - hostname: printer.yourdomain.com')
    print('         service: http://localhost:5000')
    print('       - service: http_status:404')
    print('  4) In Cloudflare DNS, add CNAME: printer -> <tunnel>.cfargotunnel.com')
    print('  5) Run: cloudflared tunnel run printer-receiver (or install as a service)')
    print('- Link in Discord: !printer link https://printer.yourdomain.com')


