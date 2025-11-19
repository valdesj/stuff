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

        # Add no_additional_services column to clients table (migration)
        try:
            cursor.execute("ALTER TABLE clients ADD COLUMN no_additional_services INTEGER NOT NULL DEFAULT 0")
        except sqlite3.OperationalError:
            # Column already exists
            pass

        # Add bill_to column to clients table for client groups (migration)
        try:
            cursor.execute("ALTER TABLE clients ADD COLUMN bill_to TEXT")
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

        # Client aliases table for name matching
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS client_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                alias TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
                UNIQUE(client_id, alias)
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

        # Client groups table for group-level contact information
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS client_groups (
                bill_to TEXT PRIMARY KEY,
                email TEXT,
                phone TEXT,
                address TEXT,
                notes TEXT
            )
        """)

        # Contract item templates (reusable descriptions)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contract_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT,
                default_pricing_type TEXT DEFAULT 'flat',
                default_unit TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Contracts and bids
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contracts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                contract_type TEXT NOT NULL,
                title TEXT NOT NULL,
                status TEXT DEFAULT 'draft',
                version INTEGER DEFAULT 1,
                parent_contract_id INTEGER,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_amount REAL DEFAULT 0.0,
                payment_terms TEXT,
                start_date TEXT,
                end_date TEXT,
                pdf_path TEXT,
                notes TEXT,
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
                FOREIGN KEY (parent_contract_id) REFERENCES contracts(id)
            )
        """)

        # Contract line items
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contract_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id INTEGER NOT NULL,
                template_id INTEGER,
                item_order INTEGER DEFAULT 0,
                description TEXT NOT NULL,
                custom_notes TEXT,
                pricing_type TEXT NOT NULL,
                quantity REAL DEFAULT 1.0,
                unit TEXT,
                unit_price REAL DEFAULT 0.0,
                total REAL DEFAULT 0.0,
                FOREIGN KEY (contract_id) REFERENCES contracts(id) ON DELETE CASCADE,
                FOREIGN KEY (template_id) REFERENCES contract_templates(id) ON DELETE SET NULL
            )
        """)

        # Warranty templates
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS warranties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                duration_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Terms templates
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS terms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Contract warranties (many-to-many)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contract_warranties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id INTEGER NOT NULL,
                warranty_id INTEGER NOT NULL,
                custom_text TEXT,
                FOREIGN KEY (contract_id) REFERENCES contracts(id) ON DELETE CASCADE,
                FOREIGN KEY (warranty_id) REFERENCES warranties(id) ON DELETE CASCADE
            )
        """)

        # Contract terms (many-to-many)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contract_terms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id INTEGER NOT NULL,
                term_id INTEGER NOT NULL,
                custom_text TEXT,
                FOREIGN KEY (contract_id) REFERENCES contracts(id) ON DELETE CASCADE,
                FOREIGN KEY (term_id) REFERENCES terms(id) ON DELETE CASCADE
            )
        """)

        self.connection.commit()

        # Add client_type column if it doesn't exist
        try:
            cursor.execute("ALTER TABLE clients ADD COLUMN client_type TEXT DEFAULT 'active'")
            self.connection.commit()
        except sqlite3.OperationalError:
            # Column already exists
            pass

        # Create indexes for performance optimization
        self.create_indexes()

    def create_indexes(self):
        """Create database indexes to optimize query performance."""
        cursor = self.connection.cursor()

        # Critical indexes for JOIN operations and WHERE clauses
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_visits_client_id ON visits(client_id)",
            "CREATE INDEX IF NOT EXISTS idx_visits_date ON visits(visit_date)",
            "CREATE INDEX IF NOT EXISTS idx_visit_materials_visit_id ON visit_materials(visit_id)",
            "CREATE INDEX IF NOT EXISTS idx_visit_materials_material_id ON visit_materials(material_id)",
            "CREATE INDEX IF NOT EXISTS idx_client_materials_client_id ON client_materials(client_id)",
            "CREATE INDEX IF NOT EXISTS idx_client_materials_material_id ON client_materials(material_id)",
            "CREATE INDEX IF NOT EXISTS idx_clients_active ON clients(is_active)",
            "CREATE INDEX IF NOT EXISTS idx_clients_bill_to ON clients(bill_to)",
            "CREATE INDEX IF NOT EXISTS idx_clients_type ON clients(client_type)",
            "CREATE INDEX IF NOT EXISTS idx_contracts_client_id ON contracts(client_id)",
            "CREATE INDEX IF NOT EXISTS idx_contracts_status ON contracts(status)",
            "CREATE INDEX IF NOT EXISTS idx_contracts_type ON contracts(contract_type)",
            "CREATE INDEX IF NOT EXISTS idx_contract_items_contract_id ON contract_items(contract_id)",
            "CREATE INDEX IF NOT EXISTS idx_contract_items_order ON contract_items(contract_id, item_order)",
        ]

        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
            except sqlite3.OperationalError:
                # Index might already exist
                pass

        self.connection.commit()

    # ==================== CLIENT OPERATIONS ====================

    def add_client(self, name: str, monthly_charge: float, email: str = "",
                   phone: str = "", address: str = "", notes: str = "", bill_to: str = "") -> int:
        """Add a new client and return their ID."""
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT INTO clients (name, email, phone, address, monthly_charge, notes, bill_to)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, email, phone, address, monthly_charge, notes, bill_to))
        self.connection.commit()
        return cursor.lastrowid

    def update_client(self, client_id: int, **kwargs):
        """Update client information."""
        allowed_fields = ['name', 'email', 'phone', 'address', 'monthly_charge', 'notes', 'bill_to']
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

    def set_client_no_additional_services(self, client_id: int, value: bool):
        """Set whether a client needs additional services/materials."""
        self.connection.execute(
            "UPDATE clients SET no_additional_services = ? WHERE id = ?",
            (1 if value else 0, client_id)
        )
        self.connection.commit()

    def get_client_no_additional_services(self, client_id: int) -> bool:
        """Get whether a client is marked as not needing additional services/materials."""
        cursor = self.connection.cursor()
        cursor.execute("SELECT no_additional_services FROM clients WHERE id = ?", (client_id,))
        row = cursor.fetchone()
        return bool(row['no_additional_services']) if row else False

    def get_clients_missing_services_materials(self) -> List[Dict]:
        """Get active clients without configured services/materials who need them."""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT c.id, c.name
            FROM clients c
            WHERE c.is_active = 1
            AND c.no_additional_services = 0
            AND NOT EXISTS (
                SELECT 1 FROM client_materials cm
                WHERE cm.client_id = c.id AND cm.is_enabled = 1
            )
            ORDER BY c.name
        """)
        return [dict(row) for row in cursor.fetchall()]

    def get_clients_missing_contact_info(self) -> List[Dict]:
        """Get active clients with missing contact information (email, phone, or address)."""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT c.id, c.name, c.email, c.phone, c.address
            FROM clients c
            WHERE c.is_active = 1
            AND (
                c.email IS NULL OR c.email = '' OR
                c.phone IS NULL OR c.phone = '' OR
                c.address IS NULL OR c.address = ''
            )
            ORDER BY c.name
        """)
        return [dict(row) for row in cursor.fetchall()]

    def delete_client(self, client_id: int):
        """Hard delete - permanently remove client and all related data."""
        self.connection.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        self.connection.commit()

    # ==================== CLIENT ALIASES ====================

    def add_client_alias(self, client_id: int, alias: str):
        """Add an alias for a client."""
        cursor = self.connection.cursor()
        try:
            cursor.execute("""
                INSERT INTO client_aliases (client_id, alias)
                VALUES (?, ?)
            """, (client_id, alias.strip()))
            self.connection.commit()
        except sqlite3.IntegrityError:
            # Alias already exists for this client
            pass

    def get_client_aliases(self, client_id: int) -> List[str]:
        """Get all aliases for a client."""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT alias FROM client_aliases
            WHERE client_id = ?
            ORDER BY alias
        """, (client_id,))
        return [row['alias'] for row in cursor.fetchall()]

    def delete_client_alias(self, client_id: int, alias: str):
        """Remove an alias from a client."""
        self.connection.execute("""
            DELETE FROM client_aliases
            WHERE client_id = ? AND alias = ?
        """, (client_id, alias))
        self.connection.commit()

    def find_client_by_name_or_alias(self, name: str) -> Optional[Dict]:
        """Find a client by their name or any of their aliases."""
        cursor = self.connection.cursor()

        # First try exact match on client name
        cursor.execute("SELECT * FROM clients WHERE LOWER(name) = LOWER(?)", (name.strip(),))
        result = cursor.fetchone()
        if result:
            return dict(result)

        # Then try aliases
        cursor.execute("""
            SELECT c.* FROM clients c
            JOIN client_aliases ca ON c.id = ca.client_id
            WHERE LOWER(ca.alias) = LOWER(?)
        """, (name.strip(),))
        result = cursor.fetchone()
        if result:
            return dict(result)

        return None

    # ==================== CLIENT GROUPS ====================

    def get_all_client_groups(self) -> List[Dict]:
        """Get all unique bill_to groups with client counts."""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT bill_to, COUNT(*) as client_count
            FROM clients
            WHERE is_active = 1 AND bill_to IS NOT NULL AND bill_to != ''
            GROUP BY bill_to
            ORDER BY bill_to
        """)
        return [dict(row) for row in cursor.fetchall()]

    def get_clients_in_group(self, bill_to: str) -> List[Dict]:
        """Get all clients in a specific bill_to group."""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT * FROM clients
            WHERE is_active = 1 AND bill_to = ?
            ORDER BY name
        """, (bill_to,))
        return [dict(row) for row in cursor.fetchall()]

    def get_group_info(self, bill_to: str) -> Optional[Dict]:
        """Get contact information for a client group."""
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM client_groups WHERE bill_to = ?", (bill_to,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def save_group_info(self, bill_to: str, email: str = "", phone: str = "", address: str = "", notes: str = ""):
        """Save or update contact information for a client group."""
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT INTO client_groups (bill_to, email, phone, address, notes)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(bill_to) DO UPDATE SET
                email = excluded.email,
                phone = excluded.phone,
                address = excluded.address,
                notes = excluded.notes
        """, (bill_to, email, phone, address, notes))
        self.connection.commit()

    def get_client_by_name(self, name: str) -> Optional[Dict]:
        """Get a client by exact name match."""
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM clients WHERE name = ? AND is_active = 1", (name,))
        row = cursor.fetchone()
        return dict(row) if row else None

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

    def get_visits_by_date(self, visit_date: str, active_only: bool = True) -> List[Dict]:
        """
        Get all visits for a specific date with client info in a single optimized query.

        Args:
            visit_date: Date in YYYY-MM-DD format
            active_only: Whether to only include active clients

        Returns:
            List of visits with client_name included
        """
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT v.*, c.name as client_name
            FROM visits v
            JOIN clients c ON v.client_id = c.id
            WHERE v.visit_date = ? AND (c.is_active = 1 OR ? = 0)
            ORDER BY v.start_time ASC
        """, (visit_date, 1 if active_only else 0))
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
        Optimized to use a single SQL query with window functions.

        Args:
            threshold_percent: Percentage threshold (e.g., 300 means 3x the average)

        Returns:
            List of visits with anomalous durations, including comparison data
        """
        cursor = self.connection.cursor()

        # Optimized query using window functions to calculate averages in SQL
        cursor.execute("""
            WITH client_stats AS (
                SELECT
                    client_id,
                    AVG(duration_minutes) as avg_duration,
                    COUNT(*) as total_visits
                FROM visits
                GROUP BY client_id
                HAVING total_visits >= 2
            )
            SELECT
                v.*,
                c.name as client_name,
                cs.avg_duration,
                cs.total_visits,
                (v.duration_minutes * 100.0 / cs.avg_duration) as percent_of_avg
            FROM visits v
            JOIN clients c ON v.client_id = c.id
            JOIN client_stats cs ON v.client_id = cs.client_id
            WHERE cs.avg_duration > 0
              AND (v.duration_minutes * 100.0 / cs.avg_duration) >= ?
            ORDER BY percent_of_avg DESC
        """, (threshold_percent,))

        return [dict(row) for row in cursor.fetchall()]

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
        """Get statistics for all clients using optimized single query."""
        from datetime import datetime
        cursor = self.connection.cursor()

        current_year = datetime.now().year
        hourly_rate = self.get_hourly_rate()

        # Optimized query using CTEs to get all stats in one query
        cursor.execute("""
            WITH
            -- Get all visit counts and time statistics per client
            visit_stats AS (
                SELECT
                    client_id,
                    COUNT(*) as visit_count,
                    SUM(CASE WHEN strftime('%Y', visit_date) = ? THEN 1 ELSE 0 END) as visits_this_year,
                    COALESCE(AVG(duration_minutes), 0) as avg_duration,
                    COALESCE(MIN(duration_minutes), 0) as min_duration,
                    COALESCE(MAX(duration_minutes), 0) as max_duration,
                    COALESCE(SUM(duration_minutes), 0) as total_duration
                FROM visits
                GROUP BY client_id
            ),
            -- Get configured material costs per client (materials only)
            configured_materials AS (
                SELECT
                    cm.client_id,
                    COALESCE(SUM(COALESCE(cm.custom_cost, m.default_cost) * cm.multiplier), 0) as configured_materials_yearly
                FROM client_materials cm
                JOIN materials m ON cm.material_id = m.id
                WHERE cm.is_enabled = 1 AND m.material_type = 'material'
                GROUP BY cm.client_id
            ),
            -- Get configured service costs per client (services only)
            configured_services AS (
                SELECT
                    cm.client_id,
                    COALESCE(SUM(COALESCE(cm.custom_cost, m.default_cost) * cm.multiplier), 0) as configured_services_yearly
                FROM client_materials cm
                JOIN materials m ON cm.material_id = m.id
                WHERE cm.is_enabled = 1 AND m.material_type = 'service'
                GROUP BY cm.client_id
            ),
            -- Get visit material costs per client (materials only)
            visit_materials_costs AS (
                SELECT
                    v.client_id,
                    COALESCE(SUM(vm.quantity * vm.cost_at_time), 0) as visit_material_cost
                FROM visits v
                LEFT JOIN visit_materials vm ON v.id = vm.visit_id
                LEFT JOIN materials m ON vm.material_id = m.id
                WHERE m.material_type = 'material'
                GROUP BY v.client_id
            ),
            -- Get visit service costs per client (services only)
            visit_services_costs AS (
                SELECT
                    v.client_id,
                    COALESCE(SUM(vm.quantity * vm.cost_at_time), 0) as visit_service_cost
                FROM visits v
                LEFT JOIN visit_materials vm ON v.id = vm.visit_id
                LEFT JOIN materials m ON vm.material_id = m.id
                WHERE m.material_type = 'service'
                GROUP BY v.client_id
            )
            -- Main query joining all CTEs
            SELECT
                c.id as client_id,
                c.name as client_name,
                c.monthly_charge as actual_monthly_charge,
                COALESCE(vs.visit_count, 0) as visit_count,
                COALESCE(vs.visits_this_year, 0) as visits_this_year,
                COALESCE(vs.avg_duration, 0) as avg_duration,
                COALESCE(vs.min_duration, 0) as min_duration,
                COALESCE(vs.max_duration, 0) as max_duration,
                COALESCE(vs.total_duration, 0) as total_duration,
                COALESCE(cm.configured_materials_yearly, 0) as configured_materials_cost_yearly,
                COALESCE(cs.configured_services_yearly, 0) as configured_services_yearly,
                COALESCE(vmc.visit_material_cost, 0) as visit_material_cost,
                COALESCE(vsc.visit_service_cost, 0) as visit_service_cost
            FROM clients c
            LEFT JOIN visit_stats vs ON c.id = vs.client_id
            LEFT JOIN configured_materials cm ON c.id = cm.client_id
            LEFT JOIN configured_services cs ON c.id = cs.client_id
            LEFT JOIN visit_materials_costs vmc ON c.id = vmc.client_id
            LEFT JOIN visit_services_costs vsc ON c.id = vsc.client_id
            WHERE c.is_active = ?
            ORDER BY c.name
        """, (str(current_year), 1 if active_only else 0))

        results = []
        for row in cursor.fetchall():
            # Calculate derived fields
            total_material_cost = row['configured_materials_cost_yearly'] + row['visit_material_cost']
            total_service_cost = row['configured_services_yearly'] + row['visit_service_cost']
            total_materials_services_cost = total_material_cost + total_service_cost

            total_labor_cost = (row['total_duration'] / 60) * 2 * hourly_rate
            total_cost = total_labor_cost + total_materials_services_cost

            visit_count = row['visit_count'] if row['visit_count'] > 0 else 1
            avg_cost_per_visit = total_cost / visit_count

            avg_labor_cost_per_visit = (row['avg_duration'] / 60) * 2 * hourly_rate
            projected_yearly_labor_cost = avg_labor_cost_per_visit * 52

            est_yearly_cost = projected_yearly_labor_cost + row['configured_materials_cost_yearly'] + row['configured_services_yearly']
            proposed_monthly_rate = est_yearly_cost / 12

            profit_loss = row['actual_monthly_charge'] - proposed_monthly_rate
            is_profitable = profit_loss >= 0

            results.append({
                'client_id': row['client_id'],
                'client_name': row['client_name'],
                'visit_count': row['visit_count'],
                'visits_this_year': row['visits_this_year'],
                'total_material_cost': round(total_material_cost, 2),
                'total_service_cost': round(total_service_cost, 2),
                'total_materials_services_cost': round(total_materials_services_cost, 2),
                'configured_materials_cost_yearly': round(row['configured_materials_cost_yearly'], 2),
                'configured_services_cost_yearly': round(row['configured_services_yearly'], 2),
                'projected_yearly_labor_cost': round(projected_yearly_labor_cost, 2),
                'avg_time_per_visit': round(row['avg_duration'], 1),
                'min_time_per_visit': round(row['min_duration'], 1),
                'max_time_per_visit': round(row['max_duration'], 1),
                'total_labor_cost': round(total_labor_cost, 2),
                'avg_cost_per_visit': round(avg_cost_per_visit, 2),
                'est_yearly_cost': round(est_yearly_cost, 2),
                'proposed_monthly_rate': round(proposed_monthly_rate, 2),
                'actual_monthly_charge': round(row['actual_monthly_charge'], 2),
                'monthly_profit_loss': round(profit_loss, 2),
                'is_profitable': is_profitable,
                'hourly_rate': round(hourly_rate, 2)
            })

        return results

    # ==================== CONTRACT TEMPLATE OPERATIONS ====================

    def add_contract_template(self, name: str, description: str, category: str = "",
                             default_pricing_type: str = "flat", default_unit: str = "") -> int:
        """Add a new contract item template."""
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT INTO contract_templates (name, description, category, default_pricing_type, default_unit)
            VALUES (?, ?, ?, ?, ?)
        """, (name, description, category, default_pricing_type, default_unit))
        self.connection.commit()
        return cursor.lastrowid

    def get_all_contract_templates(self, category: str = None) -> List[Dict]:
        """Get all contract templates, optionally filtered by category."""
        cursor = self.connection.cursor()
        if category:
            cursor.execute("""
                SELECT * FROM contract_templates
                WHERE category = ?
                ORDER BY name
            """, (category,))
        else:
            cursor.execute("SELECT * FROM contract_templates ORDER BY name")
        return [dict(row) for row in cursor.fetchall()]

    def get_contract_template(self, template_id: int) -> Optional[Dict]:
        """Get a specific contract template by ID."""
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM contract_templates WHERE id = ?", (template_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def update_contract_template(self, template_id: int, **kwargs):
        """Update a contract template."""
        allowed_fields = ['name', 'description', 'category', 'default_pricing_type', 'default_unit']
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return

        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [template_id]

        cursor = self.connection.cursor()
        cursor.execute(f"UPDATE contract_templates SET {set_clause} WHERE id = ?", values)
        self.connection.commit()

    def delete_contract_template(self, template_id: int):
        """Delete a contract template."""
        cursor = self.connection.cursor()
        cursor.execute("DELETE FROM contract_templates WHERE id = ?", (template_id,))
        self.connection.commit()

    def get_template_categories(self) -> List[str]:
        """Get all unique template categories."""
        cursor = self.connection.cursor()
        cursor.execute("SELECT DISTINCT category FROM contract_templates WHERE category != '' ORDER BY category")
        return [row[0] for row in cursor.fetchall()]

    # ==================== CONTRACT OPERATIONS ====================

    def create_contract(self, client_id: int, contract_type: str, title: str,
                       status: str = "draft", payment_terms: str = "",
                       start_date: str = "", end_date: str = "", notes: str = "") -> int:
        """Create a new contract."""
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT INTO contracts (client_id, contract_type, title, status, payment_terms,
                                 start_date, end_date, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (client_id, contract_type, title, status, payment_terms, start_date, end_date, notes))
        self.connection.commit()
        return cursor.lastrowid

    def get_contract(self, contract_id: int) -> Optional[Dict]:
        """Get a specific contract by ID."""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT c.*, cl.name as client_name
            FROM contracts c
            JOIN clients cl ON c.client_id = cl.id
            WHERE c.id = ?
        """, (contract_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_client_contracts(self, client_id: int, include_versions: bool = False) -> List[Dict]:
        """Get all contracts for a client."""
        cursor = self.connection.cursor()
        if include_versions:
            cursor.execute("""
                SELECT * FROM contracts
                WHERE client_id = ?
                ORDER BY created_date DESC, version DESC
            """, (client_id,))
        else:
            cursor.execute("""
                SELECT * FROM contracts
                WHERE client_id = ? AND parent_contract_id IS NULL
                ORDER BY created_date DESC
            """, (client_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_all_contracts(self, status: str = None, contract_type: str = None) -> List[Dict]:
        """Get all contracts with optional filters."""
        cursor = self.connection.cursor()
        query = """
            SELECT c.*, cl.name as client_name
            FROM contracts c
            JOIN clients cl ON c.client_id = cl.id
            WHERE c.parent_contract_id IS NULL
        """
        params = []

        if status:
            query += " AND c.status = ?"
            params.append(status)
        if contract_type:
            query += " AND c.contract_type = ?"
            params.append(contract_type)

        query += " ORDER BY c.created_date DESC"

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def update_contract(self, contract_id: int, **kwargs):
        """Update a contract."""
        allowed_fields = ['title', 'status', 'payment_terms', 'start_date', 'end_date',
                         'total_amount', 'pdf_path', 'notes']
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return

        updates['updated_date'] = datetime.now().isoformat()

        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [contract_id]

        cursor = self.connection.cursor()
        cursor.execute(f"UPDATE contracts SET {set_clause} WHERE id = ?", values)
        self.connection.commit()

    def create_contract_version(self, original_contract_id: int) -> int:
        """Create a new version of an existing contract."""
        # Get the original contract
        original = self.get_contract(original_contract_id)
        if not original:
            raise ValueError("Original contract not found")

        # Get the highest version number
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT MAX(version) FROM contracts
            WHERE id = ? OR parent_contract_id = ?
        """, (original_contract_id, original_contract_id))
        max_version = cursor.fetchone()[0] or original['version']
        new_version = max_version + 1

        # Create new contract version
        cursor.execute("""
            INSERT INTO contracts (client_id, contract_type, title, status, version,
                                 parent_contract_id, payment_terms, start_date, end_date,
                                 notes)
            VALUES (?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?)
        """, (original['client_id'], original['contract_type'], original['title'],
              new_version, original_contract_id, original['payment_terms'],
              original['start_date'], original['end_date'], original['notes']))

        new_contract_id = cursor.lastrowid

        # Copy all items from original
        cursor.execute("""
            INSERT INTO contract_items (contract_id, template_id, item_order, description,
                                       custom_notes, pricing_type, quantity, unit, unit_price, total)
            SELECT ?, template_id, item_order, description, custom_notes, pricing_type,
                   quantity, unit, unit_price, total
            FROM contract_items
            WHERE contract_id = ?
        """, (new_contract_id, original_contract_id))

        self.connection.commit()
        return new_contract_id

    def get_contract_versions(self, contract_id: int) -> List[Dict]:
        """Get all versions of a contract."""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT * FROM contracts
            WHERE id = ? OR parent_contract_id = ?
            ORDER BY version ASC
        """, (contract_id, contract_id))
        return [dict(row) for row in cursor.fetchall()]

    def delete_contract(self, contract_id: int):
        """Delete a contract and all its items."""
        cursor = self.connection.cursor()
        cursor.execute("DELETE FROM contracts WHERE id = ?", (contract_id,))
        self.connection.commit()

    # ==================== CONTRACT ITEM OPERATIONS ====================

    def add_contract_item(self, contract_id: int, description: str, pricing_type: str,
                         quantity: float = 1.0, unit_price: float = 0.0, unit: str = "",
                         custom_notes: str = "", template_id: int = None,
                         item_order: int = None) -> int:
        """Add an item to a contract."""
        # Calculate total
        total = quantity * unit_price

        # Get next order if not specified
        if item_order is None:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT COALESCE(MAX(item_order), -1) + 1
                FROM contract_items
                WHERE contract_id = ?
            """, (contract_id,))
            item_order = cursor.fetchone()[0]

        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT INTO contract_items (contract_id, template_id, item_order, description,
                                      custom_notes, pricing_type, quantity, unit, unit_price, total)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (contract_id, template_id, item_order, description, custom_notes,
              pricing_type, quantity, unit, unit_price, total))

        item_id = cursor.lastrowid

        # Update contract total
        self._update_contract_total(contract_id)

        self.connection.commit()
        return item_id

    def get_contract_items(self, contract_id: int) -> List[Dict]:
        """Get all items for a contract in order."""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT ci.*, ct.name as template_name
            FROM contract_items ci
            LEFT JOIN contract_templates ct ON ci.template_id = ct.id
            WHERE ci.contract_id = ?
            ORDER BY ci.item_order
        """, (contract_id,))
        return [dict(row) for row in cursor.fetchall()]

    def update_contract_item(self, item_id: int, **kwargs):
        """Update a contract item."""
        allowed_fields = ['description', 'custom_notes', 'pricing_type', 'quantity',
                         'unit', 'unit_price', 'item_order']
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return

        # Recalculate total if quantity or unit_price changed
        if 'quantity' in updates or 'unit_price' in updates:
            cursor = self.connection.cursor()
            cursor.execute("SELECT quantity, unit_price FROM contract_items WHERE id = ?", (item_id,))
            row = cursor.fetchone()
            current_qty = updates.get('quantity', row[0])
            current_price = updates.get('unit_price', row[1])
            updates['total'] = current_qty * current_price

        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [item_id]

        cursor = self.connection.cursor()
        cursor.execute(f"UPDATE contract_items SET {set_clause} WHERE id = ?", values)

        # Get contract_id and update total
        cursor.execute("SELECT contract_id FROM contract_items WHERE id = ?", (item_id,))
        contract_id = cursor.fetchone()[0]
        self._update_contract_total(contract_id)

        self.connection.commit()

    def delete_contract_item(self, item_id: int):
        """Delete a contract item."""
        cursor = self.connection.cursor()

        # Get contract_id before deleting
        cursor.execute("SELECT contract_id FROM contract_items WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        if row:
            contract_id = row[0]
            cursor.execute("DELETE FROM contract_items WHERE id = ?", (item_id,))
            self._update_contract_total(contract_id)
            self.connection.commit()

    def reorder_contract_items(self, contract_id: int, item_ids_in_order: List[int]):
        """Reorder contract items."""
        cursor = self.connection.cursor()
        for order, item_id in enumerate(item_ids_in_order):
            cursor.execute("""
                UPDATE contract_items
                SET item_order = ?
                WHERE id = ? AND contract_id = ?
            """, (order, item_id, contract_id))
        self.connection.commit()

    def _update_contract_total(self, contract_id: int):
        """Recalculate and update the contract total amount."""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT COALESCE(SUM(total), 0)
            FROM contract_items
            WHERE contract_id = ?
        """, (contract_id,))
        total = cursor.fetchone()[0]

        cursor.execute("""
            UPDATE contracts
            SET total_amount = ?, updated_date = ?
            WHERE id = ?
        """, (total, datetime.now().isoformat(), contract_id))

    # ==================== CLIENT TYPE OPERATIONS ====================

    def update_client_type(self, client_id: int, client_type: str):
        """Update a client's type (active, seasonal, project, inactive)."""
        cursor = self.connection.cursor()
        cursor.execute("""
            UPDATE clients
            SET client_type = ?
            WHERE id = ?
        """, (client_type, client_id))
        self.connection.commit()

    def get_clients_by_type(self, client_type: str, active_only: bool = True) -> List[Dict]:
        """Get all clients of a specific type."""
        cursor = self.connection.cursor()
        query = "SELECT * FROM clients WHERE client_type = ?"
        params = [client_type]

        if active_only:
            query += " AND is_active = 1"

        query += " ORDER BY name"

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
