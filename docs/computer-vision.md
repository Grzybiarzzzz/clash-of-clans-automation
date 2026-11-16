# Computer vision: from pixels to deployment positions

[Project overview](../README.md) · [Implementation](../coc_bot/vision/bb_deployment_zone.py)

Builder Base boundary detection was one of the parts I struggled with most. The goal was to place troops around the visible deployment boundary instead of relying only on fixed coordinates. That required turning noisy screen pixels into a useful geometric approximation, then turning that geometry into candidate clicks.

## Builder Base diagnostic examples

Boundary detection was difficult because the red mask captures more than the deployment boundary. These two captures show the intermediate detections alongside the selected troop positions on different base layouts.

### Compact layout

[![Compact Builder Base: red mask, Hough line candidates, and deployment positions](images/builder-base-compact.png)](images/builder-base-compact.png)

The left panel retains the outer boundary but also many pixels from buildings inside it. The middle panel shows numerous interior line candidates: Hough detection alone does not distinguish a deployment boundary from other straight features. The right panel overlays a cyan hull and the selected deployment positions around the compact layout.

### Elongated layout

[![Elongated Builder Base: red mask, Hough line candidates, and deployment positions](images/builder-base-elongated.png)](images/builder-base-elongated.png)

This layout has a different aspect ratio, with the upper part reaching the capture edge. The displayed hull follows a more elongated envelope. It illustrates why adapting positions to detected geometry is useful, and why capture bounds and missing boundary sections matter.

### Reading the panels

| Panel | Meaning |
|---|---|
| Raw mask | Pixels accepted by the red HSV thresholds; includes boundary fragments and unrelated visual features. |
| Hough lines | Raw segments in blue and merged segments in green. These are candidates, not confirmed boundary edges. |
| Positions | Cyan reconstructed hull, gray candidate points, six numbered green Baby Dragon positions, and the orange Battle Machine position. |

Click either image to inspect the full-resolution capture. The examples illustrate the diagnostic output; they do not establish whether every selected position produced a successful deployment.

### How the diagnostic view relates to the decision

The numbered positions are supplied by the deployment routine. However, `save_bb_dragon_debug_visualization` takes a fresh screenshot and reconstructs the cyan hull from the largest contour in a dilated red mask. The live detector can instead build its hull from multiple Hough-filtered contours or use a fallback. Consequently, the displayed polygon is not necessarily the exact polygon that produced those positions, and the scene may be from a slightly later frame.

The `bb_gold_dragon_debug_positions` setting saves these three-panel views under `screenshots/debug/bb_deployment_zone/`. The separate [F3 debug utility](../tools/debug/debug_bb_deployment_zone.py) contains an older contour/circularity approach and different sampling logic.

An improvement would be to pass the original frame, intermediate masks, chosen hull, and coordinates from one detector invocation to the renderer. That would make the panels an exact trace of a single decision.

## Builder Base: recovering the deployment boundary

The advanced detector is used by the BB Gold Baby Dragon routine. Other Builder Base routines also use a simpler red-mask bounding rectangle, so the convex-hull method is not the only deployment algorithm in the project.

### 1. Isolate red pixels

The bot zooms out and captures a configured screen region. It converts the image to HSV and combines two hue ranges for red, covering both ends of the hue scale. Saturation and brightness thresholds reject some unrelated pixels.

Color alone is insufficient: buildings and decorations can also be red, while the boundary can appear fragmented. The next stages add geometric evidence.

### 2. Find and merge boundary-like lines

`detect_hough_lines` applies Canny edge detection, slight dilation, and a probabilistic Hough transform. Short segments are filtered. The merge routine groups nearby segments using angle similarity, perpendicular distance, and endpoint proximity, then represents a group by its most distant endpoints.

The merged lines create a mask that retains nearby red pixels. Additional dilation connects fragments before contour extraction. This is a heuristic for preferring long boundary-like structures over isolated red objects; it does not classify buildings semantically.

### 3. Construct a convex hull

The detector combines the filtered contour points and calls `cv2.convexHull`. It simplifies the result with `cv2.approxPolyDP`, using a tolerance of 1% of the hull perimeter.

The hull bridges gaps and gives the next stage a closed polygon. It also discards concavities: it approximates an outer envelope rather than recovering the exact legal deployment region. A stray red structure can pull a hull vertex outward.

### 4. Sample the perimeter and offset candidates

The code calculates cumulative edge lengths, samples by distance along the perimeter, and interpolates between vertices. This distributes candidates along edges instead of only choosing polygon corners. The nominal interval is 50 pixels, with at least eight samples.

Each point is shifted 25 pixels along the direction from the capture-region center to the point. This is a radial offset, not a constant-distance offset along each edge's outward normal. The distinction matters when the base is off-center or an edge is oblique.

Candidates are converted back to screen coordinates, checked against a dilated red mask, filtered around the unit bar, and clamped to the configured screen bounds. The mask check excludes pixels near red lines; it is not a filled-polygon test proving that every candidate is outside the base. Clamping and fallback points also mean these are candidate positions, not guaranteed legal clicks.

### 5. Choose troop positions and fall back when needed

The Baby Dragon routine selects six spread-out positions from the candidates. The selector attempts a minimum separation, relaxes it if necessary, and finally falls back to basic spacing. A separate candidate is selected for the Battle Machine where possible.

