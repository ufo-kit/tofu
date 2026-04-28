import numpy as np
import yaml
from tofu.ez.util import add_value_to_dict_entry
from tofu.config import SECTIONS
from tofu.ez.params import EZVARS, EZVARS_prep
import os

def h5log2params(h5log, odir, ):
    #First extracting sample_x positions
    if int(h5log['entry']['beamline']['name'][()].decode()[2]) == 5:
        sx = np.array(h5log["entry"]["scan"]["data"]["s_stage_x"]["value"])[np.where(np.array(h5log['entry']['scan'] \
                                    ['data']['image_key']['value'][int(h5log['entry']['scan']['n_dark'][0]):])==0)]
    elif int(h5log['entry']['beamline']['name'][()].decode()[2]) == 7:
        sx = np.array(h5log["entry"]["scan"]["data"]["s_stage_x"]["value"])[np.where(np.array(h5log['entry']['scan'] \
                                    ['data']['image_key']['value'][:])==0)]
    else:
        print(f"Unknown beamline id: {h5log['entry']['beamline']['name'][()].decode()}")
        return
    ps = h5log['entry']['hardware']['camera']['pixelsize'][0] / h5log['entry']['hardware']['camera']['magnification'][0]
    # TODO also adjust the pixel size acording to binning
    shifts = np.array(-(sx - sx[0])/ps)
    if EZVARS['inout']['bin_before_fbp']['value']:
        shifts/=SECTIONS['reading']['resize']['value']
        # TODO also before the scan
    if np.std(shifts)>5: # if sample moved left right more than 5 pixels it was definetely done intentionally
        print(f'\"Wackel\" scan')
        #shifts with respect to image middle column
        #shifts = np.array(-sx/ps + h5log['entry']['hardware']['camera']['sensorsize_x'][0]/2).astype(int)
        midc = h5log['entry']['hardware']['camera']['roi_width'][0] / 2
        if EZVARS['inout']['bin_before_fbp']['value']:
            midc/=SECTIONS['reading']['resize']['value']
            # TODO also before the scan and do everything at one place
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
    if nz > 1:
        h5data['overall-angle'] = nz*360
    else:
        if len(np.where(srot>200)) > 0:
            h5data['overall-angle'] = 360
        else:
            h5data['overall-angle'] = 180
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