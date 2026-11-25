"""Refresh public ECB reference rates only. Tax rules require reviewed changes."""
import json
import pathlib
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta

path = pathlib.Path("salarylens/rates.json")
data = json.loads(path.read_text())
url = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
with urllib.request.urlopen(url, timeout=30) as response:
    root = ET.fromstring(response.read())
cube = next((e for e in root.iter() if "time" in e.attrib), None)
if cube is None:
    raise ValueError("Missing ECB date")
day = date.fromisoformat(cube.attrib["time"])
if not date.today() - timedelta(days=10) <= day <= date.today():
    raise ValueError("ECB rates unexpectedly stale or future-dated")
rates = {"EUR": 1.0}
for child in cube:
    if child.attrib.get("currency") in {"AUD", "CHF"}:
        rates[child.attrib["currency"]] = float(child.attrib["rate"])
if set(rates) != {"EUR", "AUD", "CHF"} or not all(v > 0 for v in rates.values()):
    raise ValueError("Incomplete FX rates")
data["fx"] = {"date": day.isoformat(), "rates": rates, "source": url}
path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
