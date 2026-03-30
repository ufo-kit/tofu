from tofu.ez.params import EZVARS_aux, EZVARS
import os
from tofu.ez.util import add_value_to_dict_entry
from tofu.ez.Helpers.stitch_funcs import main_360sti_ufol_depth1, compute_crop
from tofu.ez.Helpers.find_360_overlap import find_overlap
from tofu.util import get_first_filename, get_image_shape


def batch_stitch():
    #TODO: check that directory is empty - if loaded from params check is not applied
    stitched_data_dir_name = os.path.join(EZVARS_aux['half-acq']['workdir']['value'],
                                          'stitched-data')
    if os.path.exists(stitched_data_dir_name) and \
            len(os.listdir(stitched_data_dir_name)) > 0:
        print("# Clean directory for stitched data")
        return 1

    print(EZVARS_aux['axes-list'])
    for outscandir, innerloopdict in EZVARS_aux['axes-list'].items():
        print(f"# Stitching half acq mode data in {outscandir}")
        innerloopdirs = list(innerloopdict)
        dax = list(innerloopdict.values())
        print(f'# Stitching inner loop CT scans in {outscandir} with '
              f"overlaps {dax}")

        print(f'Overlaps: {dax}')
        first_tomo_dir = os.path.join(outscandir,
                                      innerloopdirs[0],
                                      EZVARS['inout']['tomo-dir']['value'])
        image_shape = get_image_shape(get_first_filename(first_tomo_dir))
        cra = compute_crop(dax, image_shape)
        print(f'Crop by: {cra}')
        for innerloopdir, ax, crop in zip(innerloopdirs, dax, cra):
            ctdir = os.path.join(outscandir, innerloopdir)
            outdir = os.path.join(stitched_data_dir_name, os.path.basename(outscandir), innerloopdir)
            print("================================================================")
            print(" -> Working On: " + str(ctdir))
            print(f"    axis position {ax}, margin to crop {crop} pixels")
            try:
                main_360sti_ufol_depth1(indir=ctdir,
                                        outdir=outdir,
                                        ax=ax,
                                        cro=crop,)
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