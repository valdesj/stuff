"""OCR scanning functionality for importing paper records."""
try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    try:
        from PIL import Image
    except ImportError:
        Image = None

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

import re
from datetime import datetime
from typing import List, Dict, Optional
import os
import requests
import base64
import io


class OCRScanner:
    """Handles scanning and parsing paper records using OCR."""

    def __init__(self, use_cloud: bool = True, gemini_api_key: Optional[str] = None):
        """
        Initialize the OCR scanner.

        Args:
            use_cloud: If True, use cloud OCR (requires internet). If False, use local tesseract.
            gemini_api_key: Optional Gemini API key for advanced vision parsing (recommended)
        """
        self.ocr_available = OCR_AVAILABLE
        self.use_cloud = use_cloud
        self.gemini_available = GEMINI_AVAILABLE and gemini_api_key is not None
        self.gemini_api_key = gemini_api_key

        # Initialize Gemini if available
        if self.gemini_available:
            try:
                genai.configure(api_key=gemini_api_key)
                self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
            except Exception as e:
                print(f"Failed to initialize Gemini: {e}")
                self.gemini_available = False

    def is_available(self) -> bool:
        """Check if OCR functionality is available."""
        if self.gemini_available:
            return True  # Gemini is best option
        if self.use_cloud:
            return True  # Cloud OCR is always available if internet works
        return self.ocr_available

    def scan_image_gemini(self, image_path: str) -> Optional[str]:
        """
        Scan an image using Google Gemini Vision API (best for handwritten tables).

        Args:
            image_path: Path to the image file

        Returns:
            Extracted text or None if failed
        """
        if not self.gemini_available:
            return None

        try:
            if Image is None:
                print("PIL not available, cannot use Gemini")
                return None

            # Load image
            img = Image.open(image_path)

            # Create prompt for structured data extraction
            prompt = """
            You are analyzing a handwritten visit schedule table for a landscaping business.

            Please extract ALL visit records from this image. For each visit, provide:
            - Date (in MM/DD/YYYY format)
            - Client name
            - Start time (in HH:MM 24-hour format)
            - End time (in HH:MM 24-hour format)

            Format each visit on a new line as:
            Date: MM/DD/YYYY | Client: [name] | Time: HH:MM-HH:MM

            Example output:
            Date: 01/15/2024 | Client: Smith Residence | Time: 09:30-11:45
            Date: 01/15/2024 | Client: Johnson Lawn Care | Time: 13:30-15:15

            Extract ALL visits you can identify from the table. If the handwriting is unclear, make your best guess.
            Be thorough and extract every visit shown in the image.
            """

            # Generate content with Gemini
            response = self.gemini_model.generate_content([prompt, img])

            if response and response.text:
                return response.text

            return None

        except Exception as e:
            print(f"Gemini OCR failed: {str(e)}")
            return None

    def scan_image_cloud(self, image_path: str) -> Optional[str]:
        """
        Scan an image using cloud OCR API (OCR.space - free, no API key needed).

        Args:
            image_path: Path to the image file

        Returns:
            Extracted text or None if failed
        """
        try:
            # Read image and resize if too large (OCR.space free tier has size limits)
            if Image is None:
                # PIL not available, just read the file
                with open(image_path, 'rb') as f:
                    image_data = f.read()
            else:
                # PIL is available, use it to resize if needed
                img = Image.open(image_path)

                # Resize if larger than 1MB when saved
                max_size = 1024 * 1024  # 1MB
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='JPEG', quality=85)

                # If too large, resize
                if len(img_byte_arr.getvalue()) > max_size:
                    # Resize to 50% and try again
                    new_size = (img.width // 2, img.height // 2)
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                    img_byte_arr = io.BytesIO()
                    img.save(img_byte_arr, format='JPEG', quality=75)

                image_data = img_byte_arr.getvalue()

            # Prepare request to OCR.space API (free tier)
            url = 'https://api.ocr.space/parse/image'

            # Prepare the payload
            files = {
                'file': ('image.jpg', image_data, 'image/jpeg')
            }

            payload = {
                'apikey': 'K87899142388957',  # Public free API key
                'language': 'eng',
                'isOverlayRequired': 'false',
                'OCREngine': '1',  # Use OCR Engine 1 (more permissive on free tier)
                'scale': 'true'
            }

            # Make request with timeout
            response = requests.post(url, files=files, data=payload, timeout=60)

            if response.status_code == 200:
                result = response.json()

                if result.get('IsErroredOnProcessing'):
                    error_msg = result.get('ErrorMessage', ['Unknown error'])[0]
                    print(f"Cloud OCR error: {error_msg}")
                    return None

                # Extract text from result
                parsed_results = result.get('ParsedResults', [])
                if parsed_results:
                    text = parsed_results[0].get('ParsedText', '')
                    return text

            return None

        except requests.exceptions.RequestException as e:
            print(f"Cloud OCR request failed: {str(e)}")
            return None
        except Exception as e:
            print(f"Cloud OCR failed: {str(e)}")
            return None

    def scan_image(self, image_path: str, preprocess: bool = True) -> Optional[str]:
        """
        Scan an image and extract text using OCR.
        Priority: Gemini > Cloud OCR > Local Tesseract

        Args:
            image_path: Path to the image file
            preprocess: Whether to preprocess image for better OCR accuracy (local tesseract only)

        Returns:
            Extracted text or None if failed
        """
        if not os.path.exists(image_path):
            return None

        # Try Gemini first (best for handwritten tables)
        if self.gemini_available:
            print("Using Gemini Vision AI for OCR...")
            text = self.scan_image_gemini(image_path)
            if text:
                return text
            print("Gemini OCR failed, trying other methods...")

        # Try cloud OCR second (no installation needed)
        if self.use_cloud:
            print("Using cloud OCR...")
            text = self.scan_image_cloud(image_path)
            if text:
                return text
            print("Cloud OCR failed, trying local tesseract...")

        # Fallback to local tesseract
        if not self.ocr_available:
            return None

        try:
            image = Image.open(image_path)

            # Preprocess image for better OCR accuracy
            if preprocess:
                image = self._preprocess_image(image)

            # Use different PSM modes for better results
            custom_config = r'--oem 3 --psm 6'  # PSM 6: Assume uniform block of text
            text = pytesseract.image_to_string(image, config=custom_config)
            return text
        except Exception as e:
            print(f"Local OCR failed: {str(e)}")
            return None

    def _preprocess_image(self, image: 'Image.Image') -> 'Image.Image':
        """
        Preprocess image to improve OCR accuracy.

        Args:
            image: PIL Image object

        Returns:
            Preprocessed PIL Image object
        """
        try:
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # Resize if too small (OCR works better with larger images)
            width, height = image.size
            if width < 1000:
                scale_factor = 1000 / width
                new_size = (int(width * scale_factor), int(height * scale_factor))
                image = image.resize(new_size, Image.Resampling.LANCZOS)

            # Enhance contrast and sharpness
            from PIL import ImageEnhance

            # Increase contrast
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.5)

            # Increase sharpness
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(2.0)

            return image
        except Exception as e:
            print(f"Image preprocessing failed: {str(e)}")
            return image  # Return original if preprocessing fails

    def parse_gemini_structured_output(self, text: str) -> List[Dict]:
        """
        Parse Gemini's structured visit record output.

        Expected format:
        Date: MM/DD/YYYY | Client: [name] | Time: HH:MM-HH:MM

        Args:
            text: Gemini extracted text

        Returns:
            List of parsed visit records
        """
        records = []
        lines = text.split('\n')

        # Pattern for Gemini's structured format
        gemini_pattern = r'Date:\s*([0-9/\-]+)\s*\|\s*Client:\s*(.+?)\s*\|\s*Time:\s*(\d{1,2}:\d{2})-(\d{1,2}:\d{2})'

        for line in lines:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('Example'):
                continue

            match = re.search(gemini_pattern, line, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                client_name = match.group(2).strip()
                start_time_str = match.group(3)
                end_time_str = match.group(4)

                # Normalize date
                normalized_date = self._normalize_date(date_str)
                if not normalized_date:
                    continue

                # Normalize times
                start_time = self._normalize_time(start_time_str)
                end_time = self._normalize_time(end_time_str)

                if start_time and end_time:
                    records.append({
                        'date': normalized_date,
                        'client_name': client_name,
                        'start_time': start_time,
                        'end_time': end_time,
                        'source': 'gemini'
                    })

        return records

    def parse_visit_records(self, text: str) -> List[Dict]:
        """
        Parse visit records from OCR text.

        Expected format (flexible):
        - Date: YYYY-MM-DD or MM/DD/YYYY
        - Time: HH:MM - HH:MM or HH:MM to HH:MM
        - Client name on same or nearby line

        Args:
            text: OCR extracted text

        Returns:
            List of parsed visit records
        """
        # Try Gemini structured format first
        gemini_records = self.parse_gemini_structured_output(text)
        if gemini_records:
            return gemini_records

        # Fall back to traditional parsing
        records = []
        lines = text.split('\n')

        # Patterns for matching (enhanced for handwritten text)
        date_pattern = r'(\d{4}-\d{2}-\d{2}|\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})'
        # Enhanced time pattern to handle handwritten variations:
        # - Handles missing colons (930 instead of 9:30)
        # - Handles periods instead of colons (9.30)
        # - Handles various separators (-, to, ~)
        time_pattern = r'(\d{1,2}[:.\s]?\d{2})\s*[-to~]+\s*(\d{1,2}[:.\s]?\d{2})'

        current_record = {}

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                # Empty line might indicate end of record
                if current_record:
                    if self._is_valid_record(current_record):
                        records.append(current_record.copy())
                    current_record = {}
                continue

            # Look for date
            date_match = re.search(date_pattern, line)
            if date_match:
                date_str = date_match.group(1)
                normalized_date = self._normalize_date(date_str)
                if normalized_date:
                    current_record['date'] = normalized_date
                    current_record['raw_line'] = line

            # Look for time range
            time_match = re.search(time_pattern, line)
            if time_match:
                # Normalize times to handle handwritten variations
                start_time = self._normalize_time(time_match.group(1))
                end_time = self._normalize_time(time_match.group(2))
                if start_time and end_time:
                    current_record['start_time'] = start_time
                    current_record['end_time'] = end_time

            # If we don't have a client name yet, try to extract it
            if 'client_name' not in current_record and line:
                # Remove date and time from line to get potential client name
                clean_line = re.sub(date_pattern, '', line)
                clean_line = re.sub(time_pattern, '', clean_line)
                clean_line = clean_line.strip()

                # If there's text left, it might be the client name
                if clean_line and len(clean_line) > 2:
                    # Remove common prefixes/labels
                    clean_line = re.sub(r'^(client|name|for):\s*', '', clean_line, flags=re.IGNORECASE)
                    if clean_line:
                        current_record['client_name'] = clean_line

        # Don't forget the last record
        if current_record and self._is_valid_record(current_record):
            records.append(current_record)

        return records

    def _normalize_date(self, date_str: str) -> Optional[str]:
        """
        Normalize various date formats to YYYY-MM-DD.

        Args:
            date_str: Date string in various formats

        Returns:
            Normalized date string or None if invalid
        """
        # Try different date formats
        formats = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%m-%d-%Y',
            '%d/%m/%Y',
            '%d-%m-%Y',
            '%m/%d/%y',
            '%m-%d-%y',
        ]

        for fmt in formats:
            try:
                date_obj = datetime.strptime(date_str, fmt)
                return date_obj.strftime('%Y-%m-%d')
            except ValueError:
                continue

        return None

    def _normalize_time(self, time_str: str) -> Optional[str]:
        """
        Normalize handwritten time formats to HH:MM.

        Args:
            time_str: Time string in various formats

        Returns:
            Normalized time string (HH:MM) or None if invalid
        """
        # Clean up the string
        time_str = time_str.strip().replace(' ', '')

        # Handle period instead of colon (9.30 -> 9:30)
        time_str = time_str.replace('.', ':')

        # Handle missing colon for times like "930" or "1145"
        if ':' not in time_str and len(time_str) in [3, 4]:
            if len(time_str) == 3:  # e.g., "930"
                time_str = time_str[0] + ':' + time_str[1:3]
            else:  # e.g., "1145"
                time_str = time_str[0:2] + ':' + time_str[2:4]

        # Validate format
        try:
            parts = time_str.split(':')
            if len(parts) == 2:
                hour = int(parts[0])
                minute = int(parts[1])
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    return f"{hour:02d}:{minute:02d}"
        except:
            pass

        return None

    def _is_valid_record(self, record: Dict) -> bool:
        """
        Check if a parsed record has minimum required fields.

        Args:
            record: Parsed record dictionary

        Returns:
            True if valid, False otherwise
        """
        required_fields = ['date', 'start_time', 'end_time']
        return all(field in record for field in required_fields)

    def parse_client_info(self, text: str) -> Optional[Dict]:
        """
        Parse client information from OCR text.

        Args:
            text: OCR extracted text

        Returns:
            Dictionary with client information or None
        """
        client_info = {}
        lines = text.split('\n')

        # Patterns for extracting information
        name_pattern = r'(?:name|client):\s*(.+)'
        email_pattern = r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        phone_pattern = r'(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})'
        charge_pattern = r'(?:charge|fee|rate).*?\$?\s*(\d+(?:\.\d{2})?)'

        for line in lines:
            line = line.strip()

            # Look for name
            name_match = re.search(name_pattern, line, re.IGNORECASE)
            if name_match:
                client_info['name'] = name_match.group(1).strip()

            # Look for email
            email_match = re.search(email_pattern, line)
            if email_match:
                client_info['email'] = email_match.group(1)

            # Look for phone
            phone_match = re.search(phone_pattern, line)
            if phone_match:
                client_info['phone'] = phone_match.group(1)

            # Look for monthly charge
            charge_match = re.search(charge_pattern, line, re.IGNORECASE)
            if charge_match:
                try:
                    client_info['monthly_charge'] = float(charge_match.group(1))
                except ValueError:
                    pass

        return client_info if client_info else None

    def validate_and_calculate_duration(self, record: Dict) -> Dict:
        """
        Validate time fields and calculate duration for a record.

        Args:
            record: Visit record dictionary

        Returns:
            Updated record with duration_minutes field
        """
        try:
            start = datetime.strptime(record['start_time'], '%H:%M')
            end = datetime.strptime(record['end_time'], '%H:%M')

            # Calculate duration
            duration = (end - start).total_seconds() / 60

            if duration < 0:
                # End time is before start time (might span midnight)
                duration += 24 * 60  # Add 24 hours

            record['duration_minutes'] = duration
            record['is_valid'] = duration > 0

        except Exception as e:
            record['is_valid'] = False
            record['validation_error'] = str(e)

        return record

    def scan_and_parse_visits(self, image_path: str, debug: bool = False) -> Dict:
        """
        Scan an image and parse visit records with validation.

        Args:
            image_path: Path to the image file
            debug: If True, print debugging information

        Returns:
            Dictionary with scanned text, parsed records, and status
        """
        result = {
            'success': False,
            'text': None,
            'records': [],
            'error': None,
            'debug_info': {}
        }

        # Scan the image
        text = self.scan_image(image_path)

        if debug:
            print(f"OCR extracted {len(text) if text else 0} characters")
            if text:
                print(f"First 500 chars: {text[:500]}")

        if not text or len(text) < 10:
            result['error'] = 'Failed to extract text from image or text too short'
            result['debug_info']['text_length'] = len(text) if text else 0
            return result

        result['text'] = text
        result['debug_info']['text_length'] = len(text)

        # Parse visit records
        records = self.parse_visit_records(text)

        if debug:
            print(f"Parsed {len(records)} records")
            for i, rec in enumerate(records[:3]):  # Show first 3
                print(f"Record {i+1}: {rec}")

        result['debug_info']['raw_records_count'] = len(records)

        if not records:
            result['error'] = 'No valid visit records found in the image. The image may be handwritten or in table format that needs manual review.'
            # Still return the text so user can see what was extracted
            result['success'] = False
            return result

        # Validate and calculate durations
        validated_records = []
        for record in records:
            record = self.validate_and_calculate_duration(record)
            validated_records.append(record)

        result['records'] = validated_records
        result['success'] = True
        result['debug_info']['validated_records_count'] = len(validated_records)

        return result

    def match_client_name(self, scanned_name: str, existing_clients: List[Dict], threshold: int = 80) -> Optional[Dict]:
        """
        Match a scanned client name to existing clients using fuzzy matching.

        Args:
            scanned_name: Client name from OCR
            existing_clients: List of existing client dictionaries
            threshold: Minimum similarity score (0-100) to consider a match

        Returns:
            Best matching client or None
        """
        if not scanned_name:
            return None

        scanned_name_lower = scanned_name.lower().strip()
        best_match = None
        best_score = 0

        for client in existing_clients:
            client_name = client.get('name', '').lower().strip()

            # Calculate similarity score (simple approach)
            score = self._calculate_similarity(scanned_name_lower, client_name)

            if score > best_score and score >= threshold:
                best_score = score
                best_match = client

        return best_match

    def _calculate_similarity(self, str1: str, str2: str) -> int:
        """
        Calculate similarity between two strings using simple matching.

        Args:
            str1: First string
            str2: Second string

        Returns:
            Similarity score (0-100)
        """
        # Exact match
        if str1 == str2:
            return 100

        # Check if one contains the other
        if str1 in str2 or str2 in str1:
            return 90

        # Simple word overlap
        words1 = set(str1.split())
        words2 = set(str2.split())

        if not words1 or not words2:
            return 0

        common_words = words1 & words2
        total_words = words1 | words2

        if not total_words:
            return 0

        return int((len(common_words) / len(total_words)) * 100)
