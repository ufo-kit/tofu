from tofu.ez.params import EZVARS_aux
import os
from tofu.ez.util import add_value_to_dict_entry

olap_list = {}

def overlap_list_update_from_file(data):
    olap_list = data

def batch_stitch():
    stitched_data_dir_name = os.path.join(EZVARS_aux['half-acq']['workdir']['value'],
                                          'stitched-data')
    if os.path.exists(stitched_data_dir_name) and \
            len(os.listdir(stitched_data_dir_name)) > 0:
        print("Clean directory for stitched data")
        return
    # add_value_to_dict_entry(EZVARS_aux['stitch360']['olap_switch'], 2)
    # for outscan in outloopscans:
    #     # setting params for stitch360
    #     add_value_to_dict_entry(EZVARS_aux['stitch360']['input-dir'], str(outscan))
    #     add_value_to_dict_entry(EZVARS_aux['stitch360']['output-dir'], os.path.join(
    #         stitched_data_dir_name,
    #         str(outscan[len(os.path.dirname(outscan)) + 1:]))
    #                             )
    #     os.makedirs(EZVARS_aux['stitch360']['output-dir']['value'])
    #     add_value_to_dict_entry(EZVARS_aux['stitch360']['olap_list']['value'], '')
    #     # extract string of overlaps from the table:
    #     for j in olap_lists.keys():
    #         if outscan == os.path.dirname(j):
    #             EZVARS_aux['stitch360']['olap_list']['value'] += str() + ','
    #         EZVARS_aux['stitch360']['olap_list']['value'] = \
    #             EZVARS_aux['stitch360']['olap_list']['value'][:-1]
    #     print(f'Stitching dirs in {outscan} with '
    #           f'overlaps {EZVARS_aux['stitch360']['olap_list']['value']}')