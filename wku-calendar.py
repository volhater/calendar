import re
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from icalendar import Calendar, Event
from dateutil import parser

# URL to scrape
URL = "https://www.wku.edu/registrar/academic_calendars/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

def fetch_and_parse_calendar():
    response = requests.get(URL, headers=HEADERS)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, "html.parser")
    cal = Calendar()
    cal.add('prodid', '-//WKU Academic Calendar Scraper//wku.edu//')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'WKU Academic Calendar')

    # Find main content container
    content = soup.find("div", {"id": "content"}) or soup.body
    
    # Extract text lines / list items (WKU formats these as "Event Name, Day, Date" or "Event Name: Date")
    items = content.find_all(["li", "p", "tr"])

    # Regex patterns to isolate dates (e.g., "Monday, August 24", "October 5-6", "May 11")
    date_pattern = re.compile(
        r'([A-Za-z]+,?\s+)?([A-Za-z]+)\s+(\d{1,2})(?:\s*-\s*\d{1,2})?(?:,?\s+(\d{4}))?'
    )

    current_year = datetime.now().year

    for item in items:
        text = item.get_text(strip=True)
        if not text or len(text) < 10:
            continue
            
        # Look for date structures inside text lines
        match = date_pattern.search(text)
        if match:
            try:
                # Extract parts
                full_match = match.group(0)
                event_title = text.replace(full_match, "").strip(" ,:-")
                
                # If no year is explicitly attached to the line, infer based on month
                month_str = match.group(2)
                day_str = match.group(3)
                year_str = match.group(4) if match.group(4) else str(current_year)

                # Parse into standard Date object
                date_string = f"{month_str} {day_str} {year_str}"
                event_date = parser.parse(date_string).date()

                # Clean up title
                if not event_title:
                    continue

                # Build ICS Event
                event = Event()
                event.add('summary', f"WKU: {event_title}")
                event.add('dtstart', event_date)
                event.add('dtend', event_date)
                event.add('description', f"Source: {URL}")
                event.add('uid', f"{event_date}-{hash(event_title)}@wku.edu")

                cal.add_component(event)
            except Exception:
                # Skip lines that match regex but aren't valid calendar events
                continue

    # Write output to .ics file
    output_file = "wku_academic_calendar.ics"
    with open(output_file, 'wb') as f:
        f.write(cal.to_ical())
    
    print(f"Success! Calendar generated: {output_file}")

if __name__ == "__main__":
    fetch_and_parse_calendar()