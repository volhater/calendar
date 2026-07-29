import os
import re
from datetime import datetime, time, timedelta
import requests
from bs4 import BeautifulSoup
from icalendar import Calendar, Event
from dateutil import parser
import zoneinfo

URL = "https://www.wku.edu/hr/tools/holidays.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

CENTRAL_TZ = zoneinfo.ZoneInfo("America/Chicago")

def parse_date_range(date_str):
    """
    Parses HR holiday date strings such as:
    - "Monday, September 7, 2026"
    - "Monday, October 5 - Tuesday, October 6, 2026"
    - "Monday, December 21, 2026 - Friday, January 1, 2027"
    Returns (start_date, end_date)
    """
    # Clean up excess spaces/newlines
    clean_str = re.sub(r'\s+', ' ', date_str).strip()
    
    if '-' in clean_str:
        parts = clean_str.split('-')
        start_part = parts[0].strip()
        end_part = parts[1].strip()
        
        # Extract the year from the string (defaults to end_part year or current year)
        year_match = re.search(r'\b(20\d{2})\b', clean_str)
        year_str = year_match.group(1) if year_match else str(datetime.now().year)
        
        # Ensure year is present on both parts for accurate dateutil parsing
        if not re.search(r'\b20\d{2}\b', start_part):
            start_part = f"{start_part}, {year_str}"
        if not re.search(r'\b20\d{2}\b', end_part):
            end_part = f"{end_part}, {year_str}"
            
        start_dt = parser.parse(start_part).date()
        end_dt = parser.parse(end_part).date()
        return start_dt, end_dt
    else:
        # Single day holiday
        single_dt = parser.parse(clean_str).date()
        return single_dt, single_dt

def fetch_and_parse_holidays():
    response = requests.get(URL, headers=HEADERS)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, "html.parser")
    cal = Calendar()
    cal.add('prodid', '-//WKU HR Holiday Scraper//wku.edu//')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'WKU Staff Holidays')

    # Locate table or list elements on the HR page
    rows = soup.find_all("tr")
    
    processed_events = 0

    for row in rows:
        cols = row.find_all(["td", "th"])
        if len(cols) < 2:
            continue
            
        col_text_0 = cols[0].get_text(strip=True)
        col_text_1 = cols[1].get_text(strip=True)
        
        # Determine which column is Date and which is Event Name
        if any(char.isdigit() for char in col_text_0):
            date_raw, title_raw = col_text_0, col_text_1
        elif any(char.isdigit() for char in col_text_1):
            title_raw, date_raw = col_text_0, col_text_1
        else:
            continue # Header row or non-date row
            
        try:
            start_date, end_date = parse_date_range(date_raw)
            
            # Iterate through each day in the date range
            current_date = start_date
            while current_date <= end_date:
                # 0 = Monday, 4 = Friday, 5 = Saturday, 6 = Sunday
                # ONLY create events for business days (Monday-Friday)
                if current_date.weekday() < 5:
                    dt_start = datetime.combine(current_date, time(7, 0, 0), tzinfo=CENTRAL_TZ)
                    dt_end = datetime.combine(current_date, time(16, 30, 0), tzinfo=CENTRAL_TZ)

                    event = Event()
                    event.add('summary', f"WKU Holiday: {title_raw}")
                    event.add('dtstart', dt_start)
                    event.add('dtend', dt_end)
                    event.add('description', f"WKU HR Holiday Closure: {title_raw}\nSource: {URL}")
                    event.add('uid', f"{current_date}-{hash(title_raw)}@wku.edu")

                    cal.add_component(event)
                    processed_events += 1
                    
                current_date += timedelta(days=1)
                
        except Exception as e:
            print(f"Skipping row due to parse error: '{date_raw}' -> {e}")
            continue

    # Ensure output directory exists
    output_dir = "site"
    os.makedirs(output_dir, exist_ok=True)

    # Save .ics file
    ics_path = os.path.join(output_dir, "wku_staff_holidays.ics")
    with open(ics_path, 'wb') as f:
        f.write(cal.to_ical())

    # Save HTML landing page
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>WKU Staff Holiday Calendar</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 600px; margin: 40px auto; padding: 20px; line-height: 1.6; }}
        code {{ background: #f4f4f4; padding: 4px 8px; border-radius: 4px; font-size: 0.9em; word-break: break-all; }}
        a.btn {{ display: inline-block; background: #b01c2e; color: #fff; padding: 10px 18px; border-radius: 6px; text-decoration: none; font-weight: bold; margin-top: 10px; }}
    </style>
</head>
<body>
    <h2>WKU Staff Holiday Calendar (.ics Feed)</h2>
    <p>Includes all staff holiday closures block-scheduled for business days (7:00 AM - 4:30 PM).</p>
    <p><strong>Subscription URL:</strong></p>
    <p><code>https://{os.getenv("GITHUB_REPOSITORY_OWNER", "username")}.github.io/{os.getenv("GITHUB_REPOSITORY_NAME", "repo")}/wku_staff_holidays.ics</code></p>
    <p><a class="btn" href="wku_staff_holidays.ics">Download .ics File</a></p>
    <p><small>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}</small></p>
</body>
</html>
"""
    with open(os.path.join(output_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Success! Generated feed with {processed_events} business-day holiday entries.")

if __name__ == "__main__":
    fetch_and_parse_holidays()
