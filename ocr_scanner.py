"""OCR scanning functionality using Google Gemini AI."""
try:
    import google.generativeai as genai
    from PIL import Image
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    try:
        from PIL import Image
    except ImportError:
        Image = None

import re
from datetime import datetime
from typing import List, Dict, Optional
import os


class OCRScanner:
    """Handles scanning and parsing handwritten visit records using Google Gemini AI."""

    def __init__(self, gemini_api_key: Optional[str] = None):
        """
        Initialize the OCR scanner with Gemini AI.

        Args:
            gemini_api_key: Gemini API key for vision parsing (required)
        """
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
        return self.gemini_available

    def scan_image(self, image_path: str) -> Optional[str]:
        """
        Scan an image using Google Gemini Vision API.

        Args:
            image_path: Path to the image file

        Returns:
            Extracted text or None if failed
        """
        if not self.gemini_available:
            return None

        if not os.path.exists(image_path):
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

            print("Using Gemini Vision AI for OCR...")
            # Generate content with Gemini
            response = self.gemini_model.generate_content([prompt, img])

            if response and response.text:
                return response.text

            return None

        except Exception as e:
            print(f"Gemini OCR failed: {str(e)}")
            return None

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

        Args:
            text: OCR extracted text

        Returns:
            List of parsed visit records
        """
        return self.parse_gemini_structured_output(text)

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
            result['error'] = 'Failed to extract text from image. Make sure Gemini API key is configured in Settings.'
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
            result['error'] = 'No valid visit records found. Make sure the image contains visit data in the expected format.'
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
