import yaml
import logging

from copy import deepcopy
from collections import defaultdict
from pathlib import Path
from pandas import DataFrame

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)


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


def parse_mdisorder(ppc_root_dir):
    """

    :param ppc_root_dir: the root dir where to find the predictions
    :return: a list of chars, where "D" represents disorder
    """
    mdisorder_file = Path(ppc_root_dir, 'query.mdisorder')

    if not mdisorder_file.exists():
        return []

    num_col = -1
    mdisorder = []

    with mdisorder_file.open('r') as input_file:
        for line in input_file:
            if num_col > 0:
                data = line.split()

                if len(data) == num_col:
                    mdisorder.append(data[10])
                else:
                    break
            elif line.lstrip().startswith('Number'):
                data = line.split()
                num_col = len(data)

    return mdisorder


# Open the config file and parse into python dictionary
with open("./config.yml", 'r') as stream:
    try:
        configuration = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        print(exc)

# Prepare output config
output_config = defaultdict()

# Iteratively go through every group in config
for group in configuration:
    current = deepcopy(configuration[group])

    # Every group MUST have a data dir with PP output
    data_dir = current.pop('data_dir')

    # Parse consurf
    add_consurf = True
    consurf = parse_consurf(data_dir)

    # If no CONSURF prediction can be found, throw an error
    if len(consurf) < 1:
        logging.error(f"No CONSURF scores for group: {group}. Data dir: {data_dir}.")
        add_consurf = False

    # Parse meta-disorder
    add_mdisorder = True
    mdisorder = parse_mdisorder(data_dir)
    if len(mdisorder) < 1:
        logging.error(f"No meta-disorder predictions for group: {group}. Data dir: {data_dir}.")
        add_mdisorder = False

    # Iteratively go through every region in the group
    for region in current:

        # Every region MUST have a start
        start = int(current[region]['start'])

        # !!IMPORTANT: UniProt sequence indexing != from CS sequence indexing. 1 = 0
        start -= 1

        # Every region MUST have an end
        # !!IMPORTANT: end doesn't need to be modified, as python slices excluding upper bound
        # (and considering that end should be +1, that's exactly what we want!)
        end = int(current[region]['end'])

        current[region]["region_length"] = end - start

        # Get consurf average
        if add_consurf:
            # Make sure that start and end are effectively in sequence range, otherwise log an error!
            consurf_range = range(len(consurf) + 1)
            if start not in consurf_range or end not in consurf_range:
                logging.error(f"NO consurf average will be produced for {group}/{region}.\n"
                              f"       You are trying to access region {start+1}-{end}, "
                              f"but consurf predictions are in range {1}-{len(consurf)}")
                current[region]['region_consurf_average'] = None
            else:
                region_consurf = consurf[start:end]
                current[region]['region_consurf_average'] = sum(region_consurf)/len(region_consurf)

        # Count meta-disorder "disorder"
        if add_mdisorder:
            # Make sure that start and end are effectively in sequence range, otherwise log an error!
            mdisorder_range = range(len(mdisorder) + 1)
            if start not in mdisorder_range or end not in mdisorder_range:
                logging.error(f"NO meta-disorder count will be produced for {group}/{region}.\n"
                              f"       You are trying to access region {start+1}-{end}, "
                              f"but meta-disorder predictions are in range {1}-{len(mdisorder)}")
                current[region]['meta_disorder_predicted_disorder_count'] = None
            else:
                region_mdisorder = mdisorder[start:end]
                current[region]['meta_disorder_predicted_disorder_count'] = len([m for m in region_mdisorder if m == "D"])
                current[region]['meta_disorder_predicted_disorder_fraction'] = current[region][
                                                                                   'meta_disorder_predicted_disorder_count'] / \
                                                                               current[region]["region_length"]

    # Add metadata to the output config for the group
    current['data_dir'] = data_dir
    output_config[group] = current

# Write the output config
with open("./out_config.yml", 'w') as stream:
    yaml.dump(output_config, stream)

# Create a DataFrame containing groups/region in flat (tabular) form
flattened_items = list()

for group in output_config:
    current = deepcopy(output_config[group])
    data_dir = current.pop('data_dir')

    for region in current:
        flattened_item = deepcopy(current[region])

        flattened_item['group'] = group
        flattened_item['data_dir'] = data_dir
        flattened_item['region'] = region

        flattened_items.append(flattened_item)

output_table = DataFrame(flattened_items)

# Reorder for readability
output_table = output_table[['group', 'region', 'start', 'end', 'region_length', 'region_consurf_average', 'meta_disorder_predicted_disorder_count', 'meta_disorder_predicted_disorder_fraction', 'data_dir']]

# Store
output_table.to_csv('out_table.csv', index=None)
