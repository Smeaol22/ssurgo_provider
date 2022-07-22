from math import isnan

import pandas as pd

from ssurgo_provider.object.ssurgo_soil_dto import SoilHorizon, SsurgoSoilDto


def find_soil_id_ref(pts_info_df, gdb):
    """
    Find soil references related to the soil ID and the location
    Args:
        pts_info_df(DataFrame): see. find_county_id
        gdb (DataSource): ssurgo state datasource

    Returns:
        pts_info_df (DataFrame): dataframe with mu_sym mu_key spatial_ver area_symbol for each location
    """
    layer_mu_polygon = gdb.GetLayer("MUPOLYGON")
    new_pts_info = {'mu_sym': [], 'mu_key': [], 'spatial_ver': [], 'area_symbol': []}
    pts_info_df = pd.concat(
        [pts_info_df, pd.DataFrame(new_pts_info, columns=['mu_sym', 'mu_key', 'spatial_ver', 'area_symbol'])])
    unique_county_id = pts_info_df.county_id.unique()
    for county_id in unique_county_id:
        layer_mu_polygon.SetAttributeFilter(f"AREASYMBOL = '{county_id}'")
        reduce_pts_info_df = pts_info_df[pts_info_df['county_id'] == county_id]
        index_list = list(reduce_pts_info_df.index)
        points_list = list(reduce_pts_info_df.points)

        for feature in layer_mu_polygon:
            geometry = feature.GetGeometryRef()
            if len(index_list) == 0:
                break
            for index, point in zip(index_list, points_list):
                if point.Within(geometry):
                    pts_info_df.mu_sym[index] = feature.GetField("MUSYM")
                    pts_info_df.mu_key[index] = int(feature.GetField("MUKEY"))
                    pts_info_df.spatial_ver[index] = feature.GetField("SPATIALVER")
                    pts_info_df.area_symbol[index] = feature.GetField("AREASYMBOL")
                    index_list.remove(index)
                    points_list.remove(point)

    return pts_info_df


def find_soil_horizon_distribution(pts_info_df, gdb):
    """
        This function is useful to determine the soil horizon distribution by percentage for each location
    Args:
        pts_info_df (dataframe): with mu_sym mu_key spatial_ver area_symbol for each location (see find_soil_id_ref)
        gdb (DataSource): ssurgo state datasource

    Returns:
            (dataframe) dataframe with co_key_1/2/3 co_key_1/2/3 for each location

    """
    component = gdb.GetLayer("component")

    new_pts_info = {'co_key_0': [], 'co_key_1': [], 'co_key_2': [], 'co_key_0_pct': [], 'co_key_1_pct': [],
                    'co_key_2_pct': []}
    pts_info_df = pd.concat([pts_info_df, pd.DataFrame(new_pts_info,
                                                       columns=['co_key_0', 'co_key_1', 'co_key_2', 'co_key_0_pct',
                                                                'co_key_1_pct', 'co_key_2_pct'])])
    for mu_key in pts_info_df.mu_key.unique():
        co_key_info = []
        component.SetAttributeFilter(f"mukey = '{int(mu_key)}'")
        for feature_component in component:
            comp_pct = feature_component.GetField("comppct_r")
            co_key_info.append((comp_pct if comp_pct is not None else -1, feature_component.GetField("cokey")))
        co_key_info.sort(reverse=True)
        for idx in pts_info_df[pts_info_df.mu_key == mu_key].index:
            for component_nb in range(0, 3):
                try:
                    if co_key_info[component_nb][0] > -1:
                        pts_info_df[f"co_key_{component_nb}"][idx] = co_key_info[component_nb][1]
                        pts_info_df[f"co_key_{component_nb}_pct"][idx] = co_key_info[component_nb][0]
                    else:
                        pts_info_df[f"co_key_{component_nb}"][idx] = None
                        pts_info_df[f"co_key_{component_nb}_pct"][idx] = None
                except:
                    pts_info_df[f"co_key_{component_nb}"][idx] = None
                    pts_info_df[f"co_key_{component_nb}_pct"][idx] = None
    return pts_info_df


