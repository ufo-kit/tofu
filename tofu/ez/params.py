# This file is used to share params as a global variable
import yaml


#TODO Make good structure to store parameters
# similar to tofu? and
# use tofu's structure for existing reco params

params = {}


def save_parameters(params, file_path):
    file_out = open(file_path, 'w')
    yaml.dump(params, file_out)
    print("Parameters file saved at: " + str(file_path))


