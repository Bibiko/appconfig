# setup.py

from setuptools import setup, find_packages


setup(
    name='appconfig',
    version='0.0',
    author='',
    author_email='lingweb@shh.mpg.de',
    description='Remote control for DLCE apps',
    keywords='fabric',
    url='',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'configparser; python_version < "3"',
        'Fabric3>=1.11',
        'fabtools-python>=0.19.7',
        'Jinja2',
        'pathlib2; python_version < "3"',
        'pytz',
    ],
    extras_require = {
        'dev': ['flake8'],
        'test': [
            'pytest>=3.1',
            'pytest-mock',
            'mock',
            'pytest-cov',
        ],
    },
    platforms='any',
    long_description='',
    classifiers=[
        'Private :: Do Not Upload',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
)
