# Get Variables from Config
def get_config(var):
    with open('/etc/ConsolePi/ConsolePi.conf', 'r') as cfg:
        for line in cfg:
            if var in line:      
                var_out = line.replace('{0}='.format(var), '')   
                var_out = var_out.replace('"'.format(var), '', 1)   
                var_out = var_out.split('"')      
                var_out = var_out[0]      
                break

    if var_out == 'true' or var_out == 'false':
        var_out = True if var_out == 'true' else False

    return var_out

