# An atomic model save (#71)

Written 2026-11-15 for M14, before the change. Issue #71 (D3, M6-34): "If the service stops
between the two file writes, the new model keeps the old revision number undetected. Done
when an interrupted save leaves either the old or the new model and revision, with a test."

## How a save works today

`ithax.service.commit.replace_in_order` saves `model.json` and then `project.json` (which
holds `model_revision`):
1. It writes both files' new bytes to synced temporary files beside them.
2. It renames the temporary files into place, in that order.

A rename that raises `OSError` puts back every file already renamed. A process that ends
between the two renames (a kill, a power cut, an `os._exit`) runs no clean-up, and leaves
the new model with the old revision. Nothing detects it later.

The data import saves its file and then `data/index.json` through the same function, with
the same gap.

## Options

1. **One file.** Keep the revision inside `model.json`. That changes the model format (rule
   5) and the project layout. Not taken.
2. **A checksum in `project.json`.** Save the model's SHA-256 beside the revision and refuse a
   mismatch on reading. That detects the gap but does not repair it: the old model is gone,
   so the project stays broken. Not taken.
3. **A commit record (redo journal).** Once every temporary file is written and synced, write
   one small record beside them that names each temporary and its target, atomically. That
   write is the commit point. Then do the renames and remove the record. Whoever next uses
   the folder and finds a record finishes its renames: each temporary still present is
   renamed onto its target, the folder is synced, and the record is removed. Without a
   record, the temporary files are not a commit, and the folder holds the old files. This
   is the redo-log pattern (Gray and Reuter, *Transaction Processing*, ch. 9; SQLite's
   rollback and WAL journals use the same "the journal is the commit" rule). Taken.

## Details

- **The record.** `.ithax-commit.json` in the folder of the files. Its content is
  `{"renames": [[temporary, target], ...]}`, with names relative to that folder. It is written
  with `ithax.files.atomic_write` (synced, renamed, folder synced). Every file of one commit
  sits in that folder; a change across folders is refused as a programming error.
- **When it is replayed.** On every use of a project folder: the project list, `folder(pid)`
  before every model, data or run use, and opening. It was first planned for the first use
  only; the review of PR #182 changed that, so a replay that fails is tried again rather than
  the folder admitted. Every commit and every replay holds its folder's lock for the whole
  of it, from writing or reading the record to removing it (second review of PR #182). A
  replay therefore never removes a record a later save wrote. The service is the only writer,
  so a lock in the process is enough.
- **A rename that fails** (`OSError`) after the record puts nothing back (review of PR
  #182). A roll-back has its own unsafe step: a stop part-way through it pairs the old model
  with the new revision. The record and the temporaries stay, the write is answered E186
  ("recorded"), and the next use finishes it. A replay that fails refuses the project with
  E186 until it can be finished. A target that is a folder, which no rename can replace, is
  refused before the record.
- **Left behind by a crash before the record.** The temporary files stay. They are named for
  the process and thread (`.<name>.<pid>.<thread>.tmp`), so they never collide with a later
  save, and they are not part of the model. Removing them on replay is not needed for
  correctness.

## Test

A child process runs `replace_in_order` with `os.replace` patched to call `os._exit` after the
first rename, which leaves the folder as a real crash would. The parent then checks:
- after the record was written, a replay gives the new model and revision, and no record is
  left;
- with the child stopped before the record, the folder keeps the old files.

The service-level test does the same through the model store and reads the project back
with `GET` model.
