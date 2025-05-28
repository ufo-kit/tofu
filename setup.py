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
        'tifffile',
        'scikit-image',
    ],
    extras_require={
        'interactive': ['IPython'],
        'gui': ['PyQt5', 'pyqtgraph'],
        'flow': ['PyQt5', 'networkx', 'pyqtconsole', 'pyxdg', 'qtpynodeeditor', 'pyqtgraph'],
        'test': ['pytest', 'pytest-qt'],
        'ez': ['PyQt5', 'PyYAML', 'pyqtgraph', 'matplotlib'],
    },
    description="A fast, versatile and user-friendly image "\
                "processing toolkit for computed tomography",
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
)
