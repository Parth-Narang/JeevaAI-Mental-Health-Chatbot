---
name: Jeeva
colors:
  surface: '#fbf9f6'
  surface-dim: '#dbdad7'
  surface-bright: '#fbf9f6'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f5f3f0'
  surface-container: '#efeeeb'
  surface-container-high: '#eae8e5'
  surface-container-highest: '#e4e2df'
  on-surface: '#1b1c1a'
  on-surface-variant: '#544340'
  inverse-surface: '#30312f'
  inverse-on-surface: '#f2f0ed'
  outline: '#87726f'
  outline-variant: '#dac1bd'
  surface-tint: '#93493b'
  primary: '#904639'
  on-primary: '#ffffff'
  primary-container: '#ae5e50'
  on-primary-container: '#fffbff'
  inverse-primary: '#ffb4a6'
  secondary: '#59605c'
  on-secondary: '#ffffff'
  secondary-container: '#dae1dc'
  on-secondary-container: '#5d6460'
  tertiary: '#5c5c5c'
  on-tertiary: '#ffffff'
  tertiary-container: '#757474'
  on-tertiary-container: '#fffcfb'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffdad4'
  primary-fixed-dim: '#ffb4a6'
  on-primary-fixed: '#3c0702'
  on-primary-fixed-variant: '#763226'
  secondary-fixed: '#dde4de'
  secondary-fixed-dim: '#c1c8c3'
  on-secondary-fixed: '#161d1a'
  on-secondary-fixed-variant: '#414844'
  tertiary-fixed: '#e4e2e1'
  tertiary-fixed-dim: '#c8c6c6'
  on-tertiary-fixed: '#1b1c1c'
  on-tertiary-fixed-variant: '#474747'
  background: '#fbf9f6'
  on-background: '#1b1c1a'
  surface-variant: '#e4e2df'
typography:
  display-lg:
    fontFamily: EB Garamond
    fontSize: 48px
    fontWeight: '500'
    lineHeight: 56px
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: EB Garamond
    fontSize: 36px
    fontWeight: '500'
    lineHeight: 42px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: EB Garamond
    fontSize: 32px
    fontWeight: '500'
    lineHeight: 40px
  headline-sm:
    fontFamily: EB Garamond
    fontSize: 24px
    fontWeight: '500'
    lineHeight: 32px
  body-lg:
    fontFamily: Be Vietnam Pro
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Be Vietnam Pro
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-md:
    fontFamily: Be Vietnam Pro
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0.05em
  caption:
    fontFamily: Be Vietnam Pro
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 8px
  container-margin: 32px
  gutter: 24px
  stack-sm: 16px
  stack-md: 32px
  stack-lg: 64px
---

## Brand & Style

This design system is built upon the principles of **Organic Humanism**. It rejects the cold, sterile nature of traditional healthcare interfaces in favor of a "digital sanctuary" that feels hand-crafted, empathetic, and grounding. The target audience includes individuals seeking mental clarity, emotional support, and a moment of pause in a high-velocity world.

The visual style blends **Minimalism** with **Tactile/Skeuomorphic** warmth. It prioritizes "breathability" through generous negative space and utilizes organic, non-geometric shapes that mimic forms found in nature—leaves, stones, and clouds. Every interaction should evoke a sense of being "held" rather than being "processed." Avoid sharp edges, perfect circles, or high-velocity animations; instead, use soft fades and gentle transitions that respect the user's cognitive load.

## Colors

The palette is rooted in earth tones to provide an immediate psychological "grounding" effect. 

- **Primary (Terracotta - #c06c5d):** Used sparingly for meaningful action points and highlights. It represents warmth, clay, and human vitality.
- **Secondary (Sage - #e8efe9):** The primary surface color for cards and secondary containers. This soft green promotes tranquility and rest.
- **Tertiary/Text (Charcoal - #333333):** A softer alternative to pure black, providing high legibility without the harshness of high-contrast digital ink.
- **Background (Cream - #faf8f5):** The foundation of the UI. It mimics high-quality paper or linen, reducing eye strain compared to stark white.

Avoid using pure whites or vibrant neons. Color should always feel "matte" and natural.

## Typography

The typography strategy pairs the intellectual, timeless quality of a classical serif with the approachable utility of a modern sans-serif.

**EB Garamond** is used for all display and headline levels. Its high x-height and elegant serifs evoke a "literary" and "authoritative yet gentle" feel. Use it for journaling prompts, section headers, and big-picture messages.

**Be Vietnam Pro** serves as the functional workhorse. It is warm, contemporary, and exceptionally readable. Use it for all body copy, instructional text, and UI labels. 

Always maintain generous line heights to ensure text never feels crowded. Headlines should use "Optical Sizing" where available to maintain elegance at larger scales.

## Layout & Spacing

This design system utilizes a **Fluid-Responsive Grid** that favors wide margins and asymmetrical balance to feel less "mechanical." 

- **Desktop:** 12-column grid with a max-width of 1280px. Centers the content to create a focused, "reading" experience.
- **Mobile:** 4-column grid with 24px side margins to prevent content from feeling "trapped" against the screen edges.

Spacing should follow a 8px-base scale, but when grouping elements, lean towards larger "Stack" values (`stack-lg`) to create distinct islands of information. This prevents the "list-heavy" feel of clinical apps and encourages a slower, more intentional browsing pace.

## Elevation & Depth

To maintain a non-clinical feel, the design system avoids heavy shadows or floating "material" layers. Instead, it uses **Tonal Layering** and **Subtle Inner Shadows**.

1. **Surface Tiers:** The Cream (#faf8f5) background is the lowest level. Sage (#e8efe9) containers sit on top.
2. **Soft Depth:** Instead of drop shadows, use very soft, 10% opacity Terracotta-tinted blurs to lift active elements (like a selected card).
3. **Inner Glows:** For input fields and buttons, use a subtle inner-shadow to create a "pressed" or "carved" look, making the UI feel like it is part of the paper rather than hovering over it.

## Shapes

The shape language is the core of this design system’s "Organic" feel. While the base `roundedness` is set to `2` (0.5rem) for functional elements like inputs, larger components should utilize **Variable Radii** or "Squircle" shapes.

- **Primary Cards:** Should use an "organic" corner radius where the top-left and bottom-right are slightly more rounded than their opposites (e.g., 24px / 16px / 24px / 16px) to mimic a stone or hand-cut paper.
- **Interactive Elements:** Buttons should be fully pill-shaped (`rounded-xl`) to feel soft and safe to touch.
- **Icons:** Avoid thin, technical lines. Use thick, soft-capped strokes and hand-drawn qualities.

## Components

- **Buttons:** Primary buttons use the Terracotta (#c06c5d) fill with white text. Secondary buttons use a Sage (#e8efe9) fill with Charcoal text. Always use pill shapes and avoid hard borders.
- **Cards:** Cards are Sage (#e8efe9) with no border. Use generous internal padding (min 24px). For "Journal" entries, use a "Rough Edge" border-style if possible to simulate paper.
- **Input Fields:** Use a subtle Cream-on-Cream approach with a 1px Sage border. Focused states should use a soft Terracotta outline.
- **Chips/Tags:** Used for "Moods" or "Feelings." Use the Sage background with a slightly darker Sage text for a low-contrast, calming effect.
- **Progress Bars:** Represented as "Rising Water" or "Growing Vines" through organic stroke animations rather than a standard flat bar.
- **Selection Controls:** Checkboxes and Radios should feel like hand-drawn "O" and "X" marks, avoiding perfectly geometric checkmarks.