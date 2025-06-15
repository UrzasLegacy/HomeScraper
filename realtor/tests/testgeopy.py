import geopy.distance

coords_1 = (42.106052,-71.524849)
coords_2 = (41.742449,-70.454158)

print(geopy.distance.geodesic(coords_1, coords_2).mi)