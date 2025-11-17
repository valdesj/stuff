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

import re
from datetime import datetime
from typing import List, Dict, Optional
import os
import requests
import base64
import io


class OCRScanner:
    """Handles scanning and parsing paper records using OCR."""

    def __init__(self, use_cloud: bool = True):
        """
        Initialize the OCR scanner.

        Args:
            use_cloud: If True, use cloud OCR (requires internet). If False, use local tesseract.
        """
        self.ocr_available = OCR_AVAILABLE
        self.use_cloud = use_cloud

    def is_available(self) -> bool:
        """Check if OCR functionality is available."""
        if self.use_cloud:
            return True  # Cloud OCR is always available if internet works
        return self.ocr_available

    def scan_image_cloud(self, image_path: str) -> Optional[str]:
        """
        Scan an image using cloud OCR API (OCR.space - free, no API key needed).

        Args:
            image_path: Path to the image file

        Returns:
            Extracted text or None if failed
        """
        try:
            # Read and encode image
            with open(image_path, 'rb') as f:
                image_data = f.read()

            # Prepare request to OCR.space API (free tier, no API key needed)
            url = 'https://api.ocr.space/parse/image'

            # Prepare the payload
            files = {
                'file': ('image.jpg', image_data, 'image/jpeg')
            }

            payload = {
                'apikey': 'helloworld',  # Free API key for basic use
                'language': 'eng',
                'isOverlayRequired': 'false',
                'OCREngine': '2',  # Use OCR Engine 2 for better accuracy
                'scale': 'true',
                'isTable': 'false'
            }

            # Make request with timeout
            response = requests.post(url, files=files, data=payload, timeout=30)

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
        Uses cloud OCR by default (no installation needed), falls back to local tesseract.

        Args:
            image_path: Path to the image file
            preprocess: Whether to preprocess image for better OCR accuracy (local tesseract only)

        Returns:
            Extracted text or None if failed
        """
        if not os.path.exists(image_path):
            return None

        # Try cloud OCR first (preferred - no installation needed)
        if self.use_cloud:
            text = self.scan_image_cloud(image_path)
            if text:
                return text

            # If cloud OCR fails, try local tesseract as fallback
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
        records = []
        lines = text.split('\n')

        # Patterns for matching
        date_pattern = r'(\d{4}-\d{2}-\d{2}|\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})'
        time_pattern = r'(\d{1,2}:\d{2})\s*[-to]+\s*(\d{1,2}:\d{2})'

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
                current_record['start_time'] = time_match.group(1)
                current_record['end_time'] = time_match.group(2)

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

    def scan_and_parse_visits(self, image_path: str) -> Dict:
        """
        Scan an image and parse visit records with validation.

        Args:
            image_path: Path to the image file

        Returns:
            Dictionary with scanned text, parsed records, and status
        """
        result = {
            'success': False,
            'text': None,
            'records': [],
            'error': None
        }

        # Scan the image
        text = self.scan_image(image_path)

        if not text:
            result['error'] = 'Failed to extract text from image'
            return result

        result['text'] = text

        # Parse visit records
        records = self.parse_visit_records(text)

        if not records:
            result['error'] = 'No valid visit records found in the image'
            return result

        # Validate and calculate durations
        validated_records = []
        for record in records:
            record = self.validate_and_calculate_duration(record)
            validated_records.append(record)

        result['records'] = validated_records
        result['success'] = True

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
