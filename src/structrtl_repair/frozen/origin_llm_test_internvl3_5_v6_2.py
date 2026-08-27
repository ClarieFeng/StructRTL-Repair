import re
from types import SimpleNamespace

from path_config import SCRIPT_DIR, resolve_model_path

import full_llm_test_author_eval_compatible_internvl3_5 as _internvl


_internvl.load_processor_and_model(str(resolve_model_path()), "bf16")

device = _internvl.device
model = _internvl.model
tokenizer = _internvl.tokenizer
processor = SimpleNamespace(tokenizer=tokenizer)
model_backend = _internvl.model_backend

clean_generated_code = _internvl.clean_generated_code
load_image = _internvl.load_image


def _strip_image_tags(prompt: str) -> str:
    return re.sub(r"<\s*/?\s*(image|img)\s*>", "", prompt, flags=re.IGNORECASE).strip()


def internvl_chat_generate(
    prompt: str,
    images,
    *,
    max_new_tokens: int = 1536,
    temperature: float = 0.2,
    top_p: float = 0.9,
) -> str:
    if isinstance(images, (list, tuple)):
        image = images[0] if images else None
    else:
        image = images

    generation_config = {
        "max_new_tokens": max_new_tokens,
        "do_sample": True,
        "temperature": temperature,
        "top_p": top_p,
    }

    if image is None:
        question = _strip_image_tags(prompt)
        pixel_values = None
    else:
        question = "<image>\n" + _strip_image_tags(prompt)
        pixel_values = _internvl.image_to_internvl_tensor(image)

    return _internvl.call_internvl_chat(pixel_values, question, generation_config)
