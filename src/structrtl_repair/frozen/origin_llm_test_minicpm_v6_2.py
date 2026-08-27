import os
import re
import time
from PIL import Image
import torch
from transformers import AutoModel, AutoProcessor, AutoTokenizer
from path_config import SCRIPT_DIR, resolve_model_path

try:
    from transformers import AutoModelForVision2Seq as AutoVisionModel
except ImportError:
    from transformers import AutoModelForImageTextToText as AutoVisionModel

# ==== Model and device configuration ====
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
model_path = resolve_model_path()
MODEL_PRECISION = "bf16"
model_backend = "standard_generate"

try:
    import transformers.utils.import_utils as _tf_import_utils

    if not hasattr(_tf_import_utils, "is_torch_fx_available"):
        _tf_import_utils.is_torch_fx_available = lambda: False
except Exception:
    pass

try:
    from transformers.modeling_utils import PreTrainedModel

    if not hasattr(PreTrainedModel, "all_tied_weights_keys"):
        def _get_all_tied_weights_keys(self):
            value = self.__dict__.get("_all_tied_weights_keys_compat", None)
            if value is not None:
                return value
            return {k: None for k in (getattr(self, "_tied_weights_keys", None) or [])}

        def _set_all_tied_weights_keys(self, value):
            self.__dict__["_all_tied_weights_keys_compat"] = value

        PreTrainedModel.all_tied_weights_keys = property(
            _get_all_tied_weights_keys,
            _set_all_tied_weights_keys,
        )
except Exception:
    pass


def apply_bitsandbytes_int8_patch():
    try:
        import bitsandbytes.autograd._functions as bnb_autograd_functions
        import bitsandbytes.functional as bnb_functional
        import bitsandbytes.libbitsandbytes_cpu as bnb_cuda_ops
    except Exception:
        return

    if getattr(bnb_functional.int8_vectorwise_quant, "_mgemmv_patched", False):
        return

    def safe_int8_vectorwise_quant(A, threshold=0.0):
        rows = A.shape[0]
        cols = A.shape[1]
        row_stats = torch.empty(rows, device=A.device, dtype=torch.float32)
        out_row = torch.empty(A.shape, device=A.device, dtype=torch.int8)
        outlier_cols = None

        A_row_major = A.contiguous()
        out_row_2d = out_row.view(rows, cols)

        bnb_cuda_ops.cint8_vector_quant(
            get_ptr(A_row_major),
            get_ptr(out_row_2d),
            get_ptr(row_stats),
            ct.c_float(threshold),
            ct.c_int32(rows),
            ct.c_int32(cols),
            bnb_cuda_ops._get_tensor_stream(A),
        )

        if rows > 1 and outlier_cols is not None and outlier_cols.numel() > 0:
            out_row_2d[:, outlier_cols] = 0

        return out_row, row_stats, outlier_cols

    from bitsandbytes.cextension import get_ptr
    import ctypes as ct

    safe_int8_vectorwise_quant._mgemmv_patched = True
    bnb_functional.int8_vectorwise_quant = safe_int8_vectorwise_quant
    bnb_autograd_functions.F.int8_vectorwise_quant = safe_int8_vectorwise_quant

def _first_valid_token_id(tok, candidates):
    for token in candidates:
        try:
            token_id = tok.convert_tokens_to_ids(token)
            if token_id is not None and token_id != -1:
                return token_id
        except Exception:
            pass
        try:
            encoded = tok(token, add_special_tokens=False)
            input_ids = encoded.get("input_ids") if isinstance(encoded, dict) else getattr(encoded, "input_ids", None)
            if input_ids:
                return input_ids[0]
        except Exception:
            pass
    return None


