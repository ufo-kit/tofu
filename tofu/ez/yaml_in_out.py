import yaml
import logging


LOG = logging.getLogger(__name__)

def read_yaml(filePath):
    with open(filePath) as f:
        data = yaml.load(f, Loader=yaml.FullLoader)
        LOG.debug("Imported YAML file:")
        LOG.debug(data)
        return data

def write_yaml(filePath, params):
    try:
        file = open(filePath, "w")
    except FileNotFoundError:
        LOG.debug("No filename given")
    else:
        yaml.dump(params, file)
        file.close()
