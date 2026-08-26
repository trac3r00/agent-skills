---
name: visual-qa
description: Visual quality assurance workflow for web pages, terminal UIs, and generated documents — capture screenshots, compare against baselines, and run a structured good/bad verdict. Companion to webapp-testing: where webapp-testing drives the browser, visual-qa defines what to look for and how to judge it. Use after building or changing any UI, or when asked whether a page, component, or TUI looks right.
when_to_use: After any UI build/change, before shipping a visual artifact, or when the user asks "does this look right?" Requires a browser or rendering surface to capture from (Playwright, Chrome, agent-browser, or the HyperFrames render pipeline for video). NOT a replacement for functional testing — it judges appearance and layout, not behavior.
version: 1.0.0
license: MIT (from oh-my-opencode / omo-ai; adapted)
metadata:
  agentskills:
    tags: [visual-qa, screenshot, ui, design, qa]
---

# Visual QA

A functional test says the button works. Visual QA says the button looks like
a button — on a 375px phone, at 1440px desktop, in dark mode, with the CJK
font loaded.

## The workflow

1. **Capture.** Screenshot the surface through its real renderer:
   - Web: Playwright `page.screenshot()` or `agent-browser --cdp screenshot`
   - TUI: xterm.js web terminal (never `tmux capture-pane` — it degrades
     truecolor and wide-glyph width)
   - Documents: open the PDF/PNG, don't read the source
2. **Compare.** Against the design brief, the previous baseline, or the
   reference the user provided. Look for: layout collapse, text clipping,
   CJK glyph corruption, color contrast failures, broken responsive
   breakpoints, and the three AI-default looks (cream+serif+terracotta,
   near-black+acid-green, broadsheet hairlines).
3. **Verdict.** Good / Bad with specific evidence: screenshot path, the exact
   element or region that fails, and what the fix is. "Looks fine" without a
   screenshot is not a verdict.

## What to check

| Surface | Failures to hunt |
|---|---|
| Web page | Responsive breakpoints, focus rings, reduced-motion, font loading |
| Component | Padding/margin collapse, text overflow, hover states, disabled states |
| TUI | Truecolor, wide-glyph alignment, box-drawing drift, CJK rendering |
| Document/PDF | Page breaks, image scaling, font embedding, print colors |
| Generated art | The design brief — does it match the philosophy that produced it |

## Baselines

Keep a `qa/baselines/` directory per project. Capture the current state
before any visual change; diff after. A baseline that is not updated when the
design intentionally changes is worse than no baseline — it trains you to
ignore failures.

## Pairs with

`webapp-testing` (drive the browser to the state worth capturing),
`design` (the taste standard the verdict is judged against),
`webapp-testing` (functional QA on the same surface).