def extract_soil_horizon_data(pts_info_df, gdb):
    """
        This function is useful to extract all
    Args:
        pts_info_df (dataframe): see find_soil_horizon_distribution
        gdb (DataSource): ssurgo state datasource

    Returns:
        soil_data_dict (dict): dict with SoilHorizon for each co_key in pts_info_df
    """
    co_key_list = list(pts_info_df.co_key_0) + list(pts_info_df.co_key_1) + list(pts_info_df.co_key_2)
    co_key_list_filtered = set([int(co_key) for co_key in co_key_list if not isnan(co_key)])
    c_horizon_polygon = gdb.GetLayer("chorizon")
    soil_data_dict = dict()
    for co_key in co_key_list_filtered:
        feature_nb = c_horizon_polygon.SetAttributeFilter(f"cokey = '{co_key}'")
        if feature_nb == 0:
            soil_data_dict[str(co_key)] = None
        for feature_horizon in c_horizon_polygon:
            soil_data_dict[str(co_key)] = SoilHorizon(None, feature_horizon)

    return soil_data_dict


def build_soil_composition(pts_info_df, soil_data_dict):
    """
        This function is useful to build list of SsurgoSoilDto for each location
    Args:
        pts_info_df (dataframe): see extract_soil_horizon_data
        soil_data_dict (dict): dict with SoilHorizon for each co_key in pts_info_df

    Returns:
        soil_composition_list (list): list of SsurgoSoilDto, one for each location in pts_info_df
    """
    soil_composition_list = []
    for _, pt_info in pts_info_df.iterrows():
        ssurgo_soil_dto = SsurgoSoilDto(pt_info.points.GetX(), pt_info.points.GetY())
        if not isnan(pt_info.co_key_0):
            soil_horizon = soil_data_dict[str(int(pt_info.co_key_0))]
            if soil_horizon is not None:
                soil_horizon.comppct_r = pt_info.co_key_0_pct
            ssurgo_soil_dto.horizon_0 = soil_horizon
        if not isnan(pt_info.co_key_1):
            soil_horizon = soil_data_dict[str(int(pt_info.co_key_1))]
            if soil_horizon is not None:
                soil_horizon.comppct_r = pt_info.co_key_1_pct
            ssurgo_soil_dto.horizon_1 = soil_horizon
        if not isnan(pt_info.co_key_2):
            soil_horizon = soil_data_dict[str(int(pt_info.co_key_2))]
            if soil_horizon is not None:
                soil_horizon.comppct_r = pt_info.co_key_2_pct
            ssurgo_soil_dto.horizon_2 = soil_horizon
        soil_composition_list.append(ssurgo_soil_dto)
    return soil_composition_list


def build_soil_composition_without_point(pts_info_df, soil_data_dict):
    """
        This function is useful to build list of SsurgoSoilDto for each location
    Args:
        pts_info_df (dataframe): see extract_soil_horizon_data
        soil_data_dict (dict): dict with SoilHorizon for each co_key in pts_info_df

    Returns:
        soil_composition_list (list): list of SsurgoSoilDto, one for each location in pts_info_df
    """
    soil_composition_list = []
    for _, pt_info in pts_info_df.iterrows():
        ssurgo_soil_dto = {'mu_key': pt_info.mu_key,
                           'horizon_0': None,
                           'horizon_1': None,
                           'horizon_2': None}
        if not isnan(pt_info.co_key_0):
            soil_horizon = soil_data_dict[str(int(pt_info.co_key_0))]
            if soil_horizon is not None:
                soil_horizon.comppct_r = pt_info.co_key_0_pct
            ssurgo_soil_dto['horizon_0'] = soil_horizon
        if not isnan(pt_info.co_key_1):
            soil_horizon = soil_data_dict[str(int(pt_info.co_key_1))]
            if soil_horizon is not None:
                soil_horizon.comppct_r = pt_info.co_key_1_pct
            ssurgo_soil_dto['horizon_1'] = soil_horizon
        if not isnan(pt_info.co_key_2):
            soil_horizon = soil_data_dict[str(int(pt_info.co_key_2))]
            if soil_horizon is not None:
                soil_horizon.comppct_r = pt_info.co_key_2_pct
            ssurgo_soil_dto['horizon_2'] = soil_horizon
        soil_composition_list.append(ssurgo_soil_dto)
    return soil_composition_list
