import sys
from setuptools import setup, find_packages

requires = [
    'Fabric3',
    'fabtools-python==0.19.7',
    'Jinja2',
    'pytz',
]
if sys.version_info.major == 2:
    requires.append('pathlib2')

setup(name='pyappconfig',
      version='0.0',
      description='Remote control for DLCE apps',
      long_description='',
      classifiers=[
        "Programming Language :: Python",
        ],
      author='',
      author_email='lingweb@shh.mpg.de',
      url='',
      keywords='fabric',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      install_requires=requires,
      tests_require=requires,
      test_suite="pyappconfig",
)
