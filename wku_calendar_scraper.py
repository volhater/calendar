import os
import re
from datetime import datetime, time
import requests
from bs4 import BeautifulSoup
from icalendar import Calendar, Event
from dateutil import parser
import zoneinfo  # Built-in in Python 3.9+

URL = "https://www.wku.edu/registrar/academic_calendars/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

# Define WKU local timezone (Central Time)
CENTRAL_TZ = zoneinfo.ZoneInfo("America/Chicago")

def fetch_and_parse_calendar():
    response = requests.get(URL, headers=HEADERS)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, "html.parser")
    cal = Calendar()
    cal.add('prodid', '-//WKU Academic Calendar Scraper//wku.edu//')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'WKU Academic Calendar')

    content = soup.find("div", {"id": "content"}) or soup.body
    items = content.find_all(["li", "p", "tr"])

    date_pattern = re.compile(
        r'([A-Za-z]+,?\s+)?([A-Za-z]+)\s+(\d{1,2})(?:\s*-\s*\d{1,2})?(?:,?\s+(\d{4}))?'
    )

    current_year = datetime.now().year

    for item in items:
        text = item.get_text(strip=True)
        if not text or len(text) < 10:
            continue
            
        match = date_pattern.search(text)
        if match:
            try:
                full_match = match.group(0)
                event_title = text.replace(full_match, "").strip(" ,:-")
                
                month_str = match.group(2)
                day_str = match.group(3)
                year_str = match.group(4) if match.group(4) else str(current_year)

                date_string = f"{month_str} {day_str} {year_str}"
                parsed_date = parser.parse(date_string).date()

                if not event_title:
                    continue

                # COMBINE DATE WITH 7:00 AM AND 4:30 PM TIME SLOTS
                dt_start = datetime.combine(parsed_date, time(7, 0, 0), tzinfo=CENTRAL_TZ)
                dt_end = datetime.combine(parsed_date, time(16, 30, 0), tzinfo=CENTRAL_TZ)

                event = Event()
                event.add('summary', f"WKU: {event_title}")
                event.add('dtstart', dt_start)
                event.add('dtend', dt_end)
                event.add('description', f"Source: {URL}")
                event.add('uid', f"{parsed_date}-{hash(event_title)}@wku.edu")

                cal.add_component(event)
            except Exception:
                continue

    # Ensure output directory exists
    output_dir = "site"
    os.makedirs(output_dir, exist_ok=True)

    # Save .ics file
    ics_path = os.path.join(output_dir, "wku_academic_calendar.ics")
    with open(ics_path, 'wb') as f:
        f.write(cal.to_ical())

    # Save index.html
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>WKU Academic Calendar Subscription</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 600px; margin: 40px auto; padding: 20px; line-height: 1.6; }}
        code {{ background: #f4f4f4; padding: 4px 8px; border-radius: 4px; font-size: 0.9em; word-break: break-all; }}
        a.btn {{ display: inline-block; background: #b01c2e; color: #fff; padding: 10px 18px; border-radius: 6px; text-decoration: none; font-weight: bold; margin-top: 10px; }}
    </style>
</head>
<body>
    <h2>WKU Academic Calendar (.ics Feed)</h2>
    <p>This calendar feed is automatically scraped and updated weekly from the official WKU Registrar page.</p>
    <p><strong>Subscription URL:</strong></p>
    <p><code>https://{os.getenv("GITHUB_REPOSITORY_OWNER", "username")}.github.io/{os.getenv("GITHUB_REPOSITORY_NAME", "repo")}/wku_academic_calendar.ics</code></p>
    <p><a class="btn" href="wku_academic_calendar.ics">Download .ics File</a></p>
    <p><small>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}</small></p>
</body>
</html>
"""
    with open(os.path.join(output_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html_content)

    print("Success! Generated site folder with timed .ics events and index.html")

if __name__ == "__main__":
    fetch_and_parse_calendar()
