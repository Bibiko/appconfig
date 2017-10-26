from setuptools import setup, find_packages


setup(
    name='pyappconfig',
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
        'Fabric3',
        'fabtools-python==0.19.7',
        'clldutils',
        'Jinja2',
        'pathlib2; python_version < "3"',
        'pytz',
    ],
    platforms='any',
    long_description='',
    classifiers=[
        'Private :: Do Not Upload',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
    ],
    tests_require=['pytest', 'pytest-mock', 'pytest-cov'],
    entry_points={
        'console_scripts': ['appconfig=pyappconfig.cli:main'],
    },
)
