"""OCR scanning functionality for importing paper records."""
try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

import re
from datetime import datetime
from typing import List, Dict, Optional
import os


class OCRScanner:
    """Handles scanning and parsing paper records using OCR."""

    def __init__(self):
        """Initialize the OCR scanner."""
        self.ocr_available = OCR_AVAILABLE

    def is_available(self) -> bool:
        """Check if OCR functionality is available."""
        return self.ocr_available

    def scan_image(self, image_path: str) -> Optional[str]:
        """
        Scan an image and extract text using OCR.

        Args:
            image_path: Path to the image file

        Returns:
            Extracted text or None if failed
        """
        if not self.ocr_available:
            return None

        if not os.path.exists(image_path):
            return None

        try:
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image)
            return text
        except Exception as e:
            print(f"OCR failed: {str(e)}")
            return None

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