def _patch_minicpm_tokenizer_ids(proc):
    tok = getattr(proc, "tokenizer", proc)
    alias_map = {
        "bos_id": ("bos_token_id",),
        "eos_id": ("eos_token_id",),
        "pad_id": ("pad_token_id", "eos_token_id"),
    }
    for attr, source_attrs in alias_map.items():
        if hasattr(tok, attr):
            continue
        for source_attr in source_attrs:
            value = getattr(tok, source_attr, None)
            if value is not None:
                try:
                    setattr(tok, attr, value)
                    break
                except Exception:
                    pass
    token_map = {
        "im_start_id": ("<image>", "<|image_start|>", "<image_start>", "<im_start>"),
        "im_end_id": ("</image>", "<|image_end|>", "<image_end>", "<im_end>"),
        "slice_start_id": ("<slice>", "<|slice_start|>", "<slice_start>"),
        "slice_end_id": ("</slice>", "<|slice_end|>", "<slice_end>"),
    }
    for attr, candidates in token_map.items():
        if hasattr(tok, attr):
            continue
        token_id = _first_valid_token_id(tok, candidates)
        if token_id is not None:
            try:
                setattr(tok, attr, token_id)
            except Exception:
                pass
    return tok


processor = AutoProcessor.from_pretrained(str(model_path), trust_remote_code=True)
tokenizer = _patch_minicpm_tokenizer_ids(processor)
try:
    model = AutoVisionModel.from_pretrained(
        str(model_path),
        device_map="auto",
        dtype=torch.bfloat16,
        attn_implementation="eager",
        trust_remote_code=True,
    )
except Exception as vision_error:
    print(f"[INFO] Falling back to AutoModel remote-code loader: {vision_error}")
    model = AutoModel.from_pretrained(
        str(model_path),
        device_map="auto",
        dtype=torch.bfloat16,
        low_cpu_mem_usage=True,
        trust_remote_code=True,
    )
    class_name = model.__class__.__name__.lower()
    config_name = model.config.__class__.__name__.lower()
    if "minicpm" in class_name or "minicpm" in config_name:
        model_backend = "minicpm_chat"
model.eval()

