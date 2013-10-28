from setuptools import setup, find_packages

VERSION='0.2'

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
