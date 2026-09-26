"""Builds the generation prompt from the three structured text fields."""

from adgen.spec import GenerationSpec

# Generic on purpose: product details come only from the reference image.
PROMPT_TEMPLATE = """Create a professional display advertisement.

The attached image shows the reference product. Treat it as the source of truth.

PRODUCT
- Feature the exact product from the reference image as the clear focal point.
- Preserve its identity, shape, proportions, materials, colors, and any visible branding, labels, and details.
- Do not redesign, replace, restyle, or add to the product.

CONTEXT
- Target geography: {geography}
- Season: {season}
- Reflect this geography and season naturally through the setting, lighting, props, and atmosphere. Do not alter the product to fit the context.

TEXT
- Render the following text in the image exactly as written, character for character, exactly once:
  "{required_text}"
- Use a clean, highly legible typeface with strong contrast, placed so it does not cover the product.
- Do not add any other text, slogans, prices, claims, logos, or watermarks.

STYLE
- Polished commercial advertising photography with a balanced composition and clear space for the text."""


def build_prompt(spec: GenerationSpec) -> str:
    # str.format only interprets braces in the template, never in the inserted values.
    return PROMPT_TEMPLATE.format(
        geography=spec.geography,
        season=spec.season,
        required_text=spec.required_text,
    )
