// Forge's "Send to img2img/inpaint" buttons copy the txt2img prompt textboxes as typed, so wildcards
// like __hats__ arrive unresolved. After that copy lands, swap in the expanded prompts of the selected image.
(function() {
    const SEND_BUTTONS = "#txt2img_send_to_img2img, #txt2img_send_to_inpaint";

    function textarea(id) {
        return gradioApp().querySelector(`#${id} textarea`);
    }

    function expandedForSelection() {
        const infoEl = textarea("generation_info_txt2img");
        if (!infoEl || !infoEl.value) return null;

        let info;
        try {
            info = JSON.parse(infoEl.value);
        } catch (e) {
            return null;
        }
        // Only act on generations this extension expanded
        if (!info.extra_generation_params || !("Raw prompt" in info.extra_generation_params)) return null;

        const prompts = info.all_prompts || [];
        const negatives = info.all_negative_prompts || [];
        let i = selected_gallery_index() - (info.index_of_first_image || 0);
        if (i < 0 || i >= prompts.length) i = 0; // grid or nothing selected

        return {prompt: prompts[i], negative: negatives[i]};
    }

    function setValue(el, value) {
        if (!el || value == null || el.value === value) return;
        el.value = value;
        updateInput(el);
    }

    document.addEventListener("click", function(e) {
        if (!e.target.closest || !e.target.closest(SEND_BUTTONS)) return;

        const expanded = expandedForSelection();
        if (!expanded) return;

        const rawPrompt = textarea("txt2img_prompt")?.value;
        const rawNegative = textarea("txt2img_neg_prompt")?.value;

        // Gradio's own copy lands asynchronously, so for a short while replace the raw text whenever it shows up
        const started = Date.now();
        (function apply() {
            const prompt = textarea("img2img_prompt");
            const negative = textarea("img2img_neg_prompt");
            if (prompt && prompt.value === rawPrompt) setValue(prompt, expanded.prompt);
            if (negative && negative.value === rawNegative) setValue(negative, expanded.negative);
            if (Date.now() - started < 3000) setTimeout(apply, 50);
        })();
    }, true);
})();
