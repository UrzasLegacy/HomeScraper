import datetime
import json
import os
import time
from datetime import datetime

import pandas as pd
from _dataclasses import Address, Description, Property
from _exceptions import InvalidListingType
from _utils import process_result
from scraper import RealtorScraper

from geopy.distance import distance as geo_distance


# Ensure the environment variable are set
if "HOUSE_WEBHOOK" not in os.environ:
    raise ValueError("Environment variable 'HOUSE_WEBHOOK' is not set. Please set it to your Discord webhook URL.")
if "CENTRAL_COORD" not in os.environ:
    raise ValueError("Environment variable 'CENTRAL_COORD' is not set. Please set it to your Discord webhook URL.")

CENTRAL_COORD = os.environ["CENTRAL_COORD"]  # Valley Communications
WEBHOOK = os.environ["HOUSE_WEBHOOK"]


PRICE_MAX = 350000
MAX_DISTANCE_MILES = 30  # Max distance from central point in miles
PAST_DAYS = 1  # Number of days to look back for listings
BUILD_CSV = True  # Set to True if you want to build a CSV file of the listings


WALMART_COORDS = [
    (42.1364441198502, -72.50701159161437),
    (42.17267481016297, -72.57376884396496),
    (42.108330001107944, -72.70833897965517),
    (42.341532730798555, -72.64372086093478),
    (42.3547725902552, -72.55253154057571),
]
DEBUG = False
MARKDOWN_OUTPUT = True
DISCORD_PUSH = True  # Set to False if you don't want to send messages to Discord


def main():
    current_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"HomeHarvest_{current_timestamp}.csv"
    scraper = RealtorScraper()

    results = scraper.start_scrape_location("state:Massachusetts", listing_type="buy", sort_by="newest")

    properties = results["properties"]
    total_listings = results["total"]

    # properties is dict {"total": int, "properties": list[Property]}

    with open("test_fetch.json", "w") as f:
        json.dump(properties, f, indent=4)


def get_row_distance(row):
    prop_coord = (row["latitude"], row["longitude"])
    return get_coords_distance(CENTRAL_COORD, prop_coord)


def get_coords_distance(coord1: tuple, coord2: tuple):
    """
    Calculate the distance between two coordinates using geopy.
    :param coord1: Tuple of (latitude, longitude) for the first coordinate.
    :param coord2: Tuple of (latitude, longitude) for the second coordinate.
    :return: Distance in miles.
    """
    return round(geo_distance(coord1, coord2).miles, 1)

def old():
    # Generate filename based on current timestamp
    current_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"HomeHarvest_{current_timestamp}.csv"

    properties_df = scrape_property(
        location="Massachusetts",
        listing_type="for_sale",  # or (for_sale, for_rent, pending)
        past_days=PAST_DAYS,  # sold in last 30 days - listed in last 30 days if (for_sale, for_rent)
        # property_type=['single_family','multi_family'],
        # date_from="2023-05-01", # alternative to past_days
        # date_to="2023-05-28",
        # foreclosure=True
        # mls_only=True,  # only fetch MLS listings
    )
    total_listings = len(properties_df)

    # Identify and store dropped entries (those with missing lat/lon)
    dropped_properties = properties_df[properties_df[["latitude", "longitude"]].isna().any(axis=1)]
    if not dropped_properties.empty:
        properties_df = properties_df.dropna(subset=["latitude", "longitude"])

    # Calculate distances for each property and add to DataFrame
    properties_df["distance_miles"] = properties_df.apply(get_row_distance, axis=1)

    # Filter properties
    properties_df = filter_properties(properties_df)
    properties_df = sort_properties(properties_df)

    # dropped_properties = filter_properties(dropped_properties)
    # dropped_properties = sort_properties(dropped_properties)

    if BUILD_CSV:
        properties_df.to_csv(filename, index=False)

    header = build_listings_header(
        total=total_listings,
        matched=len(properties_df),
        max_price=PRICE_MAX,
        max_distance=MAX_DISTANCE_MILES
    )

    full_message_string = header
    send_to_discord(header)
    max_paddings = get_max_padding(properties_df)

    for i, chunk in enumerate(chunk_dataframe(properties_df, chunk_size=5, chunk_limit=None), 1):
        message = format_listings(chunk, max_paddings)
        full_message_string += message
        send_to_discord(message)
        time.sleep(0.5)

    if not dropped_properties.empty:
        spacing_adjust = 51
        header = (
            ".`\n"
            "╔" + "═" * spacing_adjust + "╗\n"
            f"║ Dropped {len(dropped_properties)} properties due to missing coordinates:".ljust(spacing_adjust + 3) + "║"
            "\n╚" + "═" * spacing_adjust + "╝`"
        )
        send_to_discord(header)
        full_message_string += header

        for i, chunk in enumerate(chunk_dataframe(dropped_properties, chunk_size=5, chunk_limit=None), 1):
            message = format_listings(chunk, max_paddings)
            full_message_string += message
            send_to_discord(message)
            time.sleep(0.5)

    if MARKDOWN_OUTPUT:
        with open("output.md", "w", encoding="utf-8") as f:
            f.write(full_message_string)