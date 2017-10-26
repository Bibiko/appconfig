from __future__ import unicode_literals, print_function, division

from pyappconfig.util import Path
from pyappconfig import tasks

tasks.init(Path(__file__).parent.name)
