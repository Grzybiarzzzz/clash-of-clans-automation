# Architecture and tradeoffs

[Project overview](../README.md)

## Observe, decide, act

The automation works through the same visible interface a player uses. Screenshots feed two complementary recognition paths: template matching for visual elements and OCR for numeric values. The selected profile supplies thresholds and action settings, and the attack flow turns those decisions into mouse and keyboard events.

Reference templates are grouped by building or interface element. Multiple images accommodate different appearances. Detection overlays make the selected matches inspectable; their scores are similarity measurements rather than probabilities that a detection is correct.

The challenge is connecting imperfect observations to actions. A wrong OCR value can affect base selection, while a shifted coordinate can change where an otherwise correct decision is executed. Screen-region calibration and debug captures therefore matter as much as the high-level policy.

The [computer-vision walkthrough](computer-vision.md) follows the Builder Base pipeline from HSV segmentation through Hough lines and convex hulls to candidate troop positions. It also distinguishes the live detector from the older diagnostic utilities.

## Profiles and queues

Profiles express different objectives through settings: resources, trophies, particular buildings, or Builder Base tasks. Troop and spell placement and ability timing are configurable rather than one universal sequence.

The queue manager supports manual mode sequences and automatic switching based on resource conditions. It separates the question of which mode should run next from the detailed attack routine, although its integration still depends on the desktop application.

## Two interfaces, shared state

Tkinter provides the desktop controls. `BotStateManager` holds values and notifies subscribers when they change. FastAPI exposes state and control endpoints, and WebSocket messages carry incremental updates to the Vue interface. Changes may originate on the bot thread, so broadcasts are scheduled onto the server's event loop.

The listener binds to loopback by default. This limits network exposure but does not add authentication. The static-file route resolves requested paths and rejects paths or symbolic links that escape the frontend build directory.

## Performance choices

Template caches reduce repeated preparation, and building detection can run across multiple worker threads. Performance depends on image sizes, the number of templates, and the enabled features; speedup requires measurement on the target machine.

The input module generates curved pointer paths and variable action timing.

## Diagnostics and records

CSV outputs record statistics separately from runtime settings. The interface plots selected records, while optional Discord integrations expose monitoring and control outside the desktop. Credentials stay in a local configuration file.

Reference images are functional matching assets. Selected diagnostic captures illustrate the algorithms in the computer-vision walkthrough; raw activity logs remain separate.

## Further engineering work

Screen observation (`coc_bot/vision/`), input (`coc_bot/input/`), attack routines (`coc_bot/attacks/`), and application startup (`coc_bot/app.py`) live in separate modules. They still communicate through module-level session state in `coc_bot/runtime.py`, and the attack routines call detection and input functions directly.

The next structural step would be passing the screen source and the input device into the routines instead of importing them. That would make it possible to replay recorded screenshots through the decision logic without controlling a live desktop.

For now, the tests cover imports, the pure geometry helpers, the GUI composition, and the shared-state and web components. End-to-end behavior still depends on validation on Windows with the intended game layout.
