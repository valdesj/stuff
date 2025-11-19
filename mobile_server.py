"""Flask server for mobile camera upload via QR code."""
import os
import socket
import threading
import tempfile
from pathlib import Path
from flask import Flask, request, render_template_string, jsonify
import qrcode
from io import BytesIO
import base64


class MobileServer:
    """Web server for receiving images from mobile devices."""

    def __init__(self, callback=None):
        """
        Initialize the mobile server.

        Args:
            callback: Function to call when image is received, receives file path
        """
        self.app = Flask(__name__)
        self.callback = callback
        self.server_thread = None
        self.is_running = False
        self.port = 5000
        self.host = '0.0.0.0'
        self.temp_dir = tempfile.mkdtemp(prefix='landscaping_upload_')

        # Setup routes
        self._setup_routes()

    def _setup_routes(self):
        """Setup Flask routes."""

        @self.app.route('/')
        def index():
            """Serve the camera upload page."""
            html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Landscaping Tracker - Upload Photo</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 30px;
            max-width: 500px;
            width: 100%;
        }
        h1 {
            color: #2e7d32;
            margin-bottom: 10px;
            font-size: 24px;
            text-align: center;
        }
        .subtitle {
            color: #666;
            text-align: center;
            margin-bottom: 30px;
            font-size: 14px;
        }
        .camera-btn {
            display: block;
            width: 100%;
            padding: 18px;
            background: #2e7d32;
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 18px;
            font-weight: 600;
            cursor: pointer;
            margin-bottom: 15px;
            transition: all 0.3s;
        }
        .camera-btn:hover {
            background: #1b5e20;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(46, 125, 50, 0.4);
        }
        .camera-btn:disabled {
            background: #ccc;
            cursor: not-allowed;
            transform: none;
        }
        #preview {
            max-width: 100%;
            border-radius: 12px;
            margin-top: 20px;
            display: none;
        }
        .status {
            padding: 15px;
            border-radius: 8px;
            margin-top: 15px;
            text-align: center;
            font-weight: 500;
            display: none;
        }
        .status.success {
            background: #c8e6c9;
            color: #1b5e20;
        }
        .status.error {
            background: #ffcdd2;
            color: #c62828;
        }
        .status.uploading {
            background: #fff9c4;
            color: #f57f17;
        }
        input[type="file"] {
            display: none;
        }
        .icon {
            margin-right: 8px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🌿 Landscaping Tracker</h1>
        <p class="subtitle">Upload visit record photos</p>

        <input type="file" id="fileInput" accept="image/*" capture="environment">
        <button id="cameraBtn" class="camera-btn">
            <span class="icon">📷</span> Take Photo
        </button>

        <img id="preview" alt="Preview">
        <div id="status" class="status"></div>
    </div>

    <script>
        const fileInput = document.getElementById('fileInput');
        const cameraBtn = document.getElementById('cameraBtn');
        const preview = document.getElementById('preview');
        const status = document.getElementById('status');

        cameraBtn.addEventListener('click', () => {
            fileInput.click();
        });

        fileInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            // Show preview
            preview.src = URL.createObjectURL(file);
            preview.style.display = 'block';

            // Show uploading status
            showStatus('Uploading image...', 'uploading');
            cameraBtn.disabled = true;

            // Upload file
            const formData = new FormData();
            formData.append('image', file);

            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();

                if (result.success) {
                    showStatus('✓ Image uploaded successfully!', 'success');
                    setTimeout(() => {
                        preview.style.display = 'none';
                        fileInput.value = '';
                        hideStatus();
                        cameraBtn.disabled = false;
                    }, 2000);
                } else {
                    showStatus('✗ Upload failed: ' + result.error, 'error');
                    cameraBtn.disabled = false;
                }
            } catch (error) {
                showStatus('✗ Upload failed: ' + error.message, 'error');
                cameraBtn.disabled = false;
            }
        });

        function showStatus(message, type) {
            status.textContent = message;
            status.className = 'status ' + type;
            status.style.display = 'block';
        }

        function hideStatus() {
            status.style.display = 'none';
        }
    </script>
</body>
</html>
            """
            return render_template_string(html)

        @self.app.route('/upload', methods=['POST'])
        def upload():
            """Handle image upload from mobile."""
            try:
                if 'image' not in request.files:
                    return jsonify({'success': False, 'error': 'No image provided'}), 400

                file = request.files['image']
                if file.filename == '':
                    return jsonify({'success': False, 'error': 'No file selected'}), 400

                # Save file with timestamp
                from datetime import datetime
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"mobile_upload_{timestamp}.jpg"
                filepath = os.path.join(self.temp_dir, filename)

                file.save(filepath)

                # Call callback if provided
                if self.callback:
                    self.callback(filepath)

                return jsonify({'success': True, 'filename': filename})

            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500

    def get_local_ip(self):
        """Get the local IP address of this machine."""
        try:
            # Create a socket to determine local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except:
            return "127.0.0.1"

    def get_url(self):
        """Get the URL to access the server."""
        ip = self.get_local_ip()
        return f"http://{ip}:{self.port}"

    def generate_qr_code(self):
        """Generate QR code image for the server URL."""
        url = self.get_url()
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to base64 for display
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        return buffer

    def start(self):
        """Start the Flask server in a background thread."""
        if self.is_running:
            return

        def run_server():
            self.app.run(host=self.host, port=self.port, debug=False, use_reloader=False)

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        self.is_running = True

    def stop(self):
        """Stop the Flask server."""
        self.is_running = False
        # Flask doesn't have a clean shutdown in thread mode
        # The daemon thread will terminate when the app closes

    def cleanup(self):
        """Clean up temporary files."""
        import shutil
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except:
            pass
