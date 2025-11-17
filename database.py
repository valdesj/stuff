"""Database layer for the Landscaping Client Tracker application."""
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import os


class Database:
    """Manages all database operations for the application."""

    def __init__(self, db_path: str = "landscaping_tracker.db"):
        """Initialize database connection and create tables if needed."""
        self.db_path = db_path
        self.connection = None
        self.connect()
        self.create_tables()

    def connect(self):
        """Establish connection to SQLite database."""
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        # Enable foreign keys
        self.connection.execute("PRAGMA foreign_keys = ON")

    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()

    def create_tables(self):
        """Create all necessary tables if they don't exist."""
        cursor = self.connection.cursor()

        # Clients table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                address TEXT,
                monthly_charge REAL NOT NULL DEFAULT 0.0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT
            )
        """)

        # Global materials/services catalog
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                default_cost REAL NOT NULL DEFAULT 0.0,
                unit TEXT,
                is_global INTEGER NOT NULL DEFAULT 1,
                description TEXT,
                material_type TEXT NOT NULL DEFAULT 'material'
            )
        """)

        # Add material_type column to existing tables (migration)
        try:
            cursor.execute("ALTER TABLE materials ADD COLUMN material_type TEXT NOT NULL DEFAULT 'material'")
        except sqlite3.OperationalError:
            # Column already exists
            pass

        # Client-specific material pricing (overrides global pricing)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS client_materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                material_id INTEGER NOT NULL,
                custom_cost REAL,
                multiplier REAL NOT NULL DEFAULT 1.0,
                is_enabled INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
                FOREIGN KEY (material_id) REFERENCES materials(id) ON DELETE CASCADE,
                UNIQUE(client_id, material_id)
            )
        """)

        # Add multiplier column to existing tables (migration)
        try:
            cursor.execute("ALTER TABLE client_materials ADD COLUMN multiplier REAL NOT NULL DEFAULT 1.0")
        except sqlite3.OperationalError:
            # Column already exists
            pass
        # Visits table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                visit_date DATE NOT NULL,
                start_time TIME NOT NULL,
                end_time TIME NOT NULL,
                duration_minutes REAL NOT NULL,
                notes TEXT,
                needs_review INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
            )
        """)

        # Add needs_review column to existing tables (migration)
        try:
            cursor.execute("ALTER TABLE visits ADD COLUMN needs_review INTEGER NOT NULL DEFAULT 0")
        except sqlite3.OperationalError:
            # Column already exists
            pass
        # Materials used during visits
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS visit_materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                visit_id INTEGER NOT NULL,
                material_id INTEGER NOT NULL,
                quantity REAL NOT NULL DEFAULT 1.0,
                cost_at_time REAL NOT NULL,
                FOREIGN KEY (visit_id) REFERENCES visits(id) ON DELETE CASCADE,
                FOREIGN KEY (material_id) REFERENCES materials(id) ON DELETE CASCADE
            )
        """)

        # Settings table for global configuration
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # Initialize default settings if not exists
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('hourly_rate', '25.00')")

        self.connection.commit()

    # ==================== CLIENT OPERATIONS ====================

    def add_client(self, name: str, monthly_charge: float, email: str = "",
                   phone: str = "", address: str = "", notes: str = "") -> int:
        """Add a new client and return their ID."""
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT INTO clients (name, email, phone, address, monthly_charge, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, email, phone, address, monthly_charge, notes))
        self.connection.commit()
        return cursor.lastrowid

    def update_client(self, client_id: int, **kwargs):
        """Update client information."""
        allowed_fields = ['name', 'email', 'phone', 'address', 'monthly_charge', 'notes']
        updates = []
        values = []

        for field, value in kwargs.items():
            if field in allowed_fields:
                updates.append(f"{field} = ?")
                values.append(value)

        if updates:
            values.append(client_id)
            query = f"UPDATE clients SET {', '.join(updates)} WHERE id = ?"
            self.connection.execute(query, values)
            self.connection.commit()

    def get_client(self, client_id: int) -> Optional[Dict]:
        """Get a specific client by ID."""
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_clients(self, active_only: bool = True) -> List[Dict]:
        """Get all clients, optionally filtering by active status."""
        cursor = self.connection.cursor()
        if active_only:
            cursor.execute("SELECT * FROM clients WHERE is_active = 1 ORDER BY name")
        else:
            cursor.execute("SELECT * FROM clients ORDER BY name")
        return [dict(row) for row in cursor.fetchall()]

    def deactivate_client(self, client_id: int):
        """Soft delete - mark client as inactive."""
        self.connection.execute("UPDATE clients SET is_active = 0 WHERE id = ?", (client_id,))
        self.connection.commit()

    def activate_client(self, client_id: int):
        """Reactivate an inactive client."""
        self.connection.execute("UPDATE clients SET is_active = 1 WHERE id = ?", (client_id,))
        self.connection.commit()

    def delete_client(self, client_id: int):
        """Hard delete - permanently remove client and all related data."""
        self.connection.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        self.connection.commit()

    # ==================== MATERIAL OPERATIONS ====================

    def add_material(self, name: str, default_cost: float, unit: str = "",
                     is_global: bool = True, description: str = "", material_type: str = "material") -> int:
        """Add a new material/service to the catalog."""
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT INTO materials (name, default_cost, unit, is_global, description, material_type)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, default_cost, unit, 1 if is_global else 0, description, material_type))
        self.connection.commit()
        return cursor.lastrowid

    def get_all_materials(self) -> List[Dict]:
        """Get all materials/services."""
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM materials ORDER BY name")
        return [dict(row) for row in cursor.fetchall()]

    def update_material(self, material_id: int, **kwargs):
        """Update material information."""
        allowed_fields = ['name', 'default_cost', 'unit', 'is_global', 'description', 'material_type']
        updates = []
        values = []

        for field, value in kwargs.items():
            if field in allowed_fields:
                updates.append(f"{field} = ?")
                values.append(value)

        if updates:
            values.append(material_id)
            query = f"UPDATE materials SET {', '.join(updates)} WHERE id = ?"
            self.connection.execute(query, values)
            self.connection.commit()

    def delete_material(self, material_id: int):
        """Delete a material/service."""
        self.connection.execute("DELETE FROM materials WHERE id = ?", (material_id,))
        self.connection.commit()

    # ==================== CLIENT MATERIAL OPERATIONS ====================

    def add_client_material(self, client_id: int, material_id: int, custom_cost: Optional[float] = None, multiplier: float = 1.0):
        """Associate a material with a client, optionally with custom pricing and multiplier."""
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO client_materials (client_id, material_id, custom_cost, multiplier)
            VALUES (?, ?, ?, ?)
        """, (client_id, material_id, custom_cost, multiplier))
        self.connection.commit()

    def get_client_materials(self, client_id: int) -> List[Dict]:
        """Get all materials configured for a specific client."""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT
                cm.id, cm.client_id, cm.material_id, cm.custom_cost, cm.multiplier, cm.is_enabled,
                m.name, m.default_cost, m.unit, m.is_global, m.description,
                COALESCE(cm.custom_cost, m.default_cost) as effective_cost,
                COALESCE(cm.custom_cost, m.default_cost) * cm.multiplier as total_cost
            FROM client_materials cm
            JOIN materials m ON cm.material_id = m.id
            WHERE cm.client_id = ? AND cm.is_enabled = 1
            ORDER BY m.name
        """, (client_id,))
        return [dict(row) for row in cursor.fetchall()]

    def remove_client_material(self, client_id: int, material_id: int):
        """Remove a material from a client's configuration."""
        self.connection.execute("""
            DELETE FROM client_materials
            WHERE client_id = ? AND material_id = ?
        """, (client_id, material_id))
        self.connection.commit()

    # ==================== VISIT OPERATIONS ====================

    def add_visit(self, client_id: int, visit_date: str, start_time: str,
                  end_time: str, duration_minutes: float, notes: str = "", needs_review: int = 0) -> int:
        """Add a new visit record."""
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT INTO visits (client_id, visit_date, start_time, end_time, duration_minutes, notes, needs_review)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (client_id, visit_date, start_time, end_time, duration_minutes, notes, needs_review))
        self.connection.commit()
        return cursor.lastrowid

    def get_client_visits(self, client_id: int) -> List[Dict]:
        """Get all visits for a specific client."""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT * FROM visits
            WHERE client_id = ?
            ORDER BY visit_date DESC, start_time DESC
        """, (client_id,))
        return [dict(row) for row in cursor.fetchall()]

    def update_visit(self, visit_id: int, **kwargs):
        """Update visit information."""
        allowed_fields = ['visit_date', 'start_time', 'end_time', 'duration_minutes', 'notes', 'needs_review']
        updates = []
        values = []

        for field, value in kwargs.items():
            if field in allowed_fields:
                updates.append(f"{field} = ?")
                values.append(value)

        if updates:
            values.append(visit_id)
            query = f"UPDATE visits SET {', '.join(updates)} WHERE id = ?"
            self.connection.execute(query, values)
            self.connection.commit()

    def get_visits_needing_review(self) -> List[Dict]:
        """Get all visits that are flagged as needing review."""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT v.*, c.name as client_name
            FROM visits v
            JOIN clients c ON v.client_id = c.id
            WHERE v.needs_review = 1
            ORDER BY v.visit_date DESC, v.start_time DESC
        """)
        return [dict(row) for row in cursor.fetchall()]

    def get_visits_with_anomalous_durations(self, threshold_percent: float = 300.0) -> List[Dict]:
        """
        Get visits where duration is significantly different from the client's average.

        Args:
            threshold_percent: Percentage threshold (e.g., 300 means 3x the average)

        Returns:
            List of visits with anomalous durations, including comparison data
        """
        cursor = self.connection.cursor()

        # Get all clients with multiple visits (need at least 2 for comparison)
        cursor.execute("""
            SELECT client_id, COUNT(*) as visit_count
            FROM visits
            GROUP BY client_id
            HAVING visit_count >= 2
        """)
        clients_with_visits = [row['client_id'] for row in cursor.fetchall()]

        anomalous_visits = []

        for client_id in clients_with_visits:
            # Get all visits for this client
            cursor.execute("""
                SELECT v.*, c.name as client_name
                FROM visits v
                JOIN clients c ON v.client_id = c.id
                WHERE v.client_id = ?
                ORDER BY v.visit_date DESC
            """, (client_id,))
            visits = [dict(row) for row in cursor.fetchall()]

            if len(visits) < 2:
                continue

            # Calculate average duration for this client
            durations = [v['duration_minutes'] for v in visits]
            avg_duration = sum(durations) / len(durations)

            # Find visits that are outliers
            for visit in visits:
                if avg_duration == 0:
                    continue

                # Calculate percentage difference
                percent_of_avg = (visit['duration_minutes'] / avg_duration) * 100

                # Flag if significantly above threshold
                if percent_of_avg >= threshold_percent:
                    visit['avg_duration'] = avg_duration
                    visit['percent_of_avg'] = percent_of_avg
                    visit['total_visits'] = len(visits)
                    anomalous_visits.append(visit)

        # Sort by most extreme first
        anomalous_visits.sort(key=lambda x: x['percent_of_avg'], reverse=True)

        return anomalous_visits

    def get_visit_by_id(self, visit_id: int) -> Optional[Dict]:
        """Get a specific visit by ID."""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT v.*, c.name as client_name
            FROM visits v
            JOIN clients c ON v.client_id = c.id
            WHERE v.id = ?
        """, (visit_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def mark_visit_reviewed(self, visit_id: int):
        """Mark a visit as reviewed (clear the needs_review flag)."""
        self.connection.execute("UPDATE visits SET needs_review = 0 WHERE id = ?", (visit_id,))
        self.connection.commit()

    def delete_visit(self, visit_id: int):
        """Delete a visit record."""
        self.connection.execute("DELETE FROM visits WHERE id = ?", (visit_id,))
        self.connection.commit()

    # ==================== VISIT MATERIAL OPERATIONS ====================

    def add_visit_material(self, visit_id: int, material_id: int, quantity: float, cost_at_time: float):
        """Record material usage for a visit."""
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT INTO visit_materials (visit_id, material_id, quantity, cost_at_time)
            VALUES (?, ?, ?, ?)
        """, (visit_id, material_id, quantity, cost_at_time))
        self.connection.commit()

    def get_visit_materials(self, visit_id: int) -> List[Dict]:
        """Get all materials used during a specific visit."""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT
                vm.id, vm.visit_id, vm.material_id, vm.quantity, vm.cost_at_time,
                m.name, m.unit
            FROM visit_materials vm
            JOIN materials m ON vm.material_id = m.id
            WHERE vm.visit_id = ?
        """, (visit_id,))
        return [dict(row) for row in cursor.fetchall()]

    def delete_visit_material(self, visit_material_id: int):
        """Remove a material from a visit record."""
        self.connection.execute("DELETE FROM visit_materials WHERE id = ?", (visit_material_id,))
        self.connection.commit()

    # ==================== SETTINGS OPERATIONS ====================

    def get_setting(self, key: str, default: str = "") -> str:
        """Get a setting value by key."""
        cursor = self.connection.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row['value'] if row else default

    def set_setting(self, key: str, value: str):
        """Set a setting value."""
        self.connection.execute("""
            INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
        """, (key, value))
        self.connection.commit()

    def get_hourly_rate(self) -> float:
        """Get the hourly labor rate."""
        return float(self.get_setting('hourly_rate', '25.00'))

    def set_hourly_rate(self, rate: float):
        """Set the hourly labor rate."""
        self.set_setting('hourly_rate', str(rate))

    # ==================== ANALYTICS & CALCULATIONS ====================

    def get_client_statistics(self, client_id: int) -> Dict:
        """Calculate comprehensive statistics for a client."""
        from datetime import datetime
        cursor = self.connection.cursor()

        # Get client info
        client = self.get_client(client_id)
        if not client:
            return {}

        # Get hourly rate
        hourly_rate = self.get_hourly_rate()

        # Get current year
        current_year = datetime.now().year

        # Get visit count (all time)
        cursor.execute("SELECT COUNT(*) as visit_count FROM visits WHERE client_id = ?", (client_id,))
        visit_count = cursor.fetchone()['visit_count']

        # Get visit count (this year)
        cursor.execute("""
            SELECT COUNT(*) as visit_count
            FROM visits
            WHERE client_id = ? AND strftime('%Y', visit_date) = ?
        """, (client_id, str(current_year)))
        visits_this_year = cursor.fetchone()['visit_count']

        # Get configured materials yearly cost for this client (materials only)
        cursor.execute("""
            SELECT COALESCE(SUM(COALESCE(cm.custom_cost, m.default_cost) * cm.multiplier), 0) as configured_cost
            FROM client_materials cm
            JOIN materials m ON cm.material_id = m.id
            WHERE cm.client_id = ? AND cm.is_enabled = 1 AND m.material_type = 'material'
        """, (client_id,))
        configured_materials_cost_yearly = cursor.fetchone()['configured_cost']

        # Get configured services yearly cost for this client (services only)
        cursor.execute("""
            SELECT COALESCE(SUM(COALESCE(cm.custom_cost, m.default_cost) * cm.multiplier), 0) as configured_cost
            FROM client_materials cm
            JOIN materials m ON cm.material_id = m.id
            WHERE cm.client_id = ? AND cm.is_enabled = 1 AND m.material_type = 'service'
        """, (client_id,))
        configured_services_cost_yearly = cursor.fetchone()['configured_cost']

        # Get total material costs from actual visits (materials only)
        cursor.execute("""
            SELECT COALESCE(SUM(vm.quantity * vm.cost_at_time), 0) as visit_material_cost
            FROM visits v
            LEFT JOIN visit_materials vm ON v.id = vm.visit_id
            LEFT JOIN materials m ON vm.material_id = m.id
            WHERE v.client_id = ? AND m.material_type = 'material'
        """, (client_id,))
        visit_material_cost = cursor.fetchone()['visit_material_cost']

        # Get total service costs from actual visits (services only)
        cursor.execute("""
            SELECT COALESCE(SUM(vm.quantity * vm.cost_at_time), 0) as visit_service_cost
            FROM visits v
            LEFT JOIN visit_materials vm ON v.id = vm.visit_id
            LEFT JOIN materials m ON vm.material_id = m.id
            WHERE v.client_id = ? AND m.material_type = 'service'
        """, (client_id,))
        visit_service_cost = cursor.fetchone()['visit_service_cost']

        # Calculate total material costs (configured + visits)
        total_material_cost = configured_materials_cost_yearly + visit_material_cost

        # Calculate total service costs (configured + visits)
        total_service_cost = configured_services_cost_yearly + visit_service_cost

        # Get total materials + services costs
        total_materials_services_cost = total_material_cost + total_service_cost

        # Get visit time statistics
        cursor.execute("""
            SELECT
                COALESCE(AVG(duration_minutes), 0) as avg_duration,
                COALESCE(MIN(duration_minutes), 0) as min_duration,
                COALESCE(MAX(duration_minutes), 0) as max_duration,
                COALESCE(SUM(duration_minutes), 0) as total_duration
            FROM visits
            WHERE client_id = ?
        """, (client_id,))
        time_stats = cursor.fetchone()
        avg_time_per_visit = time_stats['avg_duration']
        min_time_per_visit = time_stats['min_duration']
        max_time_per_visit = time_stats['max_duration']
        total_time = time_stats['total_duration']

        # Calculate labor cost
        # Total time in hours * 2 crew members * hourly rate
        total_labor_cost = (total_time / 60) * 2 * hourly_rate

        # Historical average cost per visit = (labor cost + materials/services from visits) / visit count
        total_cost = total_labor_cost + total_materials_services_cost
        avg_cost_per_visit = total_cost / visit_count if visit_count > 0 else 0

        # Calculate projected yearly costs
        # Yearly labor cost = avg labor cost per visit × 52 visits
        avg_labor_cost_per_visit = (avg_time_per_visit / 60) * 2 * hourly_rate
        projected_yearly_labor_cost = avg_labor_cost_per_visit * 52

        # Total projected yearly cost = yearly labor + configured materials/services
        est_yearly_cost = projected_yearly_labor_cost + configured_materials_cost_yearly + configured_services_cost_yearly

        # Proposed monthly rate = est yearly cost / 12
        proposed_monthly_rate = est_yearly_cost / 12

        # Compare to actual monthly charge
        actual_monthly_charge = client['monthly_charge']
        profit_loss = actual_monthly_charge - proposed_monthly_rate
        is_profitable = profit_loss >= 0

        return {
            'client_id': client_id,
            'client_name': client['name'],
            'visit_count': visit_count,
            'visits_this_year': visits_this_year,
            'total_material_cost': round(total_material_cost, 2),
            'total_service_cost': round(total_service_cost, 2),
            'total_materials_services_cost': round(total_materials_services_cost, 2),
            'configured_materials_cost_yearly': round(configured_materials_cost_yearly, 2),
            'configured_services_cost_yearly': round(configured_services_cost_yearly, 2),
            'projected_yearly_labor_cost': round(projected_yearly_labor_cost, 2),
            'avg_time_per_visit': round(avg_time_per_visit, 1),
            'min_time_per_visit': round(min_time_per_visit, 1),
            'max_time_per_visit': round(max_time_per_visit, 1),
            'total_labor_cost': round(total_labor_cost, 2),
            'avg_cost_per_visit': round(avg_cost_per_visit, 2),
            'est_yearly_cost': round(est_yearly_cost, 2),
            'proposed_monthly_rate': round(proposed_monthly_rate, 2),
            'actual_monthly_charge': round(actual_monthly_charge, 2),
            'monthly_profit_loss': round(profit_loss, 2),
            'is_profitable': is_profitable,
            'hourly_rate': round(hourly_rate, 2)
        }

    def get_all_client_statistics(self, active_only: bool = True) -> List[Dict]:
        """Get statistics for all clients."""
        clients = self.get_all_clients(active_only)
        return [self.get_client_statistics(client['id']) for client in clients]
