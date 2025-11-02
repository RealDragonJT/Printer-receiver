from flask import Flask, request, jsonify
import base64
import hmac
import hashlib
import os
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Import handlers
from pi_server.simulator import PrintSimulator
from pi_server.printer_handler import PrinterHandler
from pi_server.job_queue import get_queue

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration
TESTING_MODE = os.getenv('TESTING_MODE', 'false').lower() == 'true'
LOG_DIR = Path('print_logs')
LOG_DIR.mkdir(exist_ok=True)
PRINTER_SHARED_SECRET = os.getenv('PRINTER_SHARED_SECRET', '').strip()
SIGNATURE_MAX_AGE = int(os.getenv('PRINTER_SIGNATURE_MAX_AGE', '300'))

# Initialize printer handler
if TESTING_MODE:
    print("Running in TESTING MODE - using simulator")
    printer = PrintSimulator(LOG_DIR)
else:
    print("Running in PRODUCTION MODE - using real printer")
    printer = PrinterHandler()

if PRINTER_SHARED_SECRET:
    print("Security: Shared secret enabled - requests must be signed.")
elif TESTING_MODE:
    print("Security: PRINTER_SHARED_SECRET not set. Running unsigned in testing mode.")
else:
    raise RuntimeError("PRINTER_SHARED_SECRET must be set when TESTING_MODE is false.")

