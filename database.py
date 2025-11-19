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
                description TEXT
            )
        """)

        # Client-specific material pricing (overrides global pricing)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS client_materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                material_id INTEGER NOT NULL,
                custom_cost REAL,
                is_enabled INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
                FOREIGN KEY (material_id) REFERENCES materials(id) ON DELETE CASCADE,
                UNIQUE(client_id, material_id)
            )
        """)

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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
            )
        """)

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

        # Settings table for application configuration
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

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
                     is_global: bool = True, description: str = "") -> int:
        """Add a new material/service to the catalog."""
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT INTO materials (name, default_cost, unit, is_global, description)
            VALUES (?, ?, ?, ?, ?)
        """, (name, default_cost, unit, 1 if is_global else 0, description))
        self.connection.commit()
        return cursor.lastrowid

    def get_all_materials(self) -> List[Dict]:
        """Get all materials/services."""
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM materials ORDER BY name")
        return [dict(row) for row in cursor.fetchall()]

    def update_material(self, material_id: int, **kwargs):
        """Update material information."""
        allowed_fields = ['name', 'default_cost', 'unit', 'is_global', 'description']
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

    def add_client_material(self, client_id: int, material_id: int, custom_cost: Optional[float] = None):
        """Associate a material with a client, optionally with custom pricing."""
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO client_materials (client_id, material_id, custom_cost)
            VALUES (?, ?, ?)
        """, (client_id, material_id, custom_cost))
        self.connection.commit()

    def get_client_materials(self, client_id: int) -> List[Dict]:
        """Get all materials configured for a specific client."""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT
                cm.id, cm.client_id, cm.material_id, cm.custom_cost, cm.is_enabled,
                m.name, m.default_cost, m.unit, m.is_global, m.description,
                COALESCE(cm.custom_cost, m.default_cost) as effective_cost
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
                  end_time: str, duration_minutes: float, notes: str = "") -> int:
        """Add a new visit record."""
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT INTO visits (client_id, visit_date, start_time, end_time, duration_minutes, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (client_id, visit_date, start_time, end_time, duration_minutes, notes))
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
        allowed_fields = ['visit_date', 'start_time', 'end_time', 'duration_minutes', 'notes']
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

    # ==================== ANALYTICS & CALCULATIONS ====================

    def get_client_statistics(self, client_id: int) -> Dict:
        """Calculate comprehensive statistics for a client."""
        cursor = self.connection.cursor()

        # Get client info
        client = self.get_client(client_id)
        if not client:
            return {}

        # Get visit count
        cursor.execute("SELECT COUNT(*) as visit_count FROM visits WHERE client_id = ?", (client_id,))
        visit_count = cursor.fetchone()['visit_count']

        # Get total material costs
        cursor.execute("""
            SELECT COALESCE(SUM(vm.quantity * vm.cost_at_time), 0) as total_material_cost
            FROM visits v
            LEFT JOIN visit_materials vm ON v.id = vm.visit_id
            WHERE v.client_id = ?
        """, (client_id,))
        total_material_cost = cursor.fetchone()['total_material_cost']

        # Calculate averages and projections
        avg_cost_per_visit = total_material_cost / visit_count if visit_count > 0 else 0

        # Estimate visits per year (you might want to make this configurable)
        # For now, let's calculate based on actual visit frequency if we have data
        cursor.execute("""
            SELECT
                MIN(visit_date) as first_visit,
                MAX(visit_date) as last_visit
            FROM visits
            WHERE client_id = ?
        """, (client_id,))
        date_range = cursor.fetchone()

        # Calculate visits per year based on actual data
        visits_per_year = visit_count
        if date_range['first_visit'] and date_range['last_visit']:
            from datetime import datetime
            first = datetime.fromisoformat(date_range['first_visit'])
            last = datetime.fromisoformat(date_range['last_visit'])
            days_diff = (last - first).days
            if days_diff > 0:
                visits_per_year = (visit_count / days_diff) * 365

        calculated_yearly_cost = avg_cost_per_visit * visits_per_year
        calculated_monthly_cost = calculated_yearly_cost / 12

        # Compare to actual monthly charge
        actual_monthly_charge = client['monthly_charge']
        profit_loss = actual_monthly_charge - calculated_monthly_cost
        is_profitable = profit_loss >= 0

        return {
            'client_id': client_id,
            'client_name': client['name'],
            'visit_count': visit_count,
            'total_material_cost': round(total_material_cost, 2),
            'avg_cost_per_visit': round(avg_cost_per_visit, 2),
            'visits_per_year': round(visits_per_year, 1),
            'calculated_yearly_cost': round(calculated_yearly_cost, 2),
            'calculated_monthly_cost': round(calculated_monthly_cost, 2),
            'actual_monthly_charge': round(actual_monthly_charge, 2),
            'monthly_profit_loss': round(profit_loss, 2),
            'is_profitable': is_profitable
        }

    def get_all_client_statistics(self, active_only: bool = True) -> List[Dict]:
        """Get statistics for all clients."""
        clients = self.get_all_clients(active_only)
        return [self.get_client_statistics(client['id']) for client in clients]

    # ==================== SETTINGS OPERATIONS ====================

    def get_setting(self, key: str, default: str = None) -> Optional[str]:
        """
        Get a setting value by key.

        Args:
            key: Setting key
            default: Default value if setting doesn't exist

        Returns:
            Setting value or default
        """
        cursor = self.connection.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row['value'] if row else default

    def set_setting(self, key: str, value: str):
        """
        Set a setting value.

        Args:
            key: Setting key
            value: Setting value
        """
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO settings (key, value)
            VALUES (?, ?)
        """, (key, value))
        self.connection.commit()
