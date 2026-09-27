"""
Hermes AI Agent Cloud Fine-Tuning Script (Unsloth / LoRA Fast Trainer)
Can be run on Google Colab (Free T4 GPU) or any Cloud GPU instance.
"""

import os
import torch
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments
from unsloth import FastLanguageModel

# 1. Configuration
MAX_SEQ_LENGTH = 2048
LOAD_IN_4BIT = True
MODEL_NAME = "unsloth/llama-3-8b-Instruct-bnb-4bit" # Or unsloth/Llama-3.2-3B-Instruct

print(f"Loading Base Model: {MODEL_NAME}...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=MODEL_NAME,
    max_seq_length=MAX_SEQ_LENGTH,
    dtype=None,
    load_in_4bit=LOAD_IN_4BIT,
)

# 2. Add LoRA Adapters
print("Attaching LoRA adapters...")
model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_alpha=16,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=3407,
)

# 3. Load Hermes Dataset
dataset_file = "hermes_training_dataset.jsonl"
print(f"Loading Dataset: {dataset_file}...")
dataset = load_dataset("json", data_files=dataset_file, split="train")

def formatting_prompts_func(examples):
    convos = examples["messages"]
    texts = [tokenizer.apply_chat_template(convo, tokenize=False, add_generation_prompt=False) for convo in convos]
    return {"text": texts}

dataset = dataset.map(formatting_prompts_func, batched=True)

# 4. Trainer
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=MAX_SEQ_LENGTH,
    dataset_num_proc=2,
    packing=False,
    args=TrainingArguments(
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        warmup_steps=5,
        max_steps=60,
        learning_rate=2e-4,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        logging_steps=1,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        seed=3407,
        output_dir="outputs_hermes",
    ),
)

print("Starting Fine-Tuning Training...")
trainer.train()

# 5. Save Model
OUTPUT_DIR = "hermes_custom_model"
print(f"Saving Fine-Tuned Model to {OUTPUT_DIR}...")
model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)
print("Training Complete! Hermes custom model is ready.")
