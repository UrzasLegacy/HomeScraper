from scraper import RealtorScraper
from _dataclasses import Property, Address, Description
import pandas as pd
from _utils import process_result
from _exceptions import InvalidListingType
import json


scraper = RealtorScraper()
results = scraper.start_scrape("state:Massachusetts", listing_type="buy", sort_by="newest")



with open("test_fetch.json", "w") as f:
    json.dump(results, f, indent=4)


