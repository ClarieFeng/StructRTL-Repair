import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import traceback
from pathlib import Path

# Avoid stale/incomplete Transformers dynamic-module caches when loading
# remote-code models such as InternVL under nohup.
if os.environ.get("MGEMMV_FORCE_FRESH_HF_MODULES_CACHE", "1") == "1":
    script_dir_for_cache = Path(__file__).resolve().parent
    fresh_cache = script_dir_for_cache.parent / "logs" / f"hf_modules_cache_runtime_{os.getpid()}"
    fresh_cache.mkdir(parents=True, exist_ok=True)
    os.environ["HF_MODULES_CACHE"] = str(fresh_cache)
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

from PIL import Image
import torch
from transformers import AddedToken, AutoModel, AutoProcessor, AutoTokenizer, PreTrainedTokenizerFast
try:
    from transformers.modeling_utils import PreTrainedModel

    if not hasattr(PreTrainedModel, "all_tied_weights_keys"):
        def _get_all_tied_weights_keys(self):
            value = self.__dict__.get("_all_tied_weights_keys_compat", None)
            if value is not None:
                return value
            tied_keys = getattr(self, "_tied_weights_keys", None) or []
            if isinstance(tied_keys, dict):
                return tied_keys
            return {key: None for key in tied_keys}

        def _set_all_tied_weights_keys(self, value):
            self.__dict__["_all_tied_weights_keys_compat"] = value

        PreTrainedModel.all_tied_weights_keys = property(
            _get_all_tied_weights_keys,
            _set_all_tied_weights_keys,
        )
except Exception:
    pass
from path_config import resolve_model_path

try:
    from transformers import AutoModelForVision2Seq as AutoVisionModel
except ImportError:
    from transformers import AutoModelForImageTextToText as AutoVisionModel


DEFAULT_QUANTIZATION = "bf16"
NUM_SAMPLES = 1
PASS_AT_K_MANIFEST = "../pass_at_k_samples.jsonl"

processor = None
tokenizer = None
model = None
model_backend = "standard_generate"
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

stats = {
    "total": 0,
    "syntax_pass": 0,
    "compile_pass": 0,
    "functional_pass": 0,
}


def print_separator(char="=", width=60):
    print(char * width)


