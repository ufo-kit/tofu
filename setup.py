import pkgconfig
from setuptools import setup, find_packages

VERSION='0.2dev'

REQUIRED_UFO='>=0.5'

if not pkgconfig.installed('ufo', REQUIRED_UFO):
    print("You need at least ufo-core {0}. The installed scripts "
          "might not work as expected.\n".format(REQUIRED_UFO))

setup(
    name='ufo-scripts',
    version=VERSION,
    author='Matthias Vogelgesang',
    author_email='matthias.vogelgesang@kit.edu',
    url='http://ufo.kit.edu',
    packages=find_packages(),
    scripts=['bin/ufo-reconstruct',
             'bin/ufo-sinos',
             'bin/ufo-estimate-center',
             ],
    long_description=open('README.md').read(),
)
