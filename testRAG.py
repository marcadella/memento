import os
import argparse

import evaluate
from datasets import load_dataset
from openai import OpenAI
from agents.RAGAgent import RAGAgent, NonRAGAgent
import re

def local_llm(agent, prompt, choices):
    
    full_prompt = ("You will be given a multiple choice question to answer."
                    "The answer format should be in the form of a capitalized letter with only white spaces surounding it."
                    "Make sure that your answer is the last thing you say before stopping."
                    "The multiple choices will come in the format A) answer A\nB) answer B ect."
                    f"Here is the question: \n{prompt}\n"
                    f"Here are the choices:\n{choices}"
                    )


    agent.clear_all_context()
    #print("hear")
    agent.hear("user", full_prompt)
    #print("speak")
    output_string = agent.speak()
    return output_string



def run_test(agent):

    print("Loading Hugging Face dataset...")
    dataset = load_dataset("Joschka/big_bench_hard", "logical_deduction_seven_objects", split="logical_deduction_seven_objects")
    print("Finished loading")

    samples = dataset.select(range(100))

    # 2. Load traditional, mathematical scoring metrics
    accuracy_metric = evaluate.load("accuracy")

    # 4. Gather automated prompts, references, and predictions
    predictions = []
    references = []

    #filter to find answer.
    regex_filter = re.compile(r"\(([A-Z])\)\.?$|\b([A-Z])\b")

    for item in samples:

        if not isinstance(item, dict):
            print("item not dict")
            exit()

        prompt = item["question"]
        choices_raw = item["choices"]

        choices = "\n".join([f"{label} {text}" for label, text in zip(choices_raw["label"], choices_raw["text"])])


        ground_truth = str(item["target"]) 
        
        # Run your local LLM to get a raw string output
        llm_output = local_llm(agent, prompt, choices)
        
        match = re.search(regex_filter, llm_output)

        llm_answer = match.group(1) or match.group(2) if match else ""

        try:
            llm_answer = ord(llm_answer.upper()) - 65
        except:
            llm_answer = -1

        ground_truth = ord(ground_truth.upper()) - 65

        predictions.append(llm_answer)
        references.append(ground_truth)
        
        #print(f"\nPrompt: {prompt}")
        #print(f"LLM Output: {llm_output}")
        #print(f"Reference:  {ground_truth}")


    # 5. Compute mathematical scores
    print("\n--- Computing Free Metrics ---")
    #rouge_results = rouge_metric.compute(predictions=predictions, references=references)
    accuracy_results = accuracy_metric.compute(predictions=predictions, references=references)


    if accuracy_results:

        return accuracy_results['accuracy']
    
    return None



def main():

    ######### Boilerplate

    parser = argparse.ArgumentParser(
        description="A simple llm tester"
    )

    # Add arguments
    parser.add_argument("--model", "-m", type=str, default="gpt-4.1-mini", help="Conversation name")
    parser.add_argument("--char_length", '-c',  type=int, default=4000, help="set the max context length in char")
    parser.add_argument("--use_open_ai", '-r',  type=str, default="y", help="(Y/n) bool to choose to use open ai models or not")


    # Parse arguments
    args = parser.parse_args()


    api_url = os.environ.get("CHATUIT_BASE_URL", "http://127.0.0.1:1234/v1/")
    api_key = os.environ.get("CHATUIT_API_KEY", "")


    no_list = ["n", "N", "no", "No", "NO", "false", "False", "FALSE"]

    if args.use_open_ai in no_list:
        api_url = "http://127.0.0.1:1234/v1/"
        api_key = "dummykey"

    print(api_url, api_key)

    client = OpenAI(base_url=api_url,
                api_key=api_key,
                )


    try:
        args = parser.parse_args()
    except SystemExit:
        return
    ########

    model = args.model
    char_length = args.char_length

    #used as controll to compare performance
    control_agent = NonRAGAgent("A", client, model=model, verbose=False, max_context_length_char=char_length)

    print("running_control")
    control_score = run_test(control_agent)
    print("done_control")
    
    # We create an agent

    agent = RAGAgent("A", client, model=model, verbose=False, max_context_length_char=char_length)

    print("running_rag_agent")
    score = run_test(agent)
    print("done_rag_agent")

    print(f"agentic RAG result:")
    print(f"Accuracy Score:    {score:.4f} (Accuracy metric)")
    print("Controll score (No RAG):")
    print(f"Accuracy Score:    {control_score:.4f} (Accuracy metric)")




if __name__ == "__main__":
    main()
