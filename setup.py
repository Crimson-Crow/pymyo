from setuptools import setup
import pathlib

here = pathlib.Path(__file__).parent.resolve()
long_description = (here / 'README.md').read_text(encoding='utf-8')

setup(
    name='pymyo',
    version='1.0.0b1',
    description='Pythonic API to configure or retrieve data from a Thalmic Labs Myo armband through BLE',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/Crimson-Crow/pymyo',
    author='Crimson-Crow',
    author_email='github@crimsoncrow.dev',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Framework :: AsyncIO',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Operating System :: Microsoft :: Windows :: Windows 10',
        'Operating System :: POSIX :: Linux',
        'Operating System :: MacOS :: MacOS X',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Scientific/Engineering :: Human Machine Interfaces',
        'Topic :: Communications',
    ],
    keywords='myo armband bluetooth BLE',
    license='MIT',
    py_modules=['pymyo'],
    python_requires='>=3.6, <4',
    install_requires=[
        'bleak',
        'async-property',
        'pyobservable'
    ],
    project_urls={
        'Bug Reports': 'https://github.com/Crimson-Crow/pymyo/issues',
        'Source': 'https://github.com/Crimson-Crow/pymyo',
    },
)
