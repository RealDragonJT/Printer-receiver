"""
Printer handler for TM-T88IV thermal printer
This module handles communication with the actual printer hardware
"""

import os
import time


class PrinterHandler:
    """Handle communication with TM-T88IV thermal printer"""
    
    def __init__(self):
        self.printer = None
        self.printer_connected = False
        self.write_chunk_size = self._load_chunk_size()
        self.write_chunk_delay = self._load_chunk_delay()
        self._initialize_printer()
    
    def _initialize_printer(self):
        """Initialize connection to the printer"""
        try:
            # Import python-escpos library
            from escpos.printer import Usb, Network, Serial
            
            # Try to connect to printer
            # Option 1: USB connection (most common)
            try:
                # TM-T88IV USB vendor and product IDs
                # These may need to be adjusted based on your specific model
                # Use keyword args so timeout stays unlimited and endpoints are correct.
                self.printer = Usb(
                    0x04B8,
                    0x0202,
                    timeout=0,
                    in_ep=0x82,
                    out_ep=0x01,
                )
                self.printer_connected = True
                print("Printer connected via USB")
                self.test_print()
                return
            except Exception as e:
                print(f"USB connection failed: {e}")
            
            # Option 2: Network connection
            try:
                # If printer has network interface
                # Adjust IP address as needed
                import os
                printer_ip = os.getenv('PRINTER_IP', '192.168.1.100')
                self.printer = Network(printer_ip)
                self.printer_connected = True
                print(f"Printer connected via Network at {printer_ip}")
                return
            except Exception as e:
                print(f"Network connection failed: {e}")
            
            # Option 3: Serial connection
            try:
                serial_port = os.getenv('PRINTER_SERIAL', '/dev/ttyUSB0')
                self.printer = Serial(serial_port)
                self.printer_connected = True
                print(f"Printer connected via Serial at {serial_port}")
                return
            except Exception as e:
                print(f"Serial connection failed: {e}")
            
            print("WARNING: Could not connect to printer. All print jobs will fail.")
            self.printer_connected = False
        
        except ImportError:
            print("ERROR: python-escpos library not installed")
            print("Install with: pip install python-escpos")
            self.printer_connected = False
    
    def print_escpos(self, escpos_data):
        """
        Send ESC/POS commands directly to the printer
        
        Args:
            escpos_data: bytes - Raw ESC/POS command sequence
        
        Returns:
            dict: {
                'success': bool,
                'message': str,
                'error_code': str (if error)
            }
        """
        if not self.printer_connected or self.printer is None:
            return {
                'success': False,
                'message': 'Printer not connected',
                'error_code': 'NO_PRINTER'
            }
        
        try:
            # Send raw ESC/POS data to printer
            if not escpos_data:
                return {
                    'success': True,
                    'message': 'No data to print'
                }
            
            if isinstance(escpos_data, (bytes, bytearray, memoryview)):
                data = bytes(escpos_data)
            else:
                raise TypeError("ESC/POS data must be bytes-like")
            
            current_chunk_size = self.write_chunk_size
            current_delay = self.write_chunk_delay
            min_chunk_size = 64 if os.name == 'nt' else 256
            index = 0
            reinitialized_once = False
            
            while index < len(data):
                chunk_len = min(current_chunk_size, len(data) - index)
                chunk = data[index:index + chunk_len]
                
                try:
                    # Split large payloads to prevent USB timeouts on Windows/libusb.
                    self.printer._raw(chunk)
                    index += chunk_len
                    if current_delay:
                        time.sleep(current_delay)
                except Exception as exc:
                    error_text = str(exc).lower()
                    
                    if 'timeout' in error_text and current_chunk_size > min_chunk_size:
                        # Reduce chunk size and retry same block.
                        current_chunk_size = max(min_chunk_size, current_chunk_size // 2)
                        current_delay = max(current_delay, 0.05 if os.name == 'nt' else 0.0)
                        print(f"USB timeout detected. Reducing chunk size to {current_chunk_size} bytes.")
                        time.sleep(0.1)
                        continue
                    
                    # Attempt to reinitialize printer once on timeout errors.
                    if 'timeout' in error_text:
                        if not reinitialized_once:
                            print("USB timeout persists; reinitializing printer connection.")
                            self._initialize_printer()
                            reinitialized_once = True
                            if not self.printer_connected or self.printer is None:
                                raise
                            time.sleep(0.2)
                            continue
                    
                    raise
            
            return {
                'success': True,
                'message': 'Print job sent successfully'
            }
        
        except Exception as e:
            error_msg = str(e).lower()
            
            # Detect specific error types
            if 'paper' in error_msg or 'cover' in error_msg:
                return {
                    'success': False,
                    'message': 'Printer is out of paper or cover is open',
                    'error_code': 'OUT_OF_PAPER'
                }
            elif 'offline' in error_msg or 'not responding' in error_msg:
                return {
                    'success': False,
                    'message': 'Printer is offline',
                    'error_code': 'PRINTER_OFFLINE'
                }
            else:
                return {
                    'success': False,
                    'message': f'Printer error: {str(e)}',
                    'error_code': 'PRINTER_ERROR'
                }
    
    def get_status(self):
        """
        Get printer status
        
        Returns:
            dict: Status information
        """
        if not self.printer_connected:
            return {
                'online': False,
                'message': 'Printer not connected'
            }
        
        try:
            return {
                'online': True,
                'message': 'Printer is ready',
                'model': 'TM-T88IV'
            }
        
        except Exception as e:
            return {
                'online': False,
                'message': f'Cannot get printer status: {str(e)}'
            }
    
    def test_print(self):
        """
        Print a test page
        
        Returns:
            dict: Result of test print
        """
        test_escpos = b'\x1b@'  # Initialize
        test_escpos += b'=== PRINTER TEST ===\n'
        test_escpos += b'TM-T88IV Thermal Printer\n'
        test_escpos += b'Discord Print Bot\n'
        test_escpos += b'=' * 32 + b'\n'
        test_escpos += b'\n\n\n'
        test_escpos += b'\x1dV\x42\x00'  # Partial cut
        
        return self.print_escpos(test_escpos)
    
    def cut_paper(self):
        """Execute paper cut command"""
        if not self.printer_connected:
            return {'success': False, 'message': 'Printer not connected'}
        
        try:
            cut_cmd = b'\x1dV\x42\x00'
            self.printer._raw(cut_cmd)
            return {'success': True, 'message': 'Paper cut executed'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    @staticmethod
    def _load_chunk_size():
        """Get chunk size for USB writes (env adjustable)."""
        # Windows libusb implementations tend to time out on large writes,
        # so use conservative defaults that can be overridden via env.
        default_size = 128 if os.name == 'nt' else 2048
        try:
            value = int(os.getenv('PRINTER_WRITE_CHUNK_SIZE', default_size))
            return max(256, min(8192, value))
        except (TypeError, ValueError):
            return default_size

    @staticmethod
    def _load_chunk_delay():
        """Get optional delay between chunks (env adjustable)."""
        default_delay = 0.05 if os.name == 'nt' else 0.0
        try:
            value = float(os.getenv('PRINTER_WRITE_CHUNK_DELAY', str(default_delay)))
            return max(0.0, value)
        except (TypeError, ValueError):
            return 0.0
