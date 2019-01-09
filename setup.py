# setup.py

from setuptools import setup, find_packages


setup(
    name='appconfig',
    version='0.0',
    author='',
    author_email='lingweb@shh.mpg.de',
    description='Remote control for DLCE apps',
    keywords='fabric',
    license='Apache 2.0',
    url='https://github.com/shh-dlce/appconfig',
    packages=find_packages(),
    platforms='any',
    python_requires='!=3.0.*,!=3.1.*,!=3.2.*,!=3.3.*,!=3.4.*',
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'attrs>=18.1.0',
        'Fabric3>=1.11',
        'fabtools-python>=0.19.7',
        'python-dateutil',
        'Jinja2',
        'pytz',
        'pycdstar>=0.4.1',
        'cdstarcat>=0.6.2',
    ],
    extras_require={
        'dev': ['flake8'],
        'test': [
            'mock',
            'pytest>=3.6',
            'pytest-mock',
            'pytest-cov',
        ],
    },
    long_description='',
    classifiers=[
        'Private :: Do Not Upload',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    entry_points={
        'console_scripts': [
            'appconfig=appconfig.__main__:main',
        ]
    },
)
