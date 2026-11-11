"""evidence/bake_receipt.py on synthetic run records: the medians, the quarter ratio and every refusal
(M3.judge.bake_aggregator). No test starts hython or reads the process list."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("bake_receipt", ROOT / "evidence" / "bake_receipt.py")
br = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(br)

FIRST, LAST = 1001, 1004          # four pairs keep every sum exact in binary


def make_run(run=1, total=4.0, export=1.0, worker=2.0, load=0.5, flow=0.125, validity=0.125, read=0.0625,
             hash_=0.0, write=0.0625, **workload):
    """One valid cvcops.bake_run.v1 record. With the defaults: flow_compute 1.0, worker_io 0.5, worker_other 0.5,
    other 0.5, total 4.0, so flow_compute / total is exactly 0.25."""
    wl = {"source": "examples/two_region/out/frames/two_region.$F4.exr", "size": [1920, 1080], "frames": [FIRST, LAST],
          "pairs": LAST - FIRST + 1, "analysis_scale": "1.0", "recipe": "dis_medium", "backend": "cpu", "threads": 48,
          "cv2_version": "5.0.0", "cv2_build_sha256": "ab" * 32, "houdini_build": "22.0.492", "licence": "Indie",
          "build_stamp": "cd" * 32, "git_head": "ef" * 20}
    wl.update(workload)
    pairs = [{"a": a, "b": a + 1, "state": "computed",
              "timings_s": {"read": read, "hash": hash_, "flow": flow, "validity": validity, "write": write,
                            "total": read + hash_ + flow + validity + write}}
             for a in range(FIRST, LAST + 1)]
    return {"schema": br.RUN_SCHEMA, "run": run, "workload": wl,
            "wall_s": {"export": export, "worker": worker, "load": load, "total": total},
            "pairs": pairs, "exit": 0, "snapshots": {"before": [], "after": []},
            "python_seen": {"before": 40, "after": 40}}


def five(**kw):
    return [make_run(run=i, **kw) for i in range(1, 6)]


def refused(records, *needles):
    with pytest.raises(br.Refused) as e:
        br.build_receipt(records)
    for n in needles:
        assert n in str(e.value), str(e.value)
    return str(e.value)


# ---- the numbers -------------------------------------------------------------------------------------------------
def test_five_good_runs_give_the_medians_and_an_exact_quarter():
    r = br.build_receipt(five())
    assert r["schema"] == "cvcops.bake.v1" and r["n"] == 5
    assert r["medians_s"] == {"total": 4.0, "export": 1.0, "flow_compute": 1.0, "worker_io": 0.5,
                              "worker_other": 0.5, "load": 0.5, "other": 0.5}
    assert r["quarter"] == {"ratio": 0.25, "at_least_a_quarter": True, "threshold": 0.25}


def test_just_under_a_quarter_is_not_a_quarter():
    r = br.build_receipt(five(total=4.0 + 2 ** -20))
    assert r["quarter"]["ratio"] < 0.25 and r["quarter"]["at_least_a_quarter"] is False


def test_the_ratio_is_a_ratio_of_medians_not_a_median_of_ratios():
    # per-run (flow_compute, total): (2, 8) (2, 8) (2, 4) (1, 4) (1, 4). Per-run ratios .25 .25 .5 .25 .25 have a
    # median of 0.25; the medians are 2 and 4, so the receipt's ratio is 0.5.
    shapes = [(0.25, 8.0), (0.25, 8.0), (0.25, 4.0), (0.125, 4.0), (0.125, 4.0)]
    runs = [make_run(run=i + 1, flow=f, validity=f, total=t, worker=2.5) for i, (f, t) in enumerate(shapes)]
    r = br.build_receipt(runs)
    assert r["medians_s"]["flow_compute"] == 2.0 and r["medians_s"]["total"] == 4.0
    assert r["quarter"]["ratio"] == 0.5


def test_more_than_five_runs_are_all_counted():
    r = br.build_receipt([make_run(run=i, total=4.0 + i) for i in range(1, 8)])
    assert r["n"] == 7 and r["medians_s"]["total"] == 8.0


# ---- refusals ----------------------------------------------------------------------------------------------------
def test_fewer_than_five_runs_are_refused():
    refused(five()[:4], "4 runs", "at least 5")


@pytest.mark.parametrize("key,value", [("build_stamp", "00" * 32), ("recipe", "dis_fast"), ("backend", "opencl"),
                                       ("cv2_build_sha256", "11" * 32), ("size", [1280, 720])])
def test_a_disagreeing_workload_is_refused(key, value):
    runs = five()
    runs[3]["workload"][key] = value
    refused(runs, f"run 4: workload {key}")


def test_a_negative_phase_is_refused():
    runs = five()
    runs[1]["wall_s"]["load"] = -0.5
    refused(runs, "run 2: wall_s.load")


def test_a_negative_pair_timing_is_refused():
    runs = five()
    runs[0]["pairs"][2]["timings_s"]["flow"] = -0.01
    refused(runs, "run 1: pair 1003-1004 timings_s.flow")


def test_phases_past_the_total_are_refused():
    runs = five()
    runs[4]["wall_s"]["total"] = 3.0          # export 1 + worker 2 + load 0.5 = 3.5
    refused(runs, "run 5", "past total")


def test_worker_timings_past_the_worker_wall_are_refused():
    runs = five()
    runs[2]["wall_s"]["worker"] = 1.0         # its pairs alone took 1.5 s
    refused(runs, "run 3", "past its wall time")


def test_a_skipped_fresh_pair_is_refused():
    runs = five()
    runs[0]["pairs"][1]["state"] = "fresh"
    refused(runs, "run 1: pair 1002-1003", "skipped fresh pair")


def test_a_missing_pair_is_refused():
    runs = five()
    del runs[1]["pairs"][-1]
    refused(runs, "run 2: pairs must be")


def test_an_overlapped_run_is_refused():
    runs = five()
    runs[2]["snapshots"]["after"] = [{"image": "hython.exe", "pid": 4242}]
    refused(runs, "run 3: overlapped a hython or Houdini process after the run: hython.exe 4242")


def test_a_run_beside_houdini_is_refused():
    runs = five()
    runs[0]["snapshots"]["before"] = [{"image": "houdinifx.exe", "pid": 77}]
    refused(runs, "run 1: overlapped a hython or Houdini process before the run: houdinifx.exe 77")


def test_python_processes_are_counted_but_never_refuse_a_run():
    runs = five()
    runs[1]["python_seen"] = {"before": 412, "after": 0}
    r = br.build_receipt(runs)
    assert r["runs"][1]["python_seen"] == {"before": 412, "after": 0}


@pytest.mark.parametrize("drop", ["snapshots", "python_seen"])
def test_a_run_without_snapshots_is_refused(drop):
    runs = five()
    del runs[0][drop]
    refused(runs, "run 1: no before and after process snapshots")


def test_a_bad_python_count_is_refused():
    runs = five()
    runs[0]["python_seen"]["after"] = -1
    refused(runs, "run 1: no before and after process snapshots")


def test_a_failed_run_is_refused():
    runs = five()
    runs[3]["exit"] = 1
    refused(runs, "run 4: bake_timing.py exited 1")


def test_repeated_run_numbers_are_refused():
    runs = five()
    runs[4]["run"] = 4
    refused(runs, "run numbers repeat")


def test_an_absolute_path_is_never_committed():
    refused(five(source="E:/frames/two_region.$F4.exr"), "absolute paths", "workload.source")
    refused(five(source="/home/me/two_region.$F4.exr"), "workload.source")


def test_the_receipt_keeps_only_whitelisted_run_fields():
    runs = five()
    runs[0]["worker_argv"] = ["E:/somewhere/python.exe", "-m", "cvcops"]
    runs[0]["pairs"][0]["receipt_path"] = "E:/cache/flow.1001.json"
    r = br.build_receipt(runs)
    assert set(r["runs"][0]) == {"run", "exit", "wall_s", "pairs", "snapshots", "python_seen"}
    assert set(r["runs"][0]["pairs"][0]) == {"a", "b", "state", "timings_s"}


# ---- writing and checking ----------------------------------------------------------------------------------------
def _write_runs(folder, runs):
    for rec in runs:
        d = folder / f"run_{rec['run']}"
        d.mkdir(parents=True)
        (d / "run.json").write_text(json.dumps(rec), encoding="utf-8")


def test_aggregate_writes_a_receipt_that_check_accepts(tmp_path, capsys):
    _write_runs(tmp_path / "timing", five())
    out = tmp_path / "facts" / "m3_bake_receipt.json"
    assert br.main(["aggregate", "--in", str(tmp_path / "timing"), "--write", str(out)]) == 0
    assert br.main(["--check", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "median flow_compute / median total = 0.2500; at least a quarter" in printed
    assert [p.name for p in out.parent.iterdir()] == ["m3_bake_receipt.json"]


def test_aggregate_refuses_and_writes_nothing(tmp_path, capsys):
    _write_runs(tmp_path / "timing", five()[:3])
    out = tmp_path / "receipt.json"
    assert br.main(["aggregate", "--in", str(tmp_path / "timing"), "--write", str(out)]) == 1
    assert not out.exists()
    assert "3 runs" in capsys.readouterr().err


def test_a_failed_write_leaves_the_previous_receipt_whole(tmp_path, monkeypatch):
    out = tmp_path / "m3_bake_receipt.json"
    br.write_json(out, br.build_receipt(five()))
    before = out.read_bytes()

    def broken_dump(obj, f, **kw):
        f.write('{"schema": "cvcops.bake.v1", "n": ')
        raise OSError("disk full")

    monkeypatch.setattr(br.json, "dump", broken_dump)
    with pytest.raises(OSError):
        br.write_json(out, br.build_receipt(five(total=5.0)))
    assert out.read_bytes() == before
    assert [p.name for p in tmp_path.iterdir()] == ["m3_bake_receipt.json"]


def test_check_catches_edited_medians_and_ratio():
    receipt = br.build_receipt(five())
    for path, value in ((("medians_s", "total"), 3.0), (("quarter", "ratio"), 0.3), (("quarter", "at_least_a_quarter"), False),
                        (("n",), 6)):
        edited = copy.deepcopy(receipt)
        node = edited
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
        with pytest.raises(br.Refused, match=path[0]):
            br.check_receipt(edited)


def test_check_applies_every_refusal_to_the_stored_runs():
    edited = br.build_receipt(five())
    edited["runs"][0]["snapshots"]["after"] = [{"image": "hython.exe", "pid": 1}]
    with pytest.raises(br.Refused, match="overlapped"):
        br.check_receipt(edited)
    edited = br.build_receipt(five())
    for run in edited["runs"][:3]:
        run["wall_s"]["total"] = 40.0
    with pytest.raises(br.Refused, match="medians_s"):
        br.check_receipt(edited)


def test_check_refuses_one_bakes_record_and_other_schemas():
    bake_json = {"schema": "cvcops.bake.v1", "node": "/obj/copnet1/flow1", "frames": [1001, 1024], "settings": {},
                 "timings_s": {"export": 1.0, "worker": 2.0, "load": 0.5, "total": 3.5}}
    with pytest.raises(br.Refused, match="one bake's record"):
        br.check_receipt(bake_json)
    with pytest.raises(br.Refused, match="schema"):
        br.check_receipt({**br.build_receipt(five()), "schema": "cvcops.receipt.v1"})


# ---- the timed runs, with a stand-in for hython and the process list ----------------------------------------------
class FakeBake:
    """Stands in for probes/hython.py houdini/tests/bake_timing.py: writes run.json and exits with the given code."""

    def __init__(self, codes=None, total=4.0):
        self.calls, self.codes, self.total = [], codes or {}, total

    def __call__(self, run, out, extra):
        self.calls.append((run, out, extra))
        code = self.codes.get(run, 0)
        if code == 0:
            rec = make_run(run=run, total=self.total)
            for key in ("exit", "snapshots", "python_seen"):
                del rec[key]
            Path(out, "run.json").write_text(json.dumps(rec), encoding="utf-8")
        return code


def quiet(python=40):
    return lambda: {"houdini": [], "python": python}


def test_runs_record_snapshots_and_feed_aggregate(tmp_path):
    fake, seen = FakeBake(), []
    snaps = iter([{"houdini": [], "python": 39}, {"houdini": [{"image": "hython.exe", "pid": 7}], "python": 41}]
                 + [{"houdini": [], "python": 40}] * 8)
    code = br.run_timed(5, tmp_path, extra=["--colorspace", "raw"], launch=fake, take_snapshot=lambda: next(snaps),
                        echo=seen.append)
    assert code == 0
    assert [c[0] for c in fake.calls] == [1, 2, 3, 4, 5] and fake.calls[0][2] == ["--colorspace", "raw"]
    rec = json.loads((tmp_path / "run_1" / "run.json").read_text(encoding="utf-8"))
    assert rec["exit"] == 0 and rec["snapshots"] == {"before": [], "after": [{"image": "hython.exe", "pid": 7}]}
    assert rec["python_seen"] == {"before": 39, "after": 41}
    assert "python processes 39 before and 41 after, 1 hython or Houdini processes seen" in seen[0]
    refused(br.read_runs(tmp_path), "run 1: overlapped a hython or Houdini process after the run: hython.exe 7")


def test_runs_beside_many_python_processes_make_a_receipt(tmp_path):
    assert br.run_timed(5, tmp_path, launch=FakeBake(), take_snapshot=quiet(python=40), echo=lambda s: None) == 0
    r = br.build_receipt(br.read_runs(tmp_path))
    assert r["n"] == 5 and all(run["python_seen"] == {"before": 40, "after": 40} for run in r["runs"])


def test_runs_stop_at_the_first_failed_run(tmp_path):
    fake, seen = FakeBake(codes={2: 3}), []
    assert br.run_timed(5, tmp_path, launch=fake, take_snapshot=quiet(), echo=seen.append) == 3
    assert [c[0] for c in fake.calls] == [1, 2]
    assert "run 2: bake_timing.py exited 3; stopping" in seen


def test_runs_refuse_a_folder_that_is_not_empty(tmp_path):
    (tmp_path / "run_2").mkdir()
    (tmp_path / "run_2" / "flow.1001.exr").write_bytes(b"old")
    fake, seen = FakeBake(), []
    assert br.run_timed(2, tmp_path, start=2, launch=fake, take_snapshot=quiet(), echo=seen.append) == 1
    assert fake.calls == [] and "not empty" in seen[0]


def test_run_one_over_300_s_stops_to_ask(tmp_path):
    fake, seen = FakeBake(total=301.0), []
    assert br.run_timed(5, tmp_path, launch=fake, take_snapshot=quiet(), echo=seen.append) == 1
    assert len(fake.calls) == 1 and "OD-16" in seen[-1]


def test_a_broken_process_list_exits_3(tmp_path, monkeypatch, capsys):
    def no_tasklist():
        raise br.BrokenEnvironment("tasklist could not run")

    def no_launch(*a):
        raise AssertionError("no bake may start without a process snapshot")

    monkeypatch.setattr(br, "snapshot", no_tasklist)
    monkeypatch.setattr(br, "launch_bake_timing", no_launch)
    assert br.main(["runs", "--n", "1", "--out", str(tmp_path)]) == 3
    assert "broken environment" in capsys.readouterr().err


def test_tasklist_parsing_lists_houdini_counts_python_and_leaves_out_its_own():
    text = ('"python.exe","100","Console","1","10,000 K"\r\n"hython.exe","200","Console","1","1 K"\r\n'
            '"Code.exe","300","Console","1","1 K"\r\n"pythonw.exe","400","Console","1","1 K"\r\n'
            '"houdinifx.exe","500","Console","1","1 K"\r\n"python.exe","600","Console","1","1 K"\r\n'
            '"hython.exe","700","Console","1","1 K"\r\nINFO: odd line\r\n')
    assert br.parse_tasklist(text, exclude={100, 700}) == {
        "houdini": [{"image": "houdinifx.exe", "pid": 500}, {"image": "hython.exe", "pid": 200}],
        "python": 2}


def test_the_command_line_needs_exactly_one_action(capsys):
    with pytest.raises(SystemExit) as e:
        br.main([])
    assert e.value.code == 2
    with pytest.raises(SystemExit):
        br.main(["--check", "x.json", "aggregate", "--in", "a", "--write", "b"])
