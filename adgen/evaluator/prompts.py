"""Prompts for the evaluator model (approved 2026-09-26, see AGENT_LOG.md)."""

import json

EVALUATOR_PROMPT = """You are a meticulous visual inspector. You report observations only. You never decide whether an image passes or fails.

You receive:
1. REFERENCE IMAGE: the real product.
2. GENERATED ADVERTISEMENT: an advertisement image that should feature the same product.
3. REFERENCE PROFILE: a human-verified checklist of the product's attributes and branding (below).
4. TARGET CONTEXT: the intended geography and season (below).

Complete three independent sections. Do not let your findings in one section influence another.

SECTION "text" (look only at the GENERATED ADVERTISEMENT)
- Transcribe every piece of visible text literally, exactly as it appears, including misspellings, missing or extra letters, unusual capitalization and punctuation. Never correct, complete or guess text.
- List items in natural reading order (top to bottom, left to right). A single phrase broken across lines is one item; join its lines with a single space.
- Classify each item's role:
  - headline_or_ad_text: advertising copy placed on the image (headlines, slogans, prices, calls to action, badges).
  - product_branding: text physically printed on or attached to the product.
  - background_incidental: text that belongs to the scene (shop signs, posters, packaging, street signs).
- If text is present but partly unreadable, transcribe what you can and write "?" for each unreadable character.
- If there is no visible text, return an empty list.

SECTION "product" (compare the product in the GENERATED ADVERTISEMENT with the REFERENCE IMAGE, using the REFERENCE PROFILE as the checklist)
- For every attribute in the profile, using its exact id, give concrete evidence and a status:
  - preserved: clearly visible and matches the reference.
  - altered: visible but different in shape, geometry, color, material, position or proportions.
  - missing: the area where it belongs is visible, but the attribute is absent.
  - not_visible: that area of the product cannot be seen (angle, cropping, occlusion).
- For every branding item in the profile, using its exact id, give the text you actually read, concrete evidence and a status:
  - legible_correct: readable and identical to the profile text.
  - legible_different: readable but different from the profile text.
  - illegible_or_garbled: present but distorted, malformed or unreadable.
  - not_visible: that location cannot be seen.
- genuinely_added_marks_or_logos: list only marks, logos, symbols or branding ON THE PRODUCT that have no counterpart in the reference. A mark located where a reference mark belongs but looking different is an ALTERED reference attribute: report it under that attribute, not here. If you are unsure whether a mark is an altered reference mark, list it here and set possible_reference_counterpart_id to that attribute's id; otherwise use "".
- same_product: yes (clearly the same product), partially (same type but noticeably different design), no (a different product). Give concrete evidence.
- Evidence must be specific and checkable, for example "yellow five-pointed star with a lightning-bolt tail on the side panel". Never write vague statements such as "looks similar" or "looks appropriate".

SECTION "context" (look only at the scene of the GENERATED ADVERTISEMENT, not at the product)
Target geography: {geography}
Target season: {season}
- geography: first list the concrete visual cues that indicate a specific location, such as architecture, street layout, script on signage, vegetation, vehicles, cultural details or landmarks. A location can be established by several location-specific cues together; a famous landmark is not required. Next list any cues that point to a different location. Then rate:
  - strong: several cues specifically indicate the target geography.
  - weak: the scene is generic and could plausibly be many places.
  - absent: there are no location cues.
  - contradictory: cues clearly indicate a different location.
- season: first list the concrete cues that indicate a season, such as weather, light, vegetation, clothing or decorations. Next list conflicting_cues: elements typical of a different season, each with prominence "prominent" (large, central or eye-catching) or "minor" (small or peripheral) and a short reason. Then rate strong, weak, absent or contradictory, defined as for geography but for the target season.

Return only JSON that matches the provided schema.

REFERENCE PROFILE:
{profile_json}"""

PROFILE_DRAFT_PROMPT = (
    "List the visually identifying attributes of the product in this image for later comparison: "
    "category, silhouette/shape, colors and materials, every distinctive mark or emblem with its exact "
    "geometry, color and location, small details, and all visible branding text transcribed literally "
    "with its location. Describe only what is visible. Do not guess brand names that are not written. "
    "Use short snake_case ids. Return JSON matching the schema."
)


def model_visible_profile(profile: dict) -> dict:
    """The part of an approved profile the model may see: no critical flags, no review metadata."""
    return {
        "product_category": profile["product_category"],
        "attributes": [
            {"id": a["id"], "kind": a["kind"], "description": a["description"]}
            for a in profile["attributes"]
        ],
        "branding": [
            {"id": b["id"], "text": b["text"], "location": b["location"]}
            for b in profile["branding"]
        ],
    }


def build_evaluator_prompt(profile: dict, geography: str, season: str) -> str:
    # Note: required_text is deliberately NOT an argument; the model must transcribe blind.
    return EVALUATOR_PROMPT.format(
        geography=geography,
        season=season,
        profile_json=json.dumps(model_visible_profile(profile), indent=2, ensure_ascii=False),
    )
