import base64
import io
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw

class PrintSimulator:
    """Simulate thermal printer by parsing ESC/POS and generating preview images"""
    
    def __init__(self, log_dir):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Create images subdirectory for 30-day log
        self.images_dir = self.log_dir / 'images'
        self.images_dir.mkdir(exist_ok=True)
    
    def simulate_print(self, escpos_data, username, user_id):
        """
        Simulate printing by parsing ESC/POS and generating a preview image
        
        Args:
            escpos_data: bytes - ESC/POS command sequence
            username: str - Discord username
            user_id: int - Discord user ID
        
        Returns:
            dict: {
                'success': bool,
                'image_b64': str (base64 encoded PNG),
                'message': str,
                'error_code': str (if error)
            }
        """
        try:
            # Parse ESC/POS commands and extract image data
            image = self.parse_escpos(escpos_data)
            
            if image is None:
                return {
                    'success': False,
                    'message': 'Failed to parse ESC/POS data',
                    'error_code': 'PARSE_ERROR'
                }
            
            # Save image to log (30-day retention)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            image_filename = f"{timestamp}_{user_id}_{username}.png"
            image_path = self.images_dir / image_filename
            
            image.save(image_path, 'PNG')
            
            # Convert image to base64 for return
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            img_bytes = img_byte_arr.getvalue()
            img_b64 = base64.b64encode(img_bytes).decode('utf-8')
            
            # Clean up old images (older than 30 days)
            self.cleanup_old_images()
            
            return {
                'success': True,
                'image_b64': img_b64,
                'message': 'Print simulated successfully',
                'image_path': str(image_path)
            }
        
        except Exception as e:
            print(f"Error in simulate_print: {e}")
            return {
                'success': False,
                'message': f'Simulation error: {str(e)}',
                'error_code': 'SIMULATION_ERROR'
            }
    
    def parse_escpos(self, escpos_data):
        """
        Parse ESC/POS commands and reconstruct the image
        
        This function extracts raster image commands (GS v 0) from ESC/POS data
        and reconstructs the printed output as a PIL Image
        
        Args:
            escpos_data: bytes - ESC/POS command sequence
        
        Returns:
            PIL.Image or None
        """
        try:
            # Find all GS v 0 raster commands
            # Format: GS v 0 m xL xH yL yH [data...]
            # GS = 0x1D, v = 0x76, 0 = 0x30
            
            image_lines = []
            width_bytes = None
            i = 0
            
            while i < len(escpos_data):
                # Look for GS v 0 sequence
                if (i + 7 < len(escpos_data) and 
                    escpos_data[i] == 0x1D and 
                    escpos_data[i+1] == 0x76 and 
                    escpos_data[i+2] == 0x30):
                    
                    # Found raster command
                    m = escpos_data[i+3]  # mode
                    xL = escpos_data[i+4]
                    xH = escpos_data[i+5]
                    yL = escpos_data[i+6]
                    yH = escpos_data[i+7]
                    
                    # Calculate dimensions
                    width_bytes_line = xL + (xH << 8)
                    height_lines = yL + (yH << 8)
                    
                    if width_bytes is None:
                        width_bytes = width_bytes_line
                    
                    # Extract raster data
                    data_start = i + 8
                    data_length = width_bytes_line * height_lines
                    
                    if data_start + data_length <= len(escpos_data):
                        raster_data = escpos_data[data_start:data_start + data_length]
                        
                        # Convert raster data to image line
                        for line_idx in range(height_lines):
                            line_start = line_idx * width_bytes_line
                            line_end = line_start + width_bytes_line
                            line_bytes = raster_data[line_start:line_end]
                            image_lines.append(line_bytes)
                        
                        i = data_start + data_length
                    else:
                        i += 1
                else:
                    i += 1
            
            if not image_lines or width_bytes is None:
                return self.create_fallback_image()
            
            width_px = width_bytes * 8
            height_px = len(image_lines)
            
            image = Image.new('1', (width_px, height_px), 1)
            pixels = image.load()
            
            for y, line_data in enumerate(image_lines):
                for byte_idx, byte_val in enumerate(line_data):
                    for bit_idx in range(8):
                        x = byte_idx * 8 + bit_idx
                        if x < width_px and (byte_val & (1 << (7 - bit_idx))):
                            pixels[x, y] = 0
            
            image = image.convert('L')
            return image
        
        except Exception as e:
            print(f"Error parsing ESC/POS: {e}")
            return self.create_fallback_image()
    
    def create_fallback_image(self):
        """Create a fallback image when parsing fails"""
        image = Image.new('L', (576, 100), 255)
        draw = ImageDraw.Draw(image)
        draw.text((10, 10), "Print Simulated", fill=0)
        draw.text((10, 40), "(Preview unavailable)", fill=0)
        return image
    
    def cleanup_old_images(self):
        """Delete images older than 30 days"""
        try:
            import time
            current_time = time.time()
            thirty_days = 30 * 24 * 60 * 60
            
            for image_file in self.images_dir.glob('*.png'):
                if current_time - image_file.stat().st_mtime > thirty_days:
                    image_file.unlink()
                    print(f"Deleted old image: {image_file.name}")
        except Exception as e:
            print(f"Error cleaning up old images: {e}")
    
    def get_stored_images(self, days=30):
        """Get list of stored images from the last N days"""
        try:
            import time
            current_time = time.time()
            cutoff_time = current_time - (days * 24 * 60 * 60)
            
            images = []
            for image_file in sorted(self.images_dir.glob('*.png'), reverse=True):
                if image_file.stat().st_mtime >= cutoff_time:
                    images.append({
                        'filename': image_file.name,
                        'path': str(image_file),
                        'timestamp': datetime.fromtimestamp(image_file.stat().st_mtime).isoformat()
                    })
            
            return images
        except Exception as e:
            print(f"Error getting stored images: {e}")
            return []
