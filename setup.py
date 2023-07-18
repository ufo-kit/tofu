from setuptools import setup, find_packages
from tofu import __version__

setup(
    name='ufo-tofu',
    python_requires='>=3',
    version=__version__,
    author='Matthias Vogelgesang',
    author_email='matthias.vogelgesang@kit.edu',
    url='http://github.com/ufo-kit/tofu',
    license='LGPL',
    packages=find_packages(),
    package_data={'tofu': ['gui.ui'],
                  'tofu.flow': ['composites/*.cm', 'config.json']},
    scripts=['bin/tofu'],
    exclude_package_data={'': ['README.rst']},
    install_requires= [
        'PyGObject',
        'imageio',
        'numpy',
        'networkx',
        'PyQt5',
        'pyqtconsole',
        'pyxdg',
        'qtpynodeeditor'
    ],
    description="A fast, versatile and user-friendly image "\
                "processing toolkit for computed tomography",
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
)