def clean_generated_code(text):
    """
    Extract the final Verilog module from model output and ensure it ends with endmodule.
    This removes echoed prompt text such as 'user' / 'assistant' headers.
    """
    code_block_match = re.search(
        r"```(?:verilog|Verilog|sv|systemverilog|SV)?\s*\n(.*?)```",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if code_block_match:
        text = code_block_match.group(1)

    module_matches = list(re.finditer(r"^\s*module\s+[A-Za-z_][A-Za-z0-9_$]*\b", text, re.MULTILINE))
    endmodule_matches = list(re.finditer(r"^\s*endmodule\b", text, re.MULTILINE))

    if module_matches:
        start = module_matches[-1].start()
        if endmodule_matches:
            end = endmodule_matches[-1].end()
            if end > start:
                return text[start:end].strip() + "\n"
        return text[start:].strip() + "\nendmodule\n"

    truncated = re.split(r"endmodule", text, maxsplit=1)[0]
    return truncated.strip() + "\nendmodule"

def load_image(image_path):
    """Load an image from disk and convert it to RGB format."""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")
    return Image.open(image_path).convert("RGB")

def generate_code(prompt, image_path):
    """
    Generate Verilog code based on the input prompt and image.

    Steps:
    1. Load the image from disk.
    2. Parse the prompt into text before and after the image tag.
    3. Format the input in chat style with image and text.
    4. Preprocess using processor and move tensors to the target device.
    5. Use the model to generate code tokens.
    6. Decode and clean the result.
    """
    image = load_image(image_path)
    if model_backend == "minicpm_chat":
        return clean_generated_code(minicpm_chat_generate(prompt, image, max_new_tokens=8192, temperature=0.8, top_p=0.9))

    before_text, after_text = split_prompt_at_image_tag(prompt)

    # Construct chat-style input
    messages = [{"role": "user", "content": []}]
    if before_text:
        messages[0]["content"].append({"type": "text", "text": before_text})
    messages[0]["content"].append({"type": "image"})
    if after_text:
        messages[0]["content"].append({"type": "text", "text": after_text})

    # Convert messages to input string for model
    input_text = processor.apply_chat_template(messages, add_generation_prompt=True)

    # Prepare model inputs (image and text) as tensors
    inputs = processor(image, input_text, add_special_tokens=False, return_tensors="pt").to(device)

    # Generate output token IDs using sampling
    generate_ids = model.generate(
        **inputs,
        max_new_tokens=8192,
        temperature=0.8,
        top_p=0.9,
        do_sample=True
    )

    # Decode token IDs to readable text
    output_text = processor.decode(generate_ids[0], skip_special_tokens=True)
    return clean_generated_code(output_text)


def build_minicpm_question(prompt):
    before_text, after_text = split_prompt_at_image_tag(prompt)
    parts = []
    if before_text:
        parts.append(before_text)
    if after_text:
        parts.append(after_text)
    if not parts:
        parts.append(re.sub(r"<\s*/?\s*(image|img)\s*>", "", prompt, flags=re.IGNORECASE).strip())
    return "\n".join(p for p in parts if p).strip()


def minicpm_chat_generate(prompt, image=None, *, max_new_tokens=1536, temperature=0.2, top_p=0.9):
    question = build_minicpm_question(prompt)
    kwargs = {
        "max_new_tokens": max_new_tokens,
        "temperature": temperature,
        "top_p": top_p,
    }
    if image is None:
        content = question
    elif isinstance(image, (list, tuple)):
        content = [*image, question]
    else:
        content = [image, question]
    msgs = [{"role": "user", "content": content}]
    attempts = [
        lambda: model.chat(msgs=msgs, tokenizer=tokenizer, processor=processor, **kwargs),
        lambda: model.chat(msgs=msgs, tokenizer=tokenizer, **kwargs),
        lambda: model.chat(msgs=msgs, tokenizer=processor, **kwargs),
    ]
    last_error = None
    for call in attempts:
        try:
            output = call()
            if isinstance(output, tuple):
                output = output[0]
            return str(output)
        except TypeError as exc:
            last_error = exc
            continue
    if last_error is not None:
        raise last_error
    raise RuntimeError("MiniCPM chat failed without an exception")

def split_prompt_at_image_tag(prompt):
    """Split the prompt at <image> or <img> tag (case-insensitive)."""
    parts = re.split(r"<\s*image\s*>|<\s*img\s*>", prompt, flags=re.IGNORECASE)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    else:
        return prompt.strip(), None

def process_files(base_path, num_modules_min, num_modules_max, num_tests):
    """
    Main processing loop:
    Traverse through all modules and test sets, read the description and image,
    call the model, and write the generated Verilog code.
    """
    for i in range(num_modules_min, num_modules_max + 1):
        module_name = f'module{i}'
        for j in range(1, num_tests + 1):
            test_name = f'test{j}'
            description_path = os.path.join(base_path, module_name, test_name, 'description')
            code_path = os.path.join(base_path, module_name, test_name, 'code')
            os.makedirs(code_path, exist_ok=True)

            file_index = 0
            while True:
                desc_file = os.path.join(description_path, f"description{file_index}.txt")
                image_name_file = os.path.join(description_path, f"image_name{file_index}.txt")

                if not os.path.exists(desc_file) or not os.path.exists(image_name_file):
                    break  # No more description-image pairs

                with open(desc_file, "r") as f:
                    prompt = f.read().strip()
                with open(image_name_file, "r") as f:
                    image_filename = f.read().strip()

                image_path = os.path.join(description_path, image_filename)
                if not os.path.exists(image_path):
                    print(f"[Skipping] Image not found: {image_filename}")
                    file_index += 1
                    continue

                print(f"[Processing] {module_name}/{test_name}/description{file_index}.txt + {image_filename}")

                try:
                    generated_code = generate_code(prompt, image_path)
                    cleaned_code = clean_generated_code(generated_code)

                    txt_out_path = os.path.join(code_path, f"llm_code{file_index}.txt")
                    verilog_out_path = os.path.join(code_path, f"llm_code{file_index}.v")

                    with open(txt_out_path, "w") as f:
                        f.write(generated_code)
                    with open(verilog_out_path, "w") as f:
                        f.write(cleaned_code)

                except Exception as e:
                    print(f"[Error] Failed to process {desc_file}: {e}")

                file_index += 1

            print(f"[Done] {module_name}/{test_name}")
        print(f"[Completed] All tests in {module_name}")

if __name__ == "__main__":
    base_directory = ".."
    num_modules_min = 1
    num_modules_max = 27
    num_tests = 5

    start_time = time.time()
    process_files(base_directory, num_modules_min, num_modules_max, num_tests)
    end_time = time.time()

    print(f"\n[Total Runtime] {end_time - start_time:.2f} seconds")
