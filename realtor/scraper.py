from _dataclasses import Property, Address, Description
import json
import requests

url = "https://realtor-search.p.rapidapi.com/properties/search-buy"

querystring = {"location": "state:Massachusetts", "sortBy": "relevance"}

headers = {
    "x-rapidapi-key": "b8f7e5901emsh0a13963c91d481ep141cb6jsnb9bf0cfd6db6",
    "x-rapidapi-host": "realtor-search.p.rapidapi.com",
}

response = requests.get(url, headers=headers, params=querystring)
json_data = response.json()

time_stamp_for_filename = time.strftime("%Y-%m-%d-%H%M")

with open(f"realtor_rapidapi_data_backup_{time_stamp_for_filename}.json", "w") as f:
    json.dump(json_data, f, indent=4)

with open("realtor_rapidapi_data.json", "w") as f:
    json.dump(json_data, f, indent=4)


class RealtorScraper:
    def __init__(self, mls_only: bool = False):
        self.mls_only = mls_only
        self.counter = 0
        self.API_URL = "https://realtor-search.p.rapidapi.com/"
        self.PROPERTY_URL = "https://www.realtor.com/realestateandhomes-detail/"

    def start_scrape(self, location: str, listing_type: str = "buy", sort_by: str = "relevance") -> dict:
        if listing_type not in ["buy", "rent"]:
            raise ValueError("Invalid listing type. Must be 'buy' or 'rent'.")

        endpoint = f"properties/search-{listing_type}"
        querystring = {"location": location, "sortBy": sort_by}

        headers = {
            "x-rapidapi-key": "b8f7e5901emsh0a13963c91d481ep141cb6jsnb9bf0cfd6db6",
            "x-rapidapi-host": "realtor-search.p.rapidapi.com",
        }

        response = requests.get(self.API_URL + endpoint, headers=headers, params=querystring)

        if response.status_code != 200:
            raise Exception(f"API request failed with status code {response.status_code}")

        response_json = response.json()

        return self._parse_general_search(response_json)

    def _parse_coordinates(self, result: dict) -> tuple:
        if (
            result is None
            or "location" not in result
            or result["location"] is None
            or "address" not in result["location"]
            or result["location"]["address"] is None
            or "coordinate" not in result["location"]["address"]
            or result["location"]["address"]["coordinate"] is None
        ):
            return (None, None)

        coordinates = result["location"]["address"]["coordinate"]
        latitude = coordinates.get("lat")
        longitude = coordinates.get("lon")

        return (latitude, longitude)

    def _parse_address(self, result: dict, search_type: str) -> Address:
        if (
            result is None
            or "location" not in result
            or result["location"] is None
            or "address" not in result["location"]
            or result["location"]["address"] is None
        ):
            return Address()

        address_data = result["location"]["address"]

        street = address_data.get("line")
        unit = address_data.get("unit")
        city = address_data.get("city")
        state = address_data.get("state_code")
        zip_code = address_data.get("postal_code")

        return Address(
            street=street,
            unit=unit,
            city=city,
            state=state,
            zip=zip_code,
        )

    def _parse_description(self, result: dict) -> Description:
        if result is None or "description" not in result or result["description"] is None:
            return Description()

        description_data = result["description"]

        style = description_data.get("property_type")
        beds = description_data.get("beds")
        baths_full = description_data.get("baths_full")
        baths_half = description_data.get("baths_half")
        sqft = description_data.get("sqft")
        lot_sqft = description_data.get("lot_sqft")
        sold_price = description_data.get("sold_price")
        year_built = description_data.get("year_built")
        garage = description_data.get("garage")
        stories = description_data.get("stories")

        return Description(
            style=style,
            beds=beds,
            baths_full=baths_full,
            baths_half=baths_half,
            sqft=sqft,
            lot_sqft=lot_sqft,
            sold_price=sold_price,
            year_built=year_built,
            garage=garage,
            stories=stories,
        )

    def _parse_general_search(self, response_json: dict) -> dict:
        if (
            response_json is None
            or "data" not in response_json
            or response_json["data"] is None
            or "results" not in response_json["data"]
            or response_json["data"]["results"] is None
        ):
            return {"total": 0, "properties": []}

        properties: list[Property] = []

        for result in response_json["data"]["results"]:
            self.counter += 1
            mls = result["source"].get("id") if "source" in result and isinstance(result["source"], dict) else None

            if not mls and self.mls_only:
                continue

            able_to_get_lat_long = (
                result
                and result.get("location")
                and result["location"].get("address")
                and result["location"]["address"].get("coordinate")
            )

            realty_property = Property(
                mls=mls,
                mls_id=(
                    result["source"].get("listing_id")
                    if "source" in result and isinstance(result["source"], dict)
                    else None
                ),
                property_url=f"{self.PROPERTY_URL}{result['property_id']}",
                status=result["status"].upper(),
                list_price=result["list_price"],
                list_date=(result["list_date"].split("T")[0] if result.get("list_date") else None),
                prc_sqft=result.get("price_per_sqft"),
                last_sold_date=result.get("last_sold_date"),
                hoa_fee=(result["hoa"]["fee"] if result.get("hoa") and isinstance(result["hoa"], dict) else None),
                latitude=(result["location"]["address"]["coordinate"].get("lat") if able_to_get_lat_long else None),
                longitude=(result["location"]["address"]["coordinate"].get("lon") if able_to_get_lat_long else None),
                address=self._parse_address(result, search_type="general_search"),
                #: neighborhoods=self._parse_neighborhoods(result),
                description=self._parse_description(result),
            )
            properties.append(realty_property)

        return {
            "total": response_json["data"]["total"],
            "properties": properties,
        }
