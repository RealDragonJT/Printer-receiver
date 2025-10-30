#!/usr/bin/env python3
"""
Convenience script to run the printer server
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

def _needs_setup() -> bool:
    try:
        from dotenv import dotenv_values
    except Exception:
        # If dotenv not available, rely on file presence only
        return not (PROJECT_ROOT / '.env').exists()
    env_path = PROJECT_ROOT / '.env'
    if not env_path.exists():
        return True
    values = dotenv_values(str(env_path)) or {}
    secret = (values.get('PRINTER_SHARED_SECRET') or '').strip()
    return secret == ''

def _run_setup_if_needed():
    if _needs_setup():
        print("No .env with PRINTER_SHARED_SECRET detected. Launching setup wizard...\n")
        try:
            from pi_server import setup as setup_wizard
            setup_wizard.main()
        except Exception as exc:
            print(f"Setup wizard failed or unavailable: {exc}")
            print("You can run it manually: python pi_server/setup.py")


if __name__ == '__main__':
    print("Starting Raspberry Pi Printer Server...")
    _run_setup_if_needed()
    print("Press Ctrl+C to stop the server.\n")
    # Import app after setup so .env is present before load_dotenv() runs
    from pi_server.app import main as app_main
    app_main()


