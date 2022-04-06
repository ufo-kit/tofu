import yaml
import logging


LOG = logging.getLogger(__name__)


class Yaml_IO:
    def read_yaml(self, filePath):
        with open(filePath) as f:
            data = yaml.load(f, Loader=yaml.FullLoader)
            LOG.debug(data)
            return data

    def write_yaml(self, filePath, params):
        try:
            file = open(filePath, "w")
        except FileNotFoundError:
            LOG.debug("No filename given")
        else:
            yaml.dump(params, file)
            file.close()
