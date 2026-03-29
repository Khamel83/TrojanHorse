---
name: vision
description: Smart visual analysis for websites and images using Playwright screenshots and AI vision.
---

# /vision — Visual Inspection of Websites and Images

Smart visual analysis that handles both websites and images.

## Usage

```
/vision <url> [prompt]
```

- `<url>` — Website URL OR direct image URL
- `[prompt]` — Optional: what to look for (default: comprehensive analysis)

## Behavior

| URL Type | What Happens |
|----------|--------------|
| Website (`https://example.com`) | Playwright navigates → screenshots → analyzes |
| Image (`https://.../*.png|jpg|jpeg`) | Direct analysis with mcp__4_5v_mcp__analyze_image |

## Examples

```
/vision https://example.com
→ Navigates to site, takes screenshot, analyzes layout and design

/vision https://example.com "What colors are used?"
→ Screenshots site, analyzes color palette

/vision https://mockup.png "replicate"
→ Direct image analysis for UI replication

/vision https://diagram.png "Describe the architecture"
→ Direct image analysis
```

## For UI Replication

```
/vision https://mysite.com "replicate"
```

Uses the replication prompt: "Describe in detail the layout structure, color style, main components, and interactive elements to facilitate code generation."

## Execution Steps

When invoked:

1. **Detect URL type:**
   - Ends in `.png`, `.jpg`, `.jpeg` (case insensitive) → image
   - Otherwise → website

2. **For images:**
   - Call `mcp__4_5v_mcp__analyze_image` directly
   - If prompt is "replicate", use specialized replication prompt
   - Otherwise use provided prompt or default comprehensive analysis

3. **For websites:**
   - Call `mcp__playwright__browser_navigate` with the URL
   - Call `mcp__playwright__browser_screenshot` to capture
   - Call `mcp__4_5v_mcp__analyze_image` on the screenshot
   - If prompt is "replicate", use specialized replication prompt

## Tools Used

- `mcp__playwright__browser_navigate` — Navigate to websites
- `mcp__playwright__browser_screenshot` — Capture screenshots
- `mcp__4_5v_mcp__analyze_image` — AI vision analysis

## Requirements

- Playwright MCP server must be configured
- The `mcp__4_5v_mcp__analyze_image` MCP must be available

## Local Images

For local image files, use Read tool directly:
```
Read: screenshots/mockup.png
```
