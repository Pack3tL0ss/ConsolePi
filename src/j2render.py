#!/etc/ConsolePi/venv/bin/python3
'''
Convert ConsolePi system file template to final state

params:
argv[1] template name without j2 extension (file should be in /etc/ConsolePi/src/j2)
argv[2] ignored by this script used by installer which compares resulting template to file @ argv[2] and updates if different
remaining arguments (3+) should be in form template_var=desired_value

Output:
Creates file in /tmp/ directory (/tmp/argv[1]) used to compare against system file specified in argv[2] by install script.
'''
import jinja2
import sys


def parse_args():
    parameter_dict = {}
    for user_input in sys.argv[3:]:
        if "=" not in user_input:
            continue
        varname = user_input.split("=")[0]
        varvalue = '='.join(user_input.split("=")[1:])
        varvalue = varvalue.replace('{{cr}}', '\n')
        if varvalue.lower() in ["true", "false"]:
            varvalue = True if varvalue.lower() == "true" else False
        parameter_dict[varname] = varvalue
    return parameter_dict


parameter_dict = parse_args()
templateLoader = jinja2.FileSystemLoader(searchpath="/etc/ConsolePi/src/j2/")
templateEnv = jinja2.Environment(loader=templateLoader, keep_trailing_newline=True, trim_blocks=True, lstrip_blocks=True)
template = templateEnv.get_template(sys.argv[1] + '.j2')
outputText = template.render(parameter_dict)
template.stream(parameter_dict).dump(f'/tmp/{sys.argv[1]}')

# print(outputText)
