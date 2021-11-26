from setuptools import setup, find_packages
from tofu import __version__

setup(
    name='tofu',
    python_requires='>=3',
    version=__version__,
    author='Matthias Vogelgesang',
    author_email='matthias.vogelgesang@kit.edu',
    url='http://ufo.kit.edu',
    packages=find_packages(),
    package_data={'tofu': ['gui.ui', 'ez/GUI/default_settings.yaml'],
                  'tofu.flow': ['composites/*.cm', 'config.json']},
    scripts=['bin/tofu'],
    install_requires=['tifffile'],
    long_description=open('README.md').read(),
)
