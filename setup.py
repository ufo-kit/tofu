from setuptools import setup, find_packages
import subprocess

VERSION='0.7'

make_file = 'cc -Wall -std=c99 -fopenmp -O3 -o bin/generate "generate.c" -lm -ltiff'
subprocess.call([make_file], shell = True)

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
             'bin/generate',
             ],
    long_description=open('README.md').read(),
)
