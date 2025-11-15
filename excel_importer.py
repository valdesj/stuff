"""Excel data import functionality for the Landscaping Client Tracker."""
import pandas as pd
from typing import Dict, List, Tuple
from datetime import datetime
import os


class ExcelImporter:
    """Handles importing client and visit data from Excel files."""

    def __init__(self, database):
        """Initialize with database instance."""
        self.db = database

    def import_from_file(self, file_path: str) -> Dict[str, any]:
        """
        Import data from an Excel file.

        Args:
            file_path: Path to the Excel file

        Returns:
            Dictionary with import results and any errors
        """
        if not os.path.exists(file_path):
            return {'success': False, 'error': 'File not found'}

        results = {
            'success': True,
            'clients_added': 0,
            'clients_updated': 0,
            'visits_added': 0,
            'materials_added': 0,
            'errors': [],
            'warnings': []
        }

        try:
            # Read all sheets from the Excel file
            excel_file = pd.ExcelFile(file_path)

            # Check if this is the standard format or weekly schedule format
            has_standard_sheets = ('Clients' in excel_file.sheet_names or
                                 'Materials' in excel_file.sheet_names or
                                 'Visits' in excel_file.sheet_names)

            if has_standard_sheets:
                # Import clients if sheet exists
                if 'Clients' in excel_file.sheet_names:
                    client_results = self._import_clients(excel_file)
                    results['clients_added'] = client_results['added']
                    results['clients_updated'] = client_results['updated']
                    results['errors'].extend(client_results['errors'])
                    results['warnings'].extend(client_results['warnings'])

                # Import materials if sheet exists
                if 'Materials' in excel_file.sheet_names:
                    material_results = self._import_materials(excel_file)
                    results['materials_added'] = material_results['added']
                    results['errors'].extend(material_results['errors'])

                # Import visits if sheet exists
                if 'Visits' in excel_file.sheet_names:
                    visit_results = self._import_visits(excel_file)
                    results['visits_added'] = visit_results['added']
                    results['errors'].extend(visit_results['errors'])
                    results['warnings'].extend(visit_results['warnings'])
            else:
                # Try to import as weekly schedule format
                schedule_results = self._import_weekly_schedule(file_path)
                results['clients_added'] = schedule_results['clients_added']
                results['visits_added'] = schedule_results['visits_added']
                results['errors'].extend(schedule_results['errors'])
                results['warnings'].extend(schedule_results['warnings'])

        except Exception as e:
            results['success'] = False
            results['error'] = f"Failed to read Excel file: {str(e)}"

        return results

    def _import_clients(self, excel_file: pd.ExcelFile) -> Dict:
        """Import clients from the Clients sheet."""
        results = {'added': 0, 'updated': 0, 'errors': [], 'warnings': []}

        try:
            df = pd.read_excel(excel_file, sheet_name='Clients')

            # Standardize column names (case-insensitive)
            df.columns = df.columns.str.strip().str.lower()

            # Check required columns
            required_cols = ['name', 'monthly_charge']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                results['errors'].append(f"Missing required columns in Clients sheet: {', '.join(missing_cols)}")
                return results

            # Process each row
            for idx, row in df.iterrows():
                try:
                    # Skip rows with missing name or monthly_charge
                    if pd.isna(row['name']) or pd.isna(row['monthly_charge']):
                        results['warnings'].append(f"Row {idx+2}: Skipped - missing name or monthly charge")
                        continue

                    name = str(row['name']).strip()

                    try:
                        monthly_charge = float(row['monthly_charge'])
                    except (ValueError, TypeError):
                        results['errors'].append(f"Row {idx+2}: Invalid monthly charge for '{name}'")
                        continue

                    # Check if client already exists
                    existing_clients = self.db.get_all_clients(active_only=False)
                    existing_client = next((c for c in existing_clients if c['name'].lower() == name.lower()), None)

                    if existing_client:
                        # Update existing client
                        self.db.update_client(
                            existing_client['id'],
                            email=str(row.get('email', '')).strip() if not pd.isna(row.get('email')) else '',
                            phone=str(row.get('phone', '')).strip() if not pd.isna(row.get('phone')) else '',
                            address=str(row.get('address', '')).strip() if not pd.isna(row.get('address')) else '',
                            monthly_charge=monthly_charge,
                            notes=str(row.get('notes', '')).strip() if not pd.isna(row.get('notes')) else ''
                        )
                        results['updated'] += 1
                    else:
                        # Add new client
                        self.db.add_client(
                            name=name,
                            email=str(row.get('email', '')).strip() if not pd.isna(row.get('email')) else '',
                            phone=str(row.get('phone', '')).strip() if not pd.isna(row.get('phone')) else '',
                            address=str(row.get('address', '')).strip() if not pd.isna(row.get('address')) else '',
                            monthly_charge=monthly_charge,
                            notes=str(row.get('notes', '')).strip() if not pd.isna(row.get('notes')) else ''
                        )
                        results['added'] += 1

                except Exception as e:
                    results['errors'].append(f"Row {idx+2}: {str(e)}")

        except Exception as e:
            results['errors'].append(f"Failed to import clients: {str(e)}")

        return results

    def _import_materials(self, excel_file: pd.ExcelFile) -> Dict:
        """Import materials from the Materials sheet."""
        results = {'added': 0, 'errors': []}

        try:
            df = pd.read_excel(excel_file, sheet_name='Materials')

            # Standardize column names
            df.columns = df.columns.str.strip().str.lower()

            # Check required columns
            required_cols = ['name', 'cost']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                results['errors'].append(f"Missing required columns in Materials sheet: {', '.join(missing_cols)}")
                return results

            # Process each row
            for idx, row in df.iterrows():
                try:
                    if pd.isna(row['name']) or pd.isna(row['cost']):
                        continue

                    name = str(row['name']).strip()

                    try:
                        cost = float(row['cost'])
                    except (ValueError, TypeError):
                        results['errors'].append(f"Row {idx+2}: Invalid cost for '{name}'")
                        continue

                    # Check if material already exists
                    existing_materials = self.db.get_all_materials()
                    if any(m['name'].lower() == name.lower() for m in existing_materials):
                        continue  # Skip duplicates

                    # Determine if global (default to True)
                    is_global = True
                    if 'is_global' in df.columns and not pd.isna(row.get('is_global')):
                        is_global = bool(row['is_global'])

                    self.db.add_material(
                        name=name,
                        default_cost=cost,
                        unit=str(row.get('unit', '')).strip() if not pd.isna(row.get('unit')) else '',
                        is_global=is_global,
                        description=str(row.get('description', '')).strip() if not pd.isna(row.get('description')) else ''
                    )
                    results['added'] += 1

                except Exception as e:
                    results['errors'].append(f"Row {idx+2}: {str(e)}")

        except Exception as e:
            results['errors'].append(f"Failed to import materials: {str(e)}")

        return results

    def _import_visits(self, excel_file: pd.ExcelFile) -> Dict:
        """Import visits from the Visits sheet."""
        results = {'added': 0, 'errors': [], 'warnings': []}

        try:
            df = pd.read_excel(excel_file, sheet_name='Visits')

            # Standardize column names
            df.columns = df.columns.str.strip().str.lower()

            # Check required columns
            required_cols = ['client_name', 'date', 'start_time', 'end_time']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                results['errors'].append(f"Missing required columns in Visits sheet: {', '.join(missing_cols)}")
                return results

            # Get all clients for matching
            all_clients = self.db.get_all_clients(active_only=False)
            client_map = {c['name'].lower(): c['id'] for c in all_clients}

            # Process each row
            for idx, row in df.iterrows():
                try:
                    if pd.isna(row['client_name']) or pd.isna(row['date']) or pd.isna(row['start_time']) or pd.isna(row['end_time']):
                        results['warnings'].append(f"Row {idx+2}: Skipped - missing required fields")
                        continue

                    client_name = str(row['client_name']).strip()

                    # Find client
                    client_id = client_map.get(client_name.lower())
                    if not client_id:
                        results['errors'].append(f"Row {idx+2}: Client '{client_name}' not found")
                        continue

                    # Parse date
                    if isinstance(row['date'], pd.Timestamp):
                        date_str = row['date'].strftime('%Y-%m-%d')
                    else:
                        try:
                            date_obj = pd.to_datetime(row['date'])
                            date_str = date_obj.strftime('%Y-%m-%d')
                        except:
                            results['errors'].append(f"Row {idx+2}: Invalid date format")
                            continue

                    # Parse times
                    try:
                        if isinstance(row['start_time'], pd.Timestamp):
                            start_time_str = row['start_time'].strftime('%H:%M')
                        else:
                            start_time_str = str(row['start_time']).strip()
                            # Validate time format
                            datetime.strptime(start_time_str, '%H:%M')

                        if isinstance(row['end_time'], pd.Timestamp):
                            end_time_str = row['end_time'].strftime('%H:%M')
                        else:
                            end_time_str = str(row['end_time']).strip()
                            # Validate time format
                            datetime.strptime(end_time_str, '%H:%M')

                    except Exception as e:
                        results['errors'].append(f"Row {idx+2}: Invalid time format - {str(e)}")
                        continue

                    # Calculate duration
                    start = datetime.strptime(start_time_str, '%H:%M')
                    end = datetime.strptime(end_time_str, '%H:%M')
                    duration_minutes = (end - start).total_seconds() / 60

                    if duration_minutes <= 0:
                        results['errors'].append(f"Row {idx+2}: End time must be after start time")
                        continue

                    # Add visit
                    self.db.add_visit(
                        client_id=client_id,
                        visit_date=date_str,
                        start_time=start_time_str,
                        end_time=end_time_str,
                        duration_minutes=duration_minutes,
                        notes=str(row.get('notes', '')).strip() if not pd.isna(row.get('notes')) else ''
                    )
                    results['added'] += 1

                except Exception as e:
                    results['errors'].append(f"Row {idx+2}: {str(e)}")

        except Exception as e:
            results['errors'].append(f"Failed to import visits: {str(e)}")

        return results

    def _import_weekly_schedule(self, file_path: str) -> Dict:
        """
        Import from weekly schedule format (client names in first column,
        repeated Fecha/Inicio/Fin/Total columns for each week).

        Args:
            file_path: Path to the Excel file

        Returns:
            Dictionary with import results
        """
        results = {
            'clients_added': 0,
            'visits_added': 0,
            'errors': [],
            'warnings': []
        }

        try:
            # Read the first sheet (usually the only sheet in this format)
            df = pd.read_excel(file_path, header=None)

            # Skip the first row (headers like "Semana 1", "Semana 2", etc.)
            # and use the second row for column structure
            header_row1 = df.iloc[0] if len(df) > 0 else []
            header_row2 = df.iloc[1] if len(df) > 1 else []

            # Start processing from row 2 (index 2, since 0 and 1 are headers)
            data_start = 2

            # Get all existing clients
            existing_clients = self.db.get_all_clients(active_only=False)
            client_map = {c['name'].lower(): c['id'] for c in existing_clients}

            # Process each row (each row is a client)
            for row_idx in range(data_start, len(df)):
                try:
                    row = df.iloc[row_idx]

                    # First column is the client name
                    if pd.isna(row.iloc[0]):
                        continue  # Skip empty rows

                    client_name = str(row.iloc[0]).strip()

                    # Check if client exists, if not create with $0 monthly charge
                    client_id = client_map.get(client_name.lower())
                    if not client_id:
                        client_id = self.db.add_client(
                            name=client_name,
                            monthly_charge=0.0,  # Default, user can update later
                            notes="Imported from Excel schedule"
                        )
                        client_map[client_name.lower()] = client_id
                        results['clients_added'] += 1

                    # Process each week's data (columns 1-4, 5-8, 9-12, 13-16, etc.)
                    # Each week has: Fecha (Date), Inicio (Start), Fin (End), Total
                    col_idx = 1
                    week_num = 1

                    while col_idx + 3 < len(row):
                        try:
                            fecha = row.iloc[col_idx]      # Date
                            inicio = row.iloc[col_idx + 1]  # Start time
                            fin = row.iloc[col_idx + 2]     # End time
                            # total = row.iloc[col_idx + 3]  # Total (we calculate this ourselves)

                            # Skip if date is empty
                            if pd.isna(fecha):
                                col_idx += 4
                                week_num += 1
                                continue

                            # Parse date
                            try:
                                if isinstance(fecha, pd.Timestamp):
                                    date_str = fecha.strftime('%Y-%m-%d')
                                else:
                                    # Try to parse date (could be "1/2/2025" format)
                                    date_obj = pd.to_datetime(fecha)
                                    date_str = date_obj.strftime('%Y-%m-%d')
                            except:
                                results['warnings'].append(
                                    f"Row {row_idx+1} ({client_name}), Week {week_num}: Invalid date '{fecha}'"
                                )
                                col_idx += 4
                                week_num += 1
                                continue

                            # Parse start and end times (could be "12:10 PM" format)
                            try:
                                start_time_str = self._parse_time(inicio)
                                end_time_str = self._parse_time(fin)
                            except Exception as e:
                                results['warnings'].append(
                                    f"Row {row_idx+1} ({client_name}), Week {week_num}: Invalid time - {str(e)}"
                                )
                                col_idx += 4
                                week_num += 1
                                continue

                            # Calculate duration
                            start = datetime.strptime(start_time_str, '%H:%M')
                            end = datetime.strptime(end_time_str, '%H:%M')
                            duration_minutes = (end - start).total_seconds() / 60

                            if duration_minutes <= 0:
                                results['warnings'].append(
                                    f"Row {row_idx+1} ({client_name}), Week {week_num}: End time before start time"
                                )
                                col_idx += 4
                                week_num += 1
                                continue

                            # Add visit
                            self.db.add_visit(
                                client_id=client_id,
                                visit_date=date_str,
                                start_time=start_time_str,
                                end_time=end_time_str,
                                duration_minutes=duration_minutes,
                                notes=f"Imported from Excel (Week {week_num})"
                            )
                            results['visits_added'] += 1

                        except Exception as e:
                            results['warnings'].append(
                                f"Row {row_idx+1} ({client_name}), Week {week_num}: {str(e)}"
                            )

                        col_idx += 4
                        week_num += 1

                except Exception as e:
                    results['errors'].append(f"Row {row_idx+1}: {str(e)}")

        except Exception as e:
            results['errors'].append(f"Failed to import weekly schedule: {str(e)}")

        return results

    def _parse_time(self, time_value) -> str:
        """
        Parse time from various formats and return HH:MM 24-hour format.
        Handles: "12:10 PM", "9:30 AM", pd.Timestamp, etc.

        Args:
            time_value: Time value from Excel

        Returns:
            Time string in HH:MM 24-hour format
        """
        if pd.isna(time_value):
            raise ValueError("Time is empty")

        # If it's already a pandas Timestamp
        if isinstance(time_value, pd.Timestamp):
            return time_value.strftime('%H:%M')

        # Convert to string and strip whitespace
        time_str = str(time_value).strip()

        # Try to parse as 12-hour format with AM/PM
        try:
            # Handle formats like "12:10 PM", "9:30 AM"
            dt = datetime.strptime(time_str, '%I:%M %p')
            return dt.strftime('%H:%M')
        except ValueError:
            pass

        # Try to parse as 24-hour format
        try:
            dt = datetime.strptime(time_str, '%H:%M')
            return dt.strftime('%H:%M')
        except ValueError:
            pass

        # Try with seconds
        try:
            dt = datetime.strptime(time_str, '%H:%M:%S')
            return dt.strftime('%H:%M')
        except ValueError:
            pass

        raise ValueError(f"Cannot parse time '{time_str}'")

    def generate_template(self, output_path: str) -> bool:
        """
        Generate an Excel template file with example data.

        Args:
            output_path: Path where the template should be saved

        Returns:
            True if successful, False otherwise
        """
        try:
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                # Clients sheet
                clients_data = {
                    'Name': ['ABC Landscaping', 'Smith Residence', 'Jones Commercial'],
                    'Email': ['contact@abc.com', 'john@smith.com', 'office@jones.com'],
                    'Phone': ['555-0101', '555-0102', '555-0103'],
                    'Address': ['123 Main St', '456 Oak Ave', '789 Business Blvd'],
                    'Monthly_Charge': [500.00, 350.00, 750.00],
                    'Notes': ['Weekly service', 'Bi-weekly mowing', 'Full maintenance contract']
                }
                df_clients = pd.DataFrame(clients_data)
                df_clients.to_excel(writer, sheet_name='Clients', index=False)

                # Materials sheet
                materials_data = {
                    'Name': ['Mulch', 'Fertilizer', 'Grass Seed', 'Mowing Service'],
                    'Cost': [5.50, 12.00, 8.00, 45.00],
                    'Unit': ['bag', 'bag', 'lb', 'service'],
                    'Is_Global': [True, True, True, True],
                    'Description': ['Brown mulch', 'All-purpose fertilizer', 'Fescue mix', 'Standard lawn mowing']
                }
                df_materials = pd.DataFrame(materials_data)
                df_materials.to_excel(writer, sheet_name='Materials', index=False)

                # Visits sheet
                visits_data = {
                    'Client_Name': ['ABC Landscaping', 'ABC Landscaping', 'Smith Residence'],
                    'Date': ['2024-01-15', '2024-01-22', '2024-01-20'],
                    'Start_Time': ['09:00', '09:00', '14:00'],
                    'End_Time': ['11:30', '11:00', '15:30'],
                    'Notes': ['Regular maintenance', 'Mulch application', 'Mowing and edging']
                }
                df_visits = pd.DataFrame(visits_data)
                df_visits.to_excel(writer, sheet_name='Visits', index=False)

            return True

        except Exception as e:
            print(f"Failed to generate template: {str(e)}")
            return False