def append_manifest_record(record):
    with open(PASS_AT_K_MANIFEST, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_filelist(filelist_path):
    entries = []
    if not os.path.exists(filelist_path):
        return entries

    with open(filelist_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            entries.append(line)
    return entries


def extract_module_names_from_text(text):
    return re.findall(r"^\s*module\s+([A-Za-z_][A-Za-z0-9_$]*)\b", text, flags=re.MULTILINE)


def extract_module_names_from_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return extract_module_names_from_text(f.read())
    except OSError:
        return []


def build_compile_sandbox(code_path, candidate_path, include_tb=False):
    temp_dir = tempfile.TemporaryDirectory(prefix="mgemmv_eval_")
    temp_root = Path(temp_dir.name)
    candidate_dst = temp_root / "candidate.v"
    shutil.copy2(candidate_path, candidate_dst)

    target_module_names = extract_module_names_from_file(candidate_path)
    target_module_name = target_module_names[0] if target_module_names else None

    compile_sources = [str(candidate_dst)]
    seen = {str(Path(candidate_path).resolve())}

    for entry in read_filelist(os.path.join(code_path, "filelist.txt")):
        src_path = os.path.join(code_path, entry)
        if not os.path.exists(src_path):
            continue
        abs_src = str(Path(src_path).resolve())
        if abs_src in seen:
            continue
        if src_path.endswith('.v'):
            module_names = extract_module_names_from_file(src_path)
            if target_module_name and target_module_name in module_names:
                continue
        dst_path = temp_root / os.path.basename(src_path)
        shutil.copy2(src_path, dst_path)
        compile_sources.append(str(dst_path))
        seen.add(abs_src)

    if include_tb:
        tb_path = os.path.join(code_path, "tb.v")
        if os.path.exists(tb_path):
            abs_tb = str(Path(tb_path).resolve())
            if abs_tb not in seen:
                dst_path = temp_root / "tb.v"
                shutil.copy2(tb_path, dst_path)
                compile_sources.append(str(dst_path))

    return temp_dir, compile_sources


def load_image(image_path):
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")
    return Image.open(image_path).convert("RGB")


def split_prompt_at_image_tag(prompt):
    parts = re.split(r"<\s*image\s*>|<\s*img\s*>", prompt, flags=re.IGNORECASE)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return prompt.strip(), None


def clean_generated_code(text):
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


def build_generate_kwargs(sample_idx, num_samples):
    if num_samples <= 1:
        return {
            "max_new_tokens": 8192,
            "do_sample": True,
            "temperature": 0.8,
            "top_p": 0.9,
        }

    seed = 2025 + sample_idx
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    return {
        "max_new_tokens": 8192,
        "do_sample": True,
        "temperature": 0.8,
        "top_p": 0.9,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Run author-compatible MGEMMV baseline with current evaluation flow.")
    parser.add_argument("--model-path", default=None, help="Path to the local model directory. Required unless MGEMMV_MODEL_PATH is set.")
    parser.add_argument("--base-directory", default="..", help="Base directory containing module*/test* folders.")
    parser.add_argument("--module-min", type=int, default=1, help="First module index to evaluate.")
    parser.add_argument("--module-max", type=int, default=27, help="Last module index to evaluate.")
    parser.add_argument("--num-tests", type=int, default=5, help="Number of tests per module.")
    parser.add_argument("--num-samples", type=int, default=NUM_SAMPLES, help="Number of candidates to generate per problem.")
    parser.add_argument("--manifest-path", default=PASS_AT_K_MANIFEST, help="Path to JSONL manifest used by Pass@k.py.")
    parser.add_argument(
        "--quantization",
        choices=("bf16",),
        default=DEFAULT_QUANTIZATION,
        help="Model loading mode.",
    )
    return parser.parse_args()


def _load_processor(local_model_path):
    try:
        return AutoProcessor.from_pretrained(local_model_path, trust_remote_code=True)
    except Exception:
        return AutoTokenizer.from_pretrained(local_model_path, trust_remote_code=True, use_fast=False)


def _raise_missing_tokenizer_assets(model_dir, last_error):
    found_configs = sorted(model_dir.glob("**/tokenizer_config.json"))
    found_payloads = []
    for pattern in (
        "**/tokenizer.json",
        "**/tokenizer.model",
        "**/sentencepiece.bpe.model",
        "**/vocab.json",
        "**/merges.txt",
    ):
        found_payloads.extend(sorted(model_dir.glob(pattern)))

    if found_configs and not found_payloads:
        config_locations = ", ".join(str(path) for path in found_configs)
        raise RuntimeError(
            "Tokenizer config files are present, but no usable tokenizer payload was found. "
            "The local InternVL directory needs tokenizer.json, tokenizer.model, "
            "sentencepiece.bpe.model, or vocab/merges files. "
            f"Found tokenizer configs: {config_locations}. "
            "Re-download the tokenizer artifacts, for example:\n"
            "  hf download OpenGVLab/InternVL3_5-8B-Instruct "
            "--include vocab.json --include merges.txt "
            "--include tokenizer_config.json --include special_tokens_map.json "
            "--include added_tokens.json "
            f"--local-dir {model_dir}\n"
            f"Original tokenizer error: {last_error}"
        ) from last_error

    raise last_error


def _normalize_special_token_value(value):
    if isinstance(value, dict):
        value = dict(value)
        content = value.pop("content", None)
        if content is None:
            content = value.pop("__content__", None)
        if content is None:
            return value
        return AddedToken(content, **value)
    if isinstance(value, list):
        return [_normalize_special_token_value(item) for item in value]
    return value


def _load_special_tokens_map(tokenizer_dir):
    special_tokens_path = tokenizer_dir / "special_tokens_map.json"
    if not special_tokens_path.exists():
        return {}
    with special_tokens_path.open("r", encoding="utf-8") as handle:
        special_tokens = json.load(handle)
    return {
        key: _normalize_special_token_value(value)
        for key, value in special_tokens.items()
    }


def _load_tokenizer(local_model_path):
    model_dir = Path(local_model_path)
    last_error = None
    for use_fast in (False, True):
        try:
            return AutoTokenizer.from_pretrained(
                local_model_path,
                trust_remote_code=True,
                use_fast=use_fast,
            )
        except Exception as error:
            last_error = error

    tokenizer_json_candidates = [model_dir / "tokenizer.json"]
    tokenizer_json_candidates.extend(sorted(model_dir.glob("*/tokenizer.json")))
    tokenizer_json_candidates.extend(sorted(model_dir.glob("*/*/tokenizer.json")))
    for tokenizer_json in tokenizer_json_candidates:
        if not tokenizer_json.exists():
            continue
        try:
            print(f"[INFO] AutoTokenizer failed, loading PreTrainedTokenizerFast from {tokenizer_json}")
            return PreTrainedTokenizerFast(
                tokenizer_file=str(tokenizer_json),
                bos_token="<s>",
                eos_token="</s>",
                unk_token="<unk>",
                pad_token="<unk>",
            )
        except Exception as error:
            last_error = error

    vocab_candidates = [model_dir / "vocab.json"]
    vocab_candidates.extend(sorted(model_dir.glob("*/vocab.json")))
    vocab_candidates.extend(sorted(model_dir.glob("*/*/vocab.json")))
    for vocab_file in vocab_candidates:
        merges_file = vocab_file.parent / "merges.txt"
        if not vocab_file.exists() or not merges_file.exists():
            continue
        try:
            tokenizer_class = getattr(__import__("transformers", fromlist=["Qwen2Tokenizer"]), "Qwen2Tokenizer")
            special_tokens = _load_special_tokens_map(vocab_file.parent)
            print(f"[INFO] AutoTokenizer failed, loading Qwen2Tokenizer from {vocab_file.parent}")
            return tokenizer_class(
                vocab=str(vocab_file),
                merges=str(merges_file),
                trust_remote_code=True,
                **special_tokens,
            )
        except Exception as error:
            last_error = error

    tokenizer_model_candidates = [model_dir / "tokenizer.model"]
    tokenizer_model_candidates.extend(sorted(model_dir.glob("*/tokenizer.model")))
    tokenizer_model_candidates.extend(sorted(model_dir.glob("*/*/tokenizer.model")))
    for tokenizer_model in tokenizer_model_candidates:
        if not tokenizer_model.exists():
            continue
        for class_name in ("LlamaTokenizer", "LlamaTokenizerFast"):
            try:
                tokenizer_class = getattr(__import__("transformers", fromlist=[class_name]), class_name)
                print(f"[INFO] AutoTokenizer failed, loading {class_name} from {tokenizer_model}")
                return tokenizer_class.from_pretrained(
                    str(tokenizer_model.parent),
                    trust_remote_code=True,
                    use_fast=class_name.endswith("Fast"),
                )
            except Exception as error:
                last_error = error

    local_tokenizers = (
        ("tokenization_internlm2.py", "InternLM2Tokenizer"),
        ("tokenization_internlm.py", "InternLMTokenizer"),
    )
    tokenizer_dirs = [model_dir]
    tokenizer_dirs.extend(path.parent for path in sorted(model_dir.glob("*/tokenizer_config.json")))
    tokenizer_dirs.extend(path.parent for path in sorted(model_dir.glob("*/*/tokenizer_config.json")))
    seen_dirs = set()
    for tokenizer_dir in tokenizer_dirs:
        tokenizer_dir = tokenizer_dir.resolve()
        if tokenizer_dir in seen_dirs:
            continue
        seen_dirs.add(tokenizer_dir)
        for filename, class_name in local_tokenizers:
            module_file = tokenizer_dir / filename
            if not module_file.exists():
                continue
            try:
                import importlib.util

                module_name = f"_mgemmv_internvl_tokenizer_{abs(hash(str(module_file))) & 0xFFFFFFFF:x}"
                spec = importlib.util.spec_from_file_location(module_name, module_file)
                if spec is None or spec.loader is None:
                    continue
                tokenizer_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(tokenizer_module)
                tokenizer_class = getattr(tokenizer_module, class_name)
                print(f"[INFO] AutoTokenizer failed, loading local {class_name} from {tokenizer_dir}")
                return tokenizer_class.from_pretrained(str(tokenizer_dir))
            except Exception as error:
                last_error = error

    _raise_missing_tokenizer_assets(model_dir, last_error)


def _load_internvl_from_local_files(local_model_path, dtype):
    """Bypass incomplete Transformers dynamic-module caches for local InternVL repos."""
    import importlib.util
    import sys
    import types

    model_dir = Path(local_model_path).resolve()
    module_file = model_dir / "modeling_internvl_chat.py"
    if not module_file.exists():
        raise FileNotFoundError(f"InternVL local loader cannot find {module_file}")

    package_name = f"_mgemmv_internvl_local_{abs(hash(str(model_dir))) & 0xFFFFFFFF:x}"
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__file__ = str(model_dir / "__init__.py")
        package.__path__ = [str(model_dir)]
        sys.modules[package_name] = package

    module_name = f"{package_name}.modeling_internvl_chat"
    if module_name in sys.modules:
        internvl_module = sys.modules[module_name]
    else:
        spec = importlib.util.spec_from_file_location(module_name, module_file)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not create import spec for {module_file}")
        internvl_module = importlib.util.module_from_spec(spec)
        internvl_module.__package__ = package_name
        sys.modules[module_name] = internvl_module
        spec.loader.exec_module(internvl_module)

    model_class = getattr(internvl_module, "InternVLChatModel")
    if not hasattr(model_class, "all_tied_weights_keys"):
        def _all_tied_weights_keys(self):
            tied_keys = getattr(self, "_tied_weights_keys", None) or []
            if isinstance(tied_keys, dict):
                return tied_keys
            return {key: None for key in tied_keys}

        model_class.all_tied_weights_keys = property(_all_tied_weights_keys)

    print("[INFO] Local InternVL from_pretrained start", flush=True)
    loaded_model = model_class.from_pretrained(
        str(model_dir),
        torch_dtype=dtype,
        low_cpu_mem_usage=False,
        trust_remote_code=True,
    )
    print("[INFO] Local InternVL from_pretrained done", flush=True)
    return loaded_model


def _load_model(local_model_path):
    global model_backend
    dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
    try:
        loaded_model = AutoModel.from_pretrained(
            local_model_path,
            torch_dtype=dtype,
            low_cpu_mem_usage=True,
            trust_remote_code=True,
        )
        if hasattr(loaded_model, "chat"):
            model_backend = "internvl_chat"
        else:
            model_backend = "standard_generate"
    except Exception as auto_error:
        print(f"[INFO] AutoModel remote-code loader failed: {auto_error}")
        try:
            loaded_model = AutoVisionModel.from_pretrained(local_model_path, trust_remote_code=True)
            model_backend = "standard_generate"
        except Exception as vision_error:
            print(f"[INFO] AutoVisionModel loader failed, using local InternVL loader: {vision_error}")
            loaded_model = _load_internvl_from_local_files(local_model_path, dtype)
            model_backend = "internvl_chat"
    print(f"[INFO] Moving model to {device}", flush=True)
    loaded_model = loaded_model.to(device)
    print(f"[INFO] Model moved to {device}", flush=True)
    return loaded_model


def load_processor_and_model(local_model_path, quantization_mode):
    global processor
    global tokenizer
    global model

    local_model_path = str(resolve_model_path(local_model_path))
    print(f"[INFO] Loading model from {local_model_path} with author-compatible device placement")
    model = _load_model(local_model_path)
    if model_backend == "internvl_chat":
        tokenizer = _load_tokenizer(local_model_path)
        processor = None
    else:
        processor = _load_processor(local_model_path)
        tokenizer = processor
    model.eval()
    print(f"[INFO] Model backend: {model_backend}")


def image_to_internvl_tensor(image):
    image = image.resize((448, 448), Image.BICUBIC)
    tensor = torch.tensor(list(image.getdata()), dtype=torch.float32).view(448, 448, 3)
    tensor = tensor.permute(2, 0, 1) / 255.0
    mean = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
    std = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)
    tensor = (tensor - mean) / std
    dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
    return tensor.unsqueeze(0).to(device=device, dtype=dtype)


def build_internvl_question(prompt):
    before_text, after_text = split_prompt_at_image_tag(prompt)
    parts = ["<image>"]
    if before_text:
        parts.append(before_text)
    if after_text:
        parts.append(after_text)
    return "\n".join(parts)


def call_internvl_chat(pixel_values, question, generate_kwargs):
    generation_config = dict(generate_kwargs)
    generation_config.setdefault("max_new_tokens", 8192)
    generation_config.setdefault("do_sample", True)
    generation_config.setdefault("temperature", 0.8)
    generation_config.setdefault("top_p", 0.9)

    chat_attempts = (
        lambda: model.chat(tokenizer, pixel_values, question, generation_config),
        lambda: model.chat(tokenizer, pixel_values, question, generation_config, history=None, return_history=False),
        lambda: model.chat(tokenizer, pixel_values, question, generation_config=generation_config),
        lambda: model.chat(tokenizer, pixel_values, question, generation_config=generation_config, history=None, return_history=False),
    )

    last_error = None
    for attempt in chat_attempts:
        try:
            output = attempt()
            if isinstance(output, tuple):
                output = output[0]
            return str(output)
        except TypeError as error:
            last_error = error
    if last_error is not None:
        raise last_error
    raise RuntimeError("InternVL chat failed without an exception")


def generate_code(prompt, image_path, *, sample_idx=0, num_samples=1):
    image = load_image(image_path)
    generate_kwargs = build_generate_kwargs(sample_idx, num_samples)

    if model_backend == "internvl_chat":
        pixel_values = image_to_internvl_tensor(image)
        question = build_internvl_question(prompt)
        raw_output = call_internvl_chat(pixel_values, question, generate_kwargs)
        cleaned = clean_generated_code(raw_output)
        return raw_output, cleaned

    before_text, after_text = split_prompt_at_image_tag(prompt)

    messages = [{"role": "user", "content": []}]
    if before_text:
        messages[0]["content"].append({"type": "text", "text": before_text})
    messages[0]["content"].append({"type": "image"})
    if after_text:
        messages[0]["content"].append({"type": "text", "text": after_text})

    input_text = processor.apply_chat_template(messages, add_generation_prompt=True)
    inputs = processor(image, input_text, add_special_tokens=False, return_tensors="pt").to(device)

    generate_ids = model.generate(**inputs, **generate_kwargs)

    prompt_len = inputs["input_ids"].shape[1]
    new_token_ids = generate_ids[:, prompt_len:]
    raw_output = processor.decode(
        new_token_ids[0],
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )
    cleaned = clean_generated_code(raw_output)
    return raw_output, cleaned


def check_syntax_iverilog(candidate_path, code_path):
    temp_dir, compile_sources = build_compile_sandbox(code_path, candidate_path, include_tb=False)
    out_path = os.path.join(temp_dir.name, "syntax.vvp")
    try:
        result = subprocess.run(
            ["iverilog", "-o", out_path, *compile_sources],
            capture_output=True,
            text=True,
            timeout=30,
        )
        passed = result.returncode == 0
        error_msg = result.stderr.strip() if not passed else ""
    except FileNotFoundError:
        passed = False
        error_msg = "iverilog not found — syntax check skipped"
    except subprocess.TimeoutExpired:
        passed = False
        error_msg = "iverilog timeout"
    finally:
        temp_dir.cleanup()
    return passed, error_msg


def run_functional_test(code_path, result_path, candidate_path=None, sample_tag=None):
    os.makedirs(result_path, exist_ok=True)
    file_suffix = f"_{sample_tag}" if sample_tag else ""
    output_vvp = os.path.join(result_path, f"out{file_suffix}.vvp")
    output_txt = os.path.join(result_path, f"out{file_suffix}.txt")

    temp_dir, compile_sources = build_compile_sandbox(code_path, candidate_path, include_tb=True)
    try:
        compile_cmd = ["iverilog", "-o", output_vvp, *compile_sources]
        compile_result = subprocess.run(compile_cmd, capture_output=True, text=True)
        if compile_result.returncode != 0:
            with open(output_txt, "w", encoding="utf-8") as f:
                f.write(f"Compile error:\n{compile_result.stderr.strip()}")
            return False, False, f"Compile error:\n{compile_result.stderr.strip()}"

        run_result = subprocess.run(["vvp", output_vvp], capture_output=True, text=True, timeout=60)
        sim_output = run_result.stdout

        with open(output_txt, "w", encoding="utf-8") as f:
            f.write(sim_output)
            if run_result.returncode != 0:
                f.write(f"\nSimulation stderr:\n{run_result.stderr}")
    finally:
        temp_dir.cleanup()

    match = re.search(r"(Pass(?:ed)? rate|Accuracy):\s*([0-9.]+)%", sim_output, re.IGNORECASE)
    if match:
        value = float(match.group(2))
        functional_ok = value == 100.0
        detail = f"{match.group(1)}: {value}%"
    else:
        functional_ok = False
        detail = "No pass-rate metric found in simulation output"

    return True, functional_ok, detail


def _pct(num, denom):
    return f"{100 * num / denom:.1f}" if denom > 0 else "0.0"


def pass_at_k(n, c, k):
    if c == 0:
        return 0.0
    if n < k:
        return None
    if n - c < k:
        return 1.0

    product = 1.0
    for value in range(n - c + 1, n + 1):
        product *= 1.0 - k / value
    return 1.0 - product


def compute_pass1_summary(manifest_path):
    grouped = {}
    if not os.path.exists(manifest_path):
        return None

    with open(manifest_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            grouped.setdefault(record["problem_id"], []).append(record)

    if not grouped:
        return None

    summary = {
        "total_problems": len(grouped),
        "avg_samples_per_problem": sum(len(records) for records in grouped.values()) / len(grouped),
        "syntax_no_pass": 0,
    }
    for label, field in (
        ("syntax", "syntax_ok"),
        ("compilation", "compile_ok"),
        ("functional", "functional_ok"),
    ):
        scores = []
        for records in grouped.values():
            c = sum(1 for record in records if record.get(field, False))
            if field == "syntax_ok" and c == 0:
                summary["syntax_no_pass"] += 1
            score = pass_at_k(len(records), c, 1)
            if score is not None:
                scores.append(score)
        summary[f"{label}_pass_at_1"] = sum(scores) / len(scores) if scores else 0.0
    return summary


def process_files(base_path, num_modules_min, num_modules_max, num_tests, num_samples, manifest_path):
    global PASS_AT_K_MANIFEST
    PASS_AT_K_MANIFEST = manifest_path
    stats["total"] = 0
    stats["syntax_pass"] = 0
    stats["compile_pass"] = 0
    stats["functional_pass"] = 0

    overall_start = time.time()
    if os.path.exists(PASS_AT_K_MANIFEST):
        os.remove(PASS_AT_K_MANIFEST)

    for i in range(num_modules_min, num_modules_max + 1):
        module_name = f"module{i}"
        module_start = time.time()

        module_total = 0
        module_compile_pass = 0
        module_syntax_pass = 0
        module_functional_pass = 0

        print_separator("=")
        print(f"  MODULE {i}/{num_modules_max}  —  {module_name}")
        print_separator("=")

        for j in range(1, num_tests + 1):
            test_name = f"test{j}"
            description_path = os.path.join(base_path, module_name, test_name, "description")
            code_path = os.path.join(base_path, module_name, test_name, "code")
            result_path = os.path.join(base_path, module_name, test_name, "result")
            os.makedirs(code_path, exist_ok=True)

            print_separator("-", 50)
            print(f"  [{module_name}] {test_name}")
            print_separator("-", 50)

            file_index = 0
            while True:
                desc_file = os.path.join(description_path, f"description{file_index}.txt")
                image_name_file = os.path.join(description_path, f"image_name{file_index}.txt")

                if not os.path.exists(desc_file) or not os.path.exists(image_name_file):
                    break

                with open(desc_file, "r", encoding="utf-8") as f:
                    prompt = f.read().strip()
                with open(image_name_file, "r", encoding="utf-8") as f:
                    image_filename = f.read().strip()

                image_path = os.path.join(description_path, image_filename)
                if not os.path.exists(image_path):
                    print(f"  [SKIP] Image not found: {image_filename}")
                    file_index += 1
                    continue

                item_label = f"{module_name}/{test_name}/description{file_index}"
                print(f"\n  ▶ Generating: {item_label} + {image_filename}")
                item_start = time.time()

                item_any_syntax = False
                item_any_compile = False
                item_any_functional = False
                module_total += 1
                stats["total"] += 1

                try:
                    for sample_idx in range(num_samples):
                        sample_tag = f"description{file_index}_sample{sample_idx}"
                        print(f"    Sample {sample_idx + 1}/{num_samples}")

                        raw_output, generated_code = generate_code(
                            prompt,
                            image_path,
                            sample_idx=sample_idx,
                            num_samples=num_samples,
                        )
                        preview = " ".join(raw_output.strip().split())[:180]
                        print(f"    Raw output chars     : {len(raw_output)}")
                        print(f"    Clean code chars     : {len(generated_code)}")
                        if preview:
                            print(f"    Raw preview          : {preview}")

                        txt_name = f"llm_code{file_index}.txt" if num_samples == 1 else f"llm_code{file_index}_sample{sample_idx}.txt"
                        v_name = f"llm_code{file_index}.v" if num_samples == 1 else f"llm_code{file_index}_sample{sample_idx}.v"
                        raw_name = f"llm_raw{file_index}.txt" if num_samples == 1 else f"llm_raw{file_index}_sample{sample_idx}.txt"
                        txt_out = os.path.join(code_path, txt_name)
                        v_out = os.path.join(code_path, v_name)
                        raw_out = os.path.join(code_path, raw_name)

                        with open(txt_out, "w", encoding="utf-8") as f:
                            f.write(generated_code)
                        with open(v_out, "w", encoding="utf-8") as f:
                            f.write(generated_code)
                        with open(raw_out, "w", encoding="utf-8") as f:
                            f.write(raw_output)

                        gen_elapsed = time.time() - item_start
                        print(f"  ✔ Generated  ({gen_elapsed:.1f}s)  → {v_out}")

                        syntax_ok, syntax_err = check_syntax_iverilog(v_out, code_path)
                        compile_ok = False
                        func_ok = False
                        detail = "Syntax check failed"

                        if syntax_ok:
                            compile_ok, func_ok, detail = run_functional_test(
                                code_path,
                                result_path,
                                candidate_path=v_out,
                                sample_tag=sample_tag,
                            )
                        else:
                            print("  ✘ Syntax check  FAIL")
                            for line in syntax_err.splitlines()[:8]:
                                print(f"      {line}")

                        item_any_syntax = item_any_syntax or syntax_ok
                        item_any_compile = item_any_compile or compile_ok
                        item_any_functional = item_any_functional or func_ok

                        append_manifest_record(
                            {
                                "problem_id": f"{module_name}/{test_name}/description{file_index}",
                                "sample_id": sample_idx,
                                "syntax_ok": syntax_ok,
                                "compile_ok": compile_ok,
                                "functional_ok": func_ok,
                                "detail": detail,
                                "code_file": v_out,
                                "raw_file": raw_out,
                            }
                        )

                        syntax_icon = "✔" if syntax_ok else "✘"
                        compile_icon = "✔" if compile_ok else "✘"
                        func_icon = "✔" if func_ok else "✘"
                        print(f"  {syntax_icon} Syntax       {'PASS' if syntax_ok else 'FAIL'}")
                        print(f"  {compile_icon} Compilation  {'PASS' if compile_ok else 'FAIL'}")
                        print(f"  {func_icon} Functional   {'PASS' if func_ok else 'FAIL'}  ({detail})")

                except Exception as e:
                    print(f"  ✘ [ERROR] Failed to generate: {e}")
                    traceback.print_exc()

                module_syntax_pass += int(item_any_syntax)
                module_compile_pass += int(item_any_compile)
                module_functional_pass += int(item_any_functional)
                stats["syntax_pass"] += int(item_any_syntax)
                stats["compile_pass"] += int(item_any_compile)
                stats["functional_pass"] += int(item_any_functional)

                file_index += 1

        module_elapsed = time.time() - module_start
        print_separator("-", 50)
        print(f"  MODULE SUMMARY  —  {module_name}  ({module_elapsed:.1f}s)")
        print(f"    Items generated      : {module_total}")
        print(f"    Syntax check  PASS   : {module_syntax_pass} / {module_total}  ({_pct(module_syntax_pass, module_total)}%)")
        print(f"    Syntax check  FAIL   : {module_total - module_syntax_pass} / {module_total}  ({_pct(module_total - module_syntax_pass, module_total)}%)")
        print(f"    Compilation   PASS   : {module_compile_pass} / {module_total}  ({_pct(module_compile_pass, module_total)}%)")
        print(f"    Functional    PASS   : {module_functional_pass} / {module_total}  ({_pct(module_functional_pass, module_total)}%)")
        print_separator("=")
        print()

    total_elapsed = time.time() - overall_start
    print_separator("=")
    print("  FINAL SUMMARY")
    print_separator("=")
    print("  Item-level any-sample counts")
    print(f"  Total items              : {stats['total']}")
    print(f"  Total syntax      PASS   : {stats['syntax_pass']}")
    print(f"  Total syntax      FAIL   : {stats['total'] - stats['syntax_pass']}")
    print(f"  Total compilation PASS   : {stats['compile_pass']}")
    print(f"  Total functional  PASS   : {stats['functional_pass']}")
    pass1_summary = compute_pass1_summary(PASS_AT_K_MANIFEST)
    if pass1_summary:
        print()
        print("  Unbiased Pass@1 from manifest")
        print(f"  Problems                 : {pass1_summary['total_problems']}")
        print(f"  Average samples/problem  : {pass1_summary['avg_samples_per_problem']:.2f}")
        print(f"  No syntax pass problems  : {pass1_summary['syntax_no_pass']}")
        print(f"  Syntax      Pass@1       : {pass1_summary['syntax_pass_at_1']:.4f}")
        print(f"  Compilation Pass@1       : {pass1_summary['compilation_pass_at_1']:.4f}")
        print(f"  Functional  Pass@1       : {pass1_summary['functional_pass_at_1']:.4f}")
    print(f"  Total elapsed time       : {total_elapsed:.1f}s")
    print_separator("=")


if __name__ == "__main__":
    args = parse_args()
    load_processor_and_model(args.model_path, args.quantization)
    process_files(
        args.base_directory,
        args.module_min,
        args.module_max,
        args.num_tests,
        args.num_samples,
        args.manifest_path,
    )
