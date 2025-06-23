import yaml
from collections import defaultdict

with open("configuration.yaml", "r") as f:
    config = yaml.safe_load(f)
    in_memory_store = defaultdict(dict)