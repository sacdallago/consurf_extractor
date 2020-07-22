import yaml

from copy import deepcopy
from collections import defaultdict
from pathlib import Path


def parse_consurf(ppc_root_dir):
    consurf_file = Path(ppc_root_dir, 'query.consurf.grades')

    if not consurf_file.exists():
        return []

    consurf = []
    num_col = -1
    skiped_lines = 0

    with consurf_file.open('r') as input_file:
        for line in input_file:
            if num_col > 0:
                data = line.split()

                if len(data) >= num_col:
                    consurf.append(int(data[3][0]))
                elif skiped_lines == 0:
                    skiped_lines = 1
                else:
                    break
            elif line.lstrip().startswith('POS'):
                data = line.split()
                num_col = len(data) - 5

    return consurf


with open("./config.yml", 'r') as stream:
    try:
        configuration = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        print(exc)

output_config = defaultdict()

for key in configuration:
    current = deepcopy(configuration[key])

    data_dir = current.pop('data_dir')
    consurf = parse_consurf(data_dir)

    for key in current:
        start = int(current[key]['start'])
        end = int(current[key]['end'])

        region_consurf = consurf[start:end]

        # current[key]['region_consurf'] = region_consurf
        current[key]['region_consurf_average'] = sum(region_consurf)/len(region_consurf)

    # current['consurf'] = consurf
    current['data_dir'] = data_dir
    output_config[key] = current

with open("./out_config.yml", 'w') as stream:
    yaml.dump(output_config, stream)
