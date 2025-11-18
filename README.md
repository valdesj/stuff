# 🌿 Landscaping Client Tracker

A modern desktop application for managing landscaping clients, tracking visits, and analyzing profitability.

## Features

### 📊 Client Dashboard
- Visual overview of all active clients
- Profit/loss indicators (green for profitable, red for losing money)
- Automatic calculation of costs per visit, per year, and per month
- Compare calculated costs against actual monthly charges

### 👥 Client Management
- Add, edit, and manage client information
- Soft delete (deactivate) clients to keep historical data
- Reactivate returning clients
- Hard delete option for duplicates
- Track client contact info, address, and monthly charges

### 🛠️ Materials & Services
- Global materials catalog with default costs
- Client-specific material pricing overrides
- Mark materials as global or custom
- Associate materials with specific clients
- Track units and descriptions

### 📅 Visit Tracking
- Record visits with date, start time, and end time
- Automatic duration calculation
- Track materials used during each visit
- Add notes to visit records
- Visual timeline of client visits

### 📥 Data Import
- **Excel Import**: Import clients, materials, and visits from Excel files
- **Excel Template**: Download a pre-formatted template for easy data entry
- **OCR Scanning**: Scan paper records and import visit data (requires pytesseract)
- Verification interface for reviewing scanned data before import

### 💰 Cost Analytics
- Average cost per visit
- Estimated visits per year (based on actual visit frequency)
- Calculated monthly cost
- Monthly profit/loss comparison
- Real-time profitability indicators

## Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

### Step 1: Clone or Download

```bash
git clone <repository-url>
cd stuff
```

### Step 2: Install Python Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: (Optional) Install OCR Support

For paper scanning functionality, install tesseract-ocr:

**Ubuntu/Debian:**
```bash
sudo apt-get install tesseract-ocr
```

**macOS:**
```bash
brew install tesseract
```

**Windows:**
Download and install from: https://github.com/UB-Mannheim/tesseract/wiki

## Usage

### Starting the Application

```bash
python main.py
```

### First-Time Setup

1. **Add Materials/Services**
   - Navigate to the "Materials" tab
   - Click "+ Add New Material/Service"
   - Enter name, cost, unit, and mark as global if applicable
   - Examples: Mulch ($5.50/bag), Fertilizer ($12.00/bag), Mowing Service ($45.00/service)

2. **Add Clients**
   - Navigate to the "Clients" tab
   - Click "+ Add New Client"
   - Fill in client information and monthly charge
   - Save the client

3. **Configure Client Materials**
   - Select a client from the list
   - Click "+ Add Material/Service"
   - Choose materials this client uses
   - Optionally set custom pricing for this client

4. **Record Visits**
   - Navigate to the "Visits" tab
   - Select a client from the dropdown
   - Click "+ Add New Visit"
   - Enter date, start time, and end time (duration calculates automatically)
   - Select materials used during the visit
   - Save the visit

### Importing Historical Data

#### From Excel:

1. Navigate to the "Import Data" tab
2. Click "📝 Download Excel Template"
3. Save and open the template in Excel
4. Fill in the three sheets:
   - **Clients**: Name, Email, Phone, Address, Monthly_Charge, Notes
   - **Materials**: Name, Cost, Unit, Is_Global, Description
   - **Visits**: Client_Name, Date, Start_Time, End_Time, Notes
5. Save the Excel file
6. Click "📄 Import from Excel"
7. Select your filled template
8. Review import results

#### From Paper Records (OCR):

1. Take clear photos or scans of your paper records
2. Navigate to the "Import Data" tab
3. Click "📷 Scan Paper Records"
4. Select one or more image files
5. Review and edit the detected data
6. Click "Save All Records"

### Understanding the Dashboard

The dashboard shows each client with:
- **Client Name**
- **Status**: ✓ PROFITABLE (green) or ⚠ LOSING MONEY (red)
- **Visits Recorded**: Total number of visits
- **Total Material Costs**: Sum of all materials used
- **Avg Cost per Visit**: Total costs / number of visits
- **Est. Visits/Year**: Projected annual visits based on actual frequency
- **Calculated Monthly Cost**: What you should charge based on actual costs
- **Actual Monthly Charge**: What you currently charge
- **Monthly Profit/Loss**: Difference between actual and calculated

### Managing Inactive Clients

**To Deactivate a Client:**
1. Go to "Clients" tab
2. Select the client
3. Click "Deactivate Client"
4. Client is hidden but data is preserved

**To View/Reactivate:**
1. Check "Show Inactive Clients"
2. Select the inactive client
3. Click "Reactivate Client"

## Database

The application uses **SQLite** for local storage. The database file `landscaping_tracker.db` is created automatically in the application directory.

### Database Schema

- **clients**: Client information and monthly charges
- **materials**: Global materials/services catalog
- **client_materials**: Client-specific material configurations
- **visits**: Visit records with dates and times
- **visit_materials**: Materials used during each visit

### Backup

To backup your data, simply copy `landscaping_tracker.db` to a safe location.

## Technical Details

### Built With

- **Python 3.8+**
- **CustomTkinter**: Modern UI framework
- **SQLite**: Local database
- **pandas**: Excel import/export
- **google-generativeai**: Gemini Vision API for image parsing
- **Pillow**: Image processing

### Project Structure

```
stuff/
├── main.py                    # Main application entry point
├── database.py                # Database layer and models
├── excel_importer.py          # Excel import functionality
├── gemini_vision.py           # Gemini Vision API for image parsing
├── requirements.txt           # Python dependencies
├── landscaping_tracker.db     # SQLite database (created on first run)
└── README.md                  # This file
```

## Tips for Older Users

The application is designed with larger fonts and clear buttons for easy use:

- **Large Text**: All text is sized for easy reading
- **Clear Labels**: Descriptive labels on all buttons and fields
- **Visual Indicators**: Green/red colors for profit/loss
- **Simple Navigation**: Tab-based interface for different sections
- **One Task at a Time**: Each screen focuses on a single task

## Troubleshooting

### Application won't start
- Ensure Python 3.8+ is installed: `python --version`
- Install all dependencies: `pip install -r requirements.txt`

### OCR scanning not available
- Install tesseract-ocr system package
- Verify pytesseract is installed: `pip install pytesseract`

### Import errors from Excel
- Ensure Excel file has the correct sheet names: "Clients", "Materials", "Visits"
- Check that required columns are present (see template)
- Dates should be in YYYY-MM-DD format
- Times should be in HH:MM format

### Database errors
- If database is corrupted, restore from backup
- Don't edit the .db file directly

## Future Enhancements

Potential features for future versions:
- Report generation (PDF)
- Calendar view for scheduled visits
- Email integration for client communication
- Multi-user support
- Cloud backup
- Mobile app companion

## License

This project is provided as-is for personal and commercial use.

## Support

For issues or questions, please refer to this README or check the application's built-in help.
