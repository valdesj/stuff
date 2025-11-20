"""
Landscaping Client Tracker - Main Application
A desktop application for managing landscaping clients, visits, and costs.
"""
import customtkinter as ctk
from database import Database
from excel_importer import ExcelImporter
from gemini_vision import VisitImageParser
from mobile_server import MobileServer
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from tkcalendar import DateEntry
from typing import Optional, List, Dict
from collections import defaultdict
import threading

# Matplotlib imports (moved to module level for performance)
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates
import numpy as np
from scipy.interpolate import make_interp_spline


# Configure CustomTkinter
ctk.set_appearance_mode("dark")  # Dark mode
ctk.set_default_color_theme("blue")

# Performance settings to reduce blur during scrolling
# Set these before creating any widgets
try:
    # Disable DPI scaling to prevent blur
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except:
    # Not on Windows or doesn't support, ignore
    pass


class SplashScreen:
    """Transparent splash screen showing just the logo image."""

    def __init__(self):
        self.splash = tk.Tk()
        self.splash.overrideredirect(True)  # Remove window decorations

        # Try to make window transparent
        try:
            self.splash.attributes('-alpha', 1.0)  # Fully opaque, image handles transparency
            self.splash.attributes('-topmost', True)  # Keep on top
        except:
            pass

        # Load and display logo
        try:
            import os
            from PIL import Image, ImageTk

            script_dir = os.path.dirname(os.path.abspath(__file__))
            png_path = os.path.join(script_dir, 'mJorgesLogo.png')

            if os.path.exists(png_path):
                # Load image with transparency
                img = Image.open(png_path)

                # Resize if too large (max 400x400)
                max_size = 400
                if img.width > max_size or img.height > max_size:
                    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

                self.photo = ImageTk.PhotoImage(img)

                # Create label with image
                label = tk.Label(
                    self.splash,
                    image=self.photo,
                    bg='black',  # Background color for non-transparent areas
                    bd=0,
                    highlightthickness=0
                )
                label.pack()

                # Center window on screen
                self.splash.update_idletasks()
                width = img.width
                height = img.height
                x = (self.splash.winfo_screenwidth() // 2) - (width // 2)
                y = (self.splash.winfo_screenheight() // 2) - (height // 2)
                self.splash.geometry(f'{width}x{height}+{x}+{y}')

                self.splash.update()
            else:
                # If no logo, just show a simple splash
                self.show_simple_splash()

        except Exception as e:
            print(f"Could not load splash image: {e}")
            self.show_simple_splash()

    def show_simple_splash(self):
        """Show a simple text splash if image not available."""
        label = tk.Label(
            self.splash,
            text="Landscaping Client Tracker",
            font=("Arial", 24, "bold"),
            bg='#1a1a1a',
            fg='white',
            padx=40,
            pady=40
        )
        label.pack()

        # Center window
        self.splash.update_idletasks()
        width = 400
        height = 200
        x = (self.splash.winfo_screenwidth() // 2) - (width // 2)
        y = (self.splash.winfo_screenheight() // 2) - (height // 2)
        self.splash.geometry(f'{width}x{height}+{x}+{y}')
        self.splash.update()

    def close(self):
        """Close the splash screen."""
        try:
            self.splash.destroy()
        except:
            pass


class LandscapingApp(ctk.CTk):
    """Main application window for the Landscaping Client Tracker."""

    def __init__(self):
        super().__init__()

        # Performance optimizations for smoother scrolling
        # Disable scaling to prevent blur during scroll
        ctk.set_widget_scaling(1.0)
        ctk.set_window_scaling(1.0)

        # Initialize database
        self.db = Database()

        # Load and apply saved color theme
        saved_theme = self.db.get_setting('color_theme', 'blue')
        try:
            ctk.set_default_color_theme(saved_theme)
        except:
            ctk.set_default_color_theme("blue")

        # Initialize importers (lazy load image parser only when needed)
        self.excel_importer = ExcelImporter(self.db)
        self.image_parser = None  # Lazy load when needed

        # Initialize mobile server for QR code image uploads
        self.mobile_server = MobileServer(callback=self.handle_mobile_upload)
        self.mobile_server.start()
        self.pending_mobile_uploads = []  # Queue for mobile uploads

        # Configure window
        self.title("Landscaping Client Tracker")
        self.geometry("1300x850")

        # Set application icon
        self.set_app_icon()

        # Additional performance optimizations for smoother scrolling
        try:
            # Tkinter rendering optimizations
            self.tk.call('tk', 'scaling', 1.0)
            # Disable smooth scrolling effects that cause blur
            self.option_add('*tearOff', False)
        except:
            pass

        # Configure faster scroll speed globally
        self.setup_fast_scrolling()

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
        self.tab_todo = self.tabview.add("To-Do")
        self.tab_materials = self.tabview.add("Materials")
        self.tab_import = self.tabview.add("Import Historical Data")

        # Initialize tabs
        self.init_dashboard_tab()
        self.init_clients_tab()
        self.init_visits_tab()
        self.init_daily_schedule_tab()
        self.init_todo_tab()
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

    def set_app_icon(self):
        """Set the application icon from PNG file, converting to ICO if needed."""
        try:
            import os
            from PIL import Image

            # Get the directory where the script is located
            script_dir = os.path.dirname(os.path.abspath(__file__))
            png_path = os.path.join(script_dir, 'mJorgesLogo.png')
            ico_path = os.path.join(script_dir, 'mJorgesLogo.ico')

            # Check if PNG exists
            if os.path.exists(png_path):
                # Convert PNG to ICO if ICO doesn't exist
                if not os.path.exists(ico_path):
                    print(f"Converting {png_path} to {ico_path}...")
                    img = Image.open(png_path)
                    # Resize to common icon sizes and save as ICO
                    img.save(ico_path, format='ICO', sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
                    print(f"Icon created: {ico_path}")

                # Set the icon
                self.iconbitmap(ico_path)
                print(f"Application icon set to: {ico_path}")

                # Also set the taskbar icon using iconphoto for better compatibility
                try:
                    img = Image.open(png_path)
                    photo = tk.PhotoImage(file=png_path)
                    self.iconphoto(True, photo)
                except:
                    pass  # iconphoto might not work on all systems

            else:
                print(f"Icon file not found: {png_path}")
                print("Application will use default icon. Add 'mJorgesLogo.png' to the application directory to use custom icon.")

        except ImportError:
            print("PIL/Pillow not installed. Cannot convert PNG to ICO.")
            print("Install with: pip install Pillow")
        except Exception as e:
            print(f"Could not set application icon: {e}")
            # Don't crash if icon setting fails

    def setup_fast_scrolling(self):
        """Configure faster scroll speed for all scrollable widgets."""
        # Increase scroll speed multiplier (default is typically 1-2 lines, we'll do 5)
        scroll_speed = 5

        def _on_mousewheel(event):
            """Handle mousewheel scrolling with increased speed."""
            # Find the widget under the mouse
            widget = event.widget

            # Try to find parent scrollable frame
            while widget:
                if isinstance(widget, ctk.CTkScrollableFrame):
                    # Calculate scroll amount (negative for scroll up, positive for scroll down)
                    if event.delta > 0:
                        widget._parent_canvas.yview_scroll(-scroll_speed, "units")
                    else:
                        widget._parent_canvas.yview_scroll(scroll_speed, "units")
                    return "break"
                widget = widget.master if hasattr(widget, 'master') else None

        # Bind mousewheel to the main window
        # This will apply to all widgets in the application
        self.bind_all("<MouseWheel>", _on_mousewheel, add='+')
        # For Linux
        self.bind_all("<Button-4>", lambda e: _on_mousewheel(type('Event', (), {'delta': 120, 'widget': e.widget})()), add='+')
        self.bind_all("<Button-5>", lambda e: _on_mousewheel(type('Event', (), {'delta': -120, 'widget': e.widget})()), add='+')

    def get_image_parser(self):
        """Get image parser with lazy initialization."""
        if self.image_parser is None:
            gemini_api_key = self.db.get_setting('gemini_api_key', '')
            self.image_parser = VisitImageParser(
                api_key=gemini_api_key if gemini_api_key else None
            )
        return self.image_parser

    def handle_mobile_upload(self, filepath):
        """
        Handle image uploaded from mobile device.

        Args:
            filepath: Path to uploaded image file
        """
        # Add to pending uploads queue (thread-safe)
        self.pending_mobile_uploads.append(filepath)

        # Schedule processing on main thread
        self.after(100, self.process_pending_mobile_uploads)

    def process_pending_mobile_uploads(self):
        """Process any pending mobile uploads on the main thread."""
        if not self.pending_mobile_uploads:
            return

        # Get all pending uploads
        uploads = self.pending_mobile_uploads.copy()
        self.pending_mobile_uploads.clear()

        # Process through the existing scan pipeline
        if len(uploads) == 1:
            self.process_single_mobile_upload(uploads[0])
        else:
            self.process_multiple_mobile_uploads(uploads)

    def process_single_mobile_upload(self, filepath):
        """Process a single mobile upload."""
        parser = self.get_image_parser()

        if not parser.is_available():
            messagebox.showerror(
                "Gemini API Not Configured",
                "Please configure your Gemini API key in Settings to process mobile uploads."
            )
            return

        # Show processing dialog
        progress_dialog = ctk.CTkToplevel(self)
        progress_dialog.title("Processing Mobile Upload")
        progress_dialog.geometry("450x180")
        progress_dialog.transient(self)

        # Center dialog
        progress_dialog.update_idletasks()
        x = (progress_dialog.winfo_screenwidth() // 2) - 225
        y = (progress_dialog.winfo_screenheight() // 2) - 90
        progress_dialog.geometry(f"450x180+{x}+{y}")

        progress_label = ctk.CTkLabel(
            progress_dialog,
            text="Processing image from mobile...\nThis may take a few seconds.",
            font=ctk.CTkFont(size=13)
        )
        progress_label.pack(pady=20)

        progress_bar = ctk.CTkProgressBar(progress_dialog, width=400, mode="indeterminate")
        progress_bar.pack(pady=10)
        progress_bar.start()

        # Process in background
        result_container = {'result': None}

        def process():
            result_container['result'] = parser.parse_image(filepath)

        thread = threading.Thread(target=process, daemon=True)
        thread.start()

        def check_thread():
            if thread.is_alive():
                progress_dialog.after(100, check_thread)
            else:
                progress_bar.stop()
                progress_dialog.destroy()

                result = result_container['result']
                if result['success'] and result['records']:
                    # Switch to Visits tab
                    self.tabview.set("Visits")
                    # Show results dialog
                    self.show_scanned_visits_dialog(result['records'], parser)
                else:
                    error_msg = result.get('error', 'No records found')
                    messagebox.showerror("Processing Failed", f"Could not process mobile upload:\n{error_msg}")

        progress_dialog.after(100, check_thread)

    def process_multiple_mobile_uploads(self, filepaths):
        """Process multiple mobile uploads."""
        parser = self.get_image_parser()

        if not parser.is_available():
            messagebox.showerror(
                "Gemini API Not Configured",
                "Please configure your Gemini API key in Settings to process mobile uploads."
            )
            return

        # Process all images and combine results
        all_records = []
        for filepath in filepaths:
            result = parser.parse_image(filepath)
            if result['success']:
                all_records.extend(result['records'])

        if all_records:
            self.tabview.set("Visits")
            self.show_scanned_visits_dialog(all_records, parser)
        else:
            messagebox.showwarning("No Records Found", "Could not find any visit records in the uploaded images.")

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

        # Use cached client statistics instead of re-querying
        stats_list = self.all_client_stats

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

        # Export PDF button
        export_btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        export_btn_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=8, pady=(8, 6))

        export_btn = ctk.CTkButton(
            export_btn_frame,
            text="📄 Export Client Report (PDF)",
            command=lambda: self.export_client_pdf(stats),
            font=ctk.CTkFont(size=11),
            height=32,
            fg_color="#0078D4",
            hover_color="#005A9E"
        )
        export_btn.pack(fill="x")

    def export_client_pdf(self, stats):
        """Export client statistics to a customer-friendly PDF report."""
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image as RLImage
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        import os
        import tempfile
        import matplotlib
        matplotlib.use('Agg')  # Use non-interactive backend for PDF generation
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        import numpy as np
        from collections import defaultdict
        from scipy.interpolate import make_interp_spline

        # Track temporary graph file for cleanup
        temp_graph_path = None

        # Get PDF export directory from settings
        pdf_dir = self.db.get_setting('pdf_export_path', '')
        if not pdf_dir or not os.path.exists(pdf_dir):
            result = messagebox.askyesno(
                "PDF Export Directory Not Set",
                "PDF export directory is not configured or doesn't exist.\nWould you like to select a directory now?"
            )
            if result:
                pdf_dir = filedialog.askdirectory(title="Select PDF Export Directory")
                if pdf_dir:
                    self.db.set_setting('pdf_export_path', pdf_dir)
                else:
                    return
            else:
                return

        # Create filename
        client_name = stats['client_name'].replace(' ', '_').replace('/', '_')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{client_name}_Report_{timestamp}.pdf"
        filepath = os.path.join(pdf_dir, filename)

        # Create PDF
        doc = SimpleDocTemplate(filepath, pagesize=letter, topMargin=0.75*inch, bottomMargin=0.75*inch)
        story = []
        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#0078D4'),
            spaceAfter=30,
            alignment=TA_CENTER
        )

        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#333333'),
            spaceAfter=12,
            spaceBefore=20
        )

        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=11,
            leading=16
        )

        # Title
        story.append(Paragraph(f"Service Report: {stats['client_name']}", title_style))
        story.append(Paragraph(f"Report Generated: {datetime.now().strftime('%B %d, %Y')}", normal_style))
        story.append(Spacer(1, 0.3*inch))

        # Executive Summary (customer-facing, no profitability status)
        summary_data = [
            ['Monthly Service Charge:', f"${stats['actual_monthly_charge']:.2f}"],
            ['Cost-Based Rate:', f"${stats['proposed_monthly_rate']:.2f}"],
        ]

        summary_table = Table(summary_data, colWidths=[2.5*inch, 3*inch])
        summary_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica', 11),
            ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 11),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#333333')),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
        ]))

        story.append(Paragraph("Account Summary", heading_style))
        story.append(summary_table)
        story.append(Spacer(1, 0.2*inch))

        # Visit Statistics
        story.append(Paragraph("Service History", heading_style))
        story.append(Paragraph(
            f"We have completed <b>{stats['visit_count']}</b> service visits to your property, "
            f"including <b>{stats['visits_this_year']}</b> visits this year.",
            normal_style
        ))
        story.append(Spacer(1, 0.1*inch))

        visit_data = [
            ['Total Visits (All Time):', str(stats['visit_count'])],
            ['Visits This Year:', str(stats['visits_this_year'])],
            ['Average Time per Visit:', f"{stats['avg_time_per_visit']:.1f} minutes"],
            ['Shortest Visit:', f"{stats['min_time_per_visit']:.1f} minutes"],
            ['Longest Visit:', f"{stats['max_time_per_visit']:.1f} minutes"],
        ]

        visit_table = Table(visit_data, colWidths=[3*inch, 2.5*inch])
        visit_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica', 10),
            ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 10),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))

        story.append(visit_table)
        story.append(Spacer(1, 0.2*inch))

        # Detailed Visit History for Working Year
        working_year = self.db.get_setting('working_year', str(datetime.now().year))
        story.append(Paragraph(f"Detailed Visit History ({working_year})", heading_style))

        # Get all visits for this client in the working year
        all_visits = self.db.get_client_visits(stats['client_id'])
        year_visits = [v for v in all_visits if v['visit_date'].startswith(working_year)]

        if year_visits:
            # Sort by date
            year_visits.sort(key=lambda x: x['visit_date'])

            story.append(Paragraph(
                f"Complete record of all {len(year_visits)} visits during {working_year}:",
                normal_style
            ))
            story.append(Spacer(1, 0.1*inch))

            # Create visit history table
            visit_history_data = [['Date', 'Day', 'Start', 'End', 'Duration']]

            for visit in year_visits:
                date_obj = datetime.strptime(visit['visit_date'], '%Y-%m-%d')
                date_str = date_obj.strftime('%m/%d/%Y')
                day_str = date_obj.strftime('%A')[:3]  # Mon, Tue, etc.
                start_obj = datetime.strptime(visit['start_time'], '%H:%M')
                end_obj = datetime.strptime(visit['end_time'], '%H:%M')
                start_str = start_obj.strftime('%I:%M %p').lstrip('0')
                end_str = end_obj.strftime('%I:%M %p').lstrip('0')
                duration_str = f"{visit['duration_minutes']:.0f} min"

                visit_history_data.append([date_str, day_str, start_str, end_str, duration_str])

            visit_history_table = Table(visit_history_data, colWidths=[1.1*inch, 0.6*inch, 0.9*inch, 0.9*inch, 0.8*inch])
            visit_history_table.setStyle(TableStyle([
                ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 9),
                ('FONT', (0, 1), (-1, -1), 'Helvetica', 8),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0078D4')),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                # Alternating row colors for readability
                *[('BACKGROUND', (0, i), (-1, i), colors.HexColor('#F5F5F5'))
                  for i in range(1, len(visit_history_data), 2)]
            ]))

            story.append(visit_history_table)
            story.append(Spacer(1, 0.3*inch))

            # Create visualization graph for visit durations
            story.append(Paragraph(f"Visit Duration Trends ({working_year})", heading_style))

            # Group visits by month and calculate averages
            monthly_data = defaultdict(list)
            for visit in year_visits:
                visit_date = datetime.strptime(visit['visit_date'], '%Y-%m-%d')
                month_key = visit_date.replace(day=1)  # First day of month as key
                monthly_data[month_key].append(visit['duration_minutes'])

            # Calculate monthly averages
            months = sorted(monthly_data.keys())
            averages = [np.mean(monthly_data[month]) for month in months]

            if len(months) > 0:
                # Create the graph
                fig, ax = plt.subplots(figsize=(7, 3.5), facecolor='white')
                ax.set_facecolor('white')

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
                               linestyle='-', linewidth=2.5, color='#0078D4', alpha=0.8)
                        # Plot actual data points
                        ax.plot(months, averages, marker='o', linestyle='',
                               markersize=7, color='#FF6B35', alpha=0.9, zorder=5)
                    except:
                        # Fallback to regular plot if spline fails
                        ax.plot(months, averages, marker='o', linestyle='-',
                               linewidth=2.5, markersize=7, color='#0078D4', alpha=0.8)
                else:
                    # Not enough points for smooth curve, use regular plot
                    ax.plot(months, averages, marker='o', linestyle='-',
                           linewidth=2.5, markersize=7, color='#0078D4', alpha=0.8)

                # Customize axes
                ax.set_xlabel("Month", fontsize=11, fontweight='bold', color='#333333')
                ax.set_ylabel("Average Duration (minutes)", fontsize=11, fontweight='bold', color='#333333')
                ax.set_title(f"Average Visit Duration by Month - {working_year}",
                           fontsize=13, fontweight='bold', color='#333333', pad=10)

                # Format x-axis to show month names only
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
                ax.xaxis.set_major_locator(mdates.MonthLocator())

                # Customize y-axis to show only 0 and max value
                max_duration = max(averages)
                ax.set_ylim(0, max_duration * 1.1)  # Add 10% padding at top
                ax.set_yticks([0, max_duration])
                ax.set_yticklabels(['0', f'{max_duration:.0f}'])

                # Styling
                ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5, axis='y')
                ax.tick_params(colors='#333333', labelsize=10)
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)
                ax.spines['left'].set_color('#CCCCCC')
                ax.spines['bottom'].set_color('#CCCCCC')

                plt.tight_layout()

                # Save to temporary file
                temp_graph = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                temp_graph_path = temp_graph.name  # Store path for cleanup after PDF build
                temp_graph.close()  # Close the file handle
                plt.savefig(temp_graph_path, dpi=150, bbox_inches='tight', facecolor='white')
                plt.close(fig)

                # Add graph to PDF
                graph_image = RLImage(temp_graph_path, width=6*inch, height=3*inch)
                story.append(graph_image)
                story.append(Spacer(1, 0.3*inch))

            story.append(Spacer(1, 0.2*inch))
        else:
            story.append(Paragraph(
                f"No visits recorded for {working_year}.",
                normal_style
            ))
            story.append(Spacer(1, 0.2*inch))

        # Cost Breakdown
        story.append(Paragraph("Annual Cost Breakdown", heading_style))
        story.append(Paragraph(
            "Your proposed monthly rate is calculated based on projected annual costs divided by 12 months. "
            "Here's how we arrive at these figures:",
            normal_style
        ))
        story.append(Spacer(1, 0.1*inch))

        cost_data = [
            ['Cost Category', 'Annual Amount', 'Calculation Method'],
            ['Labor Costs', f"${stats['projected_yearly_labor_cost']:.2f}",
             f"Avg {stats['avg_time_per_visit']:.1f} min/visit x 52 visits x 2 crew x ${stats['hourly_rate']:.2f}/hr"],
            ['Materials', f"${stats['configured_materials_cost_yearly']:.2f}",
             'Configured materials for annual service'],
            ['Services', f"${stats['configured_services_cost_yearly']:.2f}",
             'Additional services (fertilization, treatments, etc.)'],
            ['', '', ''],
            ['Total Annual Cost', f"${stats['est_yearly_cost']:.2f}", 'Sum of all categories above'],
            ['Proposed Monthly Rate', f"${stats['proposed_monthly_rate']:.2f}",
             f"${stats['est_yearly_cost']:.2f} / 12 months"],
        ]

        cost_table = Table(cost_data, colWidths=[2*inch, 1.5*inch, 2.5*inch])
        cost_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 11),
            ('FONT', (0, 1), (-1, -1), 'Helvetica', 9),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0078D4')),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -3), 0.5, colors.grey),
            ('LINEABOVE', (0, -2), (-1, -2), 2, colors.black),
            ('FONT', (0, -2), (-1, -1), 'Helvetica-Bold', 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
        ]))

        story.append(cost_table)
        story.append(Spacer(1, 0.3*inch))

        # Notes
        story.append(Paragraph("Understanding Your Report", heading_style))
        notes_text = """
        <b>Labor Costs:</b> Calculated based on average visit duration, assuming a 2-person crew and our standard hourly rate.<br/><br/>
        <b>Materials & Services:</b> Annual costs for fertilization, treatments, and other scheduled services specific to your property.<br/><br/>
        <b>Cost-Based Rate:</b> A transparent calculation showing our actual costs to service your property.
        This helps ensure fair and sustainable pricing.<br/><br/>
        <b>Note:</b> All calculations are based on historical data and projected annual service levels (typically 52 visits per year for weekly service).
        """
        story.append(Paragraph(notes_text, normal_style))

        # Build PDF
        try:
            doc.build(story)

            # Clean up temporary graph file after PDF is built
            if temp_graph_path and os.path.exists(temp_graph_path):
                try:
                    os.unlink(temp_graph_path)
                except:
                    pass  # Ignore cleanup errors

            messagebox.showinfo(
                "Success",
                f"PDF report exported successfully!\n\nSaved to:\n{filepath}"
            )

            # Ask if user wants to open the file
            if messagebox.askyesno("Open PDF?", "Would you like to open the PDF now?"):
                import platform
                import subprocess
                if platform.system() == 'Windows':
                    os.startfile(filepath)
                elif platform.system() == 'Darwin':  # macOS
                    subprocess.call(['open', filepath])
                else:  # Linux
                    subprocess.call(['xdg-open', filepath])

        except Exception as e:
            # Clean up temporary graph file on error
            if temp_graph_path and os.path.exists(temp_graph_path):
                try:
                    os.unlink(temp_graph_path)
                except:
                    pass  # Ignore cleanup errors
            messagebox.showerror("Error", f"Failed to create PDF:\n{str(e)}")

    # ==================== CLIENTS TAB ====================

    def init_clients_tab(self):
        """Initialize the clients management tab."""
        self.tab_clients.grid_columnconfigure(0, weight=1)
        self.tab_clients.grid_columnconfigure(1, weight=2)
        self.tab_clients.grid_rowconfigure(0, weight=1)

        # Left side - Client list with sub-tabs
        left_frame = ctk.CTkFrame(self.tab_clients)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(0, weight=1)

        # Create sub-tabs for Active, Inactive, and Groups
        self.clients_tabview = ctk.CTkTabview(left_frame)
        self.clients_tabview.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # Create the three sub-tabs
        self.clients_active_tab = self.clients_tabview.add("Active")
        self.clients_inactive_tab = self.clients_tabview.add("Inactive")
        self.clients_groups_tab = self.clients_tabview.add("Groups")

        # Configure each sub-tab
        for tab in [self.clients_active_tab, self.clients_inactive_tab, self.clients_groups_tab]:
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)

        # Active clients scrollable frame
        self.clients_active_scroll = ctk.CTkScrollableFrame(self.clients_active_tab)
        self.clients_active_scroll.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.clients_active_scroll.grid_columnconfigure(0, weight=1)
        self.clients_active_scroll._parent_canvas.configure(yscrollincrement=20)

        # Inactive clients scrollable frame
        self.clients_inactive_scroll = ctk.CTkScrollableFrame(self.clients_inactive_tab)
        self.clients_inactive_scroll.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.clients_inactive_scroll.grid_columnconfigure(0, weight=1)
        self.clients_inactive_scroll._parent_canvas.configure(yscrollincrement=20)

        # Groups scrollable frame
        self.clients_groups_scroll = ctk.CTkScrollableFrame(self.clients_groups_tab)
        self.clients_groups_scroll.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.clients_groups_scroll.grid_columnconfigure(0, weight=1)
        self.clients_groups_scroll._parent_canvas.configure(yscrollincrement=20)

        # Track selected client button
        self.selected_client_button = None
        self.client_buttons = []

        # Add client button at bottom of left frame
        add_btn = ctk.CTkButton(
            left_frame,
            text="+ Add New Client",
            command=self.add_new_client,
            font=ctk.CTkFont(size=12),
            height=35
        )
        add_btn.grid(row=1, column=0, sticky="ew", padx=12, pady=(5, 12))

        # Right side - Client details and materials
        right_frame = ctk.CTkFrame(self.tab_clients)
        right_frame.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(5, 10), pady=10)
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(1, weight=1)

        self.details_header = ctk.CTkLabel(
            right_frame,
            text="Client Details",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.details_header.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 8))

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
        """Refresh all client sub-tabs with button-style items."""
        # Clear all sub-tab scrollable frames
        for widget in self.clients_active_scroll.winfo_children():
            widget.destroy()
        for widget in self.clients_inactive_scroll.winfo_children():
            widget.destroy()
        for widget in self.clients_groups_scroll.winfo_children():
            widget.destroy()

        self.client_buttons = []
        self.selected_client_button = None

        # Get active and inactive clients
        active_clients = self.db.get_all_clients(active_only=True)
        inactive_clients = self.db.get_all_clients(active_only=False)
        inactive_clients = [c for c in inactive_clients if not c['is_active']]

        # Populate Active tab
        for idx, client in enumerate(active_clients):
            self.create_client_button(self.clients_active_scroll, client, idx)

        # Populate Inactive tab
        if inactive_clients:
            for idx, client in enumerate(inactive_clients):
                self.create_client_button(self.clients_inactive_scroll, client, idx)
        else:
            no_inactive = ctk.CTkLabel(
                self.clients_inactive_scroll,
                text="No inactive clients",
                font=ctk.CTkFont(size=14),
                text_color="gray"
            )
            no_inactive.grid(row=0, column=0, pady=50)

        # Populate Groups tab
        self.refresh_client_groups()

    def create_client_button(self, parent, client, idx):
        """Create a client button in the specified parent frame."""
        def create_click_handler(client_id, button):
            def handler():
                self.on_client_button_click(client_id, button)
            return handler

        btn = ctk.CTkButton(
            parent,
            text=client['name'],
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

    def refresh_client_groups(self):
        """Refresh the client groups display."""
        # Clear groups scroll frame
        for widget in self.clients_groups_scroll.winfo_children():
            widget.destroy()

        groups = self.db.get_all_client_groups()

        if not groups:
            no_groups = ctk.CTkLabel(
                self.clients_groups_scroll,
                text="No client groups yet\nAdd a 'Bill To' name to clients to create groups",
                font=ctk.CTkFont(size=14),
                text_color="gray"
            )
            no_groups.grid(row=0, column=0, pady=50)
            return

        # Create group buttons (similar to client buttons)
        for idx, group in enumerate(groups):
            self.create_group_button(self.clients_groups_scroll, group, idx)

    def create_group_button(self, parent, group, idx):
        """Create a group button in the groups tab."""
        def create_click_handler(bill_to, button):
            def handler():
                self.on_group_button_click(bill_to, button)
            return handler

        btn = ctk.CTkButton(
            parent,
            text=f"📋 {group['bill_to']} ({group['client_count']} properties)",
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
        btn.configure(command=create_click_handler(group['bill_to'], btn))

    def on_group_button_click(self, bill_to, button):
        """Handle group button click."""
        # Reset previous selection
        if self.selected_client_button:
            self.selected_client_button.configure(
                fg_color="#3a3a3a",
                border_width=0
            )

        # Make selected button appear pressed
        button.configure(
            fg_color="#154a78",
            border_width=2,
            border_color="#0d3552"
        )
        self.selected_client_button = button

        # Show group details on the right
        self.show_group_details(bill_to)

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
        # Update header
        self.details_header.configure(text="Client Details")

        # Clear existing widgets
        for widget in self.client_details_frame.winfo_children():
            widget.destroy()

        client = self.db.get_client(client_id)
        if not client:
            return

        # Create tabview for Client Details and Aliases
        tabview = ctk.CTkTabview(self.client_details_frame)
        tabview.pack(fill="both", expand=True, padx=5, pady=5)

        tab_details = tabview.add("Client Details")
        tab_aliases = tabview.add("Aliases")

        # ==================== CLIENT DETAILS TAB ====================
        row = 0

        # Client information form
        fields = [
            ("Name:", "name"),
            ("Bill To:", "bill_to"),
            ("Email:", "email"),
            ("Phone:", "phone"),
            ("Address:", "address"),
            ("Monthly Charge ($):", "monthly_charge"),
            ("Notes:", "notes"),
        ]

        self.client_entries = {}

        for label_text, field_name in fields:
            label = ctk.CTkLabel(
                tab_details,
                text=label_text,
                font=ctk.CTkFont(size=14)
            )
            label.grid(row=row, column=0, sticky="w", padx=10, pady=8)

            if field_name == "notes":
                entry = ctk.CTkTextbox(
                    tab_details,
                    height=80,
                    font=ctk.CTkFont(size=13)
                )
                entry.insert("1.0", client.get(field_name, ""))
            else:
                entry = ctk.CTkEntry(
                    tab_details,
                    font=ctk.CTkFont(size=13),
                    height=35
                )
                entry.insert(0, str(client.get(field_name, "")))

            entry.grid(row=row, column=1, sticky="ew", padx=10, pady=8)
            self.client_entries[field_name] = entry
            row += 1

        # No additional services checkbox
        no_services_var = tk.BooleanVar(value=self.db.get_client_no_additional_services(client_id))
        no_services_check = ctk.CTkCheckBox(
            tab_details,
            text="This client doesn't need additional services/materials",
            variable=no_services_var,
            font=ctk.CTkFont(size=12),
            command=lambda: self.toggle_client_no_services(client_id, no_services_var.get())
        )
        no_services_check.grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=8)
        row += 1

        # Buttons row
        btn_frame = ctk.CTkFrame(tab_details, fg_color="transparent")
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
            tab_details,
            text="Materials & Services for this Client",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        materials_header.grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=(20, 5))
        row += 1

        # Create materials table frame
        self.materials_table_frame = ctk.CTkFrame(tab_details)
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

        # ==================== ALIASES TAB ====================
        # Get aliases for this client
        aliases = self.db.get_client_aliases(client_id)

        # Header
        alias_header = ctk.CTkLabel(
            tab_aliases,
            text=f"Alternative Names for {client['name']}",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        alias_header.pack(pady=15)

        info_label = ctk.CTkLabel(
            tab_aliases,
            text="Aliases help match scanned names to this client automatically.\nAdd common variations or misspellings of the client name.",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        info_label.pack(pady=5)

        # Add new alias section
        add_frame = ctk.CTkFrame(tab_aliases)
        add_frame.pack(fill="x", padx=20, pady=15)

        ctk.CTkLabel(
            add_frame,
            text="Add New Alias:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side=tk.LEFT, padx=5)

        new_alias_entry = ctk.CTkEntry(add_frame, placeholder_text="Enter alias name", width=300)
        new_alias_entry.pack(side=tk.LEFT, padx=5)

        def add_alias():
            alias_name = new_alias_entry.get().strip()
            if not alias_name:
                messagebox.showwarning("Empty Alias", "Please enter an alias name.")
                return
            if alias_name.lower() == client['name'].lower():
                messagebox.showwarning("Invalid Alias", "Alias cannot be the same as the client name.")
                return

            self.db.add_client_alias(client_id, alias_name)
            messagebox.showinfo("Alias Added", f'Added "{alias_name}" as an alias.')
            new_alias_entry.delete(0, tk.END)
            # Refresh the client details to show the new alias
            self.show_client_details(client_id)

        ctk.CTkButton(
            add_frame,
            text="Add Alias",
            command=add_alias,
            fg_color="#2e7d32",
            hover_color="#1b5e20",
            width=100
        ).pack(side=tk.LEFT, padx=5)

        # List of existing aliases
        aliases_frame = ctk.CTkScrollableFrame(tab_aliases, height=300)
        aliases_frame.pack(fill="both", expand=True, padx=20, pady=10)

        if aliases:
            for alias in aliases:
                alias_row = ctk.CTkFrame(aliases_frame)
                alias_row.pack(fill="x", pady=5)

                ctk.CTkLabel(
                    alias_row,
                    text=alias,
                    font=ctk.CTkFont(size=13)
                ).pack(side=tk.LEFT, padx=10)

                def delete_alias(a=alias):
                    if messagebox.askyesno("Delete Alias", f'Delete alias "{a}"?'):
                        self.db.delete_client_alias(client_id, a)
                        self.show_client_details(client_id)

                ctk.CTkButton(
                    alias_row,
                    text="Delete",
                    command=delete_alias,
                    fg_color="red",
                    hover_color="darkred",
                    width=80,
                    height=28
                ).pack(side=tk.RIGHT, padx=10)
        else:
            ctk.CTkLabel(
                aliases_frame,
                text="No aliases yet. Add one above to help with automatic name matching.",
                font=ctk.CTkFont(size=12),
                text_color="gray"
            ).pack(pady=20)

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

        material_var.trace_add('write', lambda *args: on_material_dropdown_change())
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

    def add_new_client(self, default_name: str = ""):
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
            ("Bill To:", "bill_to"),
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
                # Pre-fill name if provided
                if field_name == "name" and default_name:
                    entry.insert(0, default_name)

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
                notes=notes_text,
                bill_to=entries['bill_to'].get().strip()
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

    def show_group_details(self, bill_to: str):
        """Display group details and list of properties."""
        # Update header
        self.details_header.configure(text="Group Details")

        # Clear existing widgets
        for widget in self.client_details_frame.winfo_children():
            widget.destroy()

        # Get group info and clients
        group_info = self.db.get_group_info(bill_to)
        clients = self.db.get_clients_in_group(bill_to)

        row = 0

        # Group header
        group_header = ctk.CTkLabel(
            self.client_details_frame,
            text=f"Group: {bill_to}",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        group_header.grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 10))
        row += 1

        # Contact information fields
        fields = [
            ("Email:", "email"),
            ("Phone:", "phone"),
            ("Address:", "address"),
            ("Notes:", "notes"),
        ]

        self.group_entries = {}

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
                    height=60,
                    font=ctk.CTkFont(size=13)
                )
                if group_info:
                    entry.insert("1.0", group_info.get(field_name, ""))
            else:
                entry = ctk.CTkEntry(
                    self.client_details_frame,
                    font=ctk.CTkFont(size=13),
                    height=35
                )
                if group_info:
                    entry.insert(0, str(group_info.get(field_name, "")))

            entry.grid(row=row, column=1, sticky="ew", padx=10, pady=8)
            self.group_entries[field_name] = entry
            row += 1

        # Button frame
        btn_frame = ctk.CTkFrame(self.client_details_frame, fg_color="transparent")
        btn_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=10)
        row += 1

        # Save button
        save_btn = ctk.CTkButton(
            btn_frame,
            text="Save Group Info",
            command=lambda: self.save_group_info(bill_to),
            font=ctk.CTkFont(size=14),
            height=35,
            fg_color="green"
        )
        save_btn.pack(side=tk.LEFT, padx=5)

        # Copy from matching client button
        copy_btn = ctk.CTkButton(
            btn_frame,
            text="Copy from Matching Client",
            command=lambda: self.copy_contact_from_client(bill_to),
            font=ctk.CTkFont(size=14),
            height=35,
            fg_color="#4a7ba7"
        )
        copy_btn.pack(side=tk.LEFT, padx=5)

        # Properties in this group
        properties_header = ctk.CTkLabel(
            self.client_details_frame,
            text=f"Properties in Group ({len(clients)})",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        properties_header.grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=(20, 10))
        row += 1

        # List properties
        for client in clients:
            client_frame = ctk.CTkFrame(self.client_details_frame, fg_color="#2b2b2b")
            client_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=4)
            client_frame.grid_columnconfigure(0, weight=1)

            client_btn = ctk.CTkButton(
                client_frame,
                text=f"  • {client['name']}",
                command=lambda c=client: self.navigate_to_client(c['id']),
                font=ctk.CTkFont(size=14),
                height=40,
                fg_color="transparent",
                hover_color="#3a3a3a",
                anchor="w"
            )
            client_btn.grid(row=0, column=0, sticky="ew", padx=5, pady=3)
            row += 1

    def navigate_to_client(self, client_id):
        """Navigate to a specific client in the Active tab."""
        self.clients_tabview.set("Active")
        self.refresh_clients_list()
        self.show_client_details(client_id)

    def save_group_info(self, bill_to: str):
        """Save group contact information."""
        try:
            email = self.group_entries['email'].get().strip()
            phone = self.group_entries['phone'].get().strip()
            address = self.group_entries['address'].get().strip()
            notes = self.group_entries['notes'].get("1.0", "end-1c")

            self.db.save_group_info(bill_to, email, phone, address, notes)
            messagebox.showinfo("Success", "Group information saved!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save group info: {str(e)}")

    def copy_contact_from_client(self, bill_to: str):
        """Copy contact information from a client matching the bill_to name."""
        try:
            # Try to find a client with name matching bill_to
            matching_client = self.db.get_client_by_name(bill_to)

            print(f"DEBUG: Looking for client with name: '{bill_to}'")
            print(f"DEBUG: Found matching client: {matching_client}")

            if matching_client:
                # Get values with proper null handling
                email_value = matching_client.get('email') or ''
                phone_value = matching_client.get('phone') or ''
                address_value = matching_client.get('address') or ''

                print(f"DEBUG: Email: '{email_value}', Phone: '{phone_value}', Address: '{address_value}'")

                # Clear and populate the email field
                self.group_entries['email'].delete(0, tk.END)
                self.group_entries['email'].insert(0, email_value)

                # Clear and populate the phone field
                self.group_entries['phone'].delete(0, tk.END)
                self.group_entries['phone'].insert(0, phone_value)

                # Clear and populate the address field
                self.group_entries['address'].delete(0, tk.END)
                self.group_entries['address'].insert(0, address_value)

                # Force UI update
                self.group_entries['email'].update()
                self.group_entries['phone'].update()
                self.group_entries['address'].update()

                # Show what was copied
                copied_fields = []
                if email_value:
                    copied_fields.append(f"Email: {email_value}")
                if phone_value:
                    copied_fields.append(f"Phone: {phone_value}")
                if address_value:
                    copied_fields.append(f"Address: {address_value}")

                if copied_fields:
                    msg = f"Copied from client '{matching_client['name']}':\n\n" + "\n".join(copied_fields)
                else:
                    msg = f"Client '{matching_client['name']}' found, but no contact info to copy.\n\nThe client exists but has empty email, phone, and address fields."

                messagebox.showinfo("Contact Info Copied", msg)
            else:
                # Show detailed warning
                all_clients = self.db.get_all_clients(active_only=True)
                client_names = [c['name'] for c in all_clients[:10]]  # Show first 10

                msg = f"No active client found with exact name: '{bill_to}'\n\n"
                msg += "To use this feature, create a client with the exact same name as the Bill To value.\n\n"
                if client_names:
                    msg += f"Active clients include:\n" + "\n".join(f"  • {name}" for name in client_names)
                    if len(all_clients) > 10:
                        msg += f"\n  ... and {len(all_clients) - 10} more"

                messagebox.showwarning("No Matching Client", msg)

        except Exception as e:
            print(f"ERROR in copy_contact_from_client: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to copy contact info:\n{str(e)}")

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
        scroll_frame._parent_canvas.configure(yscrollincrement=20)

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
        material_var.trace_add('write', lambda *args: update_cost_ui())

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

        # Scan Image button
        scan_btn = ctk.CTkButton(
            client_frame,
            text="📷 Scan Image",
            command=self.scan_visit_image,
            font=ctk.CTkFont(size=14),
            height=40,
            fg_color="#2e7d32",
            hover_color="#1b5e20"
        )
        scan_btn.pack(side=tk.LEFT, padx=10, pady=15)

        # QR Code button for mobile upload
        qr_btn = ctk.CTkButton(
            client_frame,
            text="📱 Mobile Upload",
            command=self.show_mobile_qr_code,
            font=ctk.CTkFont(size=14),
            height=40,
            fg_color="#1976d2",
            hover_color="#0d47a1"
        )
        qr_btn.pack(side=tk.LEFT, padx=10, pady=15)

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
        scroll_frame._parent_canvas.configure(yscrollincrement=20)

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

    # ==================== ALIAS MANAGEMENT ====================

    def show_alias_dialog(self, scanned_name: str, all_clients: List[Dict], client_var: tk.StringVar):
        """Show dialog to save scanned name as alias or create new client."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Client Name Not Found")
        dialog.geometry("500x400")
        dialog.transient(self)
        dialog.grab_set()

        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - 250
        y = (dialog.winfo_screenheight() // 2) - 200
        dialog.geometry(f"500x400+{x}+{y}")

        # Header
        header = ctk.CTkLabel(
            dialog,
            text=f'Scanned name: "{scanned_name}"',
            font=ctk.CTkFont(size=14, weight="bold")
        )
        header.pack(pady=15)

        question = ctk.CTkLabel(
            dialog,
            text="Is this an existing client with a different name,\nor a new client?",
            font=ctk.CTkFont(size=12)
        )
        question.pack(pady=5)

        # Option 1: Existing client (alias)
        alias_frame = ctk.CTkFrame(dialog)
        alias_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(
            alias_frame,
            text="Option 1: This is an existing client (save as alias)",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(pady=10)

        ctk.CTkLabel(
            alias_frame,
            text="Select the existing client:",
            font=ctk.CTkFont(size=11)
        ).pack(pady=5)

        client_names = [c['name'] for c in all_clients]
        alias_client_var = tk.StringVar(value="Select client...")
        alias_client_menu = ctk.CTkOptionMenu(
            alias_frame,
            values=client_names,
            variable=alias_client_var,
            width=400
        )
        alias_client_menu.pack(pady=5)

        def save_as_alias():
            selected_client = alias_client_var.get()
            if selected_client == "Select client...":
                messagebox.showwarning("No Selection", "Please select a client first.")
                return

            # Find client ID
            client = next((c for c in all_clients if c['name'] == selected_client), None)
            if client:
                self.db.add_client_alias(client['id'], scanned_name)
                client_var.set(selected_client)
                messagebox.showinfo("Alias Saved", f'Saved "{scanned_name}" as an alias for {selected_client}')
                dialog.destroy()

        ctk.CTkButton(
            alias_frame,
            text="Save as Alias",
            command=save_as_alias,
            fg_color="#2e7d32",
            hover_color="#1b5e20"
        ).pack(pady=10)

        # Option 2: New client
        new_frame = ctk.CTkFrame(dialog)
        new_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(
            new_frame,
            text="Option 2: This is a new client",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(pady=10)

        def create_new_client():
            dialog.destroy()
            # Open the add client dialog with the scanned name pre-filled
            self.add_new_client(default_name=scanned_name)

        ctk.CTkButton(
            new_frame,
            text="Create New Client",
            command=create_new_client,
            fg_color="#1976d2",
            hover_color="#1565c0"
        ).pack(pady=10)

        # Cancel button
        ctk.CTkButton(
            dialog,
            text="Cancel",
            command=dialog.destroy,
            fg_color="gray",
            hover_color="darkgray"
        ).pack(pady=10)

    # ==================== IMAGE SCANNING ====================

    def show_mobile_qr_code(self):
        """Show QR code for mobile upload."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Mobile Upload - Scan QR Code")
        dialog.geometry("500x650")
        dialog.transient(self)
        dialog.grab_set()

        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - 250
        y = (dialog.winfo_screenheight() // 2) - 325
        dialog.geometry(f"500x650+{x}+{y}")

        # Header
        header = ctk.CTkLabel(
            dialog,
            text="📱 Upload Photos from Mobile",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        header.pack(pady=20)

        # Instructions
        instructions = ctk.CTkTextbox(dialog, height=120, fg_color="transparent")
        instructions.pack(padx=20, pady=10, fill="x")
        instructions.insert("1.0", """Instructions:
1. Open your phone's camera app
2. Scan the QR code below
3. Take photos of your visit records
4. Photos will automatically appear in the app

The upload page works on any device with a camera!""")
        instructions.configure(state="disabled")

        # Generate and display QR code
        try:
            qr_buffer = self.mobile_server.generate_qr_code()

            # Convert to PhotoImage for display
            from PIL import Image, ImageTk
            qr_img = Image.open(qr_buffer)
            qr_img = qr_img.resize((300, 300), Image.Resampling.LANCZOS)
            qr_photo = ImageTk.PhotoImage(qr_img)

            # Use CTkLabel to avoid color issues
            qr_label = ctk.CTkLabel(dialog, image=qr_photo, text="")
            qr_label.image = qr_photo  # Keep reference
            qr_label.pack(pady=20)

        except Exception as e:
            error_label = ctk.CTkLabel(
                dialog,
                text=f"Error generating QR code:\n{str(e)}",
                text_color="red"
            )
            error_label.pack(pady=20)

        # URL display
        url = self.mobile_server.get_url()
        url_frame = ctk.CTkFrame(dialog)
        url_frame.pack(pady=10, padx=20, fill="x")

        url_label = ctk.CTkLabel(
            url_frame,
            text=f"Or visit: {url}",
            font=ctk.CTkFont(size=12)
        )
        url_label.pack(pady=10)

        # Copy URL button
        def copy_url():
            dialog.clipboard_clear()
            dialog.clipboard_append(url)
            copy_btn.configure(text="✓ Copied!")
            dialog.after(2000, lambda: copy_btn.configure(text="Copy URL"))

        copy_btn = ctk.CTkButton(
            url_frame,
            text="Copy URL",
            command=copy_url,
            width=120
        )
        copy_btn.pack(pady=5)

        # Status
        status_label = ctk.CTkLabel(
            dialog,
            text=f"Server running at {url}",
            font=ctk.CTkFont(size=10),
            text_color="green"
        )
        status_label.pack(pady=10)

        # Close button
        close_btn = ctk.CTkButton(
            dialog,
            text="Close",
            command=dialog.destroy,
            width=120
        )
        close_btn.pack(pady=10)

    def scan_visit_image(self):
        """Open file dialog to scan an image for visit data."""
        # Get image parser (lazy initialization)
        parser = self.get_image_parser()

        # Open file dialog
        file_path = filedialog.askopenfilename(
            title="Select Visit Record Image",
            filetypes=[
                ("Image Files", "*.png *.jpg *.jpeg *.bmp *.tiff *.tif"),
                ("All Files", "*.*")
            ]
        )

        if not file_path:
            return

        # Show progress dialog with animated progress bar
        progress_dialog = ctk.CTkToplevel(self)
        progress_dialog.title("Scanning Image")
        progress_dialog.geometry("450x180")
        progress_dialog.transient(self)
        progress_dialog.grab_set()

        # Center dialog
        progress_dialog.update_idletasks()
        x = (progress_dialog.winfo_screenwidth() // 2) - 225
        y = (progress_dialog.winfo_screenheight() // 2) - 90
        progress_dialog.geometry(f"450x180+{x}+{y}")

        progress_label = ctk.CTkLabel(
            progress_dialog,
            text="Scanning image with Gemini AI...\nThis may take a few seconds.",
            font=ctk.CTkFont(size=13)
        )
        progress_label.pack(pady=20)

        # Add animated progress bar
        progress_bar = ctk.CTkProgressBar(progress_dialog, width=400, mode="indeterminate")
        progress_bar.pack(pady=10)
        progress_bar.start()

        status_label = ctk.CTkLabel(
            progress_dialog,
            text="Extracting visit data...",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        status_label.pack(pady=5)

        # Run Gemini parsing in background thread so progress bar animates
        result_container = {}

        def parse_in_background():
            try:
                result_container['result'] = parser.parse_image(file_path)
            except Exception as e:
                result_container['error'] = str(e)

        # Start background thread
        thread = threading.Thread(target=parse_in_background, daemon=True)
        thread.start()

        # Wait for thread to complete while keeping UI responsive
        def check_thread():
            if thread.is_alive():
                # Thread still running, check again in 100ms
                progress_dialog.after(100, check_thread)
            else:
                # Thread finished
                progress_bar.stop()
                progress_dialog.destroy()

                # Handle error
                if 'error' in result_container:
                    error_str = result_container['error']
                    if 'connection' in error_str.lower() or 'network' in error_str.lower():
                        messagebox.showerror(
                            "Connection Error",
                            "Failed to connect to Gemini API.\n\nPlease check your internet connection and try again."
                        )
                    else:
                        messagebox.showerror("Error", f"Failed to scan image:\n{error_str}")
                    return

                # Handle result
                result = result_container.get('result', {})
                if not result.get('success'):
                    error_msg = result.get('error', 'Unknown error occurred')
                    messagebox.showerror("Scan Failed", error_msg)
                    return

                if not result.get('records'):
                    messagebox.showinfo(
                        "No Records Found",
                        "No visit records were found in the image.\n\n"
                        "Make sure the image contains:\n"
                        "- Date (MM/DD/YYYY or YYYY-MM-DD)\n"
                        "- Time range (h:MM - h:MM)\n"
                        "- Client name"
                    )
                    return

                # Show review dialog
                self.show_scanned_visits_dialog(result['records'], parser)

        # Start checking thread status
        progress_dialog.after(100, check_thread)

    def show_scanned_visits_dialog(self, records: list, parser):
        """Show dialog to review and import scanned visit records."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Review Scanned Visits")
        dialog.geometry("900x700")
        dialog.transient(self)
        dialog.grab_set()

        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - 450
        y = (dialog.winfo_screenheight() // 2) - 350
        dialog.geometry(f"900x700+{x}+{y}")

        # Header
        header = ctk.CTkLabel(
            dialog,
            text=f"Found {len(records)} Visit Record(s)",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        header.pack(pady=15)

        # Scrollable frame for records
        scroll_frame = ctk.CTkScrollableFrame(dialog, height=550)
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Optimize scrolling performance to prevent blur
        scroll_frame._parent_canvas.configure(yscrollincrement=20)

        # Get all clients for matching
        all_clients = self.db.get_all_clients(active_only=False)

        # Helper functions for formatting
        def format_time_12hr(time_24hr):
            """Convert 24hr time (HH:MM) to 12hr format (h:MM AM/PM)"""
            try:
                time_obj = datetime.strptime(time_24hr, '%H:%M')
                return time_obj.strftime('%I:%M %p').lstrip('0')
            except:
                return time_24hr

        def format_date_mdy(date_ymd):
            """Convert YYYY-MM-DD to MM/DD/YYYY"""
            try:
                date_obj = datetime.strptime(date_ymd, '%Y-%m-%d')
                return date_obj.strftime('%m/%d/%Y')
            except:
                return date_ymd

        def check_duplicate(client_id, visit_date):
            """Check if a visit already exists for this client on this date"""
            try:
                existing = self.db.get_visits_by_date(visit_date)
                for visit in existing:
                    if visit['client_id'] == client_id:
                        return True
                return False
            except:
                return False

        import_data = []

        for idx, record in enumerate(records):
            # Create card for each record
            card = ctk.CTkFrame(scroll_frame, border_width=2, border_color="#3a3a3a")
            card.pack(fill="x", padx=5, pady=10)

            # Header with checkbox
            header_frame = ctk.CTkFrame(card, fg_color="transparent")
            header_frame.pack(fill="x", pady=8, padx=10)

            import_checkbox_var = tk.BooleanVar(value=True)  # Default to import
            import_checkbox = ctk.CTkCheckBox(
                header_frame,
                text=f"Visit #{idx + 1}",
                variable=import_checkbox_var,
                font=ctk.CTkFont(size=14, weight="bold")
            )
            import_checkbox.pack(side=tk.LEFT)

            # Grid for fields
            fields_frame = ctk.CTkFrame(card, fg_color="transparent")
            fields_frame.pack(fill="both", padx=15, pady=10)
            fields_frame.grid_columnconfigure(1, weight=1)

            row = 0

            # Date
            ctk.CTkLabel(fields_frame, text="Date:", font=ctk.CTkFont(size=12, weight="bold")).grid(
                row=row, column=0, sticky="w", padx=5, pady=5
            )
            date_entry = ctk.CTkEntry(fields_frame, height=32)
            date_formatted = format_date_mdy(record.get('date', ''))
            date_entry.insert(0, date_formatted)
            date_entry.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
            row += 1

            # Start Time
            ctk.CTkLabel(fields_frame, text="Start Time:", font=ctk.CTkFont(size=12, weight="bold")).grid(
                row=row, column=0, sticky="w", padx=5, pady=5
            )
            start_entry = ctk.CTkEntry(fields_frame, height=32)
            start_formatted = format_time_12hr(record.get('start_time', ''))
            start_entry.insert(0, start_formatted)
            start_entry.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
            row += 1

            # End Time
            ctk.CTkLabel(fields_frame, text="End Time:", font=ctk.CTkFont(size=12, weight="bold")).grid(
                row=row, column=0, sticky="w", padx=5, pady=5
            )
            end_entry = ctk.CTkEntry(fields_frame, height=32)
            end_formatted = format_time_12hr(record.get('end_time', ''))
            end_entry.insert(0, end_formatted)
            end_entry.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
            row += 1

            # Duration
            duration_str = f"{record.get('duration_minutes', 0):.0f} minutes" if record.get('is_valid') else "Invalid"
            ctk.CTkLabel(fields_frame, text="Duration:", font=ctk.CTkFont(size=12, weight="bold")).grid(
                row=row, column=0, sticky="w", padx=5, pady=5
            )
            ctk.CTkLabel(
                fields_frame,
                text=duration_str,
                text_color="green" if record.get('is_valid') else "red"
            ).grid(row=row, column=1, sticky="w", padx=5, pady=5)
            row += 1

            # Client selection
            ctk.CTkLabel(fields_frame, text="Client:", font=ctk.CTkFont(size=12, weight="bold")).grid(
                row=row, column=0, sticky="w", padx=5, pady=5
            )

            # Try to match client (check exact name/alias first, then fuzzy match)
            scanned_client_name = record.get('client_name', '')
            matched_client = None
            match_method = None

            if scanned_client_name:
                # First try exact match by name or alias
                matched_client = self.db.find_client_by_name_or_alias(scanned_client_name)
                if matched_client:
                    match_method = "exact"
                else:
                    # Fall back to fuzzy matching
                    matched_client = parser.match_client_name(scanned_client_name, all_clients)
                    if matched_client:
                        match_method = "fuzzy"

            client_names = [c['name'] for c in all_clients]
            client_var = tk.StringVar()

            if matched_client:
                client_var.set(matched_client['name'])
            elif scanned_client_name:
                client_var.set(f"[Scanned: {scanned_client_name}] - Select below")
            else:
                client_var.set("Select client...")

            client_frame = ctk.CTkFrame(fields_frame, fg_color="transparent")
            client_frame.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
            client_frame.grid_columnconfigure(0, weight=1)

            client_menu = ctk.CTkOptionMenu(
                client_frame,
                values=client_names if client_names else ["No clients"],
                variable=client_var,
                height=32
            )
            client_menu.grid(row=0, column=0, sticky="ew")

            # If fuzzy matched or no match, offer to create alias
            if scanned_client_name and (match_method == "fuzzy" or not matched_client):
                def create_alias_for_record():
                    self.show_alias_dialog(scanned_client_name, all_clients, client_var)

                alias_btn = ctk.CTkButton(
                    client_frame,
                    text="Save as Alias" if matched_client else "New Client/Alias",
                    command=create_alias_for_record,
                    width=120,
                    height=28,
                    fg_color="gray",
                    font=ctk.CTkFont(size=11)
                )
                alias_btn.grid(row=0, column=1, padx=(5, 0))

            row += 1

            # Check for duplicate
            is_duplicate = False
            if matched_client:
                is_duplicate = check_duplicate(matched_client['id'], record.get('date', ''))
                if is_duplicate:
                    import_checkbox_var.set(False)  # Uncheck duplicates by default

            # Validation status
            status_messages = []
            if record.get('is_valid'):
                status_messages.append("[OK] Ready to import")
                status_color = "green"
            else:
                status_messages.append(f"[ERROR] {record.get('validation_error', 'Invalid record')}")
                status_color = "red"

            if is_duplicate:
                status_messages.append("[DUPLICATE] Visit already exists for this client on this date")
                status_color = "orange"

            status_text = " | ".join(status_messages)
            status_label = ctk.CTkLabel(
                card,
                text=status_text,
                font=ctk.CTkFont(size=11),
                text_color=status_color
            )
            status_label.pack(pady=8)

            # Store data for import
            import_data.append({
                'record': record,
                'date_entry': date_entry,
                'start_entry': start_entry,
                'end_entry': end_entry,
                'client_var': client_var,
                'clients_dict': {c['name']: c['id'] for c in all_clients},
                'import_checkbox': import_checkbox_var,
                'is_duplicate': is_duplicate
            })

        # Buttons
        button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        button_frame.pack(fill="x", padx=20, pady=10)

        def import_all_visits():
            """Import all checked scanned visits."""
            imported_count = 0
            skipped_count = 0
            errors = []

            for idx, data in enumerate(import_data):
                try:
                    # Check if this visit is selected for import
                    if not data['import_checkbox'].get():
                        skipped_count += 1
                        continue

                    # Get client
                    client_name = data['client_var'].get()
                    if client_name not in data['clients_dict']:
                        errors.append(f"Visit #{idx + 1}: No client selected")
                        continue

                    client_id = data['clients_dict'][client_name]

                    # Get date and times (convert from display format back to database format)
                    visit_date_display = data['date_entry'].get().strip()
                    start_time_display = data['start_entry'].get().strip()
                    end_time_display = data['end_entry'].get().strip()

                    # Convert date from MM/DD/YYYY to YYYY-MM-DD
                    try:
                        date_obj = datetime.strptime(visit_date_display, '%m/%d/%Y')
                        visit_date = date_obj.strftime('%Y-%m-%d')
                    except:
                        # Try if it's already in YYYY-MM-DD format
                        visit_date = visit_date_display

                    # Convert times from 12hr to 24hr format
                    def convert_12_to_24(time_12hr):
                        try:
                            time_obj = datetime.strptime(time_12hr, '%I:%M %p')
                            return time_obj.strftime('%H:%M')
                        except:
                            # Try if it's already in 24hr format
                            return time_12hr

                    start_time = convert_12_to_24(start_time_display)
                    end_time = convert_12_to_24(end_time_display)

                    # Calculate duration
                    try:
                        start = datetime.strptime(start_time, '%H:%M')
                        end = datetime.strptime(end_time, '%H:%M')
                        duration = (end - start).total_seconds() / 60
                        if duration < 0:
                            duration += 24 * 60
                    except:
                        errors.append(f"Visit #{idx + 1}: Invalid time format")
                        continue

                    # Add visit
                    self.db.add_visit(
                        client_id=client_id,
                        visit_date=visit_date,
                        start_time=start_time,
                        end_time=end_time,
                        duration_minutes=duration,
                        notes="Imported from scanned image"
                    )
                    imported_count += 1

                except Exception as e:
                    errors.append(f"Visit #{idx + 1}: {str(e)}")

            # Close dialog
            dialog.destroy()

            # Show result
            summary_parts = [f"Imported: {imported_count}"]
            if skipped_count > 0:
                summary_parts.append(f"Skipped: {skipped_count}")

            summary = " | ".join(summary_parts)

            if errors:
                error_msg = "\n".join(errors)
                messagebox.showwarning(
                    "Import Complete with Errors",
                    f"{summary}\n\nErrors:\n{error_msg}"
                )
            else:
                messagebox.showinfo("Success", f"Successfully imported {imported_count} visit(s)!\n{skipped_count} skipped.")

            # Refresh visits view
            self.refresh_visit_client_dropdown()
            self.refresh_dashboard()

        ctk.CTkButton(
            button_frame,
            text="Import Checked Visits",
            command=import_all_visits,
            font=ctk.CTkFont(size=14),
            height=40,
            fg_color="#2e7d32",
            hover_color="#1b5e20"
        ).pack(side=tk.LEFT, padx=5)

        ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
            font=ctk.CTkFont(size=14),
            height=40,
            fg_color="gray",
            hover_color="darkgray"
        ).pack(side=tk.RIGHT, padx=5)

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

        # Calendar picker styled like Windows taskbar calendar
        self.daily_date_picker = DateEntry(
            date_frame,
            width=24,
            background='#0078D4',  # Windows blue
            foreground='white',
            borderwidth=0,
            font=('Segoe UI', 15),
            date_pattern='mm/dd/yyyy',
            # Calendar popup styling - Windows style
            headersbackground='#1F1F1F',  # Dark header like Windows
            headersforeground='white',
            selectbackground='#0078D4',  # Windows blue for selected
            selectforeground='white',
            normalbackground='#2D2D2D',  # Clean dark background
            normalforeground='white',
            weekendbackground='#2D2D2D',  # Same as weekdays for clean look
            weekendforeground='white',
            othermonthforeground='#686868',  # Subtle gray for other months
            othermonthweforeground='#686868',
            othermonthwebackground='#2D2D2D',
            disabledbackground='#2D2D2D',
            disabledforeground='#404040',
            bordercolor='#3F3F3F',  # Subtle border
            cursor='hand2'
        )
        self.daily_date_picker.pack(side=tk.LEFT, padx=10, pady=15)

        # Style the calendar popup to match Windows - larger and cleaner
        self.daily_date_picker._calendar.configure(
            font=('Segoe UI', 16),  # Larger font like Windows
            borderwidth=1
        )

        # Adjust calendar popup window styling
        try:
            # Make the popup window larger with more padding
            self.daily_date_picker._top_cal.configure(bg='#2D2D2D')
        except:
            pass  # Window might not exist yet

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

        # Get all visits for this date in a single optimized query
        all_visits = self.db.get_visits_by_date(db_date, active_only=True)

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

    # ==================== TO-DO TAB ====================

    def init_todo_tab(self):
        """Initialize the to-do tab for data review and missing client info."""
        self.tab_todo.grid_columnconfigure(0, weight=1)
        self.tab_todo.grid_rowconfigure(0, weight=1)

        # Create sub-tabs for different to-do categories
        self.todo_tabview = ctk.CTkTabview(self.tab_todo)
        self.todo_tabview.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # Create sub-tabs (titles will be updated with counts)
        self.todo_contact_tab = self.todo_tabview.add("Contact Info")
        self.todo_services_tab = self.todo_tabview.add("Services/Materials")
        self.todo_durations_tab = self.todo_tabview.add("Unusual Durations")
        self.todo_flagged_tab = self.todo_tabview.add("Flagged Visits")

        # Configure each sub-tab
        for tab in [self.todo_contact_tab, self.todo_services_tab, self.todo_durations_tab, self.todo_flagged_tab]:
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)

        # Create scrollable frames for each sub-tab
        self.todo_contact_scroll = ctk.CTkScrollableFrame(self.todo_contact_tab)
        self.todo_contact_scroll.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.todo_contact_scroll.grid_columnconfigure(0, weight=1)

        self.todo_services_scroll = ctk.CTkScrollableFrame(self.todo_services_tab)
        self.todo_services_scroll.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.todo_services_scroll.grid_columnconfigure(0, weight=1)

        self.todo_durations_scroll = ctk.CTkScrollableFrame(self.todo_durations_tab)
        self.todo_durations_scroll.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.todo_durations_scroll.grid_columnconfigure(0, weight=1)

        self.todo_flagged_scroll = ctk.CTkScrollableFrame(self.todo_flagged_tab)
        self.todo_flagged_scroll.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.todo_flagged_scroll.grid_columnconfigure(0, weight=1)

        # Load all issues
        self.refresh_todo_list()

    def refresh_todo_list(self):
        """Refresh the list of to-do items: visits needing review, anomalous durations, and missing client data."""
        # Clear all sub-tab scrollable frames
        for widget in self.todo_contact_scroll.winfo_children():
            widget.destroy()
        for widget in self.todo_services_scroll.winfo_children():
            widget.destroy()
        for widget in self.todo_durations_scroll.winfo_children():
            widget.destroy()
        for widget in self.todo_flagged_scroll.winfo_children():
            widget.destroy()

        # Get all to-do data
        flagged_visits = self.db.get_visits_needing_review()
        anomalous_visits = self.db.get_visits_with_anomalous_durations(threshold_percent=300.0)
        missing_data_clients = self.db.get_clients_missing_services_materials()
        missing_contact_clients = self.db.get_clients_missing_contact_info()

        # Update sub-tab titles with counts
        contact_count = len(missing_contact_clients)
        services_count = len(missing_data_clients)
        durations_count = len(anomalous_visits)
        flagged_count = len(flagged_visits)

        # Rename tabs with counts
        self.todo_tabview._segmented_button._buttons_dict["Contact Info"].configure(
            text=f"Contact Info ! ({contact_count})" if contact_count > 0 else "Contact Info"
        )
        self.todo_tabview._segmented_button._buttons_dict["Services/Materials"].configure(
            text=f"Services/Materials ! ({services_count})" if services_count > 0 else "Services/Materials"
        )
        self.todo_tabview._segmented_button._buttons_dict["Unusual Durations"].configure(
            text=f"Unusual Durations ! ({durations_count})" if durations_count > 0 else "Unusual Durations"
        )
        self.todo_tabview._segmented_button._buttons_dict["Flagged Visits"].configure(
            text=f"Flagged Visits ! ({flagged_count})" if flagged_count > 0 else "Flagged Visits"
        )

        # Populate Contact Info tab
        if missing_contact_clients:
            desc_label = ctk.CTkLabel(
                self.todo_contact_scroll,
                text="These clients are missing email, phone, or address information",
                font=ctk.CTkFont(size=11),
                text_color="gray"
            )
            desc_label.grid(row=0, column=0, sticky="w", padx=10, pady=(5, 10))

            for idx, client in enumerate(missing_contact_clients):
                self.create_missing_contact_card(self.todo_contact_scroll, client, idx + 1)
        else:
            no_issues = ctk.CTkLabel(
                self.todo_contact_scroll,
                text="All clients have complete contact information!",
                font=ctk.CTkFont(size=14),
                text_color="#5FA777"
            )
            no_issues.grid(row=0, column=0, pady=50)

        # Populate Services/Materials tab
        if missing_data_clients:
            desc_label = ctk.CTkLabel(
                self.todo_services_scroll,
                text="These clients don't have any configured services/materials",
                font=ctk.CTkFont(size=11),
                text_color="gray"
            )
            desc_label.grid(row=0, column=0, sticky="w", padx=10, pady=(5, 10))

            for idx, client in enumerate(missing_data_clients):
                self.create_missing_data_card(self.todo_services_scroll, client, idx + 1)
        else:
            no_issues = ctk.CTkLabel(
                self.todo_services_scroll,
                text="All clients have configured services/materials!",
                font=ctk.CTkFont(size=14),
                text_color="#5FA777"
            )
            no_issues.grid(row=0, column=0, pady=50)

        # Populate Unusual Durations tab
        if anomalous_visits:
            desc_label = ctk.CTkLabel(
                self.todo_durations_scroll,
                text="These visits are 3x+ longer than usual for the client (possible time entry errors)",
                font=ctk.CTkFont(size=11),
                text_color="gray"
            )
            desc_label.grid(row=0, column=0, sticky="w", padx=10, pady=(5, 10))

            for idx, visit in enumerate(anomalous_visits):
                self.create_anomaly_card(self.todo_durations_scroll, visit, idx + 1)
        else:
            no_issues = ctk.CTkLabel(
                self.todo_durations_scroll,
                text="No unusual visit durations detected!",
                font=ctk.CTkFont(size=14),
                text_color="#5FA777"
            )
            no_issues.grid(row=0, column=0, pady=50)

        # Populate Flagged Visits tab
        if flagged_visits:
            desc_label = ctk.CTkLabel(
                self.todo_flagged_scroll,
                text="These visits have been manually flagged for review",
                font=ctk.CTkFont(size=11),
                text_color="gray"
            )
            desc_label.grid(row=0, column=0, sticky="w", padx=10, pady=(5, 10))

            for idx, visit in enumerate(flagged_visits):
                self.create_review_card(self.todo_flagged_scroll, visit, idx + 1)
        else:
            no_issues = ctk.CTkLabel(
                self.todo_flagged_scroll,
                text="No flagged visits!",
                font=ctk.CTkFont(size=14),
                text_color="#5FA777"
            )
            no_issues.grid(row=0, column=0, pady=50)

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
        self.refresh_todo_list()

    def delete_anomalous_visit(self, visit_id):
        """Delete a visit with anomalous duration."""
        self.db.delete_visit(visit_id)
        self.refresh_todo_list()
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
            self.refresh_todo_list()
            self.refresh_dashboard()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update visit: {str(e)}")

    def delete_flagged_visit(self, visit_id):
        """Delete a flagged visit."""
        if messagebox.askyesno("Confirm Delete", "Delete this flagged visit?"):
            self.db.delete_visit(visit_id)
            messagebox.showinfo("Success", "Visit deleted")
            self.refresh_todo_list()
            self.refresh_dashboard()

    def create_missing_data_card(self, parent, client, row):
        """Create a card for a client missing services/materials."""
        card = ctk.CTkFrame(parent, border_width=2, border_color="#7B9EB5")
        card.grid(row=row, column=0, sticky="ew", padx=10, pady=8)
        card.grid_columnconfigure(1, weight=1)

        # Header with client name
        header_label = ctk.CTkLabel(
            card,
            text=f"📝 {client['name']}",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#7B9EB5"
        )
        header_label.grid(row=0, column=0, columnspan=4, sticky="w", padx=12, pady=(10, 8))

        # Info label
        info_label = ctk.CTkLabel(
            card,
            text="This client has no configured services or materials",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        info_label.grid(row=1, column=0, columnspan=4, sticky="w", padx=12, pady=(0, 8))

        # Buttons
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.grid(row=2, column=0, columnspan=4, sticky="w", padx=12, pady=(0, 10))

        add_btn = ctk.CTkButton(
            btn_frame,
            text="Add Services/Materials",
            command=lambda: self.go_to_client_materials(client['id'], client['name']),
            font=ctk.CTkFont(size=11),
            height=30,
            fg_color="#5FA777"
        )
        add_btn.pack(side=tk.LEFT, padx=4)

        no_services_btn = ctk.CTkButton(
            btn_frame,
            text="Client Doesn't Need Additional Services",
            command=lambda: self.mark_client_no_services(client['id']),
            font=ctk.CTkFont(size=11),
            height=30,
            fg_color="gray"
        )
        no_services_btn.pack(side=tk.LEFT, padx=4)

    def create_missing_contact_card(self, parent, client, row):
        """Create a card for a client missing contact information."""
        card = ctk.CTkFrame(parent, border_width=2, border_color="#B8860B")
        card.grid(row=row, column=0, sticky="ew", padx=10, pady=8)
        card.grid_columnconfigure(1, weight=1)

        # Header with client name
        header_label = ctk.CTkLabel(
            card,
            text=f"📞 {client['name']}",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#B8860B"
        )
        header_label.grid(row=0, column=0, columnspan=4, sticky="w", padx=12, pady=(10, 8))

        # Show what's missing
        missing_items = []
        if not client.get('email'):
            missing_items.append("Email")
        if not client.get('phone'):
            missing_items.append("Phone")
        if not client.get('address'):
            missing_items.append("Address")

        info_text = f"Missing: {', '.join(missing_items)}"
        info_label = ctk.CTkLabel(
            card,
            text=info_text,
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        info_label.grid(row=1, column=0, columnspan=4, sticky="w", padx=12, pady=(0, 8))

        # Button
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.grid(row=2, column=0, columnspan=4, sticky="w", padx=12, pady=(0, 10))

        edit_btn = ctk.CTkButton(
            btn_frame,
            text="Fill in Contact Information",
            command=lambda: self.go_to_client_contact(client['id']),
            font=ctk.CTkFont(size=11),
            height=30,
            fg_color="#B8860B"
        )
        edit_btn.pack(side=tk.LEFT, padx=4)

    def go_to_client_contact(self, client_id):
        """Navigate to client contact information."""
        # Switch to Clients tab
        self.tabview.set("Clients")
        # Refresh client list and show this specific client's info
        self.refresh_clients_list()
        self.show_client_details(client_id)

    def go_to_client_materials(self, client_id, client_name):
        """Navigate to client materials configuration."""
        # Switch to Clients tab
        self.tabview.set("Clients")
        # Refresh client list and show this specific client's info
        self.refresh_clients_list()
        self.show_client_details(client_id)

    def mark_client_no_services(self, client_id):
        """Mark a client as not needing additional services/materials."""
        self.db.set_client_no_additional_services(client_id, True)
        self.refresh_todo_list()

    def toggle_client_no_services(self, client_id, value):
        """Toggle whether a client needs additional services/materials."""
        self.db.set_client_no_additional_services(client_id, value)
        self.refresh_todo_list()

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
        scroll_frame._parent_canvas.configure(yscrollincrement=20)

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
            text="Import client and visit data from Excel files.\nUse 'Scan Image' button in Visits tab to import from paper records.",
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

        instructions = ctk.CTkTextbox(self.tab_import, height=300)
        instructions.grid(row=4, column=0, sticky="ew", padx=20, pady=20)
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

Image Scanning Instructions:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Go to Visits tab and click "Scan Image" button
2. Select clear photos of your paper records
3. Gemini AI will extract visit data automatically
4. Review and correct any extracted data
5. Save verified data to the database

Note: Requires Gemini API key (configure in Settings)
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
        visits_scroll._parent_canvas.configure(yscrollincrement=20)

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
        dialog.geometry("500x650")
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

        # Gemini API Key Setting (for image scanning)
        gemini_frame = ctk.CTkFrame(scroll_frame)
        gemini_frame.pack(pady=8, padx=10, fill="x")

        gemini_label = ctk.CTkLabel(
            gemini_frame,
            text="Gemini API Key (for Image Scanning):",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        gemini_label.pack(pady=(8, 3), padx=10, anchor="w")

        gemini_entry = ctk.CTkEntry(
            gemini_frame,
            placeholder_text="Get free API key from https://aistudio.google.com/app/apikey",
            height=30,
            show="*"  # Hide the API key
        )
        gemini_entry.pack(pady=3, padx=10, fill="x")

        # Load current value
        current_gemini_key = self.db.get_setting('gemini_api_key', '')
        if current_gemini_key:
            gemini_entry.insert(0, current_gemini_key)

        gemini_help = ctk.CTkLabel(
            gemini_frame,
            text="Gemini AI provides superior image recognition for handwritten visit tables. Free tier: 15 requests/minute.\nGet your free API key: https://aistudio.google.com/app/apikey",
            font=ctk.CTkFont(size=9),
            text_color="gray",
            wraplength=700,
            justify="left"
        )
        gemini_help.pack(pady=(0, 8), padx=10, anchor="w")

        # Working Year Setting
        year_frame = ctk.CTkFrame(scroll_frame)
        year_frame.pack(pady=8, padx=10, fill="x")

        year_label = ctk.CTkLabel(
            year_frame,
            text="Working Year:",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        year_label.pack(pady=(8, 3), padx=10, anchor="w")

        current_working_year = self.db.get_setting('working_year', str(datetime.now().year))
        year_var = tk.StringVar(value=current_working_year)

        # Generate year options (current year and 5 years back)
        current_year = datetime.now().year
        year_options = [str(current_year - i) for i in range(6)]

        year_menu = ctk.CTkOptionMenu(
            year_frame,
            variable=year_var,
            values=year_options,
            height=30,
            font=ctk.CTkFont(size=11)
        )
        year_menu.pack(pady=3, padx=10, fill="x")

        year_help = ctk.CTkLabel(
            year_frame,
            text="Select which year's data to view and export in PDFs",
            font=ctk.CTkFont(size=9),
            text_color="gray"
        )
        year_help.pack(pady=(0, 8), padx=10)

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

                # Save Gemini API key
                gemini_key = gemini_entry.get().strip()
                self.db.set_setting('gemini_api_key', gemini_key)
                # Reset image parser to pick up new API key
                self.image_parser = None

                # Save working year
                new_year = year_var.get()
                old_year = self.db.get_setting('working_year', str(datetime.now().year))
                self.db.set_setting('working_year', new_year)

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
        self.refresh_todo_list()
        messagebox.showinfo("Refreshed", "All data refreshed successfully!")

    def on_closing(self):
        """Handle application closing."""
        # Clean up mobile server
        try:
            self.mobile_server.stop()
            self.mobile_server.cleanup()
        except:
            pass
        self.db.close()
        self.destroy()


if __name__ == "__main__":
    # Show splash screen
    splash = SplashScreen()

    # Function to initialize main app after a brief delay
    def start_main_app():
        # Close splash screen
        splash.close()

        # Create and run main application
        app = LandscapingApp()
        app.protocol("WM_DELETE_WINDOW", app.on_closing)
        app.mainloop()

    # Give splash screen time to display (1.5 seconds)
    splash.splash.after(1500, start_main_app)
    splash.splash.mainloop()