@app.route('/print', methods=['POST'])
def print_job():
    """
    Handle print job request
    
    Expected JSON payload:
    {
        'escpos_data': '<base64 encoded ESC/POS commands>',
        'username': '<Discord username>',
        'user_id': '<Discord user ID>',
        'testing_mode': true/false
    }
    
    Returns:
    {
        'success': true/false,
        'message': '<status message>',
        'image': '<base64 encoded image>' (optional, testing mode only)
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        # Extract data
        escpos_b64 = data.get('escpos_data')
        username = data.get('username', 'Unknown')
        user_id = data.get('user_id', 0)
        
        if not escpos_b64:
            return jsonify({'success': False, 'message': 'No ESC/POS data provided'}), 400
        
        # Verify request signature (optional, depending on configuration)
        verified, error_message = verify_request_signature(request, escpos_b64)
        if not verified:
            return jsonify({'success': False, 'message': error_message}), 401
        
        # Decode ESC/POS data
        try:
            escpos_data = base64.b64decode(escpos_b64)
        except Exception as e:
            return jsonify({'success': False, 'message': f'Invalid base64 data: {str(e)}'}), 400
        
        # Log the print job
        log_print_job(username, user_id)
        
        # Process print job
        if TESTING_MODE:
            # Simulate printing
            result = printer.simulate_print(escpos_data, username, user_id)
            
            if result['success']:
                return jsonify({
                    'success': True,
                    'message': 'Print simulated successfully',
                    'image': result.get('image_b64')
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'message': result.get('message', 'Simulation failed'),
                    'error_code': result.get('error_code', 'SIMULATION_ERROR')
                }), 503
        else:
            # Real printing
            result = printer.print_escpos(escpos_data)
            
            if result['success']:
                # Successful print - clear any queued jobs since paper is available
                queue = get_queue()
                queued_count = queue.queue_size()
                if queued_count > 0:
                    print(f"[App] Print successful - cleared {queued_count} queued job(s)")
                    queue.clear_queue()
                
                return jsonify({
                    'success': True,
                    'message': 'Print job sent to printer'
                }), 200
            else:
                error_code = result.get('error_code', 'PRINTER_ERROR')
                
                # If paper out, queue the job instead of failing
                if error_code == 'OUT_OF_PAPER':
                    queue = get_queue()
                    queue.add_job({
                        'escpos_data': escpos_b64,
                        'username': username,
                        'user_id': user_id,
                        'queued_at': datetime.utcnow().isoformat()
                    })
                    
                    queue_count = queue.queue_size()
                    
                    # Start periodic checking if not already running
                    if not queue.running:
                        queue.start_periodic_check(
                            check_paper_func=lambda: printer.check_paper_status(),
                            print_func=lambda data: printer.print_escpos(base64.b64decode(data))
                        )
                    
                    return jsonify({
                        'success': False,
                        'message': f'Printer is out of paper or cover is open. Your print will be queued and printed automatically once paper is inserted ({queue_count} job(s) in queue).',
                        'error_code': error_code,
                        'queued': True,
                        'queue_size': queue_count
                    }), 503
                else:
                    # Other errors - return normally
                    return jsonify({
                        'success': False,
                        'message': result.get('message', 'Printer error'),
                        'error_code': error_code
                    }), 503
    
    except Exception as e:
        print(f"Error processing print job: {e}")
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}',
            'error_code': 'SERVER_ERROR'
        }), 500

@app.route('/status', methods=['GET'])
def printer_status():
    """
    Get printer status
    
    Returns:
    {
        'online': true/false,
        'mode': 'testing'/'production',
        'message': '<status message>'
    }
    """
    try:
        if TESTING_MODE:
            return jsonify({
                'online': True,
                'mode': 'testing',
                'message': 'Simulator is running'
            }), 200
        else:
            status = printer.get_status()
            return jsonify(status), 200
    except Exception as e:
        return jsonify({
            'online': False,
            'mode': 'testing' if TESTING_MODE else 'production',
            'message': f'Error: {str(e)}'
        }), 500

def log_print_job(username, user_id):
    """Log a print job to file"""
    log_file = LOG_DIR / 'print_log.txt'
    timestamp = datetime.now().isoformat()
    
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"{timestamp}|{username}|{user_id}\n")

@app.route('/', methods=['GET'])
def index():
    """Root endpoint"""
    return jsonify({
        'service': 'Discord Printer API',
        'mode': 'testing' if TESTING_MODE else 'production',
        'status': 'running'
    }), 200

@app.route('/verify', methods=['POST'])
def verify():
    """Signed verification endpoint to confirm shared-secret pairing without printing.

    Expects JSON payload: { 'nonce': '<string>' }
    Requires headers when PRINTER_SHARED_SECRET is set:
      - X-Printer-Timestamp: unix epoch seconds
      - X-Printer-Signature: HMAC-SHA256 hex of f"{timestamp}.{nonce}" with PRINTER_SHARED_SECRET
    """
    try:
        # If no secret configured (testing), accept
        if not PRINTER_SHARED_SECRET:
            return jsonify({'success': True, 'message': 'Unsigned mode'}), 200

        data = request.get_json() or {}
        nonce = str(data.get('nonce', ''))

        signature = request.headers.get('X-Printer-Signature')
        timestamp_header = request.headers.get('X-Printer-Timestamp')

        if not signature or not timestamp_header:
            return jsonify({'success': False, 'message': 'Missing signature headers'}), 401

        try:
            timestamp = int(timestamp_header)
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid timestamp header'}), 401

        current_time = int(time.time())
        if SIGNATURE_MAX_AGE and abs(current_time - timestamp) > SIGNATURE_MAX_AGE:
            return jsonify({'success': False, 'message': 'Signature expired'}), 401

        payload = f"{timestamp_header}.{nonce}".encode('utf-8')
        expected = hmac.new(PRINTER_SHARED_SECRET.encode('utf-8'), payload, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(expected, signature):
            return jsonify({'success': False, 'message': 'Invalid signature'}), 401

        return jsonify({'success': True, 'message': 'Verified'}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {e}'}), 500

def verify_request_signature(request, escpos_b64: str):
    """Verify HMAC signature from the bot server if a shared secret is configured."""
    if not PRINTER_SHARED_SECRET:
        return True, None
    
    signature = request.headers.get('X-Printer-Signature')
    timestamp_header = request.headers.get('X-Printer-Timestamp')
    
    if not signature or not timestamp_header:
        return False, 'Missing signature headers'
    
    try:
        timestamp = int(timestamp_header)
    except ValueError:
        return False, 'Invalid timestamp header'
    
    current_time = int(time.time())
    if SIGNATURE_MAX_AGE and abs(current_time - timestamp) > SIGNATURE_MAX_AGE:
        return False, 'Signature expired'
    
    payload = f"{timestamp_header}.{escpos_b64}".encode('utf-8')
    expected = hmac.new(PRINTER_SHARED_SECRET.encode('utf-8'), payload, hashlib.sha256).hexdigest()
    
    if not hmac.compare_digest(expected, signature):
        return False, 'Invalid signature'
    
    return True, None

def main():
    """Run the Flask server"""
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '0.0.0.0')
    
    print(f"Starting Discord Printer API on {host}:{port}")
    print(f"Mode: {'TESTING' if TESTING_MODE else 'PRODUCTION'}")
    
    # Initialize queue and start periodic checking if jobs are queued
    if not TESTING_MODE:
        queue = get_queue()
        if queue.queue_size() > 0:
            print(f"[App] Found {queue.queue_size()} queued job(s) - starting periodic paper check")
            queue.start_periodic_check(
                check_paper_func=lambda: printer.check_paper_status(),
                print_func=lambda data: printer.print_escpos(base64.b64decode(data))
            )
    
    app.run(host=host, port=port, debug=False)

if __name__ == '__main__':
    main()
