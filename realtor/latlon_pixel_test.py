from PIL import Image, ImageDraw
import os

def latlon_to_pixel(lat, lon, bbox, image_size):
    min_lat, min_lon, max_lat, max_lon = bbox
    width, height = image_size

    # Normalize longitude
    x_ratio = (lon - min_lon) / (max_lon - min_lon)
    x = x_ratio * width

    # Normalize latitude (y is reversed in image space)
    y_ratio = (lat - min_lat) / (max_lat - min_lat)
    y = (1 - y_ratio) * height - 10 # Magical -10 offset to adjust for the top of the image??? Could not figure out why the y coordinate is off

    return int(round(x)), int(round(y))


def draw_list_to_img(coord_list):
    """
    Draw a list of coordinates on an image.
    :param coord_list: List of tuples (latitude, longitude).
    :return: PIL Image with drawn coordinates.
    """
    img = Image.open("base_map.jpg")
    draw = ImageDraw.Draw(img)

    with open("map_bbox.txt") as f:
        min_lat, min_lon, max_lat, max_lon = map(float, f.read().split(','))

    for lat, lon in coord_list:
        px, py = latlon_to_pixel(lat, lon, (min_lat, min_lon, max_lat, max_lon), img.size)
        draw.ellipse((px-4, py-4, px+4, py+4), fill="yellow", outline="black")
        print(px, py)

    return img


coord_list = [
    (42.1364441198502, -72.50701159161437),
    (42.17267481016297, -72.57376884396496),
    (42.108330001107944, -72.70833897965517),
    (42.341532730798555, -72.64372086093478),
    (42.3547725902552, -72.55253154057571),
]

img = draw_list_to_img(coord_list)  # Example coordinates


img.save("map_with_point.jpg")
