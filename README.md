How to use:

1. Make sure you have `pyyaml` installed (`pip install pyyaml`)
2. Define interesting objects or regions in the `config.yml`
3. Make sure to include the `data_dir` for each region defined in the config; then make sure each region has a `start` and `end`
4. Run the python script (`python extractor.py`)
5. Results will appear in `out_config.yml` and as flat table in `out_table.csv`.
