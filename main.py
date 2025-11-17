"""
Landscaping Client Tracker - Main Application
A desktop application for managing landscaping clients, visits, and costs.
"""
import customtkinter as ctk
from database import Database
from excel_importer import ExcelImporter
from ocr_scanner import OCRScanner
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from tkcalendar import DateEntry
from typing import Optional
from collections import defaultdict


# Configure CustomTkinter
ctk.set_appearance_mode("dark")  # Dark mode
ctk.set_default_color_theme("blue")


class LandscapingApp(ctk.CTk):
    """Main application window for the Landscaping Client Tracker."""

    def __init__(self):
        super().__init__()

        # Initialize database
        self.db = Database()

        # Load and apply saved color theme
        saved_theme = self.db.get_setting('color_theme', 'blue')
        try:
            ctk.set_default_color_theme(saved_theme)
        except:
            ctk.set_default_color_theme("blue")

        # Initialize importers (lazy load OCR scanner only when needed)
        self.excel_importer = ExcelImporter(self.db)
        self.ocr_scanner = None  # Lazy load when OCR tab is accessed

        # Configure window
        self.title("Landscaping Client Tracker")
        self.geometry("1300x850")

        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Create main container
        self.main_container = ctk.CTkFrame(self)
        self.main_container.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(1, weight=1)

        # Create header
        self.create_header()

        # Create tabview for different sections
        self.tabview = ctk.CTkTabview(self.main_container, height=750)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # Add tabs
        self.tab_dashboard = self.tabview.add("Dashboard")
        self.tab_clients = self.tabview.add("Clients")
        self.tab_visits = self.tabview.add("Visits")
        self.tab_daily = self.tabview.add("Daily Schedule")
        self.tab_review = self.tabview.add("Review")
        self.tab_materials = self.tabview.add("Materials")
        self.tab_import = self.tabview.add("Import Data")

        # Initialize tabs
        self.init_dashboard_tab()
        self.init_clients_tab()
        self.init_visits_tab()
        self.init_daily_schedule_tab()
        self.init_review_tab()
        self.init_materials_tab()
        self.init_import_tab()

        # Current selections
        self.current_client_id = None
        self.current_visit_id = None

        # Track which tabs have been loaded (lazy loading optimization)
        self.tabs_loaded = {
            'dashboard': False,
            'clients': False,
            'materials': False
        }

        # Set up tab change callback for lazy loading
        self.tabview.configure(command=self.on_tab_change)

        # Load only the dashboard initially (shown by default)
        self.refresh_dashboard()
        self.tabs_loaded['dashboard'] = True

    def get_ocr_scanner(self):
        """Get OCR scanner with lazy initialization."""
        if self.ocr_scanner is None:
            self.ocr_scanner = OCRScanner()
        return self.ocr_scanner

    def on_tab_change(self):
        """Handle tab change for lazy loading optimization."""
        current_tab = self.tabview.get()

        # Lazy load clients tab
        if current_tab == "Clients" and not self.tabs_loaded['clients']:
            self.refresh_clients_list()
            self.tabs_loaded['clients'] = True

        # Lazy load materials tab
        elif current_tab == "Materials" and not self.tabs_loaded['materials']:
            self.refresh_materials_list()
            self.tabs_loaded['materials'] = True

    def create_header(self):
        """Create the application header with title and refresh button."""
        header_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=3)
        header_frame.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            header_frame,
            text="🌿 Landscaping Client Tracker",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        title.grid(row=0, column=0, sticky="w", padx=5, pady=3)

        settings_btn = ctk.CTkButton(
            header_frame,
            text="⚙ Settings",
            command=self.show_settings_dialog,
            font=ctk.CTkFont(size=10),
            height=26,
            width=100
        )
        settings_btn.grid(row=0, column=1, padx=3, pady=3)

        refresh_btn = ctk.CTkButton(
            header_frame,
            text="Refresh All",
            command=self.refresh_all,
            font=ctk.CTkFont(size=10),
            height=26,
            width=100
        )
        refresh_btn.grid(row=0, column=2, padx=3, pady=3)

    # ==================== DASHBOARD TAB ====================

    def init_dashboard_tab(self):
        """Initialize the dashboard tab with client statistics."""
        self.tab_dashboard.grid_columnconfigure(0, weight=1)
        self.tab_dashboard.grid_rowconfigure(2, weight=1)

        # Header with filter
        header_frame = ctk.CTkFrame(self.tab_dashboard, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        header_frame.grid_columnconfigure(1, weight=1)

        header = ctk.CTkLabel(
            header_frame,
            text="Client Overview",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        header.grid(row=0, column=0, sticky="w", padx=5)

        # Client filter dropdown
        filter_label = ctk.CTkLabel(header_frame, text="Filter:", font=ctk.CTkFont(size=11))
        filter_label.grid(row=0, column=1, sticky="e", padx=(0, 5))

        self.dashboard_filter_var = tk.StringVar(value="📉 Losing Money")
        self.dashboard_filter_menu = ctk.CTkOptionMenu(
            header_frame,
            variable=self.dashboard_filter_var,
            values=["📉 Losing Money", "📈 Earning Money"],
            command=self.on_dashboard_filter_change,
            font=ctk.CTkFont(size=11),
            height=28,
            width=180
        )
        self.dashboard_filter_menu.grid(row=0, column=2, sticky="e", padx=5)

        # Client info frame (for selected client card)
        self.dashboard_client_frame = ctk.CTkFrame(self.tab_dashboard)
        self.dashboard_client_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        self.dashboard_client_frame.grid_columnconfigure(0, weight=1)

        # Visualization frame
        viz_frame = ctk.CTkFrame(self.tab_dashboard)
        viz_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        viz_frame.grid_columnconfigure(0, weight=1)
        viz_frame.grid_rowconfigure(1, weight=1)

        # Visualization header with toggle
        viz_header_frame = ctk.CTkFrame(viz_frame, fg_color="transparent")
        viz_header_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=3)

        viz_title = ctk.CTkLabel(
            viz_header_frame,
            text="Visit Trends (This Year)",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        viz_title.pack(side="left", padx=5)

        self.viz_mode_var = tk.StringVar(value="time")
        viz_toggle_frame = ctk.CTkFrame(viz_header_frame, fg_color="transparent")
        viz_toggle_frame.pack(side="right", padx=5)

        time_radio = ctk.CTkRadioButton(
            viz_toggle_frame,
            text="Time/Visit",
            variable=self.viz_mode_var,
            value="time",
            command=self.update_visualization,
            font=ctk.CTkFont(size=10)
        )
        time_radio.pack(side="left", padx=3)

        cost_radio = ctk.CTkRadioButton(
            viz_toggle_frame,
            text="Cost/Visit",
            variable=self.viz_mode_var,
            value="cost",
            command=self.update_visualization,
            font=ctk.CTkFont(size=10)
        )
        cost_radio.pack(side="left", padx=3)

        # Canvas for matplotlib
        self.viz_canvas_frame = ctk.CTkFrame(viz_frame)
        self.viz_canvas_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.viz_canvas_frame.grid_columnconfigure(0, weight=1)
        self.viz_canvas_frame.grid_rowconfigure(0, weight=1)

        self.current_viz_client_id = None

    def refresh_dashboard(self):
        """Refresh the dashboard with updated statistics."""
        # Get all client statistics
        stats_list = self.db.get_all_client_statistics(active_only=True)

        if not stats_list:
            # Clear filter options
            self.dashboard_filter_menu.configure(values=["No clients"])
            self.dashboard_filter_var.set("No clients")

            # Clear client frame
            for widget in self.dashboard_client_frame.winfo_children():
                widget.destroy()

            no_data = ctk.CTkLabel(
                self.dashboard_client_frame,
                text="No active clients. Add clients in the Clients tab.",
                font=ctk.CTkFont(size=13)
            )
            no_data.pack(pady=20)

            # Clear visualization
            for widget in self.viz_canvas_frame.winfo_children():
                widget.destroy()
            return

        # Build filter options
        filter_options = ["📉 Losing Money", "📈 Earning Money", "---"]

        # Sort clients by name and add to filter with profit indicators
        sorted_stats = sorted(stats_list, key=lambda x: x['client_name'])
        for stats in sorted_stats:
            # Add emoji indicator based on profitability
            if stats['is_profitable']:
                filter_options.append(f"✓ {stats['client_name']}")
            else:
                filter_options.append(f"⚠ {stats['client_name']}")

        # Store the stats list for later use
        self.all_client_stats = stats_list

        # Update filter dropdown
        self.dashboard_filter_menu.configure(values=filter_options)

        # Keep current selection if valid, otherwise default to "Losing Money"
        current = self.dashboard_filter_var.get()
        if current not in filter_options:
            self.dashboard_filter_var.set("📉 Losing Money")

        # Update display
        self.on_dashboard_filter_change(self.dashboard_filter_var.get())

    def on_dashboard_filter_change(self, selection):
        """Handle dashboard filter selection change."""
        # Clear client frame
        for widget in self.dashboard_client_frame.winfo_children():
            widget.destroy()

        # Get all client statistics
        stats_list = self.db.get_all_client_statistics(active_only=True)

        if not stats_list:
            return

        # Filter based on selection
        if selection == "📉 Losing Money":
            filtered = [s for s in stats_list if not s['is_profitable']]
            if filtered:
                # Show list of clients losing money
                self.show_client_list(self.dashboard_client_frame, filtered, "Clients Losing Money")
                self.current_viz_client_id = None
            else:
                msg = ctk.CTkLabel(
                    self.dashboard_client_frame,
                    text="No clients are losing money! 🎉",
                    font=ctk.CTkFont(size=13)
                )
                msg.pack(pady=20)
                self.current_viz_client_id = None
        elif selection == "📈 Earning Money":
            filtered = [s for s in stats_list if s['is_profitable']]
            if filtered:
                # Show list of profitable clients
                self.show_client_list(self.dashboard_client_frame, filtered, "Profitable Clients")
                self.current_viz_client_id = None
            else:
                msg = ctk.CTkLabel(
                    self.dashboard_client_frame,
                    text="No profitable clients yet.",
                    font=ctk.CTkFont(size=13)
                )
                msg.pack(pady=20)
                self.current_viz_client_id = None
        elif selection != "---" and selection != "No clients":
            # Remove emoji prefix if present
            client_name = selection
            if selection.startswith("✓ ") or selection.startswith("⚠ "):
                client_name = selection[2:]  # Remove first 2 characters (emoji + space)

            # Show specific client by name
            client_stats = next((s for s in stats_list if s['client_name'] == client_name), None)
            if client_stats:
                self.create_client_card(self.dashboard_client_frame, client_stats, 0)
                self.current_viz_client_id = client_stats['client_id']

        # Update visualization
        self.update_visualization()

    def show_client_list(self, parent, client_stats_list, title):
        """Display a clickable list of clients."""
        # Header
        header = ctk.CTkLabel(
            parent,
            text=title,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        header.pack(pady=(10, 15))

        # Create scrollable frame for client buttons
        scroll_frame = ctk.CTkScrollableFrame(parent, height=400)
        scroll_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Sort by profitability (most unprofitable or most profitable first)
        if "Losing" in title:
            # Sort by biggest loss first (most negative profit/loss)
            sorted_clients = sorted(client_stats_list, key=lambda x: x['monthly_profit_loss'])
        else:
            # Sort by biggest profit first (most positive profit/loss)
            sorted_clients = sorted(client_stats_list, key=lambda x: x['monthly_profit_loss'], reverse=True)

        # Create clickable buttons for each client
        for stats in sorted_clients:
            # Create frame for each client button
            client_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
            client_frame.pack(fill="x", padx=5, pady=3)

            # Determine color and icon based on profitability (muted colors for dark theme)
            if stats['is_profitable']:
                border_color = "#4A7C59"  # Muted dark green
                icon = "✓"
                text_color = "#5FA777"  # Softer green for text
            else:
                border_color = "#8B4C4C"  # Muted dark red
                icon = "⚠"
                text_color = "#C97C7C"  # Softer red for text

            # Client button
            client_btn = ctk.CTkButton(
                client_frame,
                text=f"{icon} {stats['client_name']}",
                command=lambda s=stats: self.select_client_from_list(s),
                font=ctk.CTkFont(size=12),
                height=40,
                border_width=2,
                border_color=border_color,
                fg_color="transparent",
                hover_color=("#E0E0E0", "#2B2B2B")
            )
            client_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))

            # Profit/Loss indicator
            profit_loss = stats['monthly_profit_loss']
            profit_text = f"${abs(profit_loss):.2f}/mo"
            if profit_loss >= 0:
                profit_text = f"+{profit_text}"
            else:
                profit_text = f"-{profit_text}"

            profit_label = ctk.CTkLabel(
                client_frame,
                text=profit_text,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=text_color,
                width=100
            )
            profit_label.pack(side="right")

    def select_client_from_list(self, client_stats):
        """Select a client from the filtered list and show their full overview."""
        # Update dropdown to show this client (with emoji prefix)
        if client_stats['is_profitable']:
            dropdown_value = f"✓ {client_stats['client_name']}"
        else:
            dropdown_value = f"⚠ {client_stats['client_name']}"

        self.dashboard_filter_var.set(dropdown_value)

        # Clear and show client card
        for widget in self.dashboard_client_frame.winfo_children():
            widget.destroy()

        self.create_client_card(self.dashboard_client_frame, client_stats, 0)
        self.current_viz_client_id = client_stats['client_id']

        # Update visualization
        self.update_visualization()

    def update_visualization(self, *args):
        """Update the visualization chart based on current client and mode."""
        # Lazy import matplotlib and related libraries (optimization)
        import matplotlib
        matplotlib.use('TkAgg')
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        import matplotlib.dates as mdates
        import numpy as np
        from scipy.interpolate import make_interp_spline

        # Clear existing visualization
        for widget in self.viz_canvas_frame.winfo_children():
            widget.destroy()

        if not self.current_viz_client_id:
            return

        # Get visit data for current year
        current_year = datetime.now().year
        visits = self.db.get_client_visits(self.current_viz_client_id)

        # Filter to current year
        visits_this_year = [
            v for v in visits
            if datetime.strptime(v['visit_date'], '%Y-%m-%d').year == current_year
        ]

        if not visits_this_year:
            no_data = ctk.CTkLabel(
                self.viz_canvas_frame,
                text="No visits recorded this year",
                font=ctk.CTkFont(size=11)
            )
            no_data.pack(pady=20)
            return

        # Get hourly rate for cost calculation
        hourly_rate = self.db.get_hourly_rate()

        # Group visits by month and calculate averages
        monthly_data = defaultdict(list)

        for visit in visits_this_year:
            visit_date = datetime.strptime(visit['visit_date'], '%Y-%m-%d')
            month_key = visit_date.replace(day=1)  # First day of month as key

            if self.viz_mode_var.get() == "time":
                monthly_data[month_key].append(visit['duration_minutes'])
            else:  # cost mode
                labor_cost = (visit['duration_minutes'] / 60) * 2 * hourly_rate
                visit_materials = self.db.get_visit_materials(visit['id'])
                material_cost = sum(vm['quantity'] * vm['cost_at_time'] for vm in visit_materials)
                total_cost = labor_cost + material_cost
                monthly_data[month_key].append(total_cost)

        # Calculate monthly averages
        months = sorted(monthly_data.keys())
        averages = [np.mean(monthly_data[month]) for month in months]

        if len(months) == 0:
            no_data = ctk.CTkLabel(
                self.viz_canvas_frame,
                text="No data available",
                font=ctk.CTkFont(size=11)
            )
            no_data.pack(pady=20)
            return

        # Set labels
        if self.viz_mode_var.get() == "time":
            ylabel = "Avg Time (minutes)"
            title = "Average Time per Visit by Month"
        else:
            ylabel = "Avg Cost ($)"
            title = "Average Cost per Visit by Month"

        # Create matplotlib figure
        fig = Figure(figsize=(8, 3), dpi=100, facecolor='#2b2b2b')
        ax = fig.add_subplot(111)
        ax.set_facecolor('#2b2b2b')

        # Plot with smooth curve if we have enough data points
        if len(months) >= 3:
            # Convert dates to numbers for interpolation
            months_num = mdates.date2num(months)

            # Create smooth curve using spline interpolation
            months_smooth = np.linspace(months_num.min(), months_num.max(), 300)
            try:
                spl = make_interp_spline(months_num, averages, k=min(3, len(months)-1))
                averages_smooth = spl(months_smooth)

                # Plot smooth curve
                ax.plot(mdates.num2date(months_smooth), averages_smooth,
                       linestyle='-', linewidth=2.5, color='#1f77b4', alpha=0.8)
                # Plot actual data points
                ax.plot(months, averages, marker='o', linestyle='',
                       markersize=6, color='#ff7f0e', alpha=0.9, zorder=5)
            except:
                # Fallback to regular plot if spline fails
                ax.plot(months, averages, marker='o', linestyle='-',
                       linewidth=2, markersize=6, color='#1f77b4')
        else:
            # Not enough points for smooth curve, use regular plot
            ax.plot(months, averages, marker='o', linestyle='-',
                   linewidth=2, markersize=6, color='#1f77b4')

        ax.set_xlabel("Month", fontsize=12, color='white', fontweight='bold')
        ax.set_ylabel(ylabel, fontsize=12, color='white', fontweight='bold')
        ax.set_title(title, fontsize=14, color='white', pad=8, fontweight='bold')
        ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)
        ax.tick_params(colors='white', labelsize=11)

        # Format x-axis to show month names
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
        ax.xaxis.set_major_locator(mdates.MonthLocator())

        # Adjust layout
        fig.tight_layout(pad=1.5)

        # Embed in tkinter
        canvas = FigureCanvasTkAgg(fig, master=self.viz_canvas_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

        # Update spine colors for dark theme
        for spine in ax.spines.values():
            spine.set_edgecolor('#555555')

    def create_client_card(self, parent, stats, row):
        """Create a visual card showing client statistics."""
        # Determine color based on profitability (muted colors for dark theme)
        if stats['is_profitable']:
            border_color = "#4A7C59"  # Muted dark green
            status_text = "✓ PROFITABLE"
            status_color = "#5FA777"  # Softer green
        else:
            border_color = "#8B4C4C"  # Muted dark red
            status_text = "⚠ LOSING MONEY"
            status_color = "#C97C7C"  # Softer red

        # Card frame
        card = ctk.CTkFrame(parent, border_width=1, border_color=border_color)
        card.grid(row=row, column=0, sticky="ew", padx=3, pady=3)
        card.grid_columnconfigure(1, weight=1)

        # Client name
        name_label = ctk.CTkLabel(
            card,
            text=stats['client_name'],
            font=ctk.CTkFont(size=12, weight="bold")
        )
        name_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=6, pady=(5, 2))

        # Status indicator
        status_label = ctk.CTkLabel(
            card,
            text=status_text,
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color=status_color
        )
        status_label.grid(row=0, column=2, padx=6, pady=(5, 2))

        # Statistics grid
        stats_frame = ctk.CTkFrame(card, fg_color="transparent")
        stats_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=8, pady=4)

        # Create stat items
        stat_items = [
            ("Total Visits (this year):", f"{stats['visits_this_year']}", None),
            ("Configured Materials/Services (Yearly):", f"${stats['configured_materials_cost_yearly'] + stats['configured_services_cost_yearly']:.2f}", "Total yearly cost from assigned materials/services"),
            ("Projected Labor Cost (Yearly):", f"${stats['projected_yearly_labor_cost']:.2f}", "Estimated labor cost for 52 visits/year"),
            ("Total Material Costs:", f"${stats['total_material_cost']:.2f}", "Includes configured materials + materials from visits"),
            ("Total Services Costs:", f"${stats['total_service_cost']:.2f}", "Includes configured services + services from visits"),
            ("Avg Time per Visit:", f"{stats['avg_time_per_visit']:.1f} min",
             f"Shortest: {stats['min_time_per_visit']:.1f} min\nLongest: {stats['max_time_per_visit']:.1f} min"),
            ("Est Yearly Cost:", f"${stats['est_yearly_cost']:.2f}", "Labor + configured materials/services"),
            ("Proposed Monthly Rate:", f"${stats['proposed_monthly_rate']:.2f}", "Yearly cost ÷ 12 months"),
            ("Actual Monthly Charge:", f"${stats['actual_monthly_charge']:.2f}", None),
            ("Monthly Profit/Loss:", f"${stats['monthly_profit_loss']:.2f}", None),
        ]

        for i, item in enumerate(stat_items):
            label, value = item[0], item[1]
            tooltip_text = item[2] if len(item) > 2 else None

            col = i % 2
            row_pos = i // 2

            item_frame = ctk.CTkFrame(stats_frame, fg_color="transparent")
            item_frame.grid(row=row_pos, column=col, sticky="w", padx=6, pady=1)

            lbl = ctk.CTkLabel(
                item_frame,
                text=label,
                font=ctk.CTkFont(size=9)
            )
            lbl.grid(row=0, column=0, sticky="w", padx=(0, 4))

            val = ctk.CTkLabel(
                item_frame,
                text=value,
                font=ctk.CTkFont(size=9, weight="bold")
            )
            val.grid(row=0, column=1, sticky="w")

            # Add tooltip if available
            if tooltip_text:
                info_label = ctk.CTkLabel(
                    item_frame,
                    text="?",
                    font=ctk.CTkFont(size=8, weight="bold"),
                    text_color="gray",
                    cursor="hand2"
                )
                info_label.grid(row=0, column=2, sticky="w", padx=(2, 0))

                # Create click-based tooltip
                def create_tooltip(widget, text):
                    widget.tooltip = None

                    def destroy_tooltip():
                        if hasattr(widget, 'tooltip') and widget.tooltip:
                            try:
                                widget.tooltip.destroy()
                            except:
                                pass
                            widget.tooltip = None

                    def toggle_tooltip(event):
                        # If tooltip exists, close it
                        if widget.tooltip:
                            destroy_tooltip()
                            return

                        # Otherwise, create new tooltip
                        tooltip = ctk.CTkToplevel()
                        tooltip.wm_overrideredirect(True)
                        tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
                        tooltip.attributes('-topmost', True)

                        label = ctk.CTkLabel(
                            tooltip,
                            text=text,
                            font=ctk.CTkFont(size=10),
                            fg_color=("gray85", "gray20"),
                            corner_radius=5
                        )
                        label.pack(padx=8, pady=6)

                        widget.tooltip = tooltip

                        # Close tooltip when clicking anywhere else
                        def close_on_click(e):
                            destroy_tooltip()
                            # Unbind the global click handler
                            try:
                                self.unbind_all("<Button-1>")
                            except:
                                pass

                        # Delay binding to avoid immediate closure
                        self.after(100, lambda: self.bind_all("<Button-1>", close_on_click))

                    # Toggle tooltip on click
                    widget.bind("<Button-1>", toggle_tooltip)

                create_tooltip(info_label, tooltip_text)

    # ==================== CLIENTS TAB ====================

    def init_clients_tab(self):
        """Initialize the clients management tab."""
        self.tab_clients.grid_columnconfigure(0, weight=1)
        self.tab_clients.grid_columnconfigure(1, weight=2)
        self.tab_clients.grid_rowconfigure(1, weight=1)

        # Left side - Client list
        left_frame = ctk.CTkFrame(self.tab_clients)
        left_frame.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(10, 5), pady=10)
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(2, weight=1)

        list_header = ctk.CTkLabel(
            left_frame,
            text="Client List",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        list_header.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))

        # Show inactive clients checkbox
        self.show_inactive_var = tk.BooleanVar(value=False)
        inactive_check = ctk.CTkCheckBox(
            left_frame,
            text="Show Inactive Clients",
            variable=self.show_inactive_var,
            command=self.refresh_clients_list,
            font=ctk.CTkFont(size=11)
        )
        inactive_check.grid(row=1, column=0, sticky="w", padx=12, pady=3)

        # Client list with button-style items
        self.clients_scroll_frame = ctk.CTkScrollableFrame(left_frame)
        self.clients_scroll_frame.grid(row=2, column=0, sticky="nsew", padx=8, pady=(3, 8))
        self.clients_scroll_frame.grid_columnconfigure(0, weight=1)

        # Increase scroll speed
        self.clients_scroll_frame._parent_canvas.configure(yscrollincrement=20)

        # Track selected client button
        self.selected_client_button = None
        self.client_buttons = []

        # Add client button
        add_btn = ctk.CTkButton(
            left_frame,
            text="+ Add New Client",
            command=self.add_new_client,
            font=ctk.CTkFont(size=12),
            height=35
        )
        add_btn.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))

        # Right side - Client details and materials
        right_frame = ctk.CTkFrame(self.tab_clients)
        right_frame.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(5, 10), pady=10)
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(1, weight=1)

        details_header = ctk.CTkLabel(
            right_frame,
            text="Client Details",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        details_header.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 8))

        # Scrollable frame for client details
        self.client_details_frame = ctk.CTkScrollableFrame(right_frame)
        self.client_details_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        self.client_details_frame.grid_columnconfigure(1, weight=1)

        # Initially show "Select a client" message
        self.show_client_placeholder()

    def show_client_placeholder(self):
        """Show placeholder message when no client is selected."""
        for widget in self.client_details_frame.winfo_children():
            widget.destroy()

        placeholder = ctk.CTkLabel(
            self.client_details_frame,
            text="← Select a client to view details",
            font=ctk.CTkFont(size=16),
            text_color="gray"
        )
        placeholder.grid(row=0, column=0, pady=50)

    def refresh_clients_list(self):
        """Refresh the clients list with button-style items."""
        # Clear existing buttons
        for widget in self.clients_scroll_frame.winfo_children():
            widget.destroy()

        self.client_buttons = []
        self.selected_client_button = None

        active_only = not self.show_inactive_var.get()
        clients = self.db.get_all_clients(active_only=active_only)

        # Store client IDs for reference
        self.client_ids = [c['id'] for c in clients]

        # Create button for each client
        for idx, client in enumerate(clients):
            display_name = client['name']
            if not client['is_active']:
                display_name += " (Inactive)"

            def create_click_handler(client_id, button):
                def handler():
                    self.on_client_button_click(client_id, button)
                return handler

            btn = ctk.CTkButton(
                self.clients_scroll_frame,
                text=display_name,
                font=ctk.CTkFont(size=17),
                height=51,
                corner_radius=8,
                fg_color="#3a3a3a",
                hover_color="#4a4a4a",
                text_color="white",
                anchor="w",
                border_width=0
            )
            btn.grid(row=idx, column=0, sticky="ew", padx=5, pady=4)

            # Store reference and set click handler
            self.client_buttons.append(btn)
            btn.configure(command=create_click_handler(client['id'], btn))

    def on_client_button_click(self, client_id, button):
        """Handle client button click."""
        # Reset previous selection
        if self.selected_client_button:
            self.selected_client_button.configure(
                fg_color="#3a3a3a",
                border_width=0
            )

        # Make selected button appear pressed with darker color and inner border
        button.configure(
            fg_color="#154a78",
            border_width=2,
            border_color="#0d3552"
        )
        self.selected_client_button = button

        # Show client details
        self.show_client_details(client_id)
        self.current_client_id = client_id

    def show_client_details(self, client_id: int):
        """Display detailed information for a selected client."""
        # Clear existing widgets
        for widget in self.client_details_frame.winfo_children():
            widget.destroy()

        client = self.db.get_client(client_id)
        if not client:
            return

        row = 0

        # Client information form
        fields = [
            ("Name:", "name"),
            ("Email:", "email"),
            ("Phone:", "phone"),
            ("Address:", "address"),
            ("Monthly Charge ($):", "monthly_charge"),
            ("Notes:", "notes"),
        ]

        self.client_entries = {}

        for label_text, field_name in fields:
            label = ctk.CTkLabel(
                self.client_details_frame,
                text=label_text,
                font=ctk.CTkFont(size=14)
            )
            label.grid(row=row, column=0, sticky="w", padx=10, pady=8)

            if field_name == "notes":
                entry = ctk.CTkTextbox(
                    self.client_details_frame,
                    height=80,
                    font=ctk.CTkFont(size=13)
                )
                entry.insert("1.0", client.get(field_name, ""))
            else:
                entry = ctk.CTkEntry(
                    self.client_details_frame,
                    font=ctk.CTkFont(size=13),
                    height=35
                )
                entry.insert(0, str(client.get(field_name, "")))

            entry.grid(row=row, column=1, sticky="ew", padx=10, pady=8)
            self.client_entries[field_name] = entry
            row += 1

        # Buttons row
        btn_frame = ctk.CTkFrame(self.client_details_frame, fg_color="transparent")
        btn_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=15)
        row += 1

        save_btn = ctk.CTkButton(
            btn_frame,
            text="Save Changes",
            command=lambda: self.save_client_changes(client_id),
            font=ctk.CTkFont(size=14),
            height=40,
            fg_color="green"
        )
        save_btn.pack(side=tk.LEFT, padx=5)

        if client['is_active']:
            deactivate_btn = ctk.CTkButton(
                btn_frame,
                text="Deactivate Client",
                command=lambda: self.deactivate_client(client_id),
                font=ctk.CTkFont(size=14),
                height=40,
                fg_color="orange"
            )
            deactivate_btn.pack(side=tk.LEFT, padx=5)
        else:
            activate_btn = ctk.CTkButton(
                btn_frame,
                text="Reactivate Client",
                command=lambda: self.activate_client(client_id),
                font=ctk.CTkFont(size=14),
                height=40,
                fg_color="blue"
            )
            activate_btn.pack(side=tk.LEFT, padx=5)

        delete_btn = ctk.CTkButton(
            btn_frame,
            text="Delete Permanently",
            command=lambda: self.delete_client(client_id),
            font=ctk.CTkFont(size=14),
            height=40,
            fg_color="red"
        )
        delete_btn.pack(side=tk.LEFT, padx=5)

        # Client materials section
        materials_header = ctk.CTkLabel(
            self.client_details_frame,
            text="Materials & Services for this Client",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        materials_header.grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=(20, 5))
        row += 1

        # Create materials table frame
        self.materials_table_frame = ctk.CTkFrame(self.client_details_frame)
        self.materials_table_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        self.materials_table_frame.grid_columnconfigure(0, weight=2)  # Material name
        self.materials_table_frame.grid_columnconfigure(1, weight=1)  # Cost
        self.materials_table_frame.grid_columnconfigure(2, weight=1)  # Unit
        self.materials_table_frame.grid_columnconfigure(3, weight=1)  # Total
        self.materials_table_frame.grid_columnconfigure(4, weight=0)  # Delete checkbox

        # Store material table data
        self.current_client_id = client_id
        self.material_rows = []
        self.materials_have_changes = False
        self.num_empty_rows = 1

        # Get data
        client_materials = self.db.get_client_materials(client_id)
        self.all_materials = self.db.get_all_materials()

        # Build the table
        self.rebuild_materials_table(client_materials, num_empty_rows=1)

        row += 1

    def rebuild_materials_table(self, existing_materials, num_empty_rows=1):
        """Build or rebuild the materials table."""
        # Clear existing widgets
        for widget in self.materials_table_frame.winfo_children():
            widget.destroy()

        self.material_rows = []
        self.num_empty_rows = num_empty_rows
        current_row = 0

        # Table headers
        headers = ["Material/Service", "Cost ($)", "Unit", "Total", "Delete"]
        for col, header_text in enumerate(headers):
            header = ctk.CTkLabel(
                self.materials_table_frame,
                text=header_text,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="gray"
            )
            header.grid(row=current_row, column=col, padx=5, pady=3, sticky="w")
        current_row += 1

        # Calculate total cost from materials
        total_materials_cost = 0
        for mat in existing_materials:
            # Use total_cost from database query (effective_cost * multiplier)
            total_materials_cost += mat.get('total_cost', 0)

        # Add existing materials
        for mat in existing_materials:
            self.add_material_row_to_table(current_row, mat)
            current_row += 1

        # Add empty rows for new materials
        for i in range(num_empty_rows):
            self.add_material_row_to_table(current_row, None)
            current_row += 1

        # Show total cost
        total_frame = ctk.CTkFrame(self.materials_table_frame, fg_color="transparent")
        total_frame.grid(row=current_row, column=0, columnspan=5, sticky="ew", padx=5, pady=10)

        total_label = ctk.CTkLabel(
            total_frame,
            text="Total Materials & Services Cost:",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        total_label.pack(side=tk.LEFT, padx=5)

        total_value = ctk.CTkLabel(
            total_frame,
            text=f"${total_materials_cost:.2f}",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#4CAF50"
        )
        total_value.pack(side=tk.LEFT, padx=5)
        current_row += 1

        # Add row button
        add_row_btn = ctk.CTkButton(
            self.materials_table_frame,
            text="+ Add Another Row",
            command=self.add_another_material_row,
            font=ctk.CTkFont(size=11),
            height=28,
            fg_color="transparent",
            hover_color="#3a3a3a"
        )
        add_row_btn.grid(row=current_row, column=0, columnspan=5, sticky="w", padx=5, pady=5)
        current_row += 1

        # Save button (initially disabled)
        self.materials_save_btn = ctk.CTkButton(
            self.materials_table_frame,
            text="Save Changes",
            command=self.save_all_material_changes,
            font=ctk.CTkFont(size=12, weight="bold"),
            height=35,
            fg_color="gray",
            hover_color="gray",
            state="disabled"
        )
        self.materials_save_btn.grid(row=current_row, column=0, columnspan=5, sticky="ew", padx=5, pady=10)

    def add_material_row_to_table(self, row_num, existing_material=None):
        """Add a single row to the materials table."""
        # Get materials not already assigned
        assigned_material_ids = {row['existing']['material_id'] for row in self.material_rows if row['existing']}
        available_materials = [m for m in self.all_materials if m['id'] not in assigned_material_ids or (existing_material and m['id'] == existing_material['material_id'])]

        if not available_materials and not existing_material:
            return  # No materials to add

        # Material dropdown
        material_names = [m['name'] for m in available_materials]
        selected_material = existing_material['name'] if existing_material else (material_names[0] if material_names else "")

        material_var = tk.StringVar(value=selected_material)
        material_dropdown = ctk.CTkOptionMenu(
            self.materials_table_frame,
            variable=material_var,
            values=material_names if material_names else ["No materials available"],
            font=ctk.CTkFont(size=11),
            height=28,
            dynamic_resizing=False
        )
        material_dropdown.grid(row=row_num, column=0, padx=5, pady=3, sticky="ew")

        # Cost entry
        cost_entry = ctk.CTkEntry(
            self.materials_table_frame,
            placeholder_text="Auto",
            font=ctk.CTkFont(size=11),
            height=28
        )
        cost_entry.grid(row=row_num, column=1, padx=5, pady=3, sticky="ew")

        if existing_material and existing_material.get('custom_cost'):
            cost_entry.insert(0, str(existing_material['custom_cost']))

        # Unit entry
        unit_entry = ctk.CTkEntry(
            self.materials_table_frame,
            placeholder_text="1",
            font=ctk.CTkFont(size=11),
            height=28,
            width=60
        )
        unit_entry.grid(row=row_num, column=2, padx=5, pady=3, sticky="ew")

        if existing_material:
            unit_entry.insert(0, str(existing_material.get('multiplier', 1)))

        # Total label (cost × unit)
        total_var = tk.StringVar(value="$0.00")
        total_label = ctk.CTkLabel(
            self.materials_table_frame,
            textvariable=total_var,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#4CAF50"
        )
        total_label.grid(row=row_num, column=3, padx=5, pady=3, sticky="w")

        # Calculate initial total if existing material
        if existing_material:
            total_var.set(f"${existing_material.get('total_cost', 0):.2f}")

        # Delete checkbox
        delete_var = tk.BooleanVar(value=False)
        delete_check = ctk.CTkCheckBox(
            self.materials_table_frame,
            text="",
            variable=delete_var,
            width=28,
            command=self.on_material_change
        )
        delete_check.grid(row=row_num, column=4, padx=5, pady=3)

        # Function to update total label
        def update_total_label(*args):
            # Get the effective cost
            selected_name = material_var.get()
            selected_mat = next((m for m in self.all_materials if m['name'] == selected_name), None)

            cost_str = cost_entry.get().strip()
            if cost_str and cost_str != "Auto":
                try:
                    cost = float(cost_str)
                except ValueError:
                    cost = 0
            elif selected_mat:
                cost = selected_mat['default_cost']
            else:
                cost = 0

            # Get the unit
            unit_str = unit_entry.get().strip()
            try:
                unit = float(unit_str) if unit_str else 1.0
            except ValueError:
                unit = 1.0

            # Calculate and display total
            total = cost * unit
            total_var.set(f"${total:.2f}")

        # Auto-update cost when material selection changes
        def on_material_dropdown_change(*args):
            selected_name = material_var.get()
            selected_mat = next((m for m in self.all_materials if m['name'] == selected_name), None)
            if selected_mat:
                current_cost = cost_entry.get().strip()
                if not current_cost or current_cost == "Auto":
                    cost_entry.delete(0, tk.END)
                    cost_entry.configure(placeholder_text=f"{selected_mat['default_cost']:.2f}")
            update_total_label()
            self.on_material_change()

        material_var.trace('w', on_material_dropdown_change)
        on_material_dropdown_change()  # Set initial placeholder

        # Bind change detection to entries
        def on_entry_change(e):
            update_total_label()
            self.on_material_change()

        cost_entry.bind('<KeyRelease>', on_entry_change)
        unit_entry.bind('<KeyRelease>', on_entry_change)

        # Store row reference
        row_data = {
            'row_num': row_num,
            'material_var': material_var,
            'cost_entry': cost_entry,
            'unit_entry': unit_entry,
            'delete_var': delete_var,
            'total_var': total_var,
            'existing': existing_material,
            'widgets': [material_dropdown, cost_entry, unit_entry, total_label, delete_check]
        }
        self.material_rows.append(row_data)

    def on_material_change(self):
        """Detect if there are any changes in the materials table."""
        # Check if save button exists yet (it's created after rows)
        if not hasattr(self, 'materials_save_btn') or self.materials_save_btn is None:
            return

        has_changes = False

        # Get current state from database
        db_materials = self.db.get_client_materials(self.current_client_id)
        db_material_map = {m['material_id']: m for m in db_materials}

        for row in self.material_rows:
            # Check if this is a new row (no existing material)
            if not row['existing']:
                # Check if user has entered or selected anything meaningful
                selected_name = row['material_var'].get()
                cost_str = row['cost_entry'].get().strip()
                unit_str = row['unit_entry'].get().strip()

                # Has changes if: cost entered, unit entered, or material changed from initial
                if cost_str or unit_str:
                    has_changes = True
                    break
            else:
                # Check if marked for deletion
                if row['delete_var'].get():
                    has_changes = True
                    break

                # Check if values changed
                material_id = row['existing']['material_id']
                if material_id in db_material_map:
                    db_mat = db_material_map[material_id]

                    # Check cost
                    cost_str = row['cost_entry'].get().strip()
                    current_cost = None
                    if cost_str:
                        try:
                            current_cost = float(cost_str)
                        except ValueError:
                            pass

                    db_cost = db_mat.get('custom_cost')
                    if current_cost != db_cost:
                        has_changes = True
                        break

                    # Check unit
                    unit_str = row['unit_entry'].get().strip()
                    current_unit = 1.0
                    if unit_str:
                        try:
                            current_unit = float(unit_str)
                        except ValueError:
                            pass

                    db_unit = db_mat.get('multiplier', 1.0)
                    if abs(current_unit - db_unit) > 0.001:
                        has_changes = True
                        break

        # Update save button state
        try:
            if has_changes:
                self.materials_save_btn.configure(
                    fg_color="green",
                    hover_color="#00AA00",
                    state="normal"
                )
            else:
                self.materials_save_btn.configure(
                    fg_color="gray",
                    hover_color="gray",
                    state="disabled"
                )
        except:
            pass  # Button may not exist yet during construction

    def add_another_material_row(self):
        """Add another empty row to the materials table."""
        # Simply increment the counter and add one more row without rebuilding everything
        self.num_empty_rows += 1

        # Find the next row number (before the buttons)
        next_row = len(self.material_rows) + 1  # +1 for header

        # Remove the total frame, add button and save button from grid temporarily
        total_frame = None
        add_btn = None
        save_btn = None
        for widget in self.materials_table_frame.winfo_children():
            if isinstance(widget, ctk.CTkFrame) and widget.cget("fg_color") == "transparent":
                # This is likely the total frame
                total_frame = widget
                widget.grid_forget()
            elif isinstance(widget, ctk.CTkButton):
                text = widget.cget("text")
                if "Add Another Row" in text:
                    add_btn = widget
                    widget.grid_forget()
                elif "Save Changes" in text:
                    save_btn = widget
                    widget.grid_forget()

        # Add the new empty row
        self.add_material_row_to_table(next_row, None)

        # Re-grid the widgets
        next_row += 1
        if total_frame:
            total_frame.grid(row=next_row, column=0, columnspan=5, sticky="ew", padx=5, pady=10)
        next_row += 1
        if add_btn:
            add_btn.grid(row=next_row, column=0, columnspan=5, sticky="w", padx=5, pady=5)
        next_row += 1
        if save_btn:
            save_btn.grid(row=next_row, column=0, columnspan=5, sticky="ew", padx=5, pady=10)

    def save_all_material_changes(self):
        """Save all changes in the materials table."""
        client_id = self.current_client_id

        try:
            # Process deletions first
            for row in self.material_rows:
                if row['existing'] and row['delete_var'].get():
                    self.db.remove_client_material(client_id, row['existing']['material_id'])

            # Process updates and additions
            for row in self.material_rows:
                # Skip deleted rows
                if row['delete_var'].get():
                    continue

                selected_name = row['material_var'].get()
                if not selected_name or selected_name == "No materials available":
                    continue

                # Get the material
                selected_material = next((m for m in self.all_materials if m['name'] == selected_name), None)
                if not selected_material:
                    continue

                # Get cost
                cost_str = row['cost_entry'].get().strip()
                custom_cost = None
                if cost_str and cost_str != "Auto":
                    try:
                        custom_cost = float(cost_str)
                    except ValueError:
                        messagebox.showerror("Error", f"Invalid cost value for {selected_name}")
                        return

                # Get unit/multiplier
                unit_str = row['unit_entry'].get().strip()
                try:
                    multiplier = float(unit_str) if unit_str else 1.0
                    if multiplier <= 0:
                        messagebox.showerror("Error", f"Unit must be greater than 0 for {selected_name}")
                        return
                except ValueError:
                    messagebox.showerror("Error", f"Invalid unit value for {selected_name}")
                    return

                # Add or update
                if row['existing']:
                    # Update existing
                    self.db.remove_client_material(client_id, row['existing']['material_id'])
                    self.db.add_client_material(client_id, selected_material['id'], custom_cost, multiplier)
                else:
                    # Add new
                    self.db.add_client_material(client_id, selected_material['id'], custom_cost, multiplier)

            # Refresh the view
            self.show_client_details(client_id)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save changes: {str(e)}")

    def add_new_client(self):
        """Open dialog to add a new client."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Add New Client")
        dialog.geometry("500x600")
        dialog.transient(self)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (dialog.winfo_screenheight() // 2) - (600 // 2)
        dialog.geometry(f"500x600+{x}+{y}")

        fields = [
            ("Name *:", "name"),
            ("Email:", "email"),
            ("Phone:", "phone"),
            ("Address:", "address"),
            ("Monthly Charge ($) *:", "monthly_charge"),
            ("Notes:", "notes"),
        ]

        entries = {}
        row = 0

        header = ctk.CTkLabel(
            dialog,
            text="New Client Information",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        header.grid(row=row, column=0, columnspan=2, pady=20)
        row += 1

        for label_text, field_name in fields:
            label = ctk.CTkLabel(dialog, text=label_text, font=ctk.CTkFont(size=14))
            label.grid(row=row, column=0, sticky="w", padx=20, pady=8)

            if field_name == "notes":
                entry = ctk.CTkTextbox(dialog, height=80, font=ctk.CTkFont(size=13))
            else:
                entry = ctk.CTkEntry(dialog, font=ctk.CTkFont(size=13), height=35)

            entry.grid(row=row, column=1, sticky="ew", padx=20, pady=8)
            entries[field_name] = entry
            row += 1

        dialog.grid_columnconfigure(1, weight=1)

        def save_new_client():
            name = entries['name'].get().strip()
            monthly_charge = entries['monthly_charge'].get().strip()

            if not name:
                messagebox.showerror("Error", "Client name is required")
                return

            try:
                monthly_charge = float(monthly_charge) if monthly_charge else 0.0
            except ValueError:
                messagebox.showerror("Error", "Monthly charge must be a number")
                return

            notes_text = entries['notes'].get("1.0", "end-1c") if 'notes' in entries else ""

            client_id = self.db.add_client(
                name=name,
                email=entries['email'].get().strip(),
                phone=entries['phone'].get().strip(),
                address=entries['address'].get().strip(),
                monthly_charge=monthly_charge,
                notes=notes_text
            )

            messagebox.showinfo("Success", f"Client '{name}' added successfully!")
            dialog.destroy()
            self.refresh_clients_list()
            self.refresh_dashboard()

        save_btn = ctk.CTkButton(
            dialog,
            text="Save Client",
            command=save_new_client,
            font=ctk.CTkFont(size=16),
            height=45,
            fg_color="green"
        )
        save_btn.grid(row=row, column=0, columnspan=2, sticky="ew", padx=20, pady=20)

    def save_client_changes(self, client_id: int):
        """Save changes to client information."""
        try:
            updates = {}
            for field, entry in self.client_entries.items():
                if field == "notes":
                    updates[field] = entry.get("1.0", "end-1c")
                elif field == "monthly_charge":
                    updates[field] = float(entry.get())
                else:
                    updates[field] = entry.get().strip()

            self.db.update_client(client_id, **updates)
            messagebox.showinfo("Success", "Client updated successfully!")
            self.refresh_clients_list()
            self.refresh_dashboard()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update client: {str(e)}")

    def deactivate_client(self, client_id: int):
        """Deactivate a client."""
        if messagebox.askyesno("Confirm", "Deactivate this client? They will be hidden from active views."):
            self.db.deactivate_client(client_id)
            messagebox.showinfo("Success", "Client deactivated")
            self.refresh_clients_list()
            self.refresh_dashboard()
            self.show_client_placeholder()

    def activate_client(self, client_id: int):
        """Reactivate an inactive client."""
        self.db.activate_client(client_id)
        messagebox.showinfo("Success", "Client reactivated")
        self.refresh_clients_list()
        self.refresh_dashboard()
        self.show_client_details(client_id)

    def delete_client(self, client_id: int):
        """Permanently delete a client."""
        if messagebox.askyesno(
            "Confirm Delete",
            "PERMANENTLY delete this client and all related data? This cannot be undone!"
        ):
            self.db.delete_client(client_id)
            messagebox.showinfo("Success", "Client deleted permanently")
            self.refresh_clients_list()
            self.refresh_dashboard()
            self.show_client_placeholder()

    def add_material_to_client(self, client_id: int):
        """Open dialog to add a material/service to a client."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Add Material/Service to Client")
        dialog.geometry("550x550")
        dialog.transient(self)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (550 // 2)
        y = (dialog.winfo_screenheight() // 2) - (550 // 2)
        dialog.geometry(f"550x550+{x}+{y}")

        header = ctk.CTkLabel(
            dialog,
            text="Select Material/Service",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        header.pack(pady=15)

        # Get available materials
        all_materials = self.db.get_all_materials()
        client_materials = self.db.get_client_materials(client_id)
        client_material_ids = {m['material_id'] for m in client_materials}

        # Filter out already assigned materials
        available_materials = [m for m in all_materials if m['id'] not in client_material_ids]

        if not available_materials:
            msg = ctk.CTkLabel(
                dialog,
                text="All materials are already assigned to this client.\nAdd new materials in the Materials tab first.",
                font=ctk.CTkFont(size=14)
            )
            msg.pack(pady=50)
            return

        # Scrollable frame for content
        scroll_frame = ctk.CTkScrollableFrame(dialog, height=350)
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # Material selection
        material_label = ctk.CTkLabel(scroll_frame, text="Material:", font=ctk.CTkFont(size=14))
        material_label.pack(pady=(20, 5))

        material_var = tk.StringVar(value=available_materials[0]['name'])
        material_menu = ctk.CTkOptionMenu(
            scroll_frame,
            values=[m['name'] for m in available_materials],
            variable=material_var,
            font=ctk.CTkFont(size=13),
            height=35
        )
        material_menu.pack(pady=5, padx=20, fill="x")

        # Custom cost option (only for global materials)
        custom_cost_var = tk.BooleanVar(value=False)
        custom_check = ctk.CTkCheckBox(
            scroll_frame,
            text="Use custom cost for this client",
            variable=custom_cost_var,
            font=ctk.CTkFont(size=13)
        )

        cost_label = ctk.CTkLabel(scroll_frame, text="Cost:", font=ctk.CTkFont(size=14))
        cost_entry = ctk.CTkEntry(scroll_frame, placeholder_text="Cost", height=35)

        def update_cost_ui(*args):
            """Update cost UI based on selected material."""
            selected_name = material_var.get()
            selected_material = next(m for m in available_materials if m['name'] == selected_name)

            # Clear existing cost widgets
            for widget in scroll_frame.winfo_children():
                if widget in [custom_check, cost_label, cost_entry]:
                    widget.pack_forget()

            if selected_material['is_global']:
                # Global material - show checkbox to enable custom cost
                custom_check.pack(pady=10)
                cost_entry.pack(pady=5, padx=20, fill="x")
                if not custom_cost_var.get():
                    cost_entry.configure(state="disabled")
                    cost_entry.delete(0, tk.END)
                else:
                    cost_entry.configure(state="normal")
            else:
                # Non-global material - always show cost entry (no checkbox needed)
                cost_label.pack(pady=(10, 5))
                cost_entry.configure(state="normal")
                cost_entry.delete(0, tk.END)
                cost_entry.insert(0, str(selected_material.get('default_cost', '0.00')))
                cost_entry.pack(pady=5, padx=20, fill="x")

        def toggle_cost_entry():
            if custom_cost_var.get():
                cost_entry.configure(state="normal")
            else:
                cost_entry.configure(state="disabled")
                cost_entry.delete(0, tk.END)

        custom_check.configure(command=toggle_cost_entry)
        material_var.trace('w', update_cost_ui)

        # Initial UI setup
        update_cost_ui()

        # Unit option
        multiplier_label = ctk.CTkLabel(
            scroll_frame,
            text="Unit (how many times this material is applied):",
            font=ctk.CTkFont(size=12)
        )
        multiplier_label.pack(pady=(15, 5))

        multiplier_entry = ctk.CTkEntry(
            scroll_frame,
            placeholder_text="Default: 1",
            height=35
        )
        multiplier_entry.insert(0, "1")
        multiplier_entry.pack(pady=5, padx=20, fill="x")

        help_label = ctk.CTkLabel(
            scroll_frame,
            text="Example: Fertilizer applied 3 times → enter 3",
            font=ctk.CTkFont(size=10),
            text_color="gray"
        )
        help_label.pack(pady=(0, 10))

        def save_material():
            selected_name = material_var.get()
            selected_material = next(m for m in available_materials if m['name'] == selected_name)

            custom_cost = None

            # For non-global materials, cost is always required
            if not selected_material['is_global']:
                cost_str = cost_entry.get().strip()
                if not cost_str:
                    messagebox.showerror("Error", "Cost is required for non-global materials")
                    return
                try:
                    custom_cost = float(cost_str)
                except ValueError:
                    messagebox.showerror("Error", "Cost must be a valid number")
                    return
            # For global materials, only use custom cost if checkbox is checked
            elif custom_cost_var.get():
                try:
                    custom_cost = float(cost_entry.get())
                except ValueError:
                    messagebox.showerror("Error", "Custom cost must be a valid number")
                    return

            # Get multiplier
            try:
                multiplier = float(multiplier_entry.get())
                if multiplier <= 0:
                    messagebox.showerror("Error", "Unit must be greater than 0")
                    return
            except ValueError:
                messagebox.showerror("Error", "Unit must be a valid number")
                return

            self.db.add_client_material(client_id, selected_material['id'], custom_cost, multiplier)
            messagebox.showinfo("Success", "Material added to client!")
            dialog.destroy()
            self.show_client_details(client_id)

        save_btn = ctk.CTkButton(
            dialog,
            text="Add Material",
            command=save_material,
            font=ctk.CTkFont(size=16),
            height=45,
            fg_color="green"
        )
        save_btn.pack(pady=20, padx=20, fill="x")

    def remove_client_material(self, client_id: int, material_id: int):
        """Remove a material from a client's configuration."""
        if messagebox.askyesno("Confirm", "Remove this material from the client?"):
            self.db.remove_client_material(client_id, material_id)
            messagebox.showinfo("Success", "Material removed")
            self.show_client_details(client_id)

    # ==================== VISITS TAB ====================

    def init_visits_tab(self):
        """Initialize the visits management tab."""
        self.tab_visits.grid_columnconfigure(0, weight=1)
        self.tab_visits.grid_rowconfigure(2, weight=1)

        # Header
        header = ctk.CTkLabel(
            self.tab_visits,
            text="Visit Entry & Management",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        header.grid(row=0, column=0, sticky="w", padx=15, pady=12)

        # Client selection
        client_frame = ctk.CTkFrame(self.tab_visits)
        client_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))

        client_label = ctk.CTkLabel(
            client_frame,
            text="Select Client:",
            font=ctk.CTkFont(size=16)
        )
        client_label.pack(side=tk.LEFT, padx=10, pady=15)

        self.visit_client_var = tk.StringVar(value="Select a client...")
        self.visit_client_menu = ctk.CTkOptionMenu(
            client_frame,
            values=["Select a client..."],
            variable=self.visit_client_var,
            command=self.on_visit_client_select,
            font=ctk.CTkFont(size=14),
            height=40,
            width=300
        )
        self.visit_client_menu.pack(side=tk.LEFT, padx=10, pady=15)

        add_visit_btn = ctk.CTkButton(
            client_frame,
            text="+ Add New Visit",
            command=self.add_new_visit,
            font=ctk.CTkFont(size=14),
            height=40
        )
        add_visit_btn.pack(side=tk.LEFT, padx=10, pady=15)

        # Visits list
        self.visits_scroll = ctk.CTkScrollableFrame(self.tab_visits)
        self.visits_scroll.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.visits_scroll.grid_columnconfigure(0, weight=1)

        # Load clients for dropdown
        self.refresh_visit_client_dropdown()

    def refresh_visit_client_dropdown(self):
        """Refresh the client dropdown in visits tab."""
        clients = self.db.get_all_clients(active_only=True)
        client_names = [c['name'] for c in clients]
        if not client_names:
            client_names = ["No active clients"]

        self.visit_client_menu.configure(values=client_names)
        self.visit_clients_data = {c['name']: c['id'] for c in clients}

    def on_visit_client_select(self, client_name: str):
        """Handle client selection in visits tab."""
        if client_name in self.visit_clients_data:
            client_id = self.visit_clients_data[client_name]
            self.load_client_visits(client_id)

    def load_client_visits(self, client_id: int):
        """Load and display all visits for a client."""
        # Clear existing widgets
        for widget in self.visits_scroll.winfo_children():
            widget.destroy()

        visits = self.db.get_client_visits(client_id)

        if not visits:
            no_visits = ctk.CTkLabel(
                self.visits_scroll,
                text="No visits recorded for this client yet.",
                font=ctk.CTkFont(size=16),
                text_color="gray"
            )
            no_visits.grid(row=0, column=0, pady=50)
            return

        for idx, visit in enumerate(visits):
            self.create_visit_card(self.visits_scroll, visit, idx)

    def create_visit_card(self, parent, visit, row):
        """Create a card displaying visit information."""
        card = ctk.CTkFrame(parent, border_width=2)
        card.grid(row=row, column=0, sticky="ew", padx=8, pady=6)
        card.grid_columnconfigure(1, weight=1)

        # Visit date - format as MM/DD/YYYY
        formatted_date = self.format_date_mdy(visit['visit_date'])
        date_label = ctk.CTkLabel(
            card,
            text=f"📅 {formatted_date}",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        date_label.grid(row=0, column=0, sticky="w", padx=12, pady=8)

        # Time info - format as 12-hour AM/PM
        start_time = self.format_time_12hr(visit['start_time'])
        end_time = self.format_time_12hr(visit['end_time'])
        time_text = f"🕐 {start_time} - {end_time} ({visit['duration_minutes']:.0f} min)"
        time_label = ctk.CTkLabel(
            card,
            text=time_text,
            font=ctk.CTkFont(size=12)
        )
        time_label.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 8))

        # Materials used
        materials = self.db.get_visit_materials(visit['id'])
        if materials:
            materials_frame = ctk.CTkFrame(card, fg_color="transparent")
            materials_frame.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 10))

            mat_header = ctk.CTkLabel(
                materials_frame,
                text="Materials Used:",
                font=ctk.CTkFont(size=13, weight="bold")
            )
            mat_header.pack(anchor="w", pady=(0, 5))

            total_cost = 0
            for mat in materials:
                mat_text = f"  • {mat['name']}: {mat['quantity']} {mat['unit']} @ ${mat['cost_at_time']:.2f}"
                mat_label = ctk.CTkLabel(
                    materials_frame,
                    text=mat_text,
                    font=ctk.CTkFont(size=12)
                )
                mat_label.pack(anchor="w")
                total_cost += mat['quantity'] * mat['cost_at_time']

            cost_label = ctk.CTkLabel(
                materials_frame,
                text=f"Visit Total: ${total_cost:.2f}",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color="green"
            )
            cost_label.pack(anchor="w", pady=(5, 0))

        # Notes
        if visit['notes']:
            notes_label = ctk.CTkLabel(
                card,
                text=f"Notes: {visit['notes']}",
                font=ctk.CTkFont(size=12),
                wraplength=500
            )
            notes_label.grid(row=3, column=0, sticky="w", padx=15, pady=(0, 10))

        # Delete button
        delete_btn = ctk.CTkButton(
            card,
            text="Delete",
            command=lambda: self.delete_visit(visit['id']),
            width=80,
            height=30,
            fg_color="red"
        )
        delete_btn.grid(row=0, column=1, rowspan=2, padx=15, pady=10, sticky="e")

    def add_new_visit(self):
        """Open dialog to add a new visit."""
        client_name = self.visit_client_var.get()
        if client_name not in self.visit_clients_data:
            messagebox.showwarning("No Client", "Please select a client first")
            return

        client_id = self.visit_clients_data[client_name]

        dialog = ctk.CTkToplevel(self)
        dialog.title("Add New Visit")
        dialog.geometry("600x700")
        dialog.transient(self)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (600 // 2)
        y = (dialog.winfo_screenheight() // 2) - (700 // 2)
        dialog.geometry(f"600x700+{x}+{y}")

        header = ctk.CTkLabel(
            dialog,
            text=f"New Visit for {client_name}",
            font=ctk.CTkFont(size=15, weight="bold")
        )
        header.pack(pady=15)

        # Scrollable frame for content
        scroll_frame = ctk.CTkScrollableFrame(dialog, height=550)
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # Date
        date_label = ctk.CTkLabel(scroll_frame, text="Date (MM/DD/YYYY):", font=ctk.CTkFont(size=12))
        date_label.pack(pady=(8, 4))
        date_entry = ctk.CTkEntry(scroll_frame, placeholder_text="01/15/2024", height=32)
        date_entry.insert(0, datetime.now().strftime("%m/%d/%Y"))
        date_entry.pack(pady=4, padx=20, fill="x")

        # Start time
        start_label = ctk.CTkLabel(scroll_frame, text="Start Time (h:MM AM/PM):", font=ctk.CTkFont(size=12))
        start_label.pack(pady=(8, 4))
        start_entry = ctk.CTkEntry(scroll_frame, placeholder_text="9:00 AM", height=32)
        start_entry.pack(pady=4, padx=20, fill="x")

        # End time
        end_label = ctk.CTkLabel(scroll_frame, text="End Time (h:MM AM/PM):", font=ctk.CTkFont(size=12))
        end_label.pack(pady=(8, 4))
        end_entry = ctk.CTkEntry(scroll_frame, placeholder_text="11:30 AM", height=32)
        end_entry.pack(pady=4, padx=20, fill="x")

        # Duration (calculated)
        duration_var = tk.StringVar(value="Duration will be calculated")
        duration_label = ctk.CTkLabel(
            scroll_frame,
            textvariable=duration_var,
            font=ctk.CTkFont(size=13),
            text_color="gray"
        )
        duration_label.pack(pady=5)

        def calculate_duration():
            try:
                # Parse 12-hour AM/PM format
                start_str = start_entry.get().strip()
                end_str = end_entry.get().strip()

                # Try multiple time formats
                for fmt in ['%I:%M %p', '%I:%M%p', '%H:%M']:
                    try:
                        start = datetime.strptime(start_str, fmt)
                        end = datetime.strptime(end_str, fmt)
                        break
                    except:
                        continue
                else:
                    duration_var.set("Invalid time format")
                    return None

                duration = (end - start).total_seconds() / 60
                if duration < 0:
                    duration_var.set("End time must be after start time")
                else:
                    duration_var.set(f"Duration: {duration:.0f} minutes")
                    return duration
            except:
                duration_var.set("Invalid time format")
                return None

        start_entry.bind('<KeyRelease>', lambda e: calculate_duration())
        end_entry.bind('<KeyRelease>', lambda e: calculate_duration())

        # Notes
        notes_label = ctk.CTkLabel(scroll_frame, text="Notes:", font=ctk.CTkFont(size=14))
        notes_label.pack(pady=(10, 5))
        notes_entry = ctk.CTkTextbox(scroll_frame, height=80)
        notes_entry.pack(pady=5, padx=20, fill="x")

        # Materials section
        materials_label = ctk.CTkLabel(
            scroll_frame,
            text="Materials Used (optional):",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        materials_label.pack(pady=(15, 10))

        # Get client materials
        client_materials = self.db.get_client_materials(client_id)
        materials_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        materials_frame.pack(pady=5, padx=20, fill="both")

        material_quantities = {}
        if client_materials:
            for mat in client_materials:
                mat_row = ctk.CTkFrame(materials_frame, fg_color="transparent")
                mat_row.pack(fill="x", pady=5)

                name_lbl = ctk.CTkLabel(
                    mat_row,
                    text=f"{mat['name']} (${mat['effective_cost']:.2f}/{mat['unit']})",
                    font=ctk.CTkFont(size=12)
                )
                name_lbl.pack(side=tk.LEFT, padx=5)

                qty_entry = ctk.CTkEntry(mat_row, placeholder_text="Quantity", width=100)
                qty_entry.pack(side=tk.RIGHT, padx=5)
                material_quantities[mat['material_id']] = {
                    'entry': qty_entry,
                    'cost': mat['effective_cost']
                }
        else:
            no_mat_lbl = ctk.CTkLabel(
                materials_frame,
                text="No materials configured for this client",
                text_color="gray"
            )
            no_mat_lbl.pack(pady=20)

        def save_visit():
            # Validate and save
            date_str = date_entry.get().strip()
            start_str = start_entry.get().strip()
            end_str = end_entry.get().strip()
            duration = calculate_duration()

            if not all([date_str, start_str, end_str]) or duration is None or duration < 0:
                messagebox.showerror("Error", "Please fill in valid date and times")
                return

            # Convert date from MM/DD/YYYY to YYYY-MM-DD for database
            try:
                date_obj = datetime.strptime(date_str, '%m/%d/%Y')
                db_date = date_obj.strftime('%Y-%m-%d')
            except:
                try:
                    # Also accept YYYY-MM-DD
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    db_date = date_str
                except:
                    messagebox.showerror("Error", "Invalid date format. Use MM/DD/YYYY")
                    return

            # Convert times from 12-hour to 24-hour HH:MM for database
            try:
                for fmt in ['%I:%M %p', '%I:%M%p', '%H:%M']:
                    try:
                        start_obj = datetime.strptime(start_str, fmt)
                        end_obj = datetime.strptime(end_str, fmt)
                        db_start = start_obj.strftime('%H:%M')
                        db_end = end_obj.strftime('%H:%M')
                        break
                    except:
                        continue
                else:
                    raise ValueError()
            except:
                messagebox.showerror("Error", "Invalid time format. Use h:MM AM/PM")
                return

            # Add visit
            visit_id = self.db.add_visit(
                client_id=client_id,
                visit_date=db_date,
                start_time=db_start,
                end_time=db_end,
                duration_minutes=duration,
                notes=notes_entry.get("1.0", "end-1c")
            )

            # Add materials
            for mat_id, mat_data in material_quantities.items():
                qty_str = mat_data['entry'].get().strip()
                if qty_str:
                    try:
                        qty = float(qty_str)
                        if qty > 0:
                            self.db.add_visit_material(
                                visit_id=visit_id,
                                material_id=mat_id,
                                quantity=qty,
                                cost_at_time=mat_data['cost']
                            )
                    except ValueError:
                        pass

            messagebox.showinfo("Success", "Visit added successfully!")
            dialog.destroy()
            self.load_client_visits(client_id)
            self.refresh_dashboard()

        save_btn = ctk.CTkButton(
            dialog,
            text="Save Visit",
            command=save_visit,
            font=ctk.CTkFont(size=16),
            height=45,
            fg_color="green"
        )
        save_btn.pack(pady=20, padx=20, fill="x")

    def delete_visit(self, visit_id: int):
        """Delete a visit record."""
        if messagebox.askyesno("Confirm", "Delete this visit record?"):
            self.db.delete_visit(visit_id)
            messagebox.showinfo("Success", "Visit deleted")
            # Reload current client's visits
            client_name = self.visit_client_var.get()
            if client_name in self.visit_clients_data:
                self.load_client_visits(self.visit_clients_data[client_name])
            self.refresh_dashboard()

    # ==================== DAILY SCHEDULE TAB ====================

    def init_daily_schedule_tab(self):
        """Initialize the daily schedule tab with date selector."""
        self.tab_daily.grid_columnconfigure(0, weight=1)
        self.tab_daily.grid_rowconfigure(2, weight=1)

        # Header
        header = ctk.CTkLabel(
            self.tab_daily,
            text="Daily Schedule & Travel Times",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        header.grid(row=0, column=0, sticky="w", padx=15, pady=12)

        # Date selection frame
        date_frame = ctk.CTkFrame(self.tab_daily)
        date_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))

        date_label = ctk.CTkLabel(
            date_frame,
            text="Select Date:",
            font=ctk.CTkFont(size=14)
        )
        date_label.pack(side=tk.LEFT, padx=10, pady=15)

        # Calendar picker (DateEntry widget)
        self.daily_date_picker = DateEntry(
            date_frame,
            width=18,
            background='darkblue',
            foreground='white',
            borderwidth=2,
            font=('Arial', 12),
            date_pattern='mm/dd/yyyy'
        )
        self.daily_date_picker.pack(side=tk.LEFT, padx=10, pady=15)

        # Show button
        show_btn = ctk.CTkButton(
            date_frame,
            text="Show Schedule",
            command=self.load_daily_schedule,
            font=ctk.CTkFont(size=14),
            height=35
        )
        show_btn.pack(side=tk.LEFT, padx=10, pady=15)

        # Navigation buttons
        prev_btn = ctk.CTkButton(
            date_frame,
            text="◀ Previous",
            command=self.go_to_previous_day,
            font=ctk.CTkFont(size=12),
            height=30,
            width=100,
            fg_color="transparent",
            border_width=1
        )
        prev_btn.pack(side=tk.LEFT, padx=5, pady=15)

        next_btn = ctk.CTkButton(
            date_frame,
            text="Next ▶",
            command=self.go_to_next_day,
            font=ctk.CTkFont(size=12),
            height=30,
            width=100,
            fg_color="transparent",
            border_width=1
        )
        next_btn.pack(side=tk.LEFT, padx=5, pady=15)

        # Schedule display frame
        self.daily_schedule_frame = ctk.CTkScrollableFrame(self.tab_daily)
        self.daily_schedule_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.daily_schedule_frame.grid_columnconfigure(0, weight=1)

        # Initial load
        self.load_daily_schedule()

    def go_to_previous_day(self):
        """Navigate to the previous day."""
        current_date = self.daily_date_picker.get_date()
        previous_date = current_date - timedelta(days=1)
        self.daily_date_picker.set_date(previous_date)
        self.load_daily_schedule()

    def go_to_next_day(self):
        """Navigate to the next day."""
        current_date = self.daily_date_picker.get_date()
        next_date = current_date + timedelta(days=1)
        self.daily_date_picker.set_date(next_date)
        self.load_daily_schedule()

    def load_daily_schedule(self):
        """Load and display the schedule for the selected date."""
        # Clear existing widgets
        for widget in self.daily_schedule_frame.winfo_children():
            widget.destroy()

        # Get date from calendar picker
        date_obj = self.daily_date_picker.get_date()
        db_date = date_obj.strftime('%Y-%m-%d')
        date_str = date_obj.strftime('%m/%d/%Y')

        # Get all visits for this date across all clients
        all_visits = []
        clients = self.db.get_all_clients(active_only=True)
        for client in clients:
            visits = self.db.get_client_visits(client['id'])
            for visit in visits:
                if visit['visit_date'] == db_date:
                    visit['client_name'] = client['name']
                    all_visits.append(visit)

        if not all_visits:
            no_visits = ctk.CTkLabel(
                self.daily_schedule_frame,
                text=f"No visits scheduled for {date_str}",
                font=ctk.CTkFont(size=14),
                text_color="gray"
            )
            no_visits.pack(pady=50)
            return

        # Sort visits by start time
        all_visits.sort(key=lambda x: x['start_time'])

        # Display header with summary
        summary_frame = ctk.CTkFrame(self.daily_schedule_frame, fg_color="transparent")
        summary_frame.pack(fill="x", padx=10, pady=(5, 15))

        formatted_date = date_obj.strftime("%A, %B %d, %Y")
        date_header = ctk.CTkLabel(
            summary_frame,
            text=formatted_date,
            font=ctk.CTkFont(size=15, weight="bold")
        )
        date_header.pack(anchor="w", pady=(0, 5))

        # Calculate total work time and travel time
        total_work_minutes = sum(v['duration_minutes'] for v in all_visits)
        total_travel_minutes = 0

        for i in range(len(all_visits) - 1):
            end_time = datetime.strptime(all_visits[i]['end_time'], '%H:%M')
            next_start = datetime.strptime(all_visits[i + 1]['start_time'], '%H:%M')
            gap_minutes = (next_start - end_time).total_seconds() / 60
            if gap_minutes > 0:
                total_travel_minutes += gap_minutes

        summary_text = f"{len(all_visits)} visits • {total_work_minutes:.0f} min work time • {total_travel_minutes:.0f} min travel time"
        summary_label = ctk.CTkLabel(
            summary_frame,
            text=summary_text,
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        summary_label.pack(anchor="w")

        # Display each visit with travel time
        for i, visit in enumerate(all_visits):
            # Visit card
            visit_card = ctk.CTkFrame(self.daily_schedule_frame, border_width=1)
            visit_card.pack(fill="x", padx=10, pady=5)
            visit_card.grid_columnconfigure(1, weight=1)

            # Time indicator
            start_time = self.format_time_12hr(visit['start_time'])
            end_time = self.format_time_12hr(visit['end_time'])
            time_label = ctk.CTkLabel(
                visit_card,
                text=f"{start_time}\n{end_time}",
                font=ctk.CTkFont(size=11),
                width=80,
                text_color="gray"
            )
            time_label.grid(row=0, column=0, padx=10, pady=10, sticky="n")

            # Client and duration info
            info_frame = ctk.CTkFrame(visit_card, fg_color="transparent")
            info_frame.grid(row=0, column=1, sticky="ew", padx=10, pady=10)

            client_label = ctk.CTkLabel(
                info_frame,
                text=visit['client_name'],
                font=ctk.CTkFont(size=14, weight="bold")
            )
            client_label.pack(anchor="w")

            duration_label = ctk.CTkLabel(
                info_frame,
                text=f"Duration: {visit['duration_minutes']:.0f} minutes",
                font=ctk.CTkFont(size=11),
                text_color="gray"
            )
            duration_label.pack(anchor="w")

            if visit.get('notes'):
                notes_label = ctk.CTkLabel(
                    info_frame,
                    text=f"Notes: {visit['notes']}",
                    font=ctk.CTkFont(size=10),
                    text_color="gray",
                    wraplength=400
                )
                notes_label.pack(anchor="w", pady=(3, 0))

            # Show travel time to next visit
            if i < len(all_visits) - 1:
                # Calculate gap
                end_time_obj = datetime.strptime(visit['end_time'], '%H:%M')
                next_start_obj = datetime.strptime(all_visits[i + 1]['start_time'], '%H:%M')
                gap_minutes = (next_start_obj - end_time_obj).total_seconds() / 60

                if gap_minutes > 0:
                    # Travel time indicator
                    travel_frame = ctk.CTkFrame(self.daily_schedule_frame, fg_color="transparent")
                    travel_frame.pack(fill="x", padx=10, pady=2)

                    travel_icon = ctk.CTkLabel(
                        travel_frame,
                        text="🚗",
                        font=ctk.CTkFont(size=14),
                        width=80
                    )
                    travel_icon.pack(side=tk.LEFT, padx=10)

                    travel_label = ctk.CTkLabel(
                        travel_frame,
                        text=f"Travel time: {gap_minutes:.0f} minutes → {all_visits[i + 1]['client_name']}",
                        font=ctk.CTkFont(size=11, weight="bold"),
                        text_color="#7B9EB5"
                    )
                    travel_label.pack(side=tk.LEFT, padx=5)

    # ==================== REVIEW TAB ====================

    def init_review_tab(self):
        """Initialize the review tab for flagged visits and data anomalies."""
        self.tab_review.grid_columnconfigure(0, weight=1)
        self.tab_review.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkLabel(
            self.tab_review,
            text="Data Review - Flagged Visits & Anomalies",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        header.grid(row=0, column=0, sticky="w", padx=15, pady=12)

        # Scrollable frame for issues
        self.review_scroll = ctk.CTkScrollableFrame(self.tab_review)
        self.review_scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.review_scroll.grid_columnconfigure(0, weight=1)

        # Load all issues
        self.refresh_review_list()

    def refresh_review_list(self):
        """Refresh the list of visits needing review and anomalous durations."""
        # Clear existing widgets
        for widget in self.review_scroll.winfo_children():
            widget.destroy()

        flagged_visits = self.db.get_visits_needing_review()
        anomalous_visits = self.db.get_visits_with_anomalous_durations(threshold_percent=300.0)

        # Check if there are any issues
        if not flagged_visits and not anomalous_visits:
            no_issues = ctk.CTkLabel(
                self.review_scroll,
                text="No data issues found!\nAll visits look good.",
                font=ctk.CTkFont(size=16),
                text_color="#5FA777"
            )
            no_issues.grid(row=0, column=0, pady=50)
            return

        current_row = 0

        # Section 1: Anomalous Durations
        if anomalous_visits:
            anomaly_header = ctk.CTkLabel(
                self.review_scroll,
                text=f"⚠ Unusual Visit Durations ({len(anomalous_visits)})",
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color="#C97C7C"
            )
            anomaly_header.grid(row=current_row, column=0, sticky="w", padx=10, pady=(5, 10))
            current_row += 1

            desc_label = ctk.CTkLabel(
                self.review_scroll,
                text="These visits are 3x+ longer than usual for the client (possible time entry errors)",
                font=ctk.CTkFont(size=11),
                text_color="gray"
            )
            desc_label.grid(row=current_row, column=0, sticky="w", padx=10, pady=(0, 10))
            current_row += 1

            for visit in anomalous_visits:
                self.create_anomaly_card(self.review_scroll, visit, current_row)
                current_row += 1

        # Add spacing between sections
        if flagged_visits and anomalous_visits:
            spacer = ctk.CTkFrame(self.review_scroll, height=20, fg_color="transparent")
            spacer.grid(row=current_row, column=0, sticky="ew")
            current_row += 1

        # Section 2: Manually Flagged Visits
        if flagged_visits:
            flagged_header = ctk.CTkLabel(
                self.review_scroll,
                text=f"🚩 Manually Flagged Visits ({len(flagged_visits)})",
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color="orange"
            )
            flagged_header.grid(row=current_row, column=0, sticky="w", padx=10, pady=(5, 10))
            current_row += 1

            for visit in flagged_visits:
                self.create_review_card(self.review_scroll, visit, current_row)
                current_row += 1

    def create_anomaly_card(self, parent, visit, row):
        """Create a card showing a visit with anomalous duration."""
        card = ctk.CTkFrame(parent, border_width=2, border_color="#C97C7C")
        card.grid(row=row, column=0, sticky="ew", padx=10, pady=8)
        card.grid_columnconfigure(1, weight=1)

        # Header with client name and date
        formatted_date = self.format_date_mdy(visit['visit_date'])
        header_label = ctk.CTkLabel(
            card,
            text=f"⚠ {visit['client_name']} - {formatted_date}",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#C97C7C"
        )
        header_label.grid(row=0, column=0, columnspan=4, sticky="w", padx=12, pady=(10, 8))

        # Anomaly explanation
        percent = visit['percent_of_avg']
        avg = visit['avg_duration']
        actual = visit['duration_minutes']

        anomaly_text = f"This visit: {actual:.0f} min  vs  Average: {avg:.0f} min  ({percent:.0f}% of normal)"
        anomaly_label = ctk.CTkLabel(
            card,
            text=anomaly_text,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#C97C7C"
        )
        anomaly_label.grid(row=1, column=0, columnspan=4, sticky="w", padx=12, pady=(0, 8))

        # Visit details
        row_num = 2

        # Times
        start_time = self.format_time_12hr(visit['start_time'])
        end_time = self.format_time_12hr(visit['end_time'])
        times_label = ctk.CTkLabel(
            card,
            text=f"Time: {start_time} - {end_time}",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        times_label.grid(row=row_num, column=0, columnspan=2, sticky="w", padx=12, pady=4)

        # Client visit count
        count_label = ctk.CTkLabel(
            card,
            text=f"Based on {visit['total_visits']} total visits",
            font=ctk.CTkFont(size=10),
            text_color="gray"
        )
        count_label.grid(row=row_num, column=2, columnspan=2, sticky="w", padx=12, pady=4)
        row_num += 1

        # Notes
        if visit.get('notes'):
            notes_label = ctk.CTkLabel(
                card,
                text=f"Notes: {visit['notes']}",
                font=ctk.CTkFont(size=10),
                text_color="gray",
                wraplength=600
            )
            notes_label.grid(row=row_num, column=0, columnspan=4, sticky="w", padx=12, pady=4)
            row_num += 1

        # Action buttons
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.grid(row=row_num, column=0, columnspan=4, sticky="ew", padx=12, pady=(8, 10))

        edit_btn = ctk.CTkButton(
            btn_frame,
            text="Edit Visit",
            command=lambda: self.edit_anomalous_visit(visit),
            font=ctk.CTkFont(size=11),
            height=30,
            fg_color="#5FA777"
        )
        edit_btn.pack(side=tk.LEFT, padx=4)

        ignore_btn = ctk.CTkButton(
            btn_frame,
            text="Looks Correct",
            command=lambda: self.ignore_anomaly(visit['id']),
            font=ctk.CTkFont(size=11),
            height=30,
            fg_color="gray"
        )
        ignore_btn.pack(side=tk.LEFT, padx=4)

        delete_btn = ctk.CTkButton(
            btn_frame,
            text="Delete Visit",
            command=lambda: self.delete_anomalous_visit(visit['id']),
            font=ctk.CTkFont(size=11),
            height=30,
            fg_color="#8B4C4C"
        )
        delete_btn.pack(side=tk.LEFT, padx=4)

    def edit_anomalous_visit(self, visit):
        """Open the Visits tab to edit this visit."""
        # Switch to Visits tab
        self.tabview.set("Visits")
        # The visit editing would happen in the Visits tab

    def ignore_anomaly(self, visit_id):
        """User confirmed the duration is correct, so remove from anomalies."""
        # Just refresh the list - anomalies are calculated on-the-fly
        self.refresh_review_list()

    def delete_anomalous_visit(self, visit_id):
        """Delete a visit with anomalous duration."""
        self.db.delete_visit(visit_id)
        self.refresh_review_list()
        self.refresh_dashboard()

    def create_review_card(self, parent, visit, row):
        """Create a card for editing a flagged visit."""
        card = ctk.CTkFrame(parent, border_width=2, border_color="orange")
        card.grid(row=row, column=0, sticky="ew", padx=10, pady=8)
        card.grid_columnconfigure(1, weight=1)

        # Header with client name and date
        formatted_date = self.format_date_mdy(visit['visit_date'])
        header_label = ctk.CTkLabel(
            card,
            text=f"⚠ {visit['client_name']} - {formatted_date}",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="orange"
        )
        header_label.grid(row=0, column=0, columnspan=4, sticky="w", padx=12, pady=(10, 8))

        # Editable fields
        row_num = 1

        # Date
        date_label = ctk.CTkLabel(card, text="Date:", font=ctk.CTkFont(size=11))
        date_label.grid(row=row_num, column=0, sticky="w", padx=12, pady=4)

        date_entry = ctk.CTkEntry(card, width=150, font=ctk.CTkFont(size=11))
        date_entry.insert(0, self.format_date_mdy(visit['visit_date']))
        date_entry.grid(row=row_num, column=1, sticky="w", padx=8, pady=4)

        # Start time
        start_label = ctk.CTkLabel(card, text="Start:", font=ctk.CTkFont(size=11))
        start_label.grid(row=row_num, column=2, sticky="w", padx=12, pady=4)

        start_entry = ctk.CTkEntry(card, width=120, font=ctk.CTkFont(size=11))
        start_entry.insert(0, self.format_time_12hr(visit['start_time']))
        start_entry.grid(row=row_num, column=3, sticky="w", padx=8, pady=4)
        row_num += 1

        # End time and duration
        end_label = ctk.CTkLabel(card, text="End:", font=ctk.CTkFont(size=11))
        end_label.grid(row=row_num, column=0, sticky="w", padx=12, pady=4)

        end_entry = ctk.CTkEntry(card, width=150, font=ctk.CTkFont(size=11))
        end_entry.insert(0, self.format_time_12hr(visit['end_time']))
        end_entry.grid(row=row_num, column=1, sticky="w", padx=8, pady=4)

        duration_label = ctk.CTkLabel(
            card,
            text=f"Duration: {visit['duration_minutes']:.0f} min",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        duration_label.grid(row=row_num, column=2, columnspan=2, sticky="w", padx=12, pady=4)
        row_num += 1

        # Notes
        if visit.get('notes'):
            notes_label = ctk.CTkLabel(
                card,
                text=f"Notes: {visit['notes']}",
                font=ctk.CTkFont(size=10),
                text_color="gray",
                wraplength=600
            )
            notes_label.grid(row=row_num, column=0, columnspan=4, sticky="w", padx=12, pady=4)
            row_num += 1

        # Buttons
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.grid(row=row_num, column=0, columnspan=4, sticky="ew", padx=12, pady=(8, 10))

        save_btn = ctk.CTkButton(
            btn_frame,
            text="Save & Mark Reviewed",
            command=lambda: self.save_and_mark_reviewed(
                visit['id'], date_entry, start_entry, end_entry
            ),
            font=ctk.CTkFont(size=11),
            height=30,
            fg_color="green"
        )
        save_btn.pack(side=tk.LEFT, padx=4)

        delete_btn = ctk.CTkButton(
            btn_frame,
            text="Delete Visit",
            command=lambda: self.delete_flagged_visit(visit['id']),
            font=ctk.CTkFont(size=11),
            height=30,
            fg_color="red"
        )
        delete_btn.pack(side=tk.LEFT, padx=4)

    def save_and_mark_reviewed(self, visit_id, date_entry, start_entry, end_entry):
        """Save visit changes and mark as reviewed."""
        try:
            date_str = date_entry.get().strip()
            start_str = start_entry.get().strip()
            end_str = end_entry.get().strip()

            # Convert date from MM/DD/YYYY to YYYY-MM-DD
            try:
                date_obj = datetime.strptime(date_str, '%m/%d/%Y')
                db_date = date_obj.strftime('%Y-%m-%d')
            except:
                messagebox.showerror("Error", "Invalid date format. Use MM/DD/YYYY")
                return

            # Convert times from 12-hour to 24-hour
            try:
                for fmt in ['%I:%M %p', '%I:%M%p', '%H:%M']:
                    try:
                        start_obj = datetime.strptime(start_str, fmt)
                        end_obj = datetime.strptime(end_str, fmt)
                        db_start = start_obj.strftime('%H:%M')
                        db_end = end_obj.strftime('%H:%M')
                        break
                    except:
                        continue
                else:
                    raise ValueError()
            except:
                messagebox.showerror("Error", "Invalid time format. Use h:MM AM/PM")
                return

            # Calculate duration
            start = datetime.strptime(db_start, '%H:%M')
            end = datetime.strptime(db_end, '%H:%M')
            duration = (end - start).total_seconds() / 60

            if duration <= 0:
                messagebox.showerror("Error", "End time must be after start time")
                return

            # Update visit
            self.db.update_visit(
                visit_id,
                visit_date=db_date,
                start_time=db_start,
                end_time=db_end,
                duration_minutes=duration,
                needs_review=0
            )

            messagebox.showinfo("Success", "Visit updated and marked as reviewed!")
            self.refresh_review_list()
            self.refresh_dashboard()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update visit: {str(e)}")

    def delete_flagged_visit(self, visit_id):
        """Delete a flagged visit."""
        if messagebox.askyesno("Confirm Delete", "Delete this flagged visit?"):
            self.db.delete_visit(visit_id)
            messagebox.showinfo("Success", "Visit deleted")
            self.refresh_review_list()
            self.refresh_dashboard()

    # ==================== MATERIALS TAB ====================

    def init_materials_tab(self):
        """Initialize the materials/services management tab."""
        self.tab_materials.grid_columnconfigure(0, weight=1)
        self.tab_materials.grid_rowconfigure(2, weight=1)

        # Header
        header = ctk.CTkLabel(
            self.tab_materials,
            text="Materials & Services Catalog",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        header.grid(row=0, column=0, sticky="w", padx=15, pady=12)

        # Description
        desc = ctk.CTkLabel(
            self.tab_materials,
            text="Manage your catalog of materials and services. Global items have default costs,\nwhich can be customized per client in the Clients tab.",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        desc.grid(row=1, column=0, sticky="w", padx=15, pady=(0, 8))

        # Materials list
        self.materials_scroll = ctk.CTkScrollableFrame(self.tab_materials)
        self.materials_scroll.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 10))
        self.materials_scroll.grid_columnconfigure(0, weight=1)

        # Add button
        add_btn = ctk.CTkButton(
            self.tab_materials,
            text="+ Add New Material/Service",
            command=self.add_new_material,
            font=ctk.CTkFont(size=14),
            height=45
        )
        add_btn.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 20))

    def refresh_materials_list(self):
        """Refresh the materials list display."""
        # Clear existing widgets
        for widget in self.materials_scroll.winfo_children():
            widget.destroy()

        materials = self.db.get_all_materials()

        if not materials:
            no_mat = ctk.CTkLabel(
                self.materials_scroll,
                text="No materials added yet. Click 'Add New Material/Service' to get started.",
                font=ctk.CTkFont(size=16),
                text_color="gray"
            )
            no_mat.grid(row=0, column=0, pady=50)
            return

        for idx, mat in enumerate(materials):
            self.create_material_card(self.materials_scroll, mat, idx)

    def create_material_card(self, parent, material, row):
        """Create a card for displaying material information."""
        card = ctk.CTkFrame(parent, border_width=2)
        card.grid(row=row, column=0, sticky="ew", padx=10, pady=10)
        card.grid_columnconfigure(1, weight=1)

        # Name
        name_label = ctk.CTkLabel(
            card,
            text=material['name'],
            font=ctk.CTkFont(size=16, weight="bold")
        )
        name_label.grid(row=0, column=0, sticky="w", padx=15, pady=(15, 5))

        # Cost and unit
        cost_text = f"${material['default_cost']:.2f}"
        if material['unit']:
            cost_text += f" per {material['unit']}"

        if material['is_global']:
            cost_text += " (Global)"
        else:
            cost_text += " (Custom)"

        cost_label = ctk.CTkLabel(
            card,
            text=cost_text,
            font=ctk.CTkFont(size=14)
        )
        cost_label.grid(row=1, column=0, sticky="w", padx=15, pady=(0, 5))

        # Description
        if material['description']:
            desc_label = ctk.CTkLabel(
                card,
                text=material['description'],
                font=ctk.CTkFont(size=12),
                text_color="gray",
                wraplength=500
            )
            desc_label.grid(row=2, column=0, sticky="w", padx=15, pady=(0, 15))

        # Edit button
        edit_btn = ctk.CTkButton(
            card,
            text="Edit",
            command=lambda: self.edit_material(material['id']),
            width=80,
            height=30
        )
        edit_btn.grid(row=0, column=1, padx=10, pady=10, sticky="ne")

        # Delete button
        delete_btn = ctk.CTkButton(
            card,
            text="Delete",
            command=lambda: self.delete_material(material['id']),
            width=80,
            height=30,
            fg_color="red"
        )
        delete_btn.grid(row=1, column=1, padx=10, pady=10, sticky="ne")

    def add_new_material(self):
        """Open dialog to add a new material/service."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Add New Material/Service")
        dialog.geometry("500x600")
        dialog.transient(self)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (dialog.winfo_screenheight() // 2) - (600 // 2)
        dialog.geometry(f"500x600+{x}+{y}")

        header = ctk.CTkLabel(
            dialog,
            text="New Material/Service",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        header.pack(pady=15)

        # Scrollable frame for content
        scroll_frame = ctk.CTkScrollableFrame(dialog, height=400)
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # Name
        name_label = ctk.CTkLabel(scroll_frame, text="Name *:", font=ctk.CTkFont(size=14))
        name_label.pack(pady=(10, 5))
        name_entry = ctk.CTkEntry(scroll_frame, placeholder_text="e.g., Mulch, Fertilizer", height=35)
        name_entry.pack(pady=5, padx=20, fill="x")

        # Default cost
        cost_label = ctk.CTkLabel(scroll_frame, text="Default Cost ($) *:", font=ctk.CTkFont(size=14))
        cost_label.pack(pady=(10, 5))
        cost_entry = ctk.CTkEntry(scroll_frame, placeholder_text="0.00", height=35)
        cost_entry.pack(pady=5, padx=20, fill="x")

        # Multiplier
        unit_label = ctk.CTkLabel(scroll_frame, text="Multiplier:", font=ctk.CTkFont(size=14))
        unit_label.pack(pady=(10, 5))
        unit_entry = ctk.CTkEntry(scroll_frame, placeholder_text="e.g., bag, gallon, service", height=35)
        unit_entry.pack(pady=5, padx=20, fill="x")

        # Type selection (Material or Service)
        type_label = ctk.CTkLabel(scroll_frame, text="Type *:", font=ctk.CTkFont(size=14))
        type_label.pack(pady=(10, 5))

        type_var = tk.StringVar(value="material")
        type_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        type_frame.pack(pady=5)

        material_radio = ctk.CTkRadioButton(
            type_frame,
            text="Material (physical items like fertilizer, mulch)",
            variable=type_var,
            value="material",
            font=ctk.CTkFont(size=12)
        )
        material_radio.pack(side="left", padx=10)

        service_radio = ctk.CTkRadioButton(
            type_frame,
            text="Service (labor/services)",
            variable=type_var,
            value="service",
            font=ctk.CTkFont(size=12)
        )
        service_radio.pack(side="left", padx=10)

        # Is global
        is_global_var = tk.BooleanVar(value=True)
        global_check = ctk.CTkCheckBox(
            scroll_frame,
            text="Global (same cost for all clients by default)",
            variable=is_global_var,
            font=ctk.CTkFont(size=13)
        )
        global_check.pack(pady=15)

        # Description
        desc_label = ctk.CTkLabel(scroll_frame, text="Description:", font=ctk.CTkFont(size=14))
        desc_label.pack(pady=(10, 5))
        desc_entry = ctk.CTkTextbox(scroll_frame, height=80)
        desc_entry.pack(pady=5, padx=20, fill="x")

        def save_material():
            name = name_entry.get().strip()
            cost_str = cost_entry.get().strip()

            if not name:
                messagebox.showerror("Error", "Material name is required")
                return

            try:
                cost = float(cost_str) if cost_str else 0.0
            except ValueError:
                messagebox.showerror("Error", "Cost must be a valid number")
                return

            self.db.add_material(
                name=name,
                default_cost=cost,
                unit=unit_entry.get().strip(),
                is_global=is_global_var.get(),
                description=desc_entry.get("1.0", "end-1c"),
                material_type=type_var.get()
            )

            messagebox.showinfo("Success", "Material/service added successfully!")
            dialog.destroy()
            self.refresh_materials_list()

        save_btn = ctk.CTkButton(
            dialog,
            text="Save Material",
            command=save_material,
            font=ctk.CTkFont(size=16),
            height=45,
            fg_color="green"
        )
        save_btn.pack(pady=20, padx=20, fill="x")

    def edit_material(self, material_id: int):
        """Open dialog to edit a material/service."""
        material = None
        for m in self.db.get_all_materials():
            if m['id'] == material_id:
                material = m
                break

        if not material:
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Edit Material/Service")
        dialog.geometry("500x550")
        dialog.transient(self)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (dialog.winfo_screenheight() // 2) - (550 // 2)
        dialog.geometry(f"500x550+{x}+{y}")

        header = ctk.CTkLabel(
            dialog,
            text="Edit Material/Service",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        header.pack(pady=20)

        # Name
        name_label = ctk.CTkLabel(dialog, text="Name *:", font=ctk.CTkFont(size=14))
        name_label.pack(pady=(10, 5))
        name_entry = ctk.CTkEntry(dialog, height=35)
        name_entry.insert(0, material['name'])
        name_entry.pack(pady=5, padx=20, fill="x")

        # Default cost
        cost_label = ctk.CTkLabel(dialog, text="Default Cost ($) *:", font=ctk.CTkFont(size=14))
        cost_label.pack(pady=(10, 5))
        cost_entry = ctk.CTkEntry(dialog, height=35)
        cost_entry.insert(0, str(material['default_cost']))
        cost_entry.pack(pady=5, padx=20, fill="x")

        # Multiplier
        unit_label = ctk.CTkLabel(dialog, text="Multiplier:", font=ctk.CTkFont(size=14))
        unit_label.pack(pady=(10, 5))
        unit_entry = ctk.CTkEntry(dialog, height=35)
        unit_entry.insert(0, material['unit'] or "")
        unit_entry.pack(pady=5, padx=20, fill="x")

        # Type selection (Material or Service)
        type_label = ctk.CTkLabel(dialog, text="Type *:", font=ctk.CTkFont(size=14))
        type_label.pack(pady=(10, 5))

        type_var = tk.StringVar(value=material.get('material_type', 'material'))
        type_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        type_frame.pack(pady=5)

        material_radio = ctk.CTkRadioButton(
            type_frame,
            text="Material (physical items)",
            variable=type_var,
            value="material",
            font=ctk.CTkFont(size=12)
        )
        material_radio.pack(side="left", padx=10)

        service_radio = ctk.CTkRadioButton(
            type_frame,
            text="Service (labor/services)",
            variable=type_var,
            value="service",
            font=ctk.CTkFont(size=12)
        )
        service_radio.pack(side="left", padx=10)

        # Is global
        is_global_var = tk.BooleanVar(value=bool(material['is_global']))
        global_check = ctk.CTkCheckBox(
            dialog,
            text="Global (same cost for all clients by default)",
            variable=is_global_var,
            font=ctk.CTkFont(size=13)
        )
        global_check.pack(pady=15)

        # Description
        desc_label = ctk.CTkLabel(dialog, text="Description:", font=ctk.CTkFont(size=14))
        desc_label.pack(pady=(10, 5))
        desc_entry = ctk.CTkTextbox(dialog, height=80)
        desc_entry.insert("1.0", material['description'] or "")
        desc_entry.pack(pady=5, padx=20, fill="x")

        def save_changes():
            name = name_entry.get().strip()
            cost_str = cost_entry.get().strip()

            if not name:
                messagebox.showerror("Error", "Material name is required")
                return

            try:
                cost = float(cost_str)
            except ValueError:
                messagebox.showerror("Error", "Cost must be a valid number")
                return

            self.db.update_material(
                material_id,
                name=name,
                default_cost=cost,
                unit=unit_entry.get().strip(),
                is_global=1 if is_global_var.get() else 0,
                description=desc_entry.get("1.0", "end-1c"),
                material_type=type_var.get()
            )

            messagebox.showinfo("Success", "Material/service updated successfully!")
            dialog.destroy()
            self.refresh_materials_list()

        save_btn = ctk.CTkButton(
            dialog,
            text="Save Changes",
            command=save_changes,
            font=ctk.CTkFont(size=16),
            height=45,
            fg_color="green"
        )
        save_btn.pack(pady=20, padx=20, fill="x")

    def delete_material(self, material_id: int):
        """Delete a material/service."""
        if messagebox.askyesno("Confirm Delete", "Delete this material/service from the catalog?"):
            try:
                self.db.delete_material(material_id)
                messagebox.showinfo("Success", "Material deleted")
                self.refresh_materials_list()
            except Exception as e:
                messagebox.showerror("Error", f"Could not delete material: {str(e)}")

    # ==================== IMPORT TAB ====================

    def init_import_tab(self):
        """Initialize the data import tab."""
        self.tab_import.grid_columnconfigure(0, weight=1)

        header = ctk.CTkLabel(
            self.tab_import,
            text="Import Historical Data",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        header.grid(row=0, column=0, sticky="w", padx=15, pady=12)

        desc = ctk.CTkLabel(
            self.tab_import,
            text="Import client and visit data from Excel files.\nComing soon: OCR scanning from paper records.",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        desc.grid(row=1, column=0, sticky="w", padx=15, pady=(0, 15))

        excel_btn = ctk.CTkButton(
            self.tab_import,
            text="📄 Import from Excel",
            command=self.import_from_excel,
            font=ctk.CTkFont(size=16),
            height=50
        )
        excel_btn.grid(row=2, column=0, sticky="ew", padx=50, pady=10)

        template_btn = ctk.CTkButton(
            self.tab_import,
            text="📝 Download Excel Template",
            command=self.download_excel_template,
            font=ctk.CTkFont(size=16),
            height=50,
            fg_color="gray"
        )
        template_btn.grid(row=3, column=0, sticky="ew", padx=50, pady=10)

        ocr_scanner = self.get_ocr_scanner()
        ocr_state = "normal" if ocr_scanner.is_available() else "disabled"
        ocr_text = "📷 Scan Paper Records" if ocr_scanner.is_available() else "📷 Scan Paper Records (Install pytesseract)"

        ocr_btn = ctk.CTkButton(
            self.tab_import,
            text=ocr_text,
            command=self.scan_paper_records,
            font=ctk.CTkFont(size=16),
            height=50,
            state=ocr_state
        )
        ocr_btn.grid(row=4, column=0, sticky="ew", padx=50, pady=10)

        instructions = ctk.CTkTextbox(self.tab_import, height=300)
        instructions.grid(row=5, column=0, sticky="ew", padx=20, pady=20)
        instructions.insert("1.0", """
Excel Import Instructions (To be implemented):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Prepare your Excel file with the following columns:

For Clients Sheet:
- Name (required)
- Email
- Phone
- Address
- Monthly Charge (required)
- Notes

For Visits Sheet:
- Client Name (must match a client)
- Date (YYYY-MM-DD)
- Start Time (HH:MM)
- End Time (HH:MM)
- Notes

OCR Scanning Instructions (To be implemented):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Take clear photos of your paper records
2. Upload images through the scanner
3. Review and correct any OCR errors
4. Save verified data to the database
        """)
        instructions.configure(state="disabled")

    def download_excel_template(self):
        """Generate and download an Excel template."""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialfile="landscaping_template.xlsx"
        )

        if file_path:
            if self.excel_importer.generate_template(file_path):
                messagebox.showinfo(
                    "Success",
                    f"Template saved to:\n{file_path}\n\nFill in your data and use 'Import from Excel' to load it."
                )
            else:
                messagebox.showerror("Error", "Failed to generate template")

    def import_from_excel(self):
        """Import data from Excel file."""
        file_path = filedialog.askopenfilename(
            title="Select Excel file to import",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )

        if not file_path:
            return

        # Show loading dialog
        loading_dialog = ctk.CTkToplevel(self)
        loading_dialog.title("Loading...")
        loading_dialog.geometry("300x100")
        loading_dialog.transient(self)
        loading_dialog.grab_set()

        # Center the dialog
        loading_dialog.update_idletasks()
        x = (loading_dialog.winfo_screenwidth() // 2) - (150)
        y = (loading_dialog.winfo_screenheight() // 2) - (50)
        loading_dialog.geometry(f"300x100+{x}+{y}")

        loading_label = ctk.CTkLabel(
            loading_dialog,
            text="Reading Excel file...\nPlease wait.",
            font=ctk.CTkFont(size=14)
        )
        loading_label.pack(expand=True)

        # Force update to show dialog
        loading_dialog.update()
        self.update()

        # First, preview and validate the data (in a thread-safe way)
        try:
            preview_results = self.excel_importer.preview_import(file_path)
        except Exception as e:
            loading_dialog.destroy()
            messagebox.showerror("Import Failed", f"Error reading file: {str(e)}")
            return

        loading_dialog.destroy()

        if not preview_results['success']:
            messagebox.showerror("Import Failed", preview_results.get('error', 'Unknown error'))
            return

        # If there are errors or warnings, show review dialog
        if preview_results.get('errors') or preview_results.get('warnings'):
            # Show review dialog for user to fix issues
            self.show_excel_review_dialog(file_path, preview_results)
        else:
            # No errors, proceed with import directly
            if messagebox.askyesno(
                "Confirm Import",
                f"Ready to import:\n"
                f"• {len(preview_results.get('clients', []))} clients\n"
                f"• {len(preview_results.get('visits', []))} visits\n\n"
                f"Proceed with import?"
            ):
                self.perform_excel_import(preview_results)

    def show_excel_review_dialog(self, file_path: str, preview_results: dict):
        """Show dialog for reviewing and fixing Excel import issues."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Review Excel Import - Fix Errors")
        dialog.geometry("1000x700")
        dialog.transient(self)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (1000 // 2)
        y = (dialog.winfo_screenheight() // 2) - (700 // 2)
        dialog.geometry(f"1000x700+{x}+{y}")

        # Separate visits into error and valid groups
        visits_with_errors = [v for v in preview_results.get('visits', []) if v.get('has_error')]
        visits_without_errors = [v for v in preview_results.get('visits', []) if not v.get('has_error')]

        error_count = len(visits_with_errors)
        total_visits = len(preview_results.get('visits', []))

        # Header with summary
        header = ctk.CTkLabel(
            dialog,
            text=f"Found {error_count} visits with errors out of {total_visits} total",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="red" if error_count > 0 else "green"
        )
        header.pack(pady=15)

        # Summary of import
        summary_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        summary_frame.pack(pady=(0, 8))

        summary_text = (
            f"Ready to import:\n"
            f"• {len(preview_results.get('clients', []))} clients\n"
            f"• {len(visits_without_errors)} valid visits\n"
            f"• {error_count} visits need review (shown below)"
        )

        summary_label = ctk.CTkLabel(
            summary_frame,
            text=summary_text,
            font=ctk.CTkFont(size=12),
            justify="left"
        )
        summary_label.pack()

        # Instructions
        if error_count > 0:
            instructions = ctk.CTkLabel(
                dialog,
                text="Fix the errors below by editing the date and time fields, then click 'Import Data'.",
                font=ctk.CTkFont(size=11),
                text_color="orange"
            )
            instructions.pack(pady=(0, 8))

        # Scrollable frame for error visits only
        scroll_label = ctk.CTkLabel(
            dialog,
            text="Visits with Errors (fix before importing):" if error_count > 0 else "All visits are valid!",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="red" if error_count > 0 else "green"
        )
        scroll_label.pack(pady=(8, 4))

        visits_scroll = ctk.CTkScrollableFrame(dialog, height=350)
        visits_scroll.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Store editable visit data
        self.editable_visits = []
        self.hidden_visits = visits_without_errors  # Store all valid visits

        # Only show visits with errors
        for idx, visit in enumerate(visits_with_errors):
            visit_frame = ctk.CTkFrame(visits_scroll, border_width=2, border_color="red")
            visit_frame.pack(fill="x", pady=8, padx=5)
            visit_frame.grid_columnconfigure(1, weight=1)

            # Skip checkbox at the top
            skip_var = tk.BooleanVar(value=False)
            skip_check = ctk.CTkCheckBox(
                visit_frame,
                text="Skip this entry (don't import)",
                variable=skip_var,
                font=ctk.CTkFont(size=10),
                text_color="gray"
            )
            skip_check.grid(row=0, column=0, columnspan=2, sticky="e", padx=8, pady=(6, 0))

            # Row number and client name
            header_text = f"Error #{idx+1} - {visit['client_name']}"
            header_label = ctk.CTkLabel(
                visit_frame,
                text=header_text,
                font=ctk.CTkFont(size=12, weight="bold")
            )
            header_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=8, pady=(4, 4))

            # Error message
            error_label = ctk.CTkLabel(
                visit_frame,
                text=f"❌ {visit.get('error_msg', 'Unknown error')}",
                font=ctk.CTkFont(size=11),
                text_color="red",
                wraplength=850
            )
            error_label.grid(row=2, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 8))

            # Editable fields
            row_num = 3

            # Date field - format as MM/DD/YYYY
            date_label = ctk.CTkLabel(visit_frame, text="Date (MM/DD/YYYY):", font=ctk.CTkFont(size=11))
            date_label.grid(row=row_num, column=0, sticky="w", padx=8, pady=4)

            # Format date for display using helper function
            date_val = self.format_date_mdy(str(visit.get('date', '')))

            date_entry = ctk.CTkEntry(visit_frame, width=180, font=ctk.CTkFont(size=11))
            date_entry.insert(0, date_val)
            date_entry.grid(row=row_num, column=1, sticky="w", padx=8, pady=4)
            row_num += 1

            # Start time field - format as 12-hour
            start_label = ctk.CTkLabel(visit_frame, text="Start (h:MM AM/PM):", font=ctk.CTkFont(size=11))
            start_label.grid(row=row_num, column=0, sticky="w", padx=8, pady=4)

            # Format time for display using helper function
            start_val = self.format_time_12hr(str(visit.get('start_time', '')))

            start_entry = ctk.CTkEntry(visit_frame, width=180, font=ctk.CTkFont(size=11))
            start_entry.insert(0, start_val)
            start_entry.grid(row=row_num, column=1, sticky="w", padx=8, pady=4)
            row_num += 1

            # End time field - format as 12-hour
            end_label = ctk.CTkLabel(visit_frame, text="End (h:MM AM/PM):", font=ctk.CTkFont(size=11))
            end_label.grid(row=row_num, column=0, sticky="w", padx=8, pady=4)

            # Format time for display using helper function
            end_val = self.format_time_12hr(str(visit.get('end_time', '')))

            end_entry = ctk.CTkEntry(visit_frame, width=180, font=ctk.CTkFont(size=11))
            end_entry.insert(0, end_val)
            end_entry.grid(row=row_num, column=1, sticky="w", padx=8, pady=4)
            row_num += 1

            # Create validation function for this specific visit
            def create_validator(frame, d_entry, s_entry, e_entry):
                def validate(*args):
                    """Validate the visit data and update border color."""
                    date_str = d_entry.get().strip()
                    start_str = s_entry.get().strip()
                    end_str = e_entry.get().strip()

                    # Validate date
                    date_valid = False
                    try:
                        datetime.strptime(date_str, '%m/%d/%Y')
                        date_valid = True
                    except:
                        try:
                            datetime.strptime(date_str, '%Y-%m-%d')
                            date_valid = True
                        except:
                            pass

                    # Validate times
                    times_valid = False
                    if date_valid:
                        try:
                            for fmt in ['%I:%M %p', '%I:%M%p', '%H:%M']:
                                try:
                                    start_obj = datetime.strptime(start_str, fmt)
                                    end_obj = datetime.strptime(end_str, fmt)
                                    duration = (end_obj - start_obj).total_seconds() / 60
                                    if duration > 0:
                                        times_valid = True
                                        break
                                except:
                                    continue
                        except:
                            pass

                    # Update border color
                    if date_valid and times_valid:
                        frame.configure(border_color="green")
                    else:
                        frame.configure(border_color="red")

                return validate

            # Bind validation to field changes
            validator = create_validator(visit_frame, date_entry, start_entry, end_entry)
            date_entry.bind('<KeyRelease>', validator)
            start_entry.bind('<KeyRelease>', validator)
            end_entry.bind('<KeyRelease>', validator)

            # Store editable fields
            self.editable_visits.append({
                'client_name': visit['client_name'],
                'date_entry': date_entry,
                'start_entry': start_entry,
                'end_entry': end_entry,
                'skip_var': skip_var,
                'frame': visit_frame,
                'notes': visit.get('notes', ''),
                'original_error': True
            })

        # If no errors, show success message
        if error_count == 0:
            success_label = ctk.CTkLabel(
                visits_scroll,
                text="✓ All visits are valid and ready to import!",
                font=ctk.CTkFont(size=16),
                text_color="green"
            )
            success_label.pack(pady=50)

        # Option to import errors as flagged for review
        if error_count > 0:
            options_frame = ctk.CTkFrame(dialog, fg_color="transparent")
            options_frame.pack(fill="x", padx=20, pady=(10, 0))

            self.import_errors_var = tk.BooleanVar(value=False)
            import_errors_check = ctk.CTkCheckBox(
                options_frame,
                text=f"Import error visits anyway and flag for later review ({error_count} visits)",
                variable=self.import_errors_var,
                font=ctk.CTkFont(size=12)
            )
            import_errors_check.pack(anchor="w", pady=5)

        # Buttons
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(10, 20))

        # Import button
        proceed_btn = ctk.CTkButton(
            btn_frame,
            text=f"Import Data ({len(preview_results.get('clients', []))} clients, {total_visits} visits)",
            command=lambda: self.confirm_and_import(dialog, preview_results),
            font=ctk.CTkFont(size=14),
            height=40,
            fg_color="green"
        )
        proceed_btn.pack(side=tk.LEFT, padx=5)

        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            command=dialog.destroy,
            font=ctk.CTkFont(size=14),
            height=40,
            fg_color="gray"
        )
        cancel_btn.pack(side=tk.LEFT, padx=5)

    def confirm_and_import(self, dialog, preview_results):
        """Confirm and perform the actual import using edited data."""
        # Validate and collect edited visit data
        validated_visits = []
        validation_errors = []
        skipped_count = 0

        for idx, visit_data in enumerate(self.editable_visits):
            # Skip this visit if the skip checkbox is checked
            if visit_data.get('skip_var') and visit_data['skip_var'].get():
                skipped_count += 1
                continue

            try:
                date_str = visit_data['date_entry'].get().strip()
                start_str = visit_data['start_entry'].get().strip()
                end_str = visit_data['end_entry'].get().strip()

                # Validate and convert date format from MM/DD/YYYY to YYYY-MM-DD
                try:
                    date_obj = datetime.strptime(date_str, '%m/%d/%Y')
                    date_str = date_obj.strftime('%Y-%m-%d')
                except ValueError:
                    # Try other formats
                    try:
                        from dateutil import parser
                        parsed_date = parser.parse(date_str)
                        date_str = parsed_date.strftime('%Y-%m-%d')
                    except:
                        validation_errors.append(f"Visit #{idx+1} ({visit_data['client_name']}): Invalid date format (use MM/DD/YYYY)")
                        continue

                # Validate and convert time formats from 12-hour to 24-hour
                try:
                    # Try parsing 12-hour format first
                    for fmt in ['%I:%M %p', '%I:%M%p', '%H:%M']:
                        try:
                            start_obj = datetime.strptime(start_str, fmt)
                            end_obj = datetime.strptime(end_str, fmt)
                            start_str = start_obj.strftime('%H:%M')
                            end_str = end_obj.strftime('%H:%M')
                            break
                        except:
                            continue
                    else:
                        raise ValueError()
                except ValueError:
                    validation_errors.append(f"Visit #{idx+1} ({visit_data['client_name']}): Invalid time format (use h:MM AM/PM)")
                    continue

                # Calculate duration
                start = datetime.strptime(start_str, '%H:%M')
                end = datetime.strptime(end_str, '%H:%M')
                duration_minutes = (end - start).total_seconds() / 60

                if duration_minutes <= 0:
                    validation_errors.append(f"Visit #{idx+1} ({visit_data['client_name']}): End time must be after start time")
                    continue

                # Add to validated visits
                validated_visits.append({
                    'client_name': visit_data['client_name'],
                    'date': date_str,
                    'start_time': start_str,
                    'end_time': end_str,
                    'duration_minutes': duration_minutes,
                    'notes': visit_data['notes'],
                    'has_error': False
                })

            except Exception as e:
                validation_errors.append(f"Visit #{idx+1} ({visit_data['client_name']}): {str(e)}")

        # Show validation errors if any
        if validation_errors:
            error_msg = "Please fix the following errors before importing:\n\n"
            error_msg += "\n".join(validation_errors[:10])
            if len(validation_errors) > 10:
                error_msg += f"\n... and {len(validation_errors) - 10} more errors"
            messagebox.showerror("Validation Errors", error_msg)
            return

        # Add hidden visits (those not displayed for editing) that don't have errors
        for visit in getattr(self, 'hidden_visits', []):
            if not visit.get('has_error'):
                validated_visits.append(visit)

        # Check if user wants to import errors as flagged
        import_errors_as_review = getattr(self, 'import_errors_var', None)
        import_errors_as_review = import_errors_as_review.get() if import_errors_as_review else False

        # Build confirmation message
        confirm_msg = f"This will import:\n"
        confirm_msg += f"• {len(preview_results.get('clients', []))} clients\n"
        confirm_msg += f"• {len(validated_visits)} visits\n"
        if skipped_count > 0:
            confirm_msg += f"• {skipped_count} visits skipped\n"
        confirm_msg += f"\nContinue?"

        # Confirm import with corrected data
        if messagebox.askyesno("Confirm Import", confirm_msg):
            dialog.destroy()
            # Update preview_results with validated visits
            preview_results['visits'] = validated_visits
            self.perform_excel_import(preview_results, import_errors_as_review)

    def perform_excel_import(self, preview_results, import_errors_as_review=False):
        """Actually perform the import to the database."""
        # Show progress dialog
        progress_dialog = ctk.CTkToplevel(self)
        progress_dialog.title("Importing...")
        progress_dialog.geometry("350x120")
        progress_dialog.transient(self)
        progress_dialog.grab_set()

        # Center the dialog
        progress_dialog.update_idletasks()
        x = (progress_dialog.winfo_screenwidth() // 2) - (175)
        y = (progress_dialog.winfo_screenheight() // 2) - (60)
        progress_dialog.geometry(f"350x120+{x}+{y}")

        progress_label = ctk.CTkLabel(
            progress_dialog,
            text=f"Importing {len(preview_results.get('visits', []))} visits...\nPlease wait.",
            font=ctk.CTkFont(size=14)
        )
        progress_label.pack(expand=True, pady=10)

        # Force update to show dialog
        progress_dialog.update()
        self.update()

        # Perform import
        results = self.excel_importer.execute_import(preview_results, import_errors_as_review)

        progress_dialog.destroy()

        # Build results message
        msg = "Import Complete!\n\n"
        msg += f"Clients added: {results['clients_added']}\n"
        msg += f"Visits added: {results['visits_added']}\n"

        if results.get('visits_flagged', 0) > 0:
            msg += f"Visits flagged for review: {results['visits_flagged']}\n"

        if results.get('errors'):
            msg += f"\nErrors: {len(results['errors'])}"

        messagebox.showinfo("Import Complete", msg)

        # Refresh all views
        self.refresh_all()

    def scan_paper_records(self):
        """Scan and import data from paper records."""
        ocr_scanner = self.get_ocr_scanner()

        if not ocr_scanner.is_available():
            messagebox.showerror(
                "OCR Not Available",
                "OCR functionality requires pytesseract and tesseract-ocr to be installed.\n\n"
                "Please install:\n"
                "1. tesseract-ocr system package\n"
                "2. pytesseract Python package (pip install pytesseract)"
            )
            return

        file_paths = filedialog.askopenfilenames(
            title="Select images of paper records",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.tiff *.bmp"),
                ("All files", "*.*")
            ]
        )

        if not file_paths:
            return

        all_records = []

        # Scan all images
        for file_path in file_paths:
            text = ocr_scanner.scan_image(file_path)
            if text:
                records = ocr_scanner.parse_visit_records(text)
                for record in records:
                    record['source_file'] = file_path
                    ocr_scanner.validate_and_calculate_duration(record)
                all_records.extend(records)

        if not all_records:
            messagebox.showwarning(
                "No Records Found",
                "Could not extract any visit records from the scanned images.\n\n"
                "Please ensure the images are clear and contain visit information with dates and times."
            )
            return

        # Show verification dialog
        self.show_ocr_verification_dialog(all_records)

    def show_ocr_verification_dialog(self, records: list):
        """Show dialog for verifying and editing OCR-scanned records before import."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Verify Scanned Records")
        dialog.geometry("900x700")
        dialog.transient(self)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (900 // 2)
        y = (dialog.winfo_screenheight() // 2) - (700 // 2)
        dialog.geometry(f"900x700+{x}+{y}")

        header = ctk.CTkLabel(
            dialog,
            text=f"Found {len(records)} Records - Review and Edit Before Saving",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        header.pack(pady=20)

        # Scrollable frame for records
        scroll_frame = ctk.CTkScrollableFrame(dialog, height=500)
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Get all clients for dropdown
        all_clients = self.db.get_all_clients(active_only=True)
        client_names = [c['name'] for c in all_clients]

        record_widgets = []

        for idx, record in enumerate(records):
            # Frame for each record
            record_frame = ctk.CTkFrame(scroll_frame, border_width=2)
            record_frame.pack(fill="x", padx=10, pady=10)
            record_frame.grid_columnconfigure(1, weight=1)

            # Status indicator
            is_valid = record.get('is_valid', True)
            status_color = "green" if is_valid else "red"
            status_text = "✓ Valid" if is_valid else "⚠ Needs Review"

            status_label = ctk.CTkLabel(
                record_frame,
                text=status_text,
                text_color=status_color,
                font=ctk.CTkFont(size=12, weight="bold")
            )
            status_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 5))

            # Input fields
            row_num = 1

            # Client selection
            client_label = ctk.CTkLabel(record_frame, text="Client:", font=ctk.CTkFont(size=13))
            client_label.grid(row=row_num, column=0, sticky="w", padx=10, pady=5)

            client_var = tk.StringVar(value=record.get('client_name', 'Select...'))
            client_menu = ctk.CTkOptionMenu(
                record_frame,
                values=client_names if client_names else ["No clients available"],
                variable=client_var,
                width=200
            )
            client_menu.grid(row=row_num, column=1, sticky="w", padx=10, pady=5)
            row_num += 1

            # Date
            date_label = ctk.CTkLabel(record_frame, text="Date:", font=ctk.CTkFont(size=13))
            date_label.grid(row=row_num, column=0, sticky="w", padx=10, pady=5)

            date_entry = ctk.CTkEntry(record_frame, width=200)
            date_entry.insert(0, record.get('date', ''))
            date_entry.grid(row=row_num, column=1, sticky="w", padx=10, pady=5)
            row_num += 1

            # Start time
            start_label = ctk.CTkLabel(record_frame, text="Start Time:", font=ctk.CTkFont(size=13))
            start_label.grid(row=row_num, column=0, sticky="w", padx=10, pady=5)

            start_entry = ctk.CTkEntry(record_frame, width=200)
            start_entry.insert(0, record.get('start_time', ''))
            start_entry.grid(row=row_num, column=1, sticky="w", padx=10, pady=5)
            row_num += 1

            # End time
            end_label = ctk.CTkLabel(record_frame, text="End Time:", font=ctk.CTkFont(size=13))
            end_label.grid(row=row_num, column=0, sticky="w", padx=10, pady=5)

            end_entry = ctk.CTkEntry(record_frame, width=200)
            end_entry.insert(0, record.get('end_time', ''))
            end_entry.grid(row=row_num, column=1, sticky="w", padx=10, pady=5)
            row_num += 1

            # Source file
            source_label = ctk.CTkLabel(
                record_frame,
                text=f"Source: {record.get('source_file', 'Unknown')}",
                font=ctk.CTkFont(size=10),
                text_color="gray"
            )
            source_label.grid(row=row_num, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 10))

            # Store widgets for later access
            record_widgets.append({
                'client_var': client_var,
                'date_entry': date_entry,
                'start_entry': start_entry,
                'end_entry': end_entry,
                'clients_map': {c['name']: c['id'] for c in all_clients}
            })

        def save_all_records():
            saved_count = 0
            errors = []

            for idx, widgets in enumerate(record_widgets):
                try:
                    client_name = widgets['client_var'].get()
                    client_id = widgets['clients_map'].get(client_name)

                    if not client_id:
                        errors.append(f"Record {idx+1}: Invalid client")
                        continue

                    date_str = widgets['date_entry'].get().strip()
                    start_str = widgets['start_entry'].get().strip()
                    end_str = widgets['end_entry'].get().strip()

                    # Calculate duration
                    start = datetime.strptime(start_str, '%H:%M')
                    end = datetime.strptime(end_str, '%H:%M')
                    duration = (end - start).total_seconds() / 60

                    if duration <= 0:
                        errors.append(f"Record {idx+1}: Invalid time range")
                        continue

                    self.db.add_visit(
                        client_id=client_id,
                        visit_date=date_str,
                        start_time=start_str,
                        end_time=end_str,
                        duration_minutes=duration,
                        notes="Imported from OCR scan"
                    )
                    saved_count += 1

                except Exception as e:
                    errors.append(f"Record {idx+1}: {str(e)}")

            msg = f"Successfully saved {saved_count} out of {len(record_widgets)} records."
            if errors:
                msg += f"\n\nErrors:\n" + "\n".join(errors[:5])
                if len(errors) > 5:
                    msg += f"\n... and {len(errors) - 5} more errors"

            messagebox.showinfo("Import Complete", msg)
            dialog.destroy()
            self.refresh_all()

        # Buttons
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 20))

        save_btn = ctk.CTkButton(
            btn_frame,
            text="Save All Records",
            command=save_all_records,
            font=ctk.CTkFont(size=16),
            height=45,
            fg_color="green"
        )
        save_btn.pack(side=tk.LEFT, padx=5)

        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            command=dialog.destroy,
            font=ctk.CTkFont(size=16),
            height=45,
            fg_color="red"
        )
        cancel_btn.pack(side=tk.LEFT, padx=5)

    # ==================== UTILITY METHODS ====================

    def format_time_12hr(self, time_str: str) -> str:
        """Convert 24-hour time (HH:MM) to 12-hour format (h:MM AM/PM)."""
        try:
            time_obj = datetime.strptime(time_str, '%H:%M')
            # Use %I:%M %p and strip leading zero manually for cross-platform compatibility
            formatted = time_obj.strftime('%I:%M %p')
            # Remove leading zero from hour (e.g., "09:00 AM" -> "9:00 AM")
            if formatted[0] == '0':
                formatted = formatted[1:]
            return formatted
        except:
            return time_str  # Return original if parsing fails

    def format_date_mdy(self, date_str: str) -> str:
        """Convert date (YYYY-MM-DD) to MM/DD/YYYY format."""
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            return date_obj.strftime('%m/%d/%Y')
        except:
            return date_str  # Return original if parsing fails

    def show_settings_dialog(self):
        """Show settings dialog to configure global application settings."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Settings")
        dialog.geometry("500x550")
        dialog.transient(self)
        dialog.grab_set()

        # Header
        header = ctk.CTkLabel(
            dialog,
            text="Application Settings",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        header.pack(pady=15, padx=20)

        # Scrollable frame for settings
        scroll_frame = ctk.CTkScrollableFrame(dialog, height=380)
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # Hourly Rate Setting
        hourly_frame = ctk.CTkFrame(scroll_frame)
        hourly_frame.pack(pady=8, padx=10, fill="x")

        hourly_label = ctk.CTkLabel(
            hourly_frame,
            text="Hourly Labor Rate (per person):",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        hourly_label.pack(pady=(8, 3), padx=10, anchor="w")

        hourly_entry = ctk.CTkEntry(
            hourly_frame,
            placeholder_text="e.g., 25.00",
            height=30
        )
        hourly_entry.pack(pady=3, padx=10, fill="x")

        # Load current value
        current_rate = self.db.get_hourly_rate()
        hourly_entry.insert(0, str(current_rate))

        help_text = ctk.CTkLabel(
            hourly_frame,
            text="Labor cost = (visit time in hours) × 2 crew members × hourly rate",
            font=ctk.CTkFont(size=9),
            text_color="gray"
        )
        help_text.pack(pady=(0, 8), padx=10)

        # PDF Export Path Setting
        pdf_frame = ctk.CTkFrame(scroll_frame)
        pdf_frame.pack(pady=8, padx=10, fill="x")

        pdf_label = ctk.CTkLabel(
            pdf_frame,
            text="PDF Export Directory:",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        pdf_label.pack(pady=(8, 3), padx=10, anchor="w")

        pdf_path_frame = ctk.CTkFrame(pdf_frame, fg_color="transparent")
        pdf_path_frame.pack(pady=3, padx=10, fill="x")

        pdf_entry = ctk.CTkEntry(
            pdf_path_frame,
            placeholder_text="Select directory for PDF exports",
            height=30
        )
        pdf_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        # Load current value
        current_pdf_path = self.db.get_setting('pdf_export_path', '')
        if current_pdf_path:
            pdf_entry.insert(0, current_pdf_path)

        def browse_pdf_path():
            path = filedialog.askdirectory(title="Select PDF Export Directory")
            if path:
                pdf_entry.delete(0, tk.END)
                pdf_entry.insert(0, path)

        browse_btn = ctk.CTkButton(
            pdf_path_frame,
            text="Browse",
            command=browse_pdf_path,
            width=80,
            height=30,
            font=ctk.CTkFont(size=10)
        )
        browse_btn.pack(side="right")

        pdf_help = ctk.CTkLabel(
            pdf_frame,
            text="Directory where exported PDF reports will be saved",
            font=ctk.CTkFont(size=9),
            text_color="gray"
        )
        pdf_help.pack(pady=(0, 8), padx=10)

        # Color Theme Setting
        theme_frame = ctk.CTkFrame(scroll_frame)
        theme_frame.pack(pady=8, padx=10, fill="x")

        theme_label = ctk.CTkLabel(
            theme_frame,
            text="Color Theme:",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        theme_label.pack(pady=(8, 3), padx=10, anchor="w")

        current_theme = self.db.get_setting('color_theme', 'blue')
        theme_var = tk.StringVar(value=current_theme)

        theme_options = ["blue", "dark-blue", "green"]
        theme_menu = ctk.CTkOptionMenu(
            theme_frame,
            variable=theme_var,
            values=theme_options,
            height=30,
            font=ctk.CTkFont(size=11)
        )
        theme_menu.pack(pady=3, padx=10, fill="x")

        theme_help = ctk.CTkLabel(
            theme_frame,
            text="Changes will apply after restarting the application",
            font=ctk.CTkFont(size=9),
            text_color="gray"
        )
        theme_help.pack(pady=(0, 8), padx=10)

        def save_settings():
            try:
                # Validate and save hourly rate
                new_rate = float(hourly_entry.get())
                if new_rate <= 0:
                    messagebox.showerror("Error", "Hourly rate must be greater than 0")
                    return
                self.db.set_hourly_rate(new_rate)

                # Save PDF export path
                pdf_path = pdf_entry.get().strip()
                self.db.set_setting('pdf_export_path', pdf_path)

                # Save color theme
                new_theme = theme_var.get()
                self.db.set_setting('color_theme', new_theme)

                # Apply theme immediately
                if new_theme != current_theme:
                    ctk.set_default_color_theme(new_theme)
                    messagebox.showinfo("Success", "Settings saved! Color theme will fully apply after restart.")
                else:
                    messagebox.showinfo("Success", "Settings saved successfully!")

                self.refresh_dashboard()  # Refresh dashboard to show updated calculations
                dialog.destroy()
            except ValueError:
                messagebox.showerror("Error", "Hourly rate must be a valid number")

        # Buttons
        button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        button_frame.pack(pady=10, padx=20, fill="x")

        save_btn = ctk.CTkButton(
            button_frame,
            text="Save",
            command=save_settings,
            font=ctk.CTkFont(size=11),
            height=32
        )
        save_btn.pack(side="left", padx=(0, 8), expand=True, fill="x")

        cancel_btn = ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
            font=ctk.CTkFont(size=11),
            height=32,
            fg_color="gray"
        )
        cancel_btn.pack(side="left", expand=True, fill="x")

    def refresh_all(self):
        """Refresh all data displays."""
        self.refresh_dashboard()
        self.refresh_clients_list()
        self.refresh_materials_list()
        self.refresh_visit_client_dropdown()
        self.refresh_review_list()
        messagebox.showinfo("Refreshed", "All data refreshed successfully!")

    def on_closing(self):
        """Handle application closing."""
        self.db.close()
        self.destroy()


if __name__ == "__main__":
    app = LandscapingApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
