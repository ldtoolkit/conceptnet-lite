# -*- coding: utf-8 -*-
from distutils.core import setup

packages = \
['conceptnet_lite']

package_data = \
{'': ['*']}

install_requires = \
['langcodes>=1.4,<2.0', 'pony>=0.7.10,<0.8.0', 'pySmartDL>=1.3,<2.0']

setup_kwargs = {
    'name': 'conceptnet-lite',
    'version': '0.1.6',
    'description': 'Python library to work with ConceptNet offline without the need of PostgreSQL',
    'long_description': '# conceptnet-lite\nPython library to work with ConceptNet offline without the need for PostgreSQL\n',
    'author': 'Roman Inflianskas',
    'author_email': 'infroma@gmail.com',
    'url': 'https://github.com/ldtoolkit/conceptnet-lite',
    'packages': packages,
    'package_data': package_data,
    'install_requires': install_requires,
    'python_requires': '>=3.6,<4.0',
}


setup(**setup_kwargs)
