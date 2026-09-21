"""LLM-based prompt generation for Beyond the Baseline.

Uses a Gemini text model, given the full CHANNEL_STYLE_GUIDE as a system
instruction, to turn one narration line into a single storyboard-quality
image prompt: it decides character count, location, camera angle, and the
single strongest visual beat per shot. This is what actually implements
the guide's "think like a YouTube editor" logic -- a rule-based fallback
(style_preset.build_prompt_fallback) is only used if this call fails.
"""

from style_preset import CHANNEL_STYLE_GUIDE

OUTPUT_CONTRACT = """

OUTPUT CONTRACT:
Respond with only the final image-generation prompt, as a single plain-text
paragraph. No headings, labels, markdown, bullet points, or surrounding
quotation marks. Do not explain your reasoning or restate these
instructions. Follow PROMPT LENGTH: normally about 75-150 words; use more
only for the cases the guide calls out (two-player matches, complex court
geometry, progression scenes, stadium scenes, important typography, or a
shot noted below as previously failed).
"""

SYSTEM_INSTRUCTION = CHANNEL_STYLE_GUIDE + OUTPUT_CONTRACT


def build_prompt_llm(
    client,
    text_model: str,
    line: str,
    shot_number: int,
    total_shots: int,
    script_lines: list,
    recent_prompts: list,
    aspect: str = "16:9",
    retry_hint: bool = False,
) -> str:
    """Call the Gemini text model to build one scene prompt for `line`."""
    from google.genai import types

    script_context = "\n".join(f"{n}. {l}" for n, l in script_lines)
    recent_context = (
        "\n\n".join(f"- {p}" for p in recent_prompts[-3:])
        if recent_prompts
        else "(none yet -- this is one of the first shots)"
    )

    user_content = (
        "FULL SCRIPT (for character-progression context; this shows the "
        f"whole beginner-to-pro journey so you know roughly where shot "
        f"{shot_number} of {total_shots} falls):\n{script_context}\n\n"
        "RECENTLY GENERATED PROMPTS (avoid repeating their camera angle "
        f"and environment choices):\n{recent_context}\n\n"
        f"NARRATION LINE FOR THIS SHOT (shot {shot_number} of {total_shots}):\n"
        f"\"{line}\"\n"
    )

    if aspect and aspect != "16:9":
        user_content += (
            f"\nUse {aspect} as the aspect ratio for this image instead of "
            "16:9.\n"
        )

    if retry_hint:
        user_content += (
            "\nNote: an earlier attempt at this exact shot failed to "
            "generate a usable image, so this warrants a longer, more "
            "explicit prompt per the PROMPT LENGTH exception for scenes "
            "that previously failed.\n"
        )

    response = client.models.generate_content(
        model=text_model,
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.9,
        ),
    )
    prompt = (response.text or "").strip().strip('"')
    if not prompt:
        raise RuntimeError("Text model returned an empty prompt.")
    return prompt
