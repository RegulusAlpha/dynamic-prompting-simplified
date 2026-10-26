import os
from typing import Dict, List
import gradio as gr
from modules import scripts
from modules.processing import fix_seed
from dynprompt.expander import PromptExpander, WILDCARD_TOKEN_RE
from modules import script_callbacks

EXT_NAME = "Dynamic Prompt (Forge)"
EXT_VER = "1.5.0"

# Default wildcards dir: <this_extension_root>/wildcards
DEFAULT_WILDCARD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "wildcards")

def _csv_chunks(s: str) -> List[str]:
    """Split a comma list into items, trimming whitespace and skipping empties."""
    return [p.strip() for p in (s or "").split(",") if p.strip()]

def _merge_csv(*parts: str) -> str:
    """
    Merge multiple comma lists, preserving order of first appearance
    and de-duplicating case-insensitively.
    """
    seen = set()
    out = []
    for part in parts:
        for chunk in _csv_chunks(part):
            key = chunk.lower()
            if key not in seen:
                seen.add(key)
                out.append(chunk)
    return ", ".join(out)

def _collect_mirrors_deep(text: str, base_expander: PromptExpander) -> Dict[str, List[str]]:
    """
    Deep mirroring pass with counter-based RNG:
      - Use a fresh expander (same seed/wildcard_dir/variety) so counters start at 0.
      - Collapse braces first (consumes choice counter).
      - Expand wildcards left-to-right; for any token ending with '-mir', record
        "all except chosen" (ignore empties) under that token.
      - Replace tokens with their chosen values to permit nested discovery.
    """
    mirror = PromptExpander(
        seed=base_expander.seed,
        wildcard_dir=base_expander.wildcard_dir,
        variety=base_expander.variety,
    )

    # choices first (consumes mirror's choice counter)
    s = mirror.collapse_choices(text or "")
    bag: Dict[str, List[str]] = {}

    # wildcard pass (consumes mirror's wild counter in the same sequence as Positive)
    # same cap as the positive wildcard pass so self-referencing wildcards can't hang
    for _ in range(1024):
        m = WILDCARD_TOKEN_RE.search(s)
        if not m:
            break

        token = m.group(1)
        start, end = m.span()

        opts = mirror.read_options_for_token(token)
        if not opts:
            # drop unknown to mirror main expander behavior
            s = s[:start] + s[end:]
            continue

        idx = mirror._pick_wild_index(token, len(opts))
        chosen = opts[idx] if 0 <= idx < len(opts) else ""

        if token.endswith("-mir"):
            others = [o for i, o in enumerate(opts) if i != idx and o.strip()]
            bag.setdefault(token, []).extend(others)

        # Replace the token with its chosen text and continue scanning (to handle nesting)
        s = s[:start] + chosen + s[end:]

    return bag

def get_seed(p):
    try:
        seed = p.seed
        if seed is None or seed == -1:
            if getattr(p, "all_seeds", None):
                seed = p.all_seeds[0]
        if seed is None or seed == -1:
            seed = 0
        return int(seed)
    except Exception:
        return 0

