import subprocess
import pandas as pd
import argparse
import os
import json
import subprocess
import pandas as pd
import argparse
import os
import json
import time
import re

def find_llama_root():
    # Check current directory
    if os.path.exists("build"):
        return os.getcwd()
    
    # Check parent directory
    parent = os.path.dirname(os.getcwd())
    if os.path.exists(os.path.join(parent, "build")):
        return parent
    
    # Check grandparent directory
    grandparent = os.path.dirname(parent)
    if os.path.exists(os.path.join(grandparent, "build")):
        return grandparent
    
    # Check great-grandparent directory
    great_grandparent = os.path.dirname(grandparent)
    if os.path.exists(os.path.join(great_grandparent, "build")):
        return great_grandparent
    
    raise FileNotFoundError("Could not find llama root directory")

llama_root = find_llama_root()

def extract_prompts_and_answers(parquet_file):
    df = pd.read_parquet(parquet_file)
    return df["question"].tolist(), df["answer"].tolist()

def run_llama_jobs(model, prompts, output_dir):

    pass


def extract_answer(response):
    match = re.search(r"[-+]?\d*\.?\d+$", response)
    return match.group() if match else None