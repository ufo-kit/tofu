from tofu.ez.params import EZVARS_aux, EZVARS
import os
from tofu.ez.util import add_value_to_dict_entry
from tofu.ez.Helpers.stitch_funcs import main_360_mp_depth2
from tofu.ez.Helpers.find_360_overlap import find_overlap

def batch_stitch():
    stitched_data_dir_name = os.path.join(EZVARS_aux['half-acq']['workdir']['value'],
                                          'stitched-data')
    if os.path.exists(stitched_data_dir_name) and \
            len(os.listdir(stitched_data_dir_name)) > 0:
        print("# Clean directory for stitched data")
        return
    add_value_to_dict_entry(EZVARS_aux['stitch360']['olap_switch'], 2)
    add_value_to_dict_entry(EZVARS_aux['stitch360']['crop'], True)

    print(EZVARS_aux['axes-list'])
    for outscandir in EZVARS_aux['axes-list'].keys():
        print(f"# Stitching half acq mode data in {outscandir}")
        # setting params for stitch360
        add_value_to_dict_entry(EZVARS_aux['stitch360']['input-dir'], str(outscandir))
        add_value_to_dict_entry(EZVARS_aux['stitch360']['output-dir'], os.path.join(
                               stitched_data_dir_name,
                               str(outscandir[len(os.path.dirname(outscandir)) + 1:]))
                               )
        os.makedirs(EZVARS_aux['stitch360']['output-dir']['value'])
        add_value_to_dict_entry(EZVARS_aux['stitch360']['olap_list'], '')
        # extract string of overlaps from the EZVARS_aux['axes-list'] subsections:
        for innerloopdir in EZVARS_aux['axes-list'][outscandir].keys():
            EZVARS_aux['stitch360']['olap_list']['value'] += \
                str(EZVARS_aux['axes-list'][outscandir][innerloopdir]) + ','
        EZVARS_aux['stitch360']['olap_list']['value'] = \
            EZVARS_aux['stitch360']['olap_list']['value'][:-1]
        print(f'# Stitching inner loop CT scans in {outscandir} with '
              f"overlaps {EZVARS_aux['stitch360']['olap_list']['value']}")
        try:
            main_360_mp_depth2()
        except:
            return 1
    return 0

def batch_olap_search():
    EZVARS_aux['find360olap']['input-dir']['value'] = \
        EZVARS['inout']['input-dir']['value']
    EZVARS_aux['find360olap']['tmp-dir']['value'] = \
        os.path.join(EZVARS_aux['half-acq']['workdir']['value'],
                    'temporary-data')
    EZVARS_aux['find360olap']['output-dir']['value'] = \
        os.path.join(EZVARS_aux['half-acq']['workdir']['value'],
                     'overlap-search-results')
    try:
        find_overlap()
    except:
        return 1
    return 0