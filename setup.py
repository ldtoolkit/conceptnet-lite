# -*- coding: utf-8 -*-
from distutils.core import setup

packages = \
['conceptnet_lite']

package_data = \
{'': ['*']}

install_requires = \
['graphdb>=2019.2,<2020.0', 'pySmartDL>=1.3,<2.0']

setup_kwargs = {
    'name': 'conceptnet-lite',
    'version': '0.1.0',
    'description': 'Python library to work with ConceptNet offline without the need of PostgreSQL',
    'long_description': '# conceptnet-lite\nPython library to work with ConceptNet offline without the need of PostgreSQL\n',
    'author': 'Roman Inflianskas',
    'author_email': 'infroma@gmail.com',
    'url': 'https://github.com/rominf/conceptnet-lite',
    'packages': packages,
    'package_data': package_data,
    'install_requires': install_requires,
    'python_requires': '>=3.6,<4.0',
}


setup(**setup_kwargs)