When line detection is insufficient, the advanced detector tries contours directly: a sufficiently large contour, or a combination of significant contours. If it cannot recover useful geometry, it generates ring positions. This keeps the routine moving, but the fallback carries less information about the actual boundary.

```mermaid
flowchart TD
    Capture[Screen crop] --> HSV[Two red HSV masks]
    HSV --> Lines[Canny and Hough line segments]
    Lines --> Merge[Filter and merge segments]
    Merge --> Contours[Line-filtered red contours]
    Contours --> Hull[Convex hull and polygon simplification]
    Hull --> Samples[Distance-based perimeter sampling]
    Samples --> Candidates[Radial offset and coordinate filters]
    Candidates --> Selection[Spread-out troop positions]
    Lines --> Fallback[Contour or ring fallback]
    Fallback --> Candidates
```

## Building recognition

Building and interface detection uses normalized template correlation (`TM_CCOEFF_NORMED`) with reference images. Multiple templates cover appearance variants. Building-specific thresholds control acceptance, and distance-based duplicate filtering prevents nearby matches from being counted repeatedly in the relevant detection routines.

Debug overlays can show weaker matches alongside accepted detections. That makes threshold choices inspectable: raising a threshold may remove false positives while also missing partially obscured buildings. A match score measures visual similarity, not the probability that a building was correctly identified.

## Spatial clustering for spell placement

Clumps mode groups detected buildings to find opportunities to hit several targets with one spell volley. It converts bounding-box origins into centers using configured building dimensions, then processes detections in confidence order. A building can join a group only if it is within 125 pixels of every existing member. This prevents a chain of nearby buildings from stretching a group across the base.

The algorithm greedily assigns each building to one group, selects the largest group, and averages its centers to choose a casting point. Achievement Farm then casts one Earthquake and ten Lightning spells around that point. When no multi-building group is found, the configured building-priority list determines the target.

This favors the number of nearby targets, rather than explicitly optimizing damage or modelling spell coverage. Assignment depends on confidence order and can miss a larger feasible group. The distance threshold and centroid are heuristics; they do not guarantee that every building is hit.

## Giant Arrow trajectory estimation

The detector gathers bright cyan/green glow segments across multiple frames and filters candidates by color, area, shape, and position. It forms connected groups of nearby points, then scores groups by point count and deviation from a fitted line. A larger group with a more linear arrangement receives a higher score.

For the selected group, the code fits a line and removes points more than 50 pixels away, repeating for up to three passes. It fits either `y` from `x` or `x` from `y` according to the dominant spatial extent, accommodating near-vertical paths. The final segment must be at least 200 pixels long; the endpoint is then extended by 30% for coverage.

When glow detection fails, a fallback estimates the path from purple health-bar detections, filtered by size, shape, and screen position. These are calibrated heuristics: unrelated effects can resemble the trail, and a health bar does not by itself prove that a building was hit by the arrow. The multi-frame observations estimate a spatial path rather than projectile speed or direction of travel.

## Reading numeric values

Resource numbers (scouted loot, own storages, end-screen loot) are read by a digit reader written for the game's typeface, in `coc_bot/vision/digits.py`. Troop counts, the destruction percentage, and the Builder Base "Attacker" label still use Tesseract.

The game draws every number the same way: a bright fill, a dark outline, and a wider space between groups of three digits. The reader depends on those properties rather than on whatever is behind the number:

1. **Fill mask.** A pixel belongs to a glyph when its darkest colour channel exceeds a threshold derived from the digit templates. Saturated backgrounds such as a storage bar stay out of the mask because one of their channels is dark.
2. **Segmentation.** Each connected blob of fill that has the height of a digit and is surrounded by dark outline is one digit. The outline separates neighbours, and bright scenery has no outline.
3. **Classification.** The blob is correlated with the fill shape of each template glyph. The best match must be good enough and clearly ahead of the second best.
4. **Structure.** The digits must sit on one line, and the wide gaps between them must be exactly the thousands separators. A digit that went missing shifts those gaps.

A reading that fails any of these returns no value together with a reason (`clipped`, `unknown_glyph`, `bad_grouping`, and so on). It is never reported as 0, so callers can tell "unreadable" from "empty": the scouting routines skip a base they cannot read and pause after several in a row, and the storage checks make no decision on a failed read.

The earlier reader thresholded the whole crop with Otsu's method and slid every template across it, with non-maximum suppression choosing among overlapping matches. Its cut-off depended on the background, and a missed digit silently produced a number ten times smaller. It is kept as `digits.legacy_read` for comparison and can be selected with `OCR_ENGINE = "legacy"` in `config.py`.

### Measuring it

The repository's tests exercise the reader on numbers composed from the digit templates over synthetic backgrounds. That shows the mechanism, not accuracy on real frames. For real frames the bot records what it sees:

- While running, it saves crops to `data/ocr_corpus/<screen>/` with the value it read in the file name and a row in `index.jsonl`. Every failed reading and every disagreement with the old reader is kept; routine readings are sampled.
- `python tools/ocr/replay_corpus.py --recorded` summarises which failures occurred.
- Crops copied to `tests/data/ocr/<screen>/` with the correct value in the file name become test cases. `python tools/ocr/replay_corpus.py` prints how many are read correctly, refused, or read wrong, next to the old reader's score, and `tests/test_ocr_replay.py` runs them in the suite.

After each attack the bot also compares the growth of its storages with the loot the end screen showed. A contradiction is logged as `[OCR AUDIT]`: one of the three readings was wrong, or resources were spent in between.
