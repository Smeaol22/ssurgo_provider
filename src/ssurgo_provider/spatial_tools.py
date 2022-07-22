import osgeo
import pandas as pd
from osgeo import osr, ogr
from shapely.geometry import Polygon, Point

from ssurgo_provider.object.gbd_connect import GbdConnect
from ssurgo_provider.object.map_load import OpenMap
from ssurgo_provider.object.state_info import StateInfo, StateInfoStatus
from ssurgo_provider.param import states_code


def transform_wgs84_to_albers():
    """
    Function return object able to transform py-gdalogr object from wgs84 projection to USA_Contiguous_Albers
    Returns:
        (ogr): object able to transform py-gdalogr object from wgs84 projection to USA_Contiguous_Albers

    """
    target = osr.SpatialReference()
    target.ImportFromWkt('PROJCS["USA_Contiguous_Albers_Equal_Area_Conic_USGS_version",'
                         'GEOGCS["GCS_North_American_1983",DATUM["D_North_American_1983",'
                         'SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],'
                         'UNIT["Degree",0.0174532925199433]],PROJECTION["Albers"],'
                         'PARAMETER["False_Easting",0.0],PARAMETER["False_Northing",0.0],'
                         'PARAMETER["Central_Meridian",-96.0],PARAMETER["Standard_Parallel_1",29.5],'
                         'PARAMETER["Standard_Parallel_2",45.5],PARAMETER["Latitude_Of_Origin",23.0],'
                         'UNIT["Meter",1.0],AUTHORITY["ESRI","102039"]]')
    source = osr.SpatialReference()
    source.ImportFromEPSG(4326)
    return osr.CoordinateTransformation(source, target)


def convert_geojson_to_polygon(geojson):
    """
    Convert geoJson to an ogr Polygon
    Args:
        geojson (dict): the geojson to convert with coordinates as list of (long, lat)

    Returns:
        (polygon): the geojson converted to polygon
    """
    if geojson['type'].lower() != "polygon":
        raise ValueError("Geojson should be of type polygon only")
    polygon = ogr.CreateGeometryFromWkt(
        str(Polygon([(coordinate[1], coordinate[0]) for coordinate in geojson['coordinates']])))

    return polygon


def retrieve_mu_key_from_raster_by_zone(polygon, ssurgo_folder_path):
    """
    This function retrieve all mukey in the geojson
    Args:
        polygon (Polygon): polygon represent the area where mu_key should be find
        ssurgo_folder_path (path):

    Returns:
        (dict): dict of mu_key inside the geojson area with their area percentage
    """

    transform = transform_wgs84_to_albers()

    # open connection to geo database
    gdb_connection = GbdConnect(ssurgo_folder_path)
    gdb = gdb_connection.gdb

    layer_mu_polygon = gdb.GetLayer("MUPOLYGON")

    polygon.Transform(transform)
    layer_mu_polygon.SetSpatialFilter(polygon)

    response = {}
    for feature in layer_mu_polygon:
        geometry = feature.GetGeometryRef()
        inter = polygon.Intersection(geometry)
        if inter is not None and inter is not inter.IsEmpty():
            mu_key = int(feature.GetField("MUKEY"))
            if mu_key not in response.keys():
                response[mu_key] = inter.GetArea()
            else:
                response[mu_key] += inter.GetArea()
    total_area = sum(response.values())
    for mu_key in response.keys():
        response[mu_key] = round(response[mu_key] / total_area * 100, 2)
    return response


def retrieve_state_code(points, states_gdf=None, disable_location_error=True):
    """
    Find US state code for the point (lat, long)
    Args:
        points (list(Point)): list of Point(lat, long)
        states_gdf (GeoDataFrame/None): GeoDataFrame with all US state shapefile
        disable_location_error (bool): if false display error and stop process if one point is out of USA
    Returns:
        (list(StateInfo)): list of state_info with US code and update status
    """
    states_info_list = []
    if states_gdf is None:
        open_map = OpenMap()
        states_gdf = open_map.states_gdf

    for state_name in states_gdf.NAME_1:
        state_code = states_code[state_name.lower().replace(" ", "_")]
        lat_lim = state_code['lat_lim']
        long_lim = state_code['long_lim']
        geom = None
        for point in points:
            if isinstance(point, osgeo.ogr.Geometry):
                point_shp = Point(point.GetY(), point.GetX())
            else:
                point_shp = Point(point.y, point.x)
            if lat_lim[0] <= point_shp.y <= lat_lim[1] and long_lim[0] <= point_shp.x <= long_lim[1]:
                if geom is None:
                    geom = states_gdf[states_gdf.NAME_1 == state_name].geometry.unary_union
                if geom.contains(point_shp):
                    points.remove(point)
                    states_info_list.append(
                        StateInfo(state_code=state_code["code"], points=point,
                                  status=StateInfoStatus.IN_PROGRESS))
        if len(points) == 0:
            return states_info_list

    [states_info_list.append(StateInfo(state_code=None, points=point, status=StateInfoStatus.NOT_IN_USA)) for point in
     points]
    if not disable_location_error:
        raise ValueError(f'point is not in USA, please select a point in USA')
    if not states_gdf.is_permanent:
        del states_gdf
    return states_info_list


def find_county_id(points, gdb):
    """
        This function is useful to retrieve county id associated to each locations

    Args:
        points(list): list of Points
        gdb (DataSource): ssurgo state datasource

    Returns:
        pts_info_df (DataFrame): dataframe with county_id for each location
    """
    layer_sa_polygon = gdb.GetLayer("SAPOLYGON")
    pts_info_df = pd.DataFrame({'points': [], 'county_id': []}, columns=['points', 'county_id'])

    try:
        for feature in layer_sa_polygon:
            county_id = feature.GetField("AREASYMBOL")
            geometry = feature.GetGeometryRef()
            for point in points:
                if point.Within(geometry):
                    pt_info = {'county_id': county_id,
                               'points': point}
                    pts_info_df = pts_info_df.append(pt_info, ignore_index=True)
                    points.remove(point)
                    if len(points) < 0:
                        raise ValueError("No more points to iterate")
    except ValueError:
        if len(points) < 0:
            pass
    return pts_info_df
