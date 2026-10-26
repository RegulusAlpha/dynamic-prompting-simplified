# SD WebUI Dynamic Prompt Extension

This extension adds **dynamic prompting** to SD WebUI Forge, supporting advanced prompt features including nested choices, wildcard files, and mirrored wildcards.

## ✨ Features

- **Nested choices** with `{option1|option2|{nested1|nested2}}`
- **Wildcard expansion** with `__name__` → expands from `wildcards/name.txt`
- **Line-separated wildcard files** that may themselves contain braces and wildcards
- **Mirrored wildcards** with `__name-mir__`:
  - Positive prompt gets the **chosen option**
  - Negative prompt gets **all the other options, comma-separated**
  - Strict resolution: `__name-mir__` reads **only** `wildcards/name-mir.txt` (no fallback to `name.txt`)
- **Deterministic behavior** using the current generation seed
- Works for both **positive** and **negative** prompts
- Expanded prompts are saved into PNG metadata

## 📂 Installation

1. Navigate to your SD WebUI Forge installation directory.
2. Place this folder in `extensions/`:
   ```
   extensions/
     sd-webui-dynprompt/
       scripts/
         dynprompt.py
       dynprompt/
         __init__.py
         expander.py
       wildcards/
   ```
3. Restart SD WebUI Forge.

## 📑 Wildcard Files

- Located in the `wildcards/` directory (configurable).
- Each line is one possible expansion.
- Lines may contain further braces `{}` and wildcard calls.

**Example: `wildcards/hats.txt`**
```
{red hat|blue hat|{green hat|yellow hat|{black hat|gold hat}}}
beret
top hat
```

## 🔄 Mirrored Wildcards

- File name: `name-mir.txt` (called via `__name-mir__`).
- Ensures complementary picks between positive/negative prompts.

**Example: `wildcards/hats-mir.txt`**
```
{red hat|blue hat|green hat}
{tall hat|short hat|medium hat}
```

- Braces in a `-mir` file are flattened, so this file has six options.
- Positive prompt: `portrait, __hats-mir__`
- Negative prompt: `lowres, __hats-mir__`
  - If pos → `red hat`, neg → `blue hat, green hat, tall hat, short hat, medium hat`
- A `__name-mir__` in the negative that the positive never used becomes all of its options.

This ensures that the **negative prompt excludes the token chosen in the positive prompt.**

### 🧩 Nested `-mir` behavior (auto-discovery)

Mirrored tokens can be **nested inside other wildcards**. If a wildcard you use in the **positive** prompt expands to another token like `__foo-mir__`, the extension can **automatically inject the mirrored complement** into the **negative** prompt (so you don’t have to add `__foo-mir__` manually).

- This requires the checkbox in the UI:  
  **“Automatically mirror -mir wildcards without explicitly adding them to the negative prompt.”** (enabled by default)
- The auto-inject only happens if the negative prompt does **not** already contain that `__*-mir__` token.
- Resolution is strict: `__foo-mir__` reads `wildcards/foo-mir.txt` only.

**Example (nested):**
```
wildcards/outfits.txt
---------------------
__hats-mir__, {casual|formal}

wildcards/hats-mir.txt
----------------------
{red hat|blue hat|green hat}
```

Usage:
- Positive: `portrait, __outfits__`
- Negative: *(leave blank or put your usual negatives)*

Behavior:
- The positive prompt expands `__outfits__` → which contains `__hats-mir__`.
- With the checkbox enabled, the extension auto-injects `__hats-mir__` into the **negative** and expands it there as the comma‑separated “other” options.
- If the seed picks **`red hat`** for positive, the negative gets **`blue hat, green hat`** automatically.

## ⚙️ Usage

- Write prompts as usual with `{}` and `__wildcards__`.
- Wildcards are recursively expanded.
- Mirrored wildcards respect complement logic.

**Prompt Example:**
```
Positive: portrait, {cinematic|studio|outdoor}, __hats__, soft lighting
Negative: lowres, bad anatomy, __hats-mir__
```

### UI Options
- **Enable dynamic prompt expansion** — master toggle.
- **Wildcard directory** — where your `.txt` wildcard files live (subfolders work: `__clothes/tops__`).
- **Variety** — extra randomness lane. 0 = off; the same seed + variety reproduce the same prompt.
- **Automatically mirror -mir wildcards without explicitly adding them to the negative prompt** —
  When on, any `__*-mir__` discovered in the **positive** (even nested within another wildcard) is appended to the **negative** prompt and expanded as the “others.”

## ✅ Notes

- Missing wildcard files resolve to empty string.
- Braces expand until fully resolved (up to 1024 `{…}` blocks and 1024 `__tokens__` per pass).
- A single-line wildcard file is split into choices only when the whole line is one `{…}` block; `{a|b} dress, {c|d}` is one option.
- Deterministic per seed: only braces and wildcards advance the randomness, so fixed text doesn't change picks.
- Uses the same expander as the ComfyUI node: the same seed + variety give the same prompts in both.

## 📝 Changelog

### 1.5.1
- **Send to img2img / inpaint**: the 🖼️ and 🎨 buttons now send the expanded prompts of the selected image instead of the raw `__wildcards__`.
- **Hires fix**: when the hires prompt is left empty, the hires pass now uses the expanded prompts instead of the raw `__wildcards__`.
- **Grid infotext**: the grid image's PNG info now has the expanded prompts.
- **Styles**: selected styles are no longer dropped, and wildcards inside a style are expanded.
- **Batch infotext**: the `Prompt` / `Negative prompt` extra params are removed. They always held the first image's prompt, so pasting the infotext of a later image in a batch gave the wrong prompt. `Raw prompt` / `Raw negative prompt` are still stored.

### 1.5.0
- **Variety slider**: an extra randomness lane per seed (0 = off).
- **Subfolder and dotted wildcard names**: `__clothes/tops__` and `__tops.v1__` work. Paths outside the wildcard directory are blocked.
- **Empty brace branches**: `{a|b|}` can pick nothing, so segments can be optional.
- **New randomness**: only braces and wildcards advance the random picks, so editing fixed text doesn't change them. The same seed gives different prompts than 1.4.2.
- **Expansion order**: braces → wildcards → braces from wildcard lines.
- **`-mir` files**: braces are flattened into separate options, in single-line and multi-line files, with duplicates removed.
- **`__name-mir__` in the negative** becomes the options the positive did not pick, or all of its options if the positive never used it.
- **Auto-mirror**: the mirrored options are merged into the negative with case-insensitive de-duplication.
- **Single-line wildcard files** are split into choices only when the whole line is one `{…}` block.
- Repeated commas and extra spaces are removed from the expanded prompts.
- Expansion limits are raised to 1024 `{…}` blocks and 1024 `__tokens__` per pass.
- `.gitignore`: wildcard files are ignored, except the `hats.txt` and `hats-mir.txt` examples.

## Licence & Contributing

**Contributing**
- 1 fork this repository  
- 2 make changes  
- 3 submit pull request

**License:** GNU General Public License (GPLv3) (https://www.gnu.org/licenses/gpl-3.0.en.html)

Made for [Stable Diffusion WebUI Forge](https://github.com/lllyasviel/stable-diffusion-webui-forge) <br>
Check out the version for [ComfyUI](https://github.com/RegulusAlpha/ComfyUI-DynPromptSimplified)
