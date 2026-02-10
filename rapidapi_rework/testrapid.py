import requests
import json
import pandas as pd
import time

def parse_listing_details(details):
    """
    Parse the 'details' field from a Realtor API listing.

    Args:
        details (list): List of detail dictionaries from the API response.

    Returns:
        dict: Dictionary with keys as detail names and values as detail values.
    """

    output_dict: dict = {}
    for detail in details:
        category = detail.get("category")
        text = detail.get("text")
        if category and text:
            output_dict[category] = text
    return output_dict


def construct_listing_record(item):
    """
    Construct a dictionary record for a single listing item.

    Args:
        item (dict): A single listing item from the API response.

    Returns:
        dict: Dictionary with selected fields from the listing.
    """
    # Find the "best" estimate entry
    best_estimate_entry = next(
        (e for e in item.get("current_estimates", []) if e.get("isbest_homevalue")),
        {}
    )

    details = item.get("details", [])



    record = {
        "property_id":        item.get("property_id", "None"),
        "href":               item.get("href", "None"),
        "beds":               item["description"].get("beds", "None"),
        "baths":              item["description"].get("baths", "None"),
        "sqft":               item["description"].get("sqft", "None"),
        "lot_sqft":           item["description"].get("lot_sqft", "None"),
        "best_estimate":      best_estimate_entry.get("estimate", "None"),
        "best_estimate_date": best_estimate_entry.get("date", "None"),
        "list_price":         item.get("list_price", "None"),
        "status":             item.get("status", "None"),
        "listing_id":         item.get("listing_id", "None"),
    }
    return (record, details)

def parse_listings(json_data):
    """
    Parse Realtor API JSON response into a list of dictionaries.

    Args:
        json_data (str or dict): JSON string or loaded JSON dict from the API response.

    Returns:
        pandas.DataFrame: DataFrame with one row per property and selected fields.
    """
    # If json_data is a JSON string, load it into a dict
    if isinstance(json_data, str):
        data = json.loads(json_data)
    else:
        data = json_data

    results = data["data"]["results"]
    listings = []

    for item in results:
        listings.append(construct_listing_record(item))

    # Convert to DataFrame for easy analysis
    df = pd.DataFrame(listings)
    return (df, listings)

with open("realtor_rapidapi_data.json") as f:
    raw_json_object = json.load(f)
df = parse_listings(raw_json_object)
print(df)



## QUIT
quit()



url = "https://realtor-search.p.rapidapi.com/properties/search-buy"

querystring = {"location":"state:Massachusetts","sortBy":"relevance"}

headers = {
	"x-rapidapi-key": "b8f7e5901emsh0a13963c91d481ep141cb6jsnb9bf0cfd6db6",
	"x-rapidapi-host": "realtor-search.p.rapidapi.com"
}

response = requests.get(url, headers=headers, params=querystring)
json_data = response.json()

time_stamp_for_filename = time.strftime("%Y-%m-%d-%H%M")

with open(f'realtor_rapidapi_data_backup_{time_stamp_for_filename}.json', 'w') as f:
    json.dump(json_data, f, indent=4)

with open('realtor_rapidapi_data.json', 'w') as f:
    json.dump(json_data, f, indent=4)