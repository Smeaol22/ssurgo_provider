import os
from pathlib import Path

from osgeo import ogr
from shapely.geometry import Point

from ssurgo_provider.object.gbd_connect import GbdConnect
from ssurgo_provider.object.state_info import StateInfoStatus
from ssurgo_provider.soil_tools import find_soil_id_ref, find_soil_horizon_distribution, extract_soil_horizon_data, \
    build_soil_composition, build_soil_composition_without_point
from ssurgo_provider.spatial_tools import transform_wgs84_to_albers, find_county_id, retrieve_state_code


def retrieve_multiple_soil_data(coordinates, disable_file_error=True, disable_location_error=True):
    """
    Function to retrieve soil composition from a list of location (coordinates)
    Args:
        coordinates (list(tuple)): list of location [(lat, long ), (lat, long), ...]
        disable_file_error (bool): if True disable throw exception when data file is not found for a state
        disable_location_error (bool): if True disable throw exception when location is not in USA

    Returns:
        soil_data_list (list(StateInfo)): list with complete soil StateInfo object
    """
    points = [Point(coordinate[0], coordinate[1]) for coordinate in coordinates]
    states_info_list = retrieve_state_code(points=points, disable_location_error=disable_location_error)
    states_info_list = find_ssurgo_state_folder_path(states_info_list, disable_file_error)
    soil_data_list = manage_retrieve_soils_composition(states_info_list)
    return soil_data_list


def find_ssurgo_state_folder_path(state_info_list, disable_file_error=True):
    """
    Find the gbd folder path associated to the state_code
    Args:
        state_info_list (list): list of StateInfo object with state code complete
        disable_file_error (bool): if true do not stop process with exception if missing file
    Returns:
        (list(path)): path to ssurgo soil data for the state associated to the state_point
    """

    ssurgo_data_pth = os.environ['SSURGO_DATA']
    for state_info in state_info_list:
        if state_info.status == StateInfoStatus.IN_PROGRESS:
            ssurgo_state_folder = f'gSSURGO_{state_info.state_code.upper()}.gdb'
            if ssurgo_state_folder not in os.listdir(ssurgo_data_pth):
                if not disable_file_error:
                    raise ValueError(f"no ssurgo data find for state {state_info.state_code}, please download it")
                else:
                    state_info.status = StateInfoStatus.NO_GDB_FILE_FOUND
            else:
                state_info.state_folder_pth = Path(ssurgo_data_pth) / ssurgo_state_folder
    return state_info_list


def retrieve_soil_composition(coordinates, ssurgo_folder_path):
    """
        This function is usefull to retrieve soil data for the location specified in coordinates
    Args:
        coordinates (list): list of Points (lat, long coordinate) (espg 4326)
        ssurgo_folder_path (path): path to the ssurgo database at the state level

    Returns:
        soil_composition_list (list): list of SsurgoSoilDto, one for each location

    """

    transform = transform_wgs84_to_albers()

    pts_coordinates = []
    point_base = ogr.Geometry(ogr.wkbPoint)
    for coordinate in coordinates:
        point = point_base.__copy__()
        point.AddPoint(coordinate[0], coordinate[1])
        point.Transform(transform)
        pts_coordinates.append(point)

    # open connection to geo database
    gdb_connection = GbdConnect(ssurgo_folder_path)
    gdb = gdb_connection.gdb

    pts_info_df = find_county_id(pts_coordinates, gdb)
    pts_info_df = find_soil_id_ref(pts_info_df, gdb)
    pts_info_df = find_soil_horizon_distribution(pts_info_df, gdb)
    soil_data_dict = extract_soil_horizon_data(pts_info_df, gdb)
    del gdb

    soil_composition_list = build_soil_composition(pts_info_df, soil_data_dict)
    return soil_composition_list


def manage_retrieve_soils_composition(state_info_list):
    """
    Manage all pipeline to retrieve soil data
    Args:
        state_info_list (list): list of state info object (with lat and long)

    Returns:
        (list(state_info)): list of state info object complete with soil data
    """
    sort_by_state = {}
    state_list = []
    for state_info in state_info_list:
        if state_info.status == StateInfoStatus.IN_PROGRESS:
            if state_info not in state_list:
                state_list.append(state_info.state_code)
                sort_by_state[state_info.state_code] = [state_info]
            else:
                sort_by_state[state_info.state_code].append(state_info)
    for state in state_list:
        ssurgo_folder_path = sort_by_state[state][0].state_folder_pth
        coordinates = [(state_info.points.x, state_info.points.y) for state_info in sort_by_state[state]]
        soil_data_list = retrieve_soil_composition(coordinates, ssurgo_folder_path)
        [state_info.set_soil(soil_data)
         for state_info, soil_data in zip(sort_by_state[state], soil_data_list)]
    return state_info_list


def retrieve_soil_information_from_mukey(pts_info_df, ssurgo_folder_path):
    """
        This function is usefull to retrieve soil data from mu_sym and mu_key
    Args:
        pts_info_df (dataframe): see with mu_sym mu_key spatial_ver area_symbol for each location (see find_soil_id_ref)
        ssurgo_folder_path (path): path to the ssurgo database at the state level

    Returns:
        soil_composition_list (list): list of SsurgoSoilDto, one for each location

    """

    # open connection to geo database
    gdb_connection = GbdConnect(ssurgo_folder_path)
    gdb = gdb_connection.gdb

    pts_info_df = find_soil_horizon_distribution(pts_info_df, gdb)
    soil_data_dict = extract_soil_horizon_data(pts_info_df, gdb)
    del gdb

    soil_composition_list = build_soil_composition_without_point(pts_info_df, soil_data_dict)
    return soil_composition_list
