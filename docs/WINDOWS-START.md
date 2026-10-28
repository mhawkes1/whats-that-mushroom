# Running Funga on a Windows laptop, from nothing

Written for someone who has never opened a terminal. Every step is a
download, a click or one line pasted into one window. Nothing here needs
git, a GPU, a dataset or an account.

There is exactly **one** line you type, and step 5 puts you in the right
place to type it, so you never have to learn what `cd` means.

---

## 1. Install Python

<https://www.python.org/downloads/windows/> — take the latest **3.12** or
**3.13** installer, 64-bit.

On the first screen of the installer, **tick "Add python.exe to PATH"**
before pressing Install. It is a small checkbox at the bottom and it is the
one thing people miss; without it, step 6 says `python is not recognised`.

## 2. Install Node

<https://nodejs.org> — take the **LTS** button. Accept every default.

Node is what the app's screens are built with. You will never type `node`
yourself.

## 3. Get the code

The simplest route, no account and no git:

1. Go to the repository on GitHub and switch the branch dropdown (top left,
   usually says `main`) to **`claude/mushroom-app-continue-fy5f4m`**.
2. Green **Code** button → **Download ZIP**.
3. Save it, then **right-click the .zip → Extract All…** and extract to
   `C:\funga`.

You end up with a folder like `C:\funga\whats-that-mushroom-claude-mushroom-app-continue-fy5f4m`.
Rename it to `C:\funga\app` if you like — nothing depends on the name.

> **Extract it.** Windows will happily let you browse inside a .zip as
> though it were a folder, and then nothing can write to it. If step 6 fails
> with permission errors, this is why.

**If you expect to do this more than once,** install GitHub Desktop
(<https://desktop.github.com>) instead. It is a normal window with buttons:
*Clone*, then *Fetch origin* whenever you want the latest changes, with no
ZIP to re-download and no terminal.

## 4. Put the trained model in place

Only if you have `model.onnx` from a training run. Skip this and the app
still runs — it serves a stub whose answers are meaningless, which is the
right thing to look at first anyway.

Inside the folder from step 3, create `ml\runs\baseline\` if it is not
there, and copy in **all three** files from the run:

```
ml\runs\baseline\model.onnx           ~350 MB   the trained model
ml\runs\baseline\labels.json          tiny      which index is which species
ml\runs\baseline\calibration.json     tiny      the fitted confidence scale
```

**All three, not two.** `labels.json` is the only thing that turns the
model's answer — a number — into a species name, and it belongs to that
specific checkpoint. The app now **refuses to start** if the model is there
and `labels.json` is not, rather than deriving the order from the taxonomy
and quietly naming every species after the first gap as its neighbour. Two
files out of three used to look like it worked.

Without `calibration.json` it starts, says so, and reports every percentage
as uncalibrated — rule 4.

## 5. Open a terminal already pointing at the folder

This is the step that replaces knowing any commands.

1. Open the folder from step 3 in **File Explorer**, so you can see
   `README.md` and the `scripts` folder in it.
2. Click the **address bar** at the top (the strip showing
   `C:\funga\app`), so the path goes blue.
3. Type `powershell` over it and press **Enter**.

A blue window opens, already in that folder. That window is where the line
in step 6 goes.

## 6. The one line

Click into the blue window, paste this and press **Enter**:

```powershell
python scripts\try_it.py
```

Right-click pastes in PowerShell; Ctrl-V also works.

The first run takes a few minutes: it installs what is missing, starts the
API and the app's screens, and then prints a web address. Open that address
in your browser. It also prints a line like

```
244 species  |  model_loaded=True  calibrated=True  taxonomy_reviewed=False
```

which is the app telling you honestly what it is running. `model_loaded`
distinguishes the real classifier from the stub; `taxonomy_reviewed` stays
`False` until a mycologist has signed off the species data, and that is a
release blocker, not a detail.

**Press Ctrl-C in the blue window to stop everything.**

---

## When something goes wrong

| What you see | What it means |
| --- | --- |
| `python is not recognised` | Step 1's checkbox was missed. Re-run the Python installer, choose **Modify**, tick "Add python.exe to PATH". Then close and reopen the blue window. |
| `Node is not installed, or not on your PATH` | Step 2. Node's installer needs the terminal closed and reopened afterwards. |
| `A model is present ... but there is no labels.json` | Step 4 — copy all three files. This refusal is deliberate. |
| Permission or read-only errors | The ZIP was browsed rather than extracted. See step 3. |
| It installs for ages the first time | Expected. Several hundred megabytes of dependencies, once. |
| Something else | `.try_it_api.log` and `.try_it_web.log` appear in the folder and hold the real error. |

## What to do once it loads

The launcher prints this too, and it adapts to whether a model is loaded.
Briefly:

- Tick all six consent boxes. There is no accept-all, deliberately.
- With the stub: whatever it names is meaningless. Look at what happens
  *around* the name.
- With a trained model: the name is a real identification over 244 British
  species. Then photograph something that is **not** a mushroom — a chair, a
  pavement — and watch it decline. That refusal is a different one from
  "I'm not sure what this is", and the difference is deliberate.
- Either way, the verdict worth finding is **"I can't safely narrow this
  down"**: a lethal pair in play and the app refusing to choose between
  them. No competitor will ever show you that.
- Try the red cross, top right. That screen is hardcoded, works with no
  network, and sits above the consent gate.

## If you would rather not install anything at all

- `docs/walkthrough.html` is a recording of real responses from a running
  API — open it in a browser, no install, no Python.
- `python scripts\demo.py` walks eight scenes through the real safety layer
  in the blue window, in about thirty seconds. Needs step 1 only: no Node,
  no browser.
