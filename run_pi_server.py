#!/usr/bin/env python3
"""
Convenience script to run the printer server
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from pi_server.app import main

if __name__ == '__main__':
    print("Starting Raspberry Pi Printer Server...")
    print("Make sure you have configured your .env file!")
    print("Press Ctrl+C to stop the server.\n")
    main()


