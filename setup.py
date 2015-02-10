from setuptools import setup, find_packages
import subprocess

VERSION='0.7'

setup(
    name='ufo-scripts',
    version=VERSION,
    author='Matthias Vogelgesang',
    author_email='matthias.vogelgesang@kit.edu',
    url='http://ufo.kit.edu',
    packages=find_packages(),
    package_data={'':['gui.ui']},
    scripts=['bin/ufo-reconstruct',
             'bin/ufo-sinos',
             'bin/ufo-estimate-center',
             'bin/ufo-perf',
             ],
    long_description=open('README.md').read(),
)
