from dataclasses import dataclass
from enum import Enum
from typing import Optional
from dataclasses import asdict


class SiteName(Enum):
    ZILLOW = "zillow"
    REDFIN = "redfin"
    REALTOR = "realtor.com"

    @classmethod
    def get_by_value(cls, value):
        for item in cls:
            if item.value == value:
                return item
        raise ValueError(f"{value} not found in {cls}")


@dataclass
class Address:
    street: str | None = None
    unit: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    county: str | None = None

    def to_dict(self):
        return asdict(self)

@dataclass
class Description:
    beds: int | None = None
    baths_full_calc: int | None = None
    baths_half_calc: int | None = None
    sqft: int | None = None
    lot_sqft: int | None = None
    type: str | None = None

    def to_dict(self):
        return asdict(self)


#stories, garage, year_built
@dataclass
class Details:
    homeowners_association: list[str] | None = None # Calculated Total Monthly Association Fees
    other_property_info: list[str] | None = None # zoning, parcel number, source property type, annual tax amount
    building_and_construction: list[str] | None = None # property age, year built, roof, house style,
    other_rooms: list[str] | None = None # basement description
    bedrooms: list[str] | None = None
    bathrooms: list[str] | None = None
    appliances: list[str] | None = None
    heating_and_cooling: list[str] | None = None
    land_info: list[str] | None = None
    home_features: list[str] | None = None
    interior_features: list[str] | None = None
    exterior_and_lot_features: list[str] | None = None
    garage_and_parking: list[str] | None = None
    utilities: list[str] | None = None
    kitchen_and_dining: list[str] | None = None
    accessibility_features: list[str] | None = None
    school_information: list[str] | None = None
    amenities_and_community_features: list[str] | None = None
    pool_and_spa: list[str] | None = None
    multi_unit_info: list[str] | None = None
    waterfront_and_water_access: list[str] | None = None

    def to_dict(self):
        return asdict(self)

@dataclass
class Property:
    property_url: str
    address: Address | None = None
    list_price: int | None = None
    list_date: str | None = None
    description: Description | None = None
    last_sold_date: str | None = None
    last_sold_price: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    estimate: int | None = None
    virtual_tour: str | None = None
    flags: list[str] | None = None
    street_view: str | None = None
    photos: list[str] | None = None
    details: Details | None = None

    def to_dict(self):
        return asdict(self)

