"""Parse handwritten visit schedules using Google Gemini Vision API."""
try:
    import google.generativeai as genai
    from PIL import Image
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    Image = None

import re
from datetime import datetime
from typing import List, Dict, Optional
import os


class VisitImageParser:
    """Parse handwritten visit schedules from images using Google Gemini Vision API."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the parser with Gemini API key.

        Args:
            api_key: Google Gemini API key
        """
        self.available = GEMINI_AVAILABLE and api_key is not None

        if self.available:
            try:
                genai.configure(api_key=api_key)

                # Try different model names in order of preference
                model_names = [
                    'gemini-1.5-flash-latest',
                    'gemini-1.5-pro-latest',
                    'gemini-pro-vision',
                    'gemini-1.5-flash',
                    'gemini-1.5-pro',
                    'models/gemini-1.5-flash-latest',
                    'models/gemini-pro-vision'
                ]

                self.model = None
                last_error = None

                for model_name in model_names:
                    try:
                        print(f"Trying model: {model_name}...")
                        self.model = genai.GenerativeModel(model_name)
                        print(f"✓ Successfully initialized Gemini with model: {model_name}")
                        break
                    except Exception as e:
                        print(f"✗ Failed: {e}")
                        last_error = e
                        continue

                if self.model is None:
                    print(f"Failed to initialize any Gemini model. Last error: {last_error}")
                    self.available = False

            except Exception as e:
                print(f"Failed to configure Gemini: {e}")
                self.available = False

    def is_available(self) -> bool:
        """Check if Gemini is available."""
        return self.available


    def parse_image(self, image_path: str) -> Dict:
        """
        Parse visit records from an image using Gemini Vision API.

        Args:
            image_path: Path to the image file

        Returns:
            Dictionary with parsed records and status
        """
        result = {
            'success': False,
            'records': [],
            'error': None
        }

        if not self.available:
            result['error'] = 'Gemini API not configured. Please add your API key in Settings.'
            return result

        if not os.path.exists(image_path):
            result['error'] = 'Image file not found.'
            return result

        try:
            if Image is None:
                result['error'] = 'PIL/Pillow not installed.'
                return result

            # Load image
            img = Image.open(image_path)

            # Create prompt for Gemini
            prompt = """
            Extract ALL visit records from this handwritten landscaping schedule.

            For each visit, provide:
            - Date (MM/DD/YYYY format)
            - Client name
            - Start time (HH:MM 24-hour format)
            - End time (HH:MM 24-hour format)

            Format each visit as:
            Date: MM/DD/YYYY | Client: [name] | Time: HH:MM-HH:MM

            Example:
            Date: 01/15/2024 | Client: Smith Residence | Time: 09:30-11:45

            Extract every visit you can identify. If handwriting is unclear, make your best guess.
            """

            print(f"Parsing image with Gemini Vision AI using model: {self.model._model_name}...")

            # Try to generate content with error handling for different API formats
            try:
                response = self.model.generate_content([prompt, img])
            except Exception as api_error:
                # If the error is about the model, try with just the image and prompt separately
                print(f"First attempt failed: {api_error}")
                print("Trying alternative API format...")
                try:
                    response = self.model.generate_content([img, prompt])
                except Exception as api_error2:
                    raise Exception(f"Both API formats failed. Error 1: {api_error}, Error 2: {api_error2}")

            if not response or not response.text:
                result['error'] = 'Gemini returned no response.'
                return result

            # Parse the structured output
            records = self._parse_response(response.text)

            if not records:
                result['error'] = 'No valid visit records found in image.'
                return result

            # Validate and calculate durations
            validated_records = []
            for record in records:
                record = self._validate_record(record)
                validated_records.append(record)

            result['records'] = validated_records
            result['success'] = True
            return result

        except Exception as e:
            result['error'] = f'Failed to parse image: {str(e)}'
            return result

    def _parse_response(self, text: str) -> List[Dict]:
        """Parse Gemini's structured response into visit records."""
        records = []
        pattern = r'Date:\s*([0-9/\-]+)\s*\|\s*Client:\s*(.+?)\s*\|\s*Time:\s*(\d{1,2}:\d{2})-(\d{1,2}:\d{2})'

        for line in text.split('\n'):
            line = line.strip()
            if not line or line.startswith(('#', 'Example')):
                continue

            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                date_str, client_name, start_str, end_str = match.groups()

                # Normalize date and times
                date = self._normalize_date(date_str)
                start_time = self._normalize_time(start_str)
                end_time = self._normalize_time(end_str)

                if date and start_time and end_time:
                    records.append({
                        'date': date,
                        'client_name': client_name.strip(),
                        'start_time': start_time,
                        'end_time': end_time
                    })

        return records

    def _normalize_date(self, date_str: str) -> Optional[str]:
        """Normalize date to YYYY-MM-DD format."""
        formats = ['%Y-%m-%d', '%m/%d/%Y', '%m-%d-%Y', '%d/%m/%Y', '%m/%d/%y']

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
            except ValueError:
                continue
        return None

    def _normalize_time(self, time_str: str) -> Optional[str]:
        """Normalize time to HH:MM format."""
        time_str = time_str.strip().replace(' ', '').replace('.', ':')

        # Handle missing colon (e.g., "930" -> "9:30")
        if ':' not in time_str and len(time_str) in [3, 4]:
            if len(time_str) == 3:
                time_str = time_str[0] + ':' + time_str[1:3]
            else:
                time_str = time_str[0:2] + ':' + time_str[2:4]

        try:
            parts = time_str.split(':')
            if len(parts) == 2:
                hour, minute = int(parts[0]), int(parts[1])
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    return f"{hour:02d}:{minute:02d}"
        except:
            pass
        return None

    def _validate_record(self, record: Dict) -> Dict:
        """Validate and calculate duration for a record."""
        try:
            start = datetime.strptime(record['start_time'], '%H:%M')
            end = datetime.strptime(record['end_time'], '%H:%M')
            duration = (end - start).total_seconds() / 60

            if duration < 0:
                duration += 24 * 60  # Handle overnight

            record['duration_minutes'] = duration
            record['is_valid'] = duration > 0
        except Exception as e:
            record['is_valid'] = False
            record['validation_error'] = str(e)

        return record

    def match_client_name(self, scanned_name: str, existing_clients: List[Dict], threshold: int = 80) -> Optional[Dict]:
        """
        Match a scanned client name to existing clients using fuzzy matching.

        Args:
            scanned_name: Client name from image
            existing_clients: List of existing client dictionaries
            threshold: Minimum similarity score (0-100)

        Returns:
            Best matching client or None
        """
        if not scanned_name:
            return None

        scanned_lower = scanned_name.lower().strip()
        best_match = None
        best_score = 0

        for client in existing_clients:
            client_name = client.get('name', '').lower().strip()
            score = self._similarity_score(scanned_lower, client_name)

            if score > best_score and score >= threshold:
                best_score = score
                best_match = client

        return best_match

    def _similarity_score(self, str1: str, str2: str) -> int:
        """Calculate similarity between two strings (0-100)."""
        if str1 == str2:
            return 100
        if str1 in str2 or str2 in str1:
            return 90

        # Word overlap
        words1 = set(str1.split())
        words2 = set(str2.split())
        if not words1 or not words2:
            return 0

        common = words1 & words2
        total = words1 | words2
        return int((len(common) / len(total)) * 100) if total else 0
