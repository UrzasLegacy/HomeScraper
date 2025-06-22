import pandas as pd
from typing import List, Dict, Any

from _exceptions import InvalidListingType
from _dataclasses import Property

ordered_properties = [
    "property_url",
    "list_price",
    "sqft",
    "street",
    "unit",
    "city",
    "state",
    "zip_code",
    "beds",
    "full_baths",
    "half_baths",
    "year_built",
    "list_date",
    "lot_sqft",
    "price_per_sqft",
    "latitude",
    "longitude",
    "stories",
    "hoa_fee",
    "status",
]


def process_result(result: Property) -> pd.DataFrame:
    prop_data = {prop: None for prop in ordered_properties}
    prop_data.update(result.__dict__)

    if "address" in prop_data:
        address_data = prop_data["address"]
        prop_data["street"] = address_data.street
        prop_data["unit"] = address_data.unit
        prop_data["city"] = address_data.city
        prop_data["state"] = address_data.state
        prop_data["zip_code"] = address_data.zip

    prop_data["price_per_sqft"] = prop_data["prc_sqft"]

    description = result.description
    prop_data["style"] = description.style
    prop_data["beds"] = description.beds
    prop_data["full_baths"] = description.baths_full
    prop_data["half_baths"] = description.baths_half
    prop_data["sqft"] = description.sqft
    prop_data["lot_sqft"] = description.lot_sqft
    prop_data["sold_price"] = description.sold_price
    prop_data["year_built"] = description.year_built
    prop_data["parking_garage"] = description.garage
    prop_data["stories"] = description.stories

    properties_df = pd.DataFrame([prop_data])
    properties_df = properties_df.reindex(columns=ordered_properties)

    return properties_df[ordered_properties]


def convert_json_to_results(json_data: dict) -> list[Property]:
    if not json_data or "data" not in json_data or "results" not in json_data["data"]:
        raise InvalidListingType("Invalid JSON data structure")

    results = json_data["data"]["results"]
    properties = []

    for item in results:
        property_obj = Property(
            property_url=item.get("href", ""),
            address=item.get("address", {}),
            list_price=item.get("list_price", 0),
            list_date=item.get("list_date", ""),
            hoa_fee=item.get("hoa_fee", 0),
            description=item.get("description", {}),
            latitude=item.get("latitude", 0.0),
            longitude=item.get("longitude", 0.0),
        )
        properties.append(property_obj)

    return properties



def convert_details_format(data: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    Convert a list of {'category': str, 'text': List[str]} dicts
    into a single dict mapping category -> text list.
    """
    result: Dict[str, List[str]] = {}
    for entry in data:
        cat = entry.get("category")
        texts = entry.get("text", [])
        if cat is None:
            continue
        if not isinstance(texts, list):
            texts = [str(texts)]
        result[cat] = texts




    return result

# read json from file