class DynPromptScript(scripts.Script):
    def title(self):
        return EXT_NAME

    def show(self, is_img2img):
        # Show on both txt2img and img2img
        return scripts.AlwaysVisible

    def ui(self, is_img2img):
        with gr.Accordion(f"{EXT_NAME} v{EXT_VER}", open=False):
            enable = gr.Checkbox(
                value=True,
                label="Enable dynamic prompt expansion",
            )
            wildcard_dir = gr.Textbox(
                value=DEFAULT_WILDCARD_DIR,
                label="Wildcard directory",
                info="Folder with *.txt wildcard lists (e.g., hats.txt → __hats__, hats-mir.txt → __hats-mir__).",
            )
            variety = gr.Slider(
                minimum=0, maximum=100, step=1, value=0,
                label="Variety",
                info="Extra randomness lane. 0 = off; same seed + variety reproduce.",
            )
            auto_mirror = gr.Checkbox(
                value=True,
                label="Automatically mirror -mir wildcards without explicitly adding them to the negative prompt",
                info="Any __name-mir__ in the positive (even nested) adds the options it did not pick to the negative."
            )
            gr.Markdown(
                "Supports nested `{a|b|{c|d}}`, wildcards `__name__`, and mirrored wildcards `__name-mir__`.\n"
                "**Mirrored behavior:** positive gets the chosen option; negative gets all remaining options (comma-separated)."
            )
        # The order here must match process() arguments after `p`
        return [enable, wildcard_dir, auto_mirror, variety]

    def process(self, p, enable, wildcard_dir, auto_mirror, variety=0):
        # Banner so you can confirm this script loaded in the WebUI console
        print(f"[{EXT_NAME}] v{EXT_VER} loaded; enable={enable}, auto_mirror={auto_mirror}")

        if not enable:
            return

        if not wildcard_dir or not os.path.isdir(wildcard_dir):
            wildcard_dir = DEFAULT_WILDCARD_DIR

        # Ensure seeds are prepared; SD uses these to size prompt arrays
        fix_seed(p)
        base_seed = get_seed(p)

        try:
            total = max(1, p.batch_size * p.n_iter)
        except Exception:
            total = 1

        all_prompts = []
        all_negative = []

        # Raw user inputs (used both for expansion and token detection)
        pos_text_raw = p.prompt or ""
        neg_text_raw = p.negative_prompt or ""

        for i in range(total):
            expander = PromptExpander(seed=base_seed + i, wildcard_dir=wildcard_dir, variety=variety)

            # A) Positive prompt: full expansion (choices -> wildcards -> choices)
            pos_expanded = expander.expand_prompt(pos_text_raw, phase="pos")

            # B) Deep mirror: collect exclusions for ANY __*-mir__ appearing during Positive expansion
            mirrored = _collect_mirrors_deep(pos_text_raw, expander) if pos_text_raw.strip() else {}

            # C) User Negative: an explicit __*-mir__ becomes the options the Positive did not pick
            #    (all options if the Positive never used it); everything else expands normally (pick-one)
            def _mirror_token(m):
                token = m.group(1)
                if not token.endswith("-mir"):
                    return m.group(0)
                if token in mirrored:
                    return ", ".join(mirrored[token])
                return ", ".join(o for o in expander.read_options_for_token(token) if o.strip())

            neg_user = expander.expand_prompt(WILDCARD_TOKEN_RE.sub(_mirror_token, neg_text_raw), phase="pos")

            mirrored_additions = ""
            if auto_mirror:
                mirrored_additions = ", ".join(o for others in mirrored.values() for o in others)

            # D) Merge user negative + mirrored exclusions (dedup; preserve order)
            all_prompts.append(pos_expanded)
            all_negative.append(_merge_csv(neg_user, mirrored_additions))

        # Provide expanded prompts to the pipeline and embed them in PNG metadata
        p.all_prompts = all_prompts
        p.all_negative_prompts = all_negative
        p.prompt = all_prompts[0]
        p.negative_prompt = all_negative[0]

        # Store expanded prompts in extra_generation_params for infotext
        p.extra_generation_params["Prompt"] = all_prompts[0]
        p.extra_generation_params["Negative prompt"] = all_negative[0]
        p.extra_generation_params["Raw prompt"] = pos_text_raw
        p.extra_generation_params["Raw negative prompt"] = neg_text_raw

    def before_image_saved(self, p, **kwargs):
        """
        Hook to ensure expanded prompts are embedded in the image's infotext before saving.
        """
        # Reinforce expanded prompts in infotext
        if hasattr(p, "all_prompts") and p.all_prompts:
            p.extra_generation_params["Prompt"] = p.all_prompts[0]
        if hasattr(p, "all_negative_prompts") and p.all_negative_prompts:
            p.extra_generation_params["Negative prompt"] = p.all_negative_prompts[0]
        print(f"[{EXT_NAME}] Before image saved: Embedded expanded prompts in infotext")

# Register the callback to hook into image saving
script_callbacks.on_before_image_saved(DynPromptScript().before_image_saved)