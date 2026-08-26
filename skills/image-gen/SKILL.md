---
name: image-gen
description: Image generation routing and prompt discipline — which provider for which job (gpt-image for text rendering and design fidelity, grok for fast iteration and photoreal people), how to structure prompts that survive the model (subject, composition, style, lighting, negatives), and the honest constraints of each provider installed on this machine. Use before generating any image so the first generation is closer to the brief.
when_to_use: Any image generation task — hero images, product shots, avatars, textures, slide art. NOT a provider itself (it routes to what's installed: the harness's generate_image tool, codex image features, grok via groken) and NOT a post-processing tool.
version: 1.0.0
license: MIT
metadata:
  agentskills:
    tags: [image-generation, prompts, design, providers]
---

# Image Gen

The first generation should be close. Provider choice and prompt structure
decide that, not luck.

## Provider routing

| Job | Provider | Why |
|---|---|---|
| Text in image (posters, UI mockups, signage) | gpt-image (gpt-image-2) | Best-in-class verbatim text rendering |
| Design fidelity, brand-adjacent work | gpt-image | Follows structured art direction |
| Fast iteration, photoreal people | grok (via groken cloud) | Speed, identity realism |
| Textures, tiles, sprites | gpt-image low quality first, then high | Cheap drafts before the final render |

Check what's installed before promising: the harness's `generate_image`
tool for gpt-image; the groken bridge for grok. Never fake a provider that
isn't there — say what's missing.

## Prompt structure (the part people skip)

1. **Subject** — one clear subject, named concretely ("a ceramic pour-over
   coffee dripper" not "coffee thing").
2. **Composition** — where the subject sits, camera angle, framing
   ("centered, slight low angle, product shot on seamless").
3. **Style** — the visual language ("editorial product photography",
   "flat vector illustration", "35mm film grain").
4. **Lighting** — the single biggest quality lever ("soft key from upper
   left, subtle rim light", "overcast window light").
5. **Negatives** — what to avoid ("no text, no watermark, no hands").
6. **Verbatim text** — if text appears, put it in quotes exactly
   (`the words "SALE ENDS FRIDAY"`) and keep it short.

## Iteration discipline

Draft cheap (low quality), pick a direction, then render the final at high
quality. Read the model's revised_prompt when available — it tells you what
it actually heard. One strong revision beats five blind regenerations.

## Pairs with

`design` (the taste standard the image is judged against),
`higgsfield-generate` (heavier video/3D/audio generation when installed).
