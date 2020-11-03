try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup
import pathlib

here = pathlib.Path(__file__).parent.resolve()

long_description = (here / 'README.rst').read_text(encoding='utf-8')

setup(
    name             = 'pymyo',
    version          = '1.0.0',
    description      = '', # TODO
    long_description = long_description,
    url              = 'https://github.com/Crimson-Crow/pymyo',
    author           = 'William Flynn',
    author_email     = 'github@crimsoncrow.dev',
    license          = 'MIT',
    py_modules       = ['pymyo'],
    install_requires=[
        'pygatt==4.0.5',
    ],
    extras_require={
        'gatttool': ['pexpect; platform_system=="Linux"'],
    },
    keywords='myo, armband, bluetooth, BLE',
    classifiers=(
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Scientific/Engineering :: Human Machine Interfaces'
    ),
    project_urls={
        'Bug Reports': 'https://github.com/Crimson-Crow/pymyo/issues',
        'Source': 'https://github.com/Crimson-Crow/pymyo',
    },
)
