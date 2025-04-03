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

from concurrent.futures import ThreadPoolExecutor

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

def run_llama_batched(model, prompts, output_dir, threads=4, batch_size=32):
    if not os.path.exists(model):
        raise FileNotFoundError(f"Model file not found: {model}")
    
    os.makedirs(output_dir, exist_ok=True)
    prompt_file = "prompts.txt"
    output_file = f"{output_dir}/responses.txt"
    with open(prompt_file, "w") as f:
        f.write("\n".join(prompts))
    
    cmd = [
        os.path.join(llama_root, "build/bin/llama-batched"),
        "-m", model,
        "-t", str(threads),
        "-b", str(batch_size),  # Batch size for prompts
        "-f", prompt_file,
        "-c", "8192",           # Context size (matches model’s n_ctx_train)
        "-n", "256"             # Max tokens to generate per prompt
    ]
    
    start_time = time.time()
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        print(f"Stderr: {e.stderr}")
        raise
    elapsed_time = time.time() - start_time
    
    with open(output_file, "w") as f:
        f.write(result.stdout)
    
    return result.stdout.splitlines(), elapsed_time

def extract_answer(response):
    match = re.search(r"[-+]?\d*\.?\d+$", response)
    return match.group() if match else None

    
def score_responses(responses, true_answers):
    correct = 0
    for resp, true in zip(responses, true_answers):
        pred = extract_answer(resp)
        if pred and pred == str(true):
            correct += 1
    return correct / len(true_answers) * 100

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=os.path.join(llama_root, "models/smollm2-360m-instruct-q8_0.gguf"))
    parser.add_argument("--output-dir", default="outputs")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=128)
    args = parser.parse_args()

    # Step 1: Load GSM8K
    prompts, answers = extract_prompts_and_answers("test-00000-of-00001.parquet")

    # Step 2: Run with batching and measure time
    responses, elapsed_time = run_llama_batched(args.model, prompts, args.output_dir, args.threads, args.batch_size)

    # Step 3: Score
    score = score_responses(responses, answers)
    print(f"Score: {score:.2f}% correct")
    print(f"Time for 1 run: {elapsed_time:.2f} seconds")

    # Step 4: Save results
    results = [{"prompt": p, "response": r, "true_answer": a} for p, r, a in zip(prompts, responses, answers)]
    with open(f"{args.output_dir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    # Step 5: Save and score
    with open(f"{args.output_dir}/eval.json", "w") as f:
        json.dump({"score": score, "elapsed_time": elapsed_time}, f, indent=2)

if __name__ == "__main__":
    main()