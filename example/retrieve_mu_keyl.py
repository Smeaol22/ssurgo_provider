from pathlib import Path

from osgeo import ogr, osr

from ssurgo_provider.spatial_tools import retrieve_mu_key_from_raster_by_zone, convert_geojson_to_polygon

source = osr.SpatialReference()
target = osr.SpatialReference()
source.ImportFromEPSG(4326)
target.ImportFromEPSG(4326)

geojson = {'type': 'Polygon', 'coordinates': [
    (-83.292448, 40.574234), (-83.292448, 40.584234), (-83.302448, 40.584234), (-83.302448, 40.574234),
    (-83.292448, 40.574234)]}  # [(long, lat), (long,lat)]
polygon = convert_geojson_to_polygon(geojson)

testpolywkt = 'POLYGON ((-83.292448 40.574234, -83.292448 40.584234, -83.302448 40.584234, -83.302448 40.574234,' \
              '-83.292448 40.574234))'

# The line below sets the TRADITIONAL_GIS_ORDER that I was expecting.
target.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
transform = osr.CoordinateTransformation(source, target)
polygon2 = ogr.CreateGeometryFromWkt(testpolywkt)
polygon2.Transform(transform)

print(polygon.Centroid().GetX())
print(polygon2.Centroid().GetX())

ssurgo_folder_path = Path().absolute().parent / 'resources' / 'October 2021 gSSURGO by State' / 'gSSURGO_OH' / 'gSSURGO_OH.gdb'

mu_key_dict = retrieve_mu_key_from_raster_by_zone(polygon, ssurgo_folder_path)

print(mu_key_dict)
