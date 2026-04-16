from tofu.ez.ctdir_walker import substitute_shared_flatsdarks
from tofu.ez.params import EZVARS_aux, EZVARS
import os
from tofu.ez.util import add_value_to_dict_entry, get_fd_names, export_values
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
        outscandir_out = os.path.join(stitched_data_dir_name, os.path.basename(outscandir))
        if not os.path.exists(outscandir_out):
            os.makedirs(outscandir_out)
        # Export the parameters used to get stitched-data
        export_values(os.path.join(outscandir_out, "tofuez_all_parameters.yaml"),
                      ['ezvars', 'tofu', 'ezvars_aux'])
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

        substitute_subdirs = substitute_shared_flatsdarks()
        reduction_mode = EZVARS['flat-correction']['reduction-mode']['value']
        fd_names = get_fd_names()

        for innerloopdir, ax, crop in zip(innerloopdirs, dax, cra):
            ctdir = os.path.join(outscandir, innerloopdir)
            outdir = os.path.join(outscandir_out, innerloopdir)
            print("================================================================")
            print(" -> Working On: " + str(ctdir))
            print(f"    axis position {ax}, margin to crop {crop} pixels")
            try:
                main_360sti_ufol_depth1(indir=ctdir,
                                        outdir=outdir,
                                        ax=ax,
                                        cro=crop,
                                        substitute_subdirs=substitute_subdirs,
                                        reduction_mode=reduction_mode,
                                        fd_names=fd_names,
                                        )
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