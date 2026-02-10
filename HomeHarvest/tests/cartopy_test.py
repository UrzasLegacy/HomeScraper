import os

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cartopy.mpl.geoaxes as geoaxes
import matplotlib.pyplot as plt
from cartopy.io.shapereader import Reader
from shapely.geometry import box

from PIL import Image
import matplotlib.pyplot as plt



COORDS = os.environ["CENTRAL_COORD"].split(",")
CENTRAL_LATITUDE, CENTRAL_LONGITUDE = map(float, COORDS)
PADDING = 0.05
LABEL_OFFSET = PADDING * 0.01

LANDMARKS = {
    "Valley Comms": (CENTRAL_LATITUDE, CENTRAL_LONGITUDE),
    "Agawam": (42.0631, -72.6134),
    "Springfield": (42.1014, -72.5903),
    "West Springfield": (42.1093, -72.6349),
    "Westfield": (42.1280, -72.7612),
    "Chicopee": (42.1553, -72.6001),
    "Holyoke": (42.2032, -72.6255),
    "Ludlow": (42.1815, -72.4784),
    "South Hadley": (42.2596, -72.5813),
    "Hadley": (42.3417, -72.5889),
    "Amherst": (42.3732, -72.5199),
    "Easthampton": (42.2668, -72.6688),
    "Northampton": (42.3251, -72.6412),
    "Belchertown": (42.2751, -72.4006),
    "Wilbraham": (42.1234, -72.4312),
    "Southwick": (42.0545, -72.7701),
    "Longmeadow": (42.0501, -72.5826),
    "East Longmeadow": (42.0634, -72.5126),
}

def draw_map(extra_coords: dict[str, tuple[float, float]] = None):
    """
    Draw a map with the given coordinates.
    :param extra_coords: Optional dictionary of additional coordinates to plot.
    """
    if extra_coords is None:
        extra_coords = {}
    os.chdir(r"F:\Backup\AliProjects\AliPY\HomeScraper\HomeHarvest\tests")
    min_lat = min(lat for lat, lon in LANDMARKS.values()) - PADDING
    max_lat = max(lat for lat, lon in LANDMARKS.values()) + PADDING
    min_lon = min(lon for lat, lon in LANDMARKS.values()) - PADDING
    max_lon = max(lon for lat, lon in LANDMARKS.values()) + PADDING

    print(f"Bounding box: ({min_lat}, {min_lon}) to ({max_lat}, {max_lon})")

    # Set up the plot
    fig = plt.figure(figsize=(8, 8))
    ax: geoaxes.GeoAxes = plt.axes(projection=ccrs.PlateCarree())
    ax.set_extent((min_lon, max_lon, min_lat, max_lat))  # bounding box
    ax.axis('off')
    # Ensure the map area fills the saved image (no figure/axes margins)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_position([0, 0, 1, 1])

    # Add features
    ax.add_feature(cfeature.STATES, edgecolor='gray')
    ax.add_feature(cfeature.BORDERS, linestyle=':')

    bbox = box(min_lon, min_lat, max_lon, max_lat)
    bbox_length = abs(min_lat - max_lat)
    bbox_height = abs(min_lon - max_lon)
    print(f"Bounding box lengths: (width: {bbox_height}, height: {bbox_length})")

    roads = Reader(r'F:\Backup\AliProjects\AliPY\HomeScraper\HomeHarvest\tests\primary_roads\tl_2024_us_primaryroads.shp')
    filtered_roads = [geom for geom in roads.geometries() if geom.intersects(bbox)]
    road_feature = cfeature.ShapelyFeature(filtered_roads, ccrs.PlateCarree(), facecolor="none", edgecolor="black", linewidth=0.5)
    ax.add_feature(road_feature)

    area_water = Reader(r'F:\Backup\AliProjects\AliPY\HomeScraper\HomeHarvest\tests\area_water\tl_2024_25013_areawater.shp')
    filtered_area_water = [geom for geom in area_water.geometries() if geom.intersects(bbox)]
    area_water_feature = cfeature.ShapelyFeature(filtered_area_water, ccrs.PlateCarree(), facecolor="blue", edgecolor="blue", linewidth=0.1, alpha=0.25)
    ax.add_feature(area_water_feature)

    # Plot landmarks
    for name, (lat, lon) in LANDMARKS.items():
        details = details_by_name(name)
        ax.plot(lon, lat, marker='o', color=details["label_color"], markersize=details["marker_size"])
        ax.text(lon + LABEL_OFFSET, lat + LABEL_OFFSET, name, fontsize=details["fontsize"])

    # Plot extra coordinates
    for name, (lat, lon) in extra_coords.items():
        ax.plot(lon, lat, marker='o', color="violet", markersize=4)

    ax.text(bbox.centroid.x + 0.1, min_lat + 0.0125, "Connecticut", fontsize=12, horizontalalignment='center', verticalalignment='center')
    ax.text(bbox.centroid.x - 0.1, max_lat - 0.0125, "Massachusetts", fontsize=12, horizontalalignment='center', verticalalignment='center')

    plt.ioff()
    # Save with zero padding so pixel->lat/lon mapping can assume the full image is the extent
    fig.savefig("base_map.jpg", dpi=125, bbox_inches="tight", pad_inches=0)

    # Save bbox as metadata (e.g., in a JSON or txt)
    with open("map_bbox.txt", "w") as f:
        f.write(",".join(map(str, [min_lat, min_lon, max_lat, max_lon])))







def details_by_name(name):
    if name == "Valley Comms":
        return {"label_color": "red", "marker_size": 4, "fontsize": 8}
    if "Walmart" in name:
        return {"label_color": "green", "marker_size": 2, "fontsize": 8}
    return {"label_color": "blue", "marker_size": 2, "fontsize": 8}


draw_map({
    "Walmart 1": (42.1364441198502, -72.50701159161437),
    "Walmart 2": (42.17267481016297, -72.57376884396496),
    "Walmart 3": (42.108330001107944, -72.70833897965517),
    "Walmart 4": (42.341532730798555, -72.64372086093478),
    "Walmart 5": (42.3547725902552, -72.55253154057571),})