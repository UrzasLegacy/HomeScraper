from _dataclasses import Property, Address, Description, Details
import json
import requests
import time
from typing import List, Dict, Any

# https://rapidapi.com/ntd119/api/realtor-search/playground/apiendpoint_7799087b-495b-429c-9040-9b80ac90c34c

TESTING = True


class RealtorScraper:
    def __init__(self, mls_only: bool = False):
        self.mls_only = mls_only
        self.counter = 0
        self.API_URL = "https://realtor-search.p.rapidapi.com/"
        self.PROPERTY_URL = "https://www.realtor.com/realestateandhomes-detail/"

    def start_scrape(self, location: str, listing_type: str = "buy", sort_by: str = "relevance", page: int = 1) -> dict:
        if listing_type not in ["buy"]:
            raise ValueError("Invalid listing type. Must be 'buy'")

        if TESTING:
            response_json = read_json_from_file("realtor_rapid_api_data_example.json")
            print(response_json)
            return self._parse_general(response_json)

        endpoint = f"properties/search-{listing_type}"
        querystring = {
            "location": location,
            "sortBy": sort_by,
            "resultsPerPage": "50",
            "prices": ",350000",
            "bedrooms": "2",
            "maxHoaFeesPerMonth": 0,
            "page": page,
        }

        headers = {
            "x-rapidapi-key": "b8f7e5901emsh0a13963c91d481ep141cb6jsnb9bf0cfd6db6",
            "x-rapidapi-host": "realtor-search.p.rapidapi.com",
        }

        response = requests.get(self.API_URL + endpoint, headers=headers, params=querystring)

        if response.status_code != 200:
            raise Exception(f"API request failed with status code {response.status_code}")

        response_json = response.json()

        return self._parse_general(response_json)

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
        county = result["location"].get("county")

        return Address(
            street=street,
            unit=unit,
            city=city,
            state=state,
            zip=zip_code,
            county=county,
        )

    def _parse_description(self, result: dict) -> Description:
        if result is None or "description" not in result or result["description"] is None:
            return Description()

        description_data = result["description"]

        beds = description_data.get("beds")
        baths_full_calc = description_data.get("baths_full_calc")
        baths_half_calc = description_data.get("baths_half_calc")
        sqft = description_data.get("sqft")
        lot_sqft = description_data.get("lot_sqft")
        type = description_data.get("type")

        return Description(
            type=type,
            beds=beds,
            baths_full_calc=baths_full_calc,
            baths_half_calc=baths_half_calc,
            sqft=sqft,
            lot_sqft=lot_sqft,
        ).to_dict()


    def _parse_details(self, result: dict) -> Details:
        if result is None or "details" not in result or result["details"] is None:
            return Details()

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
                cat = cat.lower().replace(" ", "_")
                if not isinstance(texts, list):
                    texts = [str(texts)]
                result[cat] = texts
            return result

        details_raw = result.get("details", [])
        details_data = convert_details_format(details_raw)

        bedrooms = details_data.get("bedrooms")
        bathrooms = details_data.get("bathrooms")
        other_rooms = details_data.get("other_rooms")
        appliances = details_data.get("appliances")
        heating_and_cooling = details_data.get("heating_and_cooling")
        land_info = details_data.get("land_info")
        home_features = details_data.get("home_features")
        interior_features = details_data.get("interior_features")
        exterior_and_lot_features = details_data.get("exterior_and_lot_features")
        garage_and_parking = details_data.get("garage_and_parking")
        homeowners_association = details_data.get("homeowners_association")
        other_property_info = details_data.get("other_property_info")
        building_and_construction = details_data.get("building_and_construction")
        utilities = details_data.get("utilities")
        kitchen_and_dining = details_data.get("kitchen_and_dining")
        accessibility_features = details_data.get("accessibility_features")
        school_information = details_data.get("school_information")
        amenities_and_community_features = details_data.get("amenities_and_community_features")
        pool_and_spa = details_data.get("pool_and_spa")
        multi_unit_info = details_data.get("multi_unit_info")
        waterfront_and_water_access = details_data.get("waterfront_and_water_access")

        return Details(
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            other_rooms=other_rooms,
            appliances=appliances,
            heating_and_cooling=heating_and_cooling,
            land_info=land_info,
            home_features=home_features,
            interior_features=interior_features,
            exterior_and_lot_features=exterior_and_lot_features,
            garage_and_parking=garage_and_parking,
            homeowners_association=homeowners_association,
            other_property_info=other_property_info,
            building_and_construction=building_and_construction,
            utilities=utilities,
            kitchen_and_dining=kitchen_and_dining,
            accessibility_features=accessibility_features,
            school_information=school_information,
            amenities_and_community_features=amenities_and_community_features,
            pool_and_spa=pool_and_spa,
            multi_unit_info=multi_unit_info,
            waterfront_and_water_access=waterfront_and_water_access,
        ).to_dict()


    def _parse_general(self, response_json: dict) -> dict:
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

            exploded_details = self._parse_details(result)

            realty_property = Property(
                property_url=f"{self.PROPERTY_URL}{result['property_id']}",
                address=self._parse_address(result, search_type="general_search"),
                list_price=result["list_price"],
                list_date=(result["list_date"].split("T")[0] if result.get("list_date") else None),
                last_sold_date=result.get("last_sold_date"),
                last_sold_price = result.get("last_sold_price"),

                latitude=(result["location"]["address"]["coordinate"].get("lat") if able_to_get_lat_long else None),
                longitude=(result["location"]["address"]["coordinate"].get("lon") if able_to_get_lat_long else None),
                description=self._parse_description(result),
                details=exploded_details
            ).to_dict()
            properties.append(realty_property)

        output = {
            "total": response_json["data"]["total"],
            "properties": properties,
        }

        write_json_to_file(output)

        return output


def write_json_to_file(json_data: dict) -> None:
    time_stamp_for_filename = time.strftime("%Y-%m-%d-%H%M")
    with open(f"realtor_rapidapi_data_backup_{time_stamp_for_filename}.json", "w") as f:
        json.dump(json_data, f, indent=4)

    with open("realtor_rapidapi_data.json", "w") as f:
        json.dump(json_data, f, indent=4)


def read_json_from_file(file_path: str) -> dict:
    """
    Read JSON data from a file and return it as a dictionary.

    Args:
        file_path (str): Path to the JSON file.

    Returns:
        dict: Parsed JSON data.
    """
    with open(file_path, 'r') as file:
        return json.load(file)