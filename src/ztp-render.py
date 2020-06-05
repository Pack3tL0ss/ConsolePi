#!/etc/ConsolePi/venv/bin/python3

import sys
import yaml
from jinja2 import Environment, FileSystemLoader

sys.path.insert(0, '/etc/ConsolePi/src/pypkg')
from consolepi import log, utils # NoQA


# Look for config template by same name in same dir
if not len(sys.argv) > 1:
    print('Template Name Must be provided')
    sys.exit(1)
elif not utils.valid_file(sys.argv[1] + '.j2'):
    print(f'{sys.argv[1]}.j2 Not Found or empty')
    sys.exit(1)
else:
    cfg_templ = sys.argv[1] + '.j2'

# Look for variables file by same name in same dir
if utils.valid_file(sys.argv[1] + '.yaml'):
    var_file = sys.argv[1] + '.yaml'
# Look for single common variables file
elif utils.valid_file('./variables.yaml'):
    var_file = 'variables.yaml'
else:
    print('No Valid Variable File Found')
    sys.exit(1)

config_data = yaml.load(open(var_file), Loader=yaml.FullLoader)
if var_file == 'variables.yaml':
    config_data = config_data.get(sys.argv[1])


# Load Jinja2 template
env = Environment(loader=FileSystemLoader('./'), trim_blocks=True, lstrip_blocks=True)
template = env.get_template(cfg_templ)

# Render the template with data and print the output
print(template.render(config_data))
