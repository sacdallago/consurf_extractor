import yaml
import logging

from copy import deepcopy
from collections import defaultdict, namedtuple
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


def parse_profbval(ppc_root_dir):
    """
    Ranges: 0-10 (Very Low)
            11-30 (Low)
            31-70 (Intermediate)
            71-90 (High)
            91-100 (Very High)

    :param ppc_root_dir: the root dir where to find the predictions
    :return: list of values (see function definition for interpretation)
    """
    profbval_file = Path(ppc_root_dir, 'query.profbval')

    if not profbval_file.exists():
        return []

    profbval = []
    read_line = False

    with profbval_file.open('r') as input_file:
        for line in input_file:
            if read_line:
                data = line.split()

                if len(data) == 3:
                    profbval.append(int(data[1]))
                else:
                    break
            elif line.lstrip().startswith('* out vec: (I8,A1,100I4)'):
                read_line = True

    return profbval


reprof_prediction_template = namedtuple('reprof_prediction', ['structure', 'accessibility'])


def parse_reprof(ppc_root_dir) -> reprof_prediction_template:
    """
    structure values:
        H - Helix
        E - Strand
        L - Turn

    accessibility values:
        e - Exposed
        i - Intermediate
        b - Buried

    :param ppc_root_dir: the root dir where to find the predictions
    :return: touple of lists: (structure, accessibility)
    """
    reprof_file = Path(ppc_root_dir, 'query.reprof')

    if not reprof_file.exists():
        return reprof_prediction_template(accessibility=[], structure=[])

    num_col = -1
    structure = []
    accessibility = []

    with reprof_file.open('r') as input_file:
        for line in input_file:
            if num_col > 0:
                data = line.split()

                if len(data) == num_col:
                    structure.append(data[2])
                    accessibility.append(data[11])
                else:
                    break
            elif line.lstrip().startswith('#'):
                continue
            elif line.lstrip().startswith('No'):
                data = line.split()
                num_col = len(data)

    return reprof_prediction_template(accessibility=accessibility, structure=structure)


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

    # Parse profbval
    add_profbval = True
    profbval = parse_profbval(data_dir)
    if len(profbval) < 1:
        logging.error(f"No profbval predictions for group: {group}. Data dir: {data_dir}.")
        add_profbval = False

    # Parse reprof
    add_reprof = True
    reprof = parse_reprof(data_dir)
    if len(reprof.accessibility) < 1:
        logging.error(f"No reprof accessibility predictions for group: {group}. Data dir: {data_dir}.")
        add_reprof = False

    regions = current.pop("regions")

    # Iteratively go through every region in the group
    for region in regions:

        # Every region MUST have a start
        start = int(regions[region]['start'])

        # !!IMPORTANT: UniProt sequence indexing != from CS sequence indexing. 1 = 0
        start -= 1

        # Every region MUST have an end
        # !!IMPORTANT: end doesn't need to be modified, as python slices excluding upper bound
        # (and considering that end should be +1, that's exactly what we want!)
        end = int(regions[region]['end'])

        regions[region]["region_length"] = end - start

        # Get consurf average
        if add_consurf:
            # Make sure that start and end are effectively in sequence range, otherwise log an error!
            consurf_range = range(len(consurf) + 1)
            if start not in consurf_range or end not in consurf_range:
                logging.error(f"NO consurf average will be produced for {group}/{region}.\n"
                              f"       You are trying to access region {start+1}-{end}, "
                              f"but consurf predictions are in range {1}-{len(consurf)}")
                regions[region]['region_consurf_average'] = None
            else:
                region_consurf = consurf[start:end]
                regions[region]['region_consurf_average'] = sum(region_consurf)/len(region_consurf)

        # Get consurf average
        if add_profbval:
            # Make sure that start and end are effectively in sequence range, otherwise log an error!
            profbval_range = range(len(profbval) + 1)
            if start not in profbval_range or end not in profbval_range:
                logging.error(f"NO profbval average will be produced for {group}/{region}.\n"
                              f"       You are trying to access region {start + 1}-{end}, "
                              f"but profbval predictions are in range {1}-{len(consurf)}")
                regions[region]['region_profbval_average'] = None
            else:
                region_profbval = profbval[start:end]
                regions[region]['region_profbval_average'] = sum(region_profbval) / len(region_profbval)

        # Count meta-disorder "disorder"
        if add_mdisorder:
            # Make sure that start and end are effectively in sequence range, otherwise log an error!
            mdisorder_range = range(len(mdisorder) + 1)
            if start not in mdisorder_range or end not in mdisorder_range:
                logging.error(f"NO meta-disorder count will be produced for {group}/{region}.\n"
                              f"       You are trying to access region {start+1}-{end}, "
                              f"but meta-disorder predictions are in range {1}-{len(mdisorder)}")
                regions[region]['meta_disorder_predicted_disorder_count'] = None
            else:
                region_mdisorder = mdisorder[start:end]
                regions[region]['meta_disorder_predicted_disorder_count'] = len([m for m in region_mdisorder if m == "D"])
                regions[region]['meta_disorder_predicted_disorder_fraction'] = regions[region]['meta_disorder_predicted_disorder_count'] / regions[region]["region_length"]

        # Count reprof "Exposed"
        if add_reprof:
            # Make sure that start and end are effectively in sequence range, otherwise log an error!
            reprof_range = range(len(reprof.accessibility) + 1)
            if start not in reprof_range or end not in reprof_range:
                logging.error(f"NO reprof accessibility count will be produced for {group}/{region}.\n"
                              f"       You are trying to access region {start + 1}-{end}, "
                              f"but reprof accessibility predictions are in range {1}-{len(mdisorder)}")
                regions[region]['reprof_predicted_exposed_count'] = None
            else:
                region_reprof = reprof.accessibility[start:end]
                regions[region]['reprof_predicted_exposed_count'] = len(
                    [m for m in region_reprof if m == "e"])
                regions[region]['reprof_predicted_exposed_fraction'] = regions[region]['reprof_predicted_exposed_count'] / regions[region]["region_length"]

    # Add metadata to the output config for the group
    current['regions'] = regions
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
    regions = current.pop('regions')

    for region in regions:
        flattened_item = deepcopy(regions[region])

        flattened_item['group'] = group
        flattened_item['data_dir'] = data_dir
        flattened_item['region'] = region

        flattened_items.append(flattened_item)

output_table = DataFrame(flattened_items)

# Reorder for readability
output_table = output_table[['group', 'region', 'start', 'end', 'region_length', 'region_consurf_average',
                             'region_profbval_average', 'meta_disorder_predicted_disorder_count',
                             'meta_disorder_predicted_disorder_fraction', 'reprof_predicted_exposed_count',
                             'reprof_predicted_exposed_fraction', 'data_dir']]

# Store
output_table.to_csv('out_table.csv', index=None)
