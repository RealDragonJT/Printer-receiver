"""
Printer handler for TM-T88IV thermal printer
This module handles communication with the actual printer hardware
"""

import os
import time
import configparser
import threading
from pathlib import Path


class PrinterHandler:
    """Handle communication with TM-T88IV thermal printer"""
    
    def __init__(self):
        self.printer = None
        self.printer_connected = False
        self.write_chunk_size = self._load_chunk_size()
        self.write_chunk_delay = self._load_chunk_delay()
        self.config = self._load_config()
        self.print_lock = threading.Lock()  # Lock to prevent concurrent print jobs
        self._initialize_printer()
    
    def _initialize_printer(self):
        """Initialize connection to the printer"""
        try:
            # Import python-escpos library
            from escpos.printer import Usb, Network, Serial
            
            # Use config.ini if provided
            connection = (self.config.get('printer', 'connection', fallback='usb') if self.config else 'usb').lower()
            if connection == 'usb':
                try:
                    # Configurable USB IDs
                    vid_str = self.config.get('printer', 'usb_vendor_id', fallback='') if self.config else ''
                    pid_str = self.config.get('printer', 'usb_product_id', fallback='') if self.config else ''
                    if not vid_str or not pid_str:
                        detected = self.detect_printers_usb()
                        if detected:
                            vid, pid = detected[0]
                        else:
                            vid = 0x04B8
                            pid = 0x0202
                    else:
                        vid = int(vid_str, 16) if isinstance(vid_str, str) and vid_str else 0x04B8
                        pid = int(pid_str, 16) if isinstance(pid_str, str) and pid_str else 0x0202
                    # Use timeout=5 for USB operations to prevent hanging when cover is open
                    self.printer = Usb(vid, pid, timeout=5, in_ep=0x82, out_ep=0x01)
                    self.printer_connected = True
                    print(f"Printer connected via USB (VID=0x{vid:04X}, PID=0x{pid:04X})")
                    self.test_print()
                    return
                except Exception as e:
                    print(f"USB connection failed: {e}")
                    # fallthrough to try others
            if connection == 'network':
                try:
                    printer_ip = self.config.get('printer', 'ip', fallback=os.getenv('PRINTER_IP', '')) if self.config else os.getenv('PRINTER_IP', '')
                    port = int(self.config.get('printer', 'port', fallback='9100')) if self.config else 9100
                    self.printer = Network(printer_ip, port=port)
                    self.printer_connected = True
                    print(f"Printer connected via Network at {printer_ip}:{port}")
                    return
                except Exception as e:
                    print(f"Network connection failed: {e}")
            if connection == 'serial':
                try:
                    serial_port = self.config.get('printer', 'device', fallback=os.getenv('PRINTER_SERIAL', '/dev/ttyUSB0')) if self.config else os.getenv('PRINTER_SERIAL', '/dev/ttyUSB0')
                    baudrate = int(self.config.get('printer', 'baudrate', fallback='19200')) if self.config else 19200
                    self.printer = Serial(serial_port, baudrate=baudrate)
                    self.printer_connected = True
                    print(f"Printer connected via Serial at {serial_port} (baud {baudrate})")
                    return
                except Exception as e:
                    print(f"Serial connection failed: {e}")

            print("WARNING: Could not connect to printer. All print jobs will fail.")
            self.printer_connected = False
        
        except ImportError:
            print("ERROR: python-escpos library not installed")
            print("Install with: pip install python-escpos")
            self.printer_connected = False

    @staticmethod
    def detect_printers_usb():
        """Return a list of (vid, pid) for connected USB printers (best-effort)."""
        devices = []
        try:
            import usb.core  # pyusb
            for dev in usb.core.find(find_all=True):
                vid = int(dev.idVendor)
                pid = int(dev.idProduct)
                # Prefer Epson (0x04B8) but include all
                devices.append((vid, pid))
            # Sort with Epson first
            devices.sort(key=lambda vp: 0 if vp[0] == 0x04B8 else 1)
        except Exception:
            pass
        if not devices and os.name == 'nt':
            print("Windows: If using TM-T88IV, install libusbK driver via Zadig and retry.")
        return devices

    @staticmethod
    def _load_config():
        """Load optional config.ini for printer connection settings."""
        try:
            cfg_path = Path(__file__).resolve().parents[1] / 'config.ini'
            if not cfg_path.exists():
                return None
            cfg = configparser.ConfigParser()
            cfg.read(cfg_path)
            return cfg
        except Exception:
            return None
    
    def _feed_with_timeout(self, timeout_seconds=2):
        """
        Try feed command with timeout and verification
        
        Returns:
            (success, error) tuple
        """
        feed_result = {'success': False, 'error': None, 'completed': False, 'started': False}
        feed_exception = [None]  # Use list to allow modification in nested function
        
        def feed_operation():
            try:
                feed_result['started'] = True
                # ESC J n (feed n dot lines) - feed minimal amount for speed
                feed_cmd = b"\x1b\x4a\x02"  # Feed 2 dot lines (minimal)
                self.printer._raw(feed_cmd)
                time.sleep(0.1)  # Short wait
                
                feed_result['success'] = True
                feed_result['completed'] = True
            except Exception as e:
                feed_exception[0] = e
                feed_result['error'] = str(e)
                feed_result['completed'] = True
        
        # Run feed in a separate thread with timeout
        feed_thread = threading.Thread(target=feed_operation, name="FeedTestThread")
        feed_thread.daemon = True
        start_time = time.time()
        feed_thread.start()
        feed_thread.join(timeout=timeout_seconds)
        
        if feed_thread.is_alive():
            # Thread is still running = timeout occurred
            return False, f"Feed timeout after {timeout_seconds}s"
        
        if not feed_result.get('started', False):
            return False, "Feed operation didn't start"
        
        if not feed_result['completed']:
            return False, "Feed command didn't complete"
        
        if feed_result['error']:
            return False, feed_result['error']
        
        if feed_result['success']:
            return True, None
        
        return False, "Unknown feed error"
    
    def _read_status_byte(self, timeout_ms=800):
        """Try to read printer status byte via USB with timeout"""
        status_result = {'value': None, 'error': None}
        
        def read_operation():
            try:
                if hasattr(self.printer, 'device') and hasattr(self.printer, 'in_ep'):
                    import usb.core
                    dev = self.printer.device
                    IN_EP = self.printer.in_ep
                    
                    # Request status
                    self.printer._raw(b"\x10\x04")  # DLE EOT
                    time.sleep(0.15)  # Shorter wait
                    
                    # Try to read response with timeout
                    try:
                        resp = dev.read(IN_EP, 64, timeout=timeout_ms)
                        if resp and len(resp) > 0:
                            status_result['value'] = resp[0]
                    except usb.core.USBError as e:
                        # USB read timeout/error - printer might not respond
                        status_result['error'] = str(e)
            except Exception as e:
                status_result['error'] = str(e)
        
        # Run status read in a separate thread with timeout
        read_thread = threading.Thread(target=read_operation)
        read_thread.daemon = True
        read_thread.start()
        read_thread.join(timeout=(timeout_ms / 1000.0) + 0.5)  # Thread timeout slightly longer than USB timeout
        
        if read_thread.is_alive():
            return None
        
        if status_result['error']:
            return None
        
        return status_result['value']
    
    def check_paper_status(self):
        """
        Check printer paper status using feed test and status byte verification
        
        Returns:
            dict with 'paper_ok' boolean and 'error_code' if paper is out
        """
        if not self.printer_connected or self.printer is None:
            return {'paper_ok': False, 'error_code': 'NO_PRINTER'}
        
        try:
            # First, try to get status byte before feed
            status_before = self._read_status_byte(timeout_ms=500)
            if status_before is not None:
                paper_end_before = bool(status_before & 0x08)
                cover_open_before = bool(status_before & 0x20)
                if paper_end_before or cover_open_before:
                    return {'paper_ok': False, 'error_code': 'OUT_OF_PAPER'}
            
            # Try feed with 2 second timeout
            try:
                feed_success, feed_error = self._feed_with_timeout(timeout_seconds=2)
            except Exception as feed_ex:
                feed_success, feed_error = False, str(feed_ex)
            
            # Check status after feed
            time.sleep(0.2)
            status_after = self._read_status_byte(timeout_ms=500)
            
            if status_after is not None:
                paper_end = bool(status_after & 0x08)
                cover_open = bool(status_after & 0x20)
                if paper_end or cover_open:
                    return {'paper_ok': False, 'error_code': 'OUT_OF_PAPER'}
                else:
                    return {'paper_ok': True}
            
            # Fall back to feed result if status read fails
            if feed_success:
                return {'paper_ok': True}
            else:
                return {'paper_ok': False, 'error_code': 'OUT_OF_PAPER'}
                
        except Exception as e:
            # If check fails, assume paper out to be safe
            return {'paper_ok': False, 'error_code': 'OUT_OF_PAPER'}
    
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
        
        # Check paper status before acquiring lock (fast fail if paper out)
        try:
            paper_status = self.check_paper_status()
            print(f"[PrinterHandler] Paper status check result: {paper_status}")
        except Exception as e:
            # If check fails, assume paper out to prevent printing and queue the job
            print(f"[PrinterHandler] Paper status check exception: {e}")
            import traceback
            traceback.print_exc()
            paper_status = {'paper_ok': False, 'error_code': 'OUT_OF_PAPER'}
        
        if not paper_status.get('paper_ok', True):
            print(f"[PrinterHandler] Paper check failed, returning OUT_OF_PAPER error")
            return {
                'success': False,
                'message': 'Printer is out of paper or cover is open',
                'error_code': paper_status.get('error_code', 'OUT_OF_PAPER')
            }
        
        print(f"[PrinterHandler] Paper check passed, acquiring lock and printing...")
        
        # Acquire lock to prevent concurrent print jobs (prevents ESC/POS command corruption)
        with self.print_lock:
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
                        error_type = type(exc).__name__
                        error_str = str(exc)
                        
                        print(f"[PrinterHandler] Error during chunk write: {error_str} ({error_type})")
                        
                        # USB timeout errors can be transient - try retry first before assuming paper out
                        if 'timeout' in error_text and self.printer_connected:
                            if not reinitialized_once:
                                print(f"[PrinterHandler] Timeout persists, reinitializing printer connection")
                                try:
                                    self._initialize_printer()
                                    reinitialized_once = True
                                    if not self.printer_connected or self.printer is None:
                                        raise
                                    current_delay = max(current_delay, 0.05 if os.name == 'nt' else 0.0)
                                    time.sleep(0.3)  # Wait after reinit
                                    continue
                                except Exception as reinit_exc:
                                    print(f"[PrinterHandler] Reinitialization failed: {reinit_exc}")
                                    # If reinit fails, likely paper out or hardware issue
                                    return {
                                        'success': False,
                                        'message': 'Printer is out of paper or cover is open',
                                        'error_code': 'OUT_OF_PAPER'
                                    }
                            
                            # If we've tried everything, likely paper out
                            print(f"[PrinterHandler] Timeout error persists after retries, assuming paper out")
                            return {
                                'success': False,
                                'message': 'Printer is out of paper or cover is open',
                                'error_code': 'OUT_OF_PAPER'
                            }
                        
                        # For non-timeout errors, re-raise to be handled by outer exception handler
                        raise
                
                print(f"[PrinterHandler] Print job completed successfully")
                return {
                    'success': True,
                    'message': 'Print job sent successfully'
                }
            
            except Exception as e:
                error_msg = str(e)
                error_msg_lower = error_msg.lower()
                error_type = type(e).__name__
                full_error = f"{error_msg_lower} {error_type.lower()}"
                
                print(f"[PrinterHandler] Exception during print: {error_msg} ({error_type})")
                import traceback
                traceback.print_exc()
                
                # Don't check paper status here (inside lock) as it uses threading
                # Instead, use error message patterns to detect paper out
                
                # Detect offline/connection errors first
                offline_keywords = ['offline', 'not responding', 'unreachable', 'connection refused', 'connection reset']
                if any(keyword in error_msg_lower for keyword in offline_keywords):
                    return {
                        'success': False,
                        'message': 'Printer is offline or unreachable',
                        'error_code': 'PRINTER_OFFLINE'
                    }
                
                # Detect specific paper-related keywords (be more conservative)
                paper_keywords = ['paper end', 'cover open', 'paper empty', 'roll empty', 'paper sensor']
                if any(keyword in full_error for keyword in paper_keywords):
                    return {
                        'success': False,
                        'message': 'Printer is out of paper or cover is open',
                        'error_code': 'OUT_OF_PAPER'
                    }
                
                # For USB errors, be more specific - only timeout might indicate paper out
                if self.printer_connected:
                    # Only timeout errors are likely paper out, other USB errors might be different issues
                    if 'timeout' in error_msg_lower:
                        return {
                            'success': False,
                            'message': 'Printer is out of paper or cover is open',
                            'error_code': 'OUT_OF_PAPER'
                        }
                    
                    # For other USB errors, return generic error instead of assuming paper out
                    usb_error_patterns = ['usb', 'libusb', 'device', 'i/o', 'broken pipe', 'bad file descriptor']
                    if any(pattern in full_error for pattern in usb_error_patterns):
                        return {
                            'success': False,
                            'message': f'Printer communication error: {error_msg}',
                            'error_code': 'PRINTER_ERROR'
                        }
                    
                    # Default to generic error instead of assuming paper out
                    return {
                        'success': False,
                        'message': f'Printer error: {error_msg}',
                        'error_code': 'PRINTER_ERROR'
                    }
                
                # Printer not connected or other error
                return {
                    'success': False,
                    'message': f'Printer error: {error_msg}',
                    'error_code': 'PRINTER_ERROR'
                }
        # Lock is automatically released here
    
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
        # Use conservative chunk size by default to avoid libusb timeouts.
        default_size = 128
        try:
            value = int(os.getenv('PRINTER_WRITE_CHUNK_SIZE', default_size))
            return max(64, min(8192, value))
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
