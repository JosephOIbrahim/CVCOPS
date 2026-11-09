"""Minimal read-only parser for Houdini INDX (.hda/.hdalc) archives.
Usage: python3 -I hda_extract.py <file.hda> <out_dir>
Writes each leaf section to out_dir; gunzips *.gz sections. Never executes content."""
import sys, os, struct, gzip, re

def parse_indx(buf, base=0):
    """Return list of (name, abs_offset, size) for an INDX blob starting at buf[0:]."""
    if buf[:4] != b"INDX":
        return None
    pos = 4
    # header: int32 unknown, int32 unknown, int32 count  (big-endian)
    a, b, count = struct.unpack(">iii", buf[pos:pos + 12]); pos += 12
    entries = []
    for _ in range(count):
        (nlen,) = struct.unpack(">i", buf[pos:pos + 4]); pos += 4
        name = buf[pos:pos + nlen].decode("utf-8", "replace"); pos += nlen
        off, size, mtime = struct.unpack(">iii", buf[pos:pos + 12]); pos += 12
        entries.append((name, off, size))
    data_start = pos
    return [(n, data_start + o, s) for (n, o, s) in entries], data_start

def safe(name):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)[:120]

def walk(buf, out_dir, depth=0, prefix=""):
    parsed = parse_indx(buf)
    if not parsed:
        return
    entries, data_start = parsed
    for name, off, size in entries:
        blob = buf[off:off + size]
        label = prefix + safe(name)
        print("  " * depth + f"{name}  ({size} bytes)")
        if blob[:4] == b"INDX":
            walk(blob, out_dir, depth + 1, label + "__")
            continue
        path = os.path.join(out_dir, label)
        if name.endswith(".gz"):
            try:
                blob = gzip.decompress(blob); path = path[:-3]
            except Exception as e:
                print("  " * depth + f"   (gunzip failed: {e})")
        with open(path, "wb") as f:
            f.write(blob)

if __name__ == "__main__":
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    with open(src, "rb") as f:
        walk(f.read(), out)
