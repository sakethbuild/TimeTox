import json
import os

files = [
    "results/vanilla_summaries_run1.json",
    "results/vanilla_summaries_run2.json", 
    "results/vanilla_summaries_run3.json",
    "results/vanilla_summaries_run4.json",
    "results/vanilla_summaries_run5.json",
    "results/vanilla_summaries_dataset.json",
    "results/vanilla_summaries_dataset_run2.json",
    "results/vanilla_summaries_dataset_run3.json"
]

print("File Count Summary:")
for f in files:
    try:
        with open(f, 'r') as fp:
            data = json.load(fp)
            print(f"{f}: {len(data)}")
    except FileNotFoundError:
        print(f"{f}: Not Found")
    except Exception as e:
        print(f"{f}: Error {e}")
