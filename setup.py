from setuptools import setup

with open('README.md', 'r', encoding='utf-8') as fh:
    long_description = fh.read()

setup(
    name             = 'pymyo',
    version          = '1.0.0',
    author           = 'William Flynn',
    author_email     = 'github@crimsoncrow.dev',
    description      = 'A complete and pythonic API to interact with a Myo armband through BLE',
    long_description = long_description,
    long_description_content_type="text/markdown",
    url              = 'https://github.com/Crimson-Crow/pymyo',
    license          = 'MIT',
    py_modules       = ['pymyo'],
    install_requires=[
        'pygatt==4.0.5',
    ],
    extras_require={
        'gatttool': ['pexpect'],
    },
    python_requires='~=3.5',
    keywords='myo armband bluetooth BLE',
    classifiers=(
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Scientific/Engineering :: Human Machine Interfaces'
    ),
    project_urls={
        'Bug Reports': 'https://github.com/Crimson-Crow/pymyo/issues',
        'Source': 'https://github.com/Crimson-Crow/pymyo',
    },
)
