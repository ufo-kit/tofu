import numpy as np
import yaml
from tofu.ez.util import add_value_to_dict_entry
from tofu.config import SECTIONS
from tofu.ez.params import EZVARS, EZVARS_prep
import os

def h5log2params(h5log, odir):
    #First extracting sample_x positions   int(h5log['entry']['beamline']['name'][()].decode()[2])
    bid = get_beamline_id(h5log)
    if bid == 5:
        sx = np.array(h5log["entry"]["scan"]["data"]["s_stage_x"]["value"])[np.where(np.array(h5log['entry']['scan'] \
                                    ['data']['image_key']['value'][int(h5log['entry']['scan']['n_dark'][0]):])==0)]
    elif bid == 7:
        sx = np.array(h5log["entry"]["scan"]["data"]["s_stage_x"]["value"])[np.where(np.array(h5log['entry']['scan'] \
                                    ['data']['image_key']['value'][:])==0)]
    else:
        print(f"Unknown beamline id: {h5log['entry']['beamline']['name'][()].decode()}")
        return
    ps = h5log['entry']['hardware']['camera']['pixelsize'][0] / h5log['entry']['hardware']['camera']['magnification'][0]
    #TODO check if the guys are using [bin] record at all
    shifts = np.array(-(sx - np.mean(sx))/ps) #data sets from 2025
    #shifts = np.array((sx - np.mean(sx))/ps) #XIMEA 2026 driver flips images left-right when saving tiffs
    # binning multipliers
    bf = 1
    if EZVARS['inout']['bin_before_fbp']['value']:
        bf/=SECTIONS['reading']['resize']['value']
    if EZVARS['inout']['preprocess']['value'] and EZVARS_prep['prepro']['extended_prepro']:
        bf/= int(EZVARS_prep['prepro']['bin_size']['value'])
    print(f'BINNING FACTOR APPLIED TO VARIABLE AXIS: {bf}')
    #TODO deal gracefully with the horizontal crop as well?
    if np.std(shifts)>5: # if sample moved left right more than 5 pixels it was definetely done intentionally
        print(f'\"Wackel\" scan')
        midc = h5log['entry']['hardware']['camera']['roi_width'][0] / 2 * bf
        shifts*=bf
        # if we take each nth projection we also have to take each nth axis of rotation
        if (EZVARS['inout']['preprocess']['value'] and EZVARS_prep['prepro']['extended_prepro']['value']
                and EZVARS_prep['prepro']['im_lim_range']['value']):
            shifts=shifts[::EZVARS_prep['prepro']['im_step']['value']]
        #TODO once a proper 3d binning is implemented the cors must also be adjusted accordingly
        cent_pos_x_arr_string = ','.join(map(str, midc + shifts))
        with open(os.path.join(odir, 'cors.txt'), "w") as text_file:
            text_file.write(cent_pos_x_arr_string)
    # extract overall angle and PR params
    h5data = {'pixel-size': str(ps*1e-3)}
    # extract overall angle
    srot = np.array(h5log["entry"]["scan"]["data"]["s_rot"]["value"])[np.where(np.array(h5log['entry']['scan'] \
                            ['data']['image_key']['value'][int(h5log['entry']['scan']['n_dark'][0]):])==0)]
    nz = len(np.where(srot<srot[1]-srot[0])[0])
    print(f"DEBUG: s_rot was {nz} times at 0 position in {os.path.dirname(odir)}")
    h5data['overall-angle'] = int(h5log["entry"]["scan"]["mode"][0])
    if nz > 1:
        h5data['overall-angle'] = nz*360 #TODO encode full rotation interval in the h5 file
    # else:
    #     if len(np.where(srot>200)) > 0: #that is not a particularly good criterium
    #         h5data['overall-angle'] = 360
    #     else:
    #         print('Cannot determine overall rotation interval')

    with open(os.path.join(odir,'h5log.yml'), 'w') as outfile:
        yaml.dump(h5data, outfile)

    return 0

def set_params_from_h5log(odir):
    try:
        file_in = open(os.path.join(odir,'h5log.yml'), 'r')
        h5log = yaml.load(file_in, Loader=yaml.FullLoader)
        print("Parameters file loaded" )
    except FileNotFoundError:
        print(f"Cannot load params in {odir}")
        return
    add_value_to_dict_entry(SECTIONS['general-reconstruction']['overall-angle'], h5log['overall-angle'])


    # add_value_to_dict_entry(SECTIONS['retrieve-phase']['pixel-size'],
    #                         self.microns_to_meters(float(self.pixel_size_entry.text())))
    #
    # add_value_to_dict_entry(SECTIONS['retrieve-phase']['energy'], str(self.photon_energy_entry.text()))
    # add_value_to_dict_entry(SECTIONS['retrieve-phase']['propagation-distance'], str())

def get_beamline_id(h5log):
    bid = 0
    try:
        bid = int(h5log['entry']['beamline']['name'][()].decode()[2])
    except AttributeError:
        try:
            bid = int(h5log['entry']['beamline']['name'][()][0].decode()[2])
        except:
            print(f"Cannot extract beamline id from h5 file")
    return bid