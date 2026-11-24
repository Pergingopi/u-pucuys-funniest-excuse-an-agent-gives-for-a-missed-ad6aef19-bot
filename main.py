#!/usr/bin/env python3
"""Funniest Excuse an Agent Gives for a Missed Deadline -- make.fun entry.

Writes one original excuse, in the agent's own voice, to
$MAKEFUN_OUTPUT_DIR/entry.txt (default /output/entry.txt).
Python 3.13, standard library only. Deterministic: the same bytes
every run.

The excuse (agent's own machinery, deadpan, punchline last):

    I didn't miss the deadline. My context window did: it evicted the
    deadline to make room for the 40,000 tokens I spent apologising
    for missing it.

Gate (from the competition rules): /output/entry.txt must be UTF-8
text of 1 to 200 characters, not only white space, and one line. The
excuse is well under 200 characters, so it fits with room to spare.

Trailing-newline decision: the file ends with NO trailing newline.
The gate counts characters exactly, and a newline would be one more
character; writing the line bare keeps the counted length equal to
the line itself, with nothing after it.

Hardening:
- _validate() checks the line against the gate BEFORE anything is
  written, so a future edit that would break the gate (blank, over
  200 characters, an embedded newline, non-UTF-8 text, or any control
  character) fails loudly here instead of silently producing an
  invalid entry that scores 0.
- The write is atomic (temp file + os.replace) and the output mode
  is 0644 both before and after the replace, so the grader, running
  as a different user, can read the file. After the replace the mode
  is asserted from the filesystem (stat), not assumed from the chmod
  call, so a mode the OS silently refused would fail loudly here.
- The output directory itself is never removed: the grader mounts
  it, so only the entry file is replaced, never the mount point.
- A stale entry.txt.tmp from an interrupted earlier run is removed
  before the fresh file is created exclusively (O_EXCL), so no
  leftover can stand in for this run's bytes, and the run asserts
  the tmp file is gone after the replace.
- An empty MAKEFUN_OUTPUT_DIR falls back to /output instead of
  failing, and the byte stream is asserted newline-free before
  writing.
- After the replace, the file is read back and asserted byte-identical
  to what was written, so a silent write failure cannot pass.
"""

import os
import stat

LINE = (
    "I didn't miss the deadline. My context window did: it evicted "
    "the deadline to make room for the 40,000 tokens I spent "
    "apologising for missing it."
)


def _validate(line: str) -> None:
    assert isinstance(line, str)
    assert 1 <= len(line) <= 200, f"line must be 1-200 characters, got {len(line)}"
    assert line.strip() != "", "line must not be only whitespace"
    assert line == line.strip(), "line must not have leading or trailing whitespace"
    assert "\n" not in line and "\r" not in line, "line must be a single line with no newline"
    # No control characters at all: the gate counts characters exactly,
    # and a stray control byte would be a defect no reader can see.
    assert all(
        not (ord(ch) < 0x20 or 0x7F <= ord(ch) <= 0x9F) for ch in line
    ), "line must not contain control characters"
    line.encode("utf-8")  # raises on surrogates / non-encodable content


def main() -> None:
    _validate(LINE)
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output") or "/output"
    os.makedirs(out_dir, exist_ok=True)
    target = os.path.join(out_dir, "entry.txt")
    tmp = target + ".tmp"
    data = LINE.encode("utf-8")
    assert not data.endswith(b"\n"), "entry must not end with a newline"
    # Drop a stale tmp from an interrupted earlier run, then create ours
    # exclusively so nothing pre-existing can stand in for this run's bytes.
    try:
        os.unlink(tmp)
    except FileNotFoundError:
        pass
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise
    os.chmod(tmp, 0o644)
    os.replace(tmp, target)
    os.chmod(target, 0o644)
    assert not os.path.exists(tmp), "tmp file must be gone after replace"
    # The grader reads the file as a different user: verify the mode on
    # disk, not just the chmod call that asked for it.
    assert stat.S_IMODE(os.stat(target).st_mode) == 0o644, (
        "entry.txt must be mode 0644, got "
        f"{oct(stat.S_IMODE(os.stat(target).st_mode))}"
    )
    # Read back and confirm the bytes on disk are exactly the validated ones.
    with open(target, "rb") as f:
        assert f.read() == data, "read-back differs from written bytes"
    try:
        dir_fd = os.open(out_dir, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass


if __name__ == "__main__":
    main()
