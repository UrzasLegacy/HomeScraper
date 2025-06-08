import time
import urllib
import os

from datetime import datetime
import pandas as pd
import requests
from geopy.distance import distance as geo_distance
from homeharvest import scrape_property


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


def filter_properties(properties_df: pd.DataFrame):
    """Filter properties based on specific criteria."""

    # if distance_miles doesnt exist in dataframe, add it with a default value
    if "distance_miles" not in properties_df.columns:
        properties_df["distance_miles"] = 0.0

    properties_df = properties_df[properties_df["hoa_fee"] == 0] # Filter out properties with HOA fees
    properties_df = properties_df[properties_df['list_price'] <= PRICE_MAX]  # Filter out properties with price > PRICE_MAX
    properties_df = properties_df[properties_df["distance_miles"] <= MAX_DISTANCE_MILES]

    return properties_df


def sort_properties(properties_df: pd.DataFrame):
    """Sort properties based on specific criteria."""

    # if "distance_miles" not in properties_df.columns:
    #     properties_df["distance_miles"] = 0.0

    #properties_df = properties_df.sort_values("distance_miles")
    #properties_df = properties_df.sort_values("list_price", ascending=True)

    # sort by list date
    if "list_date" in properties_df.columns:
        properties_df = properties_df.sort_values("list_date", ascending=False)
    return properties_df


def send_to_discord(content, debug=DEBUG):
    if debug:
        print(f"Sending to Discord: {content}")
    if not DISCORD_PUSH:
        return 200
    data = {
        "content": content
    }
    response = requests.post(WEBHOOK, json=data)
    return response.status_code


def build_google_maps_url(latitude, longitude):
    """ Build a Google Maps URL for the given latitude and longitude."""
    return f"https://www.google.com/maps/search/?api=1&query={latitude},{longitude}"


def build_google_maps_url_from_address(address):
  """ Build a Google Maps URL for the given street address (non-API URL)."""
  base_url = "https://www.google.com/maps/search/"
  return base_url + urllib.parse.quote(address)


def format_listings(properties_df, max_paddings=None):
    """ Format the listings DataFrame into a string for Discord display."""
    df = compute_fields_for_display(properties_df)

    # Format each row with padding
    lines = []
    for _, row in df.iterrows():
        line = (
            f"[🔗](<{row['property_url']}>) [:map:](<{build_google_maps_url_from_address(row['address'])}>) `"
            + row["address"].ljust(max_paddings["address"]) + " | "
            + row["price"].ljust(max_paddings["price"]) + " | "
            + f"🛏 {row['beds'].ljust(max_paddings['beds'])} | "
            + f"🛁 {row['baths'].ljust(max_paddings['baths'])} | "
            + row["sqft"].ljust(max_paddings["sqft"]) + " | "
            + "Built: " + row["year"].ljust(max_paddings["year"]) + " | "
            + row["style"].ljust(max_paddings["style"]) + " | "
            + "Lot: " + row["lot"].ljust(max_paddings["lot"]) + " | "
            + "🅿️  " + row["parking"].ljust(max_paddings["parking"]) + " | "
            + "Distance: " + row["distance_miles"].ljust(max_paddings["distance_miles"]) + 'mi`'
        )
        lines.append(f"{line}")

    return f".\n{'\n'.join(lines)}\n"


def compute_fields_for_display(properties_df: pd.DataFrame) -> pd.DataFrame:
    df = properties_df.head().copy()

    if "distance_miles" in df.columns:
        df["distance_miles"] = pd.to_numeric(df["distance_miles"], errors='coerce').fillna(0).astype(float).round(1).astype(str)
    else:
        df["distance_miles"] = "N/A"

    df = df.infer_objects(copy=False)
    df["address"] = df["street"] + ", " + df["city"] + ", " + df["state"] + " " + df["zip_code"].astype(str)
    df["price"] = "$" + pd.to_numeric(df["list_price"], errors='coerce').fillna(0).astype(int).map(lambda x: f"{x:,}")
    df["beds"] = pd.to_numeric(df["beds"], errors='coerce').fillna(0).astype(int).astype(str)
    df["baths"] = (pd.to_numeric(df["full_baths"], errors='coerce').fillna(0).astype(int) + 0.5 * pd.to_numeric(df["half_baths"], errors='coerce').fillna(0).astype(int)).astype(str)
    df["sqft"] = pd.to_numeric(df["sqft"], errors='coerce').fillna(0).astype(int).astype(str) + " sqft"
    df["year"] = pd.to_numeric(df["year_built"], errors='coerce').fillna(0).astype(int).astype(str)
    df["style"] = df["style"].fillna("")
    df["lot"] = df["lot_sqft"].fillna(0).astype(int).astype(str) + " sqft"
    df["parking"] = df["parking_garage"].fillna("—").astype(str)
    df["property_url"] = df["property_url"].fillna("#")

    return df


def get_max_padding(properties_df: pd.DataFrame):
    """
    Get the maximum padding required for each column in the DataFrame.
    """

    df = compute_fields_for_display(properties_df)

    col_widths = {
        "address": df["address"].map(len).max() + 10,
        "price": df["price"].map(len).max() + 1,
        "beds": df["beds"].map(len).max(),
        "baths": df["baths"].map(len).max() + 1,
        "sqft": df["sqft"].map(len).max() + 1,
        "year": df["year"].map(len).max(),
        "style": df["style"].map(len).max(),
        "lot": df["lot"].map(len).max() + 1,
        "parking": df["parking"].map(len).max(),
        "distance_miles": df["distance_miles"].map(len).max() + 1,
    }

    return col_widths


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


def chunk_dataframe(df, chunk_size=5, chunk_limit=None):
    """Yield successive chunk_size-sized chunks from a DataFrame."""
    if chunk_limit is None:
        chunk_limit = len(df)
    for i in range(0, chunk_limit, chunk_size):
        yield df.iloc[i:i + chunk_size]


def build_listings_header(total, matched, max_price, max_distance):
    # top =    "╔" + "═" + "╗"
    # title =  "║ BEGIN LISTINGS REPORT" + "║"
    # middle = "╠" + "═" + "╣"
    # line1 =  f"║ Total listings searched: {total}" + "║"
    # line2 =  f"║ Matching filters:        {matched}" + "║"
    # bottom = "╚" + "╝"
    # message_list = [top, title, middle, line1, line2, bottom]

    spacing_adjust = 51 # len(max(message_list, key=len))

    top =    "╔" + "═" * spacing_adjust + "╗"
    title =  "║ BEGIN LISTINGS REPORT".ljust(spacing_adjust + 1) + "║"
    middle = "╠" + "═" * spacing_adjust + "╣"
    line1 =  f"║ Total listings searched: {total}".ljust(spacing_adjust + 1) + "║"
    line2 =  f"║ Matching filters:        {matched}".ljust(spacing_adjust + 1) + "║"
    bottom = "╚" + "═" * spacing_adjust + "╝"

    return ".`\n" + "\n".join([top, title, middle, line1, line2, bottom]) + '`'


def main():
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
        mls_only=True,  # only fetch MLS listings
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

if __name__ == "__main__":
    main()