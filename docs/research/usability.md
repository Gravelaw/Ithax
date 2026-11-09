# Usability: time for a new user to run a first template model

Spec 0 "Success measures" (M10, AKS-125): "Time for a new user to run a first template model: under 30 minutes, with no code written. Three outside testers timed from installer to Results, following the script in `docs/research/usability.md`." The outside testers are the owner's (spec 4 acceptance, "fallback as in spec 3"; the owner accepted the owner-only fallback for every owner-only check on 2026-11-09, B6 in PR #51's DECISIONS entry).

## Question

What script do the three outside testers follow, what is timed, and what can a session check before they do?

## Finding

- **There is no installer yet.** Packaging is M11 (spec 3 "Packaging"; Linux first, owner decision B4 of 2026-11-09). Until then the product is installed from source: a Python environment, `pip install`, and `npm ci` and `npm run build` in `ui/`. That is typing commands, which a tester who "writes no code" should not have to do, so the timing below starts at the app's first start on a machine the owner has prepared, and the install is timed again with the installer at M11 (reading, owner to confirm).
- **The path from first start to Results exists and is tested end to end**, by pointer and through documented routes only: `ui/e2e/learn.spec.ts` (Home, Learn, "Start the lesson" on the coffee shop, the steps, the exercise run, Results with the answer), `ui/e2e/build.spec.ts` (the Build form to a completed run without data) and `ui/e2e/pointer-only.spec.ts` (the coffee shop built from an empty project). A tester following the script below needs only the mouse and, for the project name, the keyboard.
- **The session's own timing of the install from source** (one run, 2026-11-09, at f1388b6, in this Linux container with 4 cores, not a tester's machine, while other runs used the same cores): `git clone` 0.5 s; `python3 -m venv` and `pip install .` with no pip cache 538 s (about 9 min, every dependency downloaded); `npm ci` and `npm run build` 7.5 s (npm's cache was warm). So the install from source alone could take a third of the 30 minutes on a slow connection; the M11 installer has to bring it well under that.
- **The installer exists from M11** (2026-11-09, AKS-127; spec 3 "Packaging"): one archive with its checksum, unpacked and installed with its `install.sh`, no Python, `pip` or `npm` needed. The session timed it in a clean `ubuntu:24.04` container as an ordinary user, from copying the archive in to the coffee shop template's first result through the documented API: checksum checked by 0.3 s, unpacked by 4.5 s, installed by 5.9 s, first result by 9.4 s, 13.2 s in all with the container's start (`tests/linux_package/test_linux_package.py`, marker `package`; the same offline with `--network none`, 15.1 s). A tester's own timing adds the download and the reading of the install steps. So from M11 the owner's step 1 below is the installer, and the tester's clock can start at the download. The install is still three commands typed in a terminal (check, unpack, `install.sh`), copied from the README; a tester who writes no code may find that the hardest step, and a package that installs with a double-click (a `.deb` that needs no network where WebKitGTK is present, or a graphical installer) is left for the owner (DECISIONS M11 "The Linux package", candidate bucket Phase 1a).
- **Nothing has been timed with an outside tester.** The measure stays open for the owner (Awaiting owner, AKS-82).

## Tester script

For the owner, before each tester (not timed):

1. On a Linux machine (Phase 1 is Linux first), from M11: put the package (`lcsim-<version>-linux-x86_64.tar.gz` and its `.sha256` file) in the tester's Downloads folder; the tester installs it as the README's "Install on Linux" says, timed as part of step 1 (owner to confirm; candidate bucket Phase 1a). Before M11 the product was installed from source: `python3 -m venv .venv`, `.venv/bin/pip install .`, then in `ui/` `npm ci` and `npm run build`.
2. From M11 `install.sh` adds lcsim to the desktop's applications and links the command `lcsim`; before M11, make a desktop shortcut or a one-line script that runs `.venv/bin/python -m lcsim.launcher` from the repository folder.
3. Remove `~/.config/lcsim` and `~/.local/share/lcsim` (or the platform's folders) so the tester sees the first start.
4. Give the tester only this sheet. Do not help; note where they hesitate and what they say.

For the tester (timed from step 1 to step 7; write the time at each step):

1. **Start the clock.** From M11: install the app from the Downloads folder as the README says, then start it from the applications menu (or `lcsim`). Before M11: start the app from the shortcut.
2. Read the welcome notice and press **Continue**.
3. On Home, press **Learn**.
4. In the gallery, find "Coffee shop queue" and press **Start the lesson**.
5. Read each step on the card beside the model and press **Next** until the last step.
6. On the last step, press **Make the change**, choose what you think will happen, then press **Run the exercise**.
7. When the run monitor says Done, press **See the results**. **Stop the clock** when the results page shows the answer to your prediction.

If a tester gets stuck for more than five minutes on one step, note the step, help them past it, and record the run as "helped".

Record sheet, one row per tester:

| Tester (role, no name) | Date | Machine (cores, memory, OS) | Minutes to step 7 | Helped? | Where they hesitated | Code written? |
| --- | --- | --- | --- | --- | --- | --- |

The measure is met when all three testers reach step 7 in under 30 minutes, unhelped, writing no code. Add the sheet to this note and a dated line to `docs/DECISIONS.md`.

## Sources

- Spec 0 "Success measures"; spec 4 "Learn and Build modes" and its acceptance table ("A first-time user completes one Learn walkthrough without outside help"); spec 3 "Design before building" (the owner's fallback) and "Packaging".
- The Learn walkthrough steps in PR #55 (AKS-124), on which the tester's steps 2 to 7 are based.
- The owner's decisions of 2026-11-09 (PR #51): B4 (Linux first), B6 (owner-only fallback accepted).

## Decision

- The script above is the M10 script; the timing starts at the first start until the M11 installer exists, then at the installer (owner to confirm; candidate bucket Phase 1a). Updated at M11 (2026-11-09, AKS-127): the installer exists, so the owner's step 1 hands the tester the package and the tester's step 1 installs it with the clock running.
- The coffee shop's lesson is the first template run timed, since it is the Learn gallery's first student template and its run takes about a second (`docs/research/performance.md`).
- The timing by three outside testers is an owner row (Awaiting owner, AKS-82); under B6 the owner may do the scripted think-aloud run first and log it.

## Tested

The script's steps 2 to 7 are the steps of `ui/e2e/learn.spec.ts`, which passes in `npm run e2e` at this commit. The install from source was timed once as above; no tester has run the script. At M11 the installer was timed by `pytest -m package` in a clean container (above); no tester has run the script with it.
