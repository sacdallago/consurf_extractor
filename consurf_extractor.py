import yaml

from copy import deepcopy
from collections import defaultdict
from pathlib import Path
from pandas import DataFrame


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

for group in configuration:
    current = deepcopy(configuration[group])

    data_dir = current.pop('data_dir')
    consurf = parse_consurf(data_dir)

    for region in current:
        start = int(current[region]['start'])

        # !!IMPORTANT: UniProt sequence indexing != from CS sequence indexing. 1 = 0
        start -= 1

        # !!IMPORTANT: end doesn't need to be modified, as python slices excluding upper bound
        # (and considering that end should be +1, that's exactly what we want!)
        end = int(current[region]['end'])

        # Make sure that start and end are effectively in sequence range, otherwise throw an error!
        sequence_range = range(len(consurf))

        if start not in sequence_range or end not in sequence_range:
            raise Exception(f"You are tryin to access region {start+1}-{end}, "
                            f"but consurf prediction is in range {1}-{len(consurf)}")

        region_consurf = consurf[start:end]

        current[region]['region_consurf_average'] = sum(region_consurf)/len(region_consurf)

    current['data_dir'] = data_dir
    output_config[group] = current

with open("./out_config.yml", 'w') as stream:
    yaml.dump(output_config, stream)

# Create a dataframe containing the info in tabular form

unnested_items = list()

for group in output_config:
    current = deepcopy(output_config[group])
    data_dir = current.pop('data_dir')

    for region in current:
        unnested_item = deepcopy(current[region])

        unnested_item['group'] = group
        unnested_item['data_dir'] = data_dir
        unnested_item['region'] = region

        unnested_items.append(unnested_item)

output_table = DataFrame(unnested_items)

# Reorder for readability
output_table = output_table[['group', 'region', 'start', 'end', 'region_consurf_average', 'data_dir']]

# Store
output_table.to_csv('out_table.csv', index=None)