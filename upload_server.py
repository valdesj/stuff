"""Web upload server for receiving images from mobile devices."""
import os
import socket
import threading
import io
from typing import Callable, Optional
from datetime import datetime
import qrcode
from PIL import Image

try:
    from flask import Flask, request, render_template_string, jsonify
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False


class UploadServer:
    """Lightweight web server for receiving image uploads from phones."""

    def __init__(self, upload_callback: Callable[[str, bytes], None], port: int = 5000):
        """
        Initialize the upload server.

        Args:
            upload_callback: Function to call when an image is uploaded (filename, image_bytes)
            port: Port to run the server on
        """
        if not FLASK_AVAILABLE:
            raise ImportError("Flask is not available. Install with: pip install flask")

        self.port = port
        self.upload_callback = upload_callback
        self.app = Flask(__name__)
        self.server_thread = None
        self.is_running = False
        self.upload_count = 0

        # Configure Flask
        self.app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload
        self.app.config['UPLOAD_FOLDER'] = '/tmp/uploads'

        # Suppress Flask logging to avoid cluttering console
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)

        self._setup_routes()

    def _setup_routes(self):
        """Set up Flask routes."""

        @self.app.route('/')
        def index():
            """Serve the upload page."""
            return render_template_string(self._get_upload_html())

        @self.app.route('/upload', methods=['POST'])
        def upload():
            """Handle image upload."""
            try:
                if 'image' not in request.files:
                    return jsonify({'success': False, 'error': 'No image provided'}), 400

                file = request.files['image']
                if file.filename == '':
                    return jsonify({'success': False, 'error': 'No file selected'}), 400

                # Read image data
                image_data = file.read()

                # Generate unique filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"upload_{timestamp}_{self.upload_count}.jpg"
                self.upload_count += 1

                # Call the callback
                self.upload_callback(filename, image_data)

                return jsonify({'success': True, 'message': 'Image uploaded successfully!'})

            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/status')
        def status():
            """Health check endpoint."""
            return jsonify({'status': 'running', 'uploads': self.upload_count})

    def _get_upload_html(self) -> str:
        """Get the HTML for the upload page."""
        return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Upload Visit Records</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            padding: 30px;
            max-width: 500px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        h1 {
            color: #333;
            font-size: 24px;
            margin-bottom: 10px;
            text-align: center;
        }
        .subtitle {
            color: #666;
            font-size: 14px;
            text-align: center;
            margin-bottom: 30px;
        }
        .upload-area {
            border: 3px dashed #667eea;
            border-radius: 15px;
            padding: 40px 20px;
            text-align: center;
            background: #f8f9ff;
            transition: all 0.3s ease;
            cursor: pointer;
        }
        .upload-area:hover {
            border-color: #764ba2;
            background: #f0f2ff;
        }
        .upload-area.dragover {
            border-color: #764ba2;
            background: #e8ebff;
            transform: scale(1.02);
        }
        .camera-icon {
            font-size: 60px;
            margin-bottom: 15px;
        }
        .upload-text {
            color: #667eea;
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 10px;
        }
        .upload-hint {
            color: #888;
            font-size: 14px;
        }
        input[type="file"] {
            display: none;
        }
        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            width: 100%;
            margin-top: 20px;
            transition: transform 0.2s ease;
        }
        .btn:hover {
            transform: translateY(-2px);
        }
        .btn:active {
            transform: translateY(0);
        }
        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        .preview {
            margin-top: 20px;
            border-radius: 10px;
            overflow: hidden;
            display: none;
        }
        .preview img {
            width: 100%;
            height: auto;
            display: block;
        }
        .status {
            margin-top: 15px;
            padding: 15px;
            border-radius: 10px;
            text-align: center;
            font-weight: 600;
            display: none;
        }
        .status.success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .status.error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .upload-count {
            text-align: center;
            color: #667eea;
            font-weight: 600;
            margin-top: 15px;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📷 Upload Visit Records</h1>
        <p class="subtitle">Take a photo of your paper records to import</p>

        <div class="upload-area" id="uploadArea" onclick="document.getElementById('fileInput').click()">
            <div class="camera-icon">📸</div>
            <div class="upload-text">Tap to Take Photo</div>
            <div class="upload-hint">or drag and drop an image here</div>
        </div>

        <input type="file" id="fileInput" accept="image/*" capture="environment" onchange="handleFile(this.files[0])">

        <div class="preview" id="preview">
            <img id="previewImg" src="" alt="Preview">
        </div>

        <button class="btn" id="uploadBtn" onclick="uploadImage()" disabled>Upload Image</button>

        <div class="status" id="status"></div>
        <div class="upload-count" id="uploadCount"></div>
    </div>

    <script>
        let selectedFile = null;
        let uploadCount = 0;

        // Drag and drop handlers
        const uploadArea = document.getElementById('uploadArea');

        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });

        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');

            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFile(files[0]);
            }
        });

        function handleFile(file) {
            if (!file) return;

            // Validate file type
            if (!file.type.startsWith('image/')) {
                showStatus('Please select an image file', 'error');
                return;
            }

            selectedFile = file;

            // Show preview
            const reader = new FileReader();
            reader.onload = (e) => {
                document.getElementById('previewImg').src = e.target.result;
                document.getElementById('preview').style.display = 'block';
                document.getElementById('uploadBtn').disabled = false;
            };
            reader.readAsDataURL(file);
        }

        async function uploadImage() {
            if (!selectedFile) return;

            const uploadBtn = document.getElementById('uploadBtn');
            uploadBtn.disabled = true;
            uploadBtn.textContent = 'Uploading...';

            const formData = new FormData();
            formData.append('image', selectedFile);

            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();

                if (result.success) {
                    uploadCount++;
                    showStatus('✓ Image uploaded successfully!', 'success');
                    updateUploadCount();

                    // Reset for next upload
                    setTimeout(() => {
                        resetForm();
                    }, 1500);
                } else {
                    showStatus('✗ Upload failed: ' + result.error, 'error');
                    uploadBtn.disabled = false;
                    uploadBtn.textContent = 'Upload Image';
                }
            } catch (error) {
                showStatus('✗ Upload failed: ' + error.message, 'error');
                uploadBtn.disabled = false;
                uploadBtn.textContent = 'Upload Image';
            }
        }

        function showStatus(message, type) {
            const status = document.getElementById('status');
            status.textContent = message;
            status.className = 'status ' + type;
            status.style.display = 'block';
        }

        function updateUploadCount() {
            const countEl = document.getElementById('uploadCount');
            countEl.textContent = uploadCount === 1 ? '1 image uploaded' : uploadCount + ' images uploaded';
        }

        function resetForm() {
            selectedFile = null;
            document.getElementById('preview').style.display = 'none';
            document.getElementById('uploadBtn').disabled = true;
            document.getElementById('uploadBtn').textContent = 'Upload Image';
            document.getElementById('fileInput').value = '';
            document.getElementById('status').style.display = 'none';
        }
    </script>
</body>
</html>
        '''

    def get_local_ip(self) -> Optional[str]:
        """Get the local IP address of this machine."""
        try:
            # Create a socket to get the local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception:
            return None

    def get_server_url(self) -> Optional[str]:
        """Get the server URL (for QR code generation)."""
        ip = self.get_local_ip()
        if ip:
            return f"http://{ip}:{self.port}"
        return None

    def generate_qr_code(self) -> Optional[Image.Image]:
        """
        Generate a QR code for the upload URL.

        Returns:
            PIL Image object or None if server URL is unavailable
        """
        url = self.get_server_url()
        if not url:
            return None

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        return img

    def start(self):
        """Start the web server in a background thread."""
        if self.is_running:
            return

        def run_server():
            self.app.run(host='0.0.0.0', port=self.port, debug=False, use_reloader=False)

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        self.is_running = True

    def stop(self):
        """Stop the web server."""
        # Flask doesn't have a clean shutdown method when running in a thread
        # The daemon thread will be killed when the main program exits
        self.is_running = False

    def is_available(self) -> bool:
        """Check if the upload server is available."""
        return FLASK_AVAILABLE
