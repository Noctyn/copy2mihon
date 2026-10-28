"""CLI-level smoke tests covering argument wiring."""

from copy2mihon import cli
from copy2mihon.cli import build_parser, convert_command, export_command, merge_command


def _capture_pipeline(monkeypatch):
    calls = {}

    def fake_pipeline(**kwargs):
        calls.update(kwargs)

    monkeypatch.setattr(cli, "_run_export_pipeline", fake_pipeline)
    monkeypatch.setattr(cli, "prompt_for_token", lambda *args, **kwargs: "token")
    return calls


def test_merge_command_wires_backup_file(monkeypatch, tmp_path):
    backup = tmp_path / "existing.tachibk"
    backup.write_bytes(b"")

    calls = _capture_pipeline(monkeypatch)
    args = build_parser().parse_args(["merge", "-b", str(backup), "--no-include-history"])

    merge_command(args)

    assert calls["existing_backup"] == str(backup)
    assert calls["include_history"] is False
    assert calls["output"] == f"{backup.stem}_merged.tachibk"


def test_export_command_respects_no_export_json(monkeypatch, tmp_path):
    calls = _capture_pipeline(monkeypatch)
    args = build_parser().parse_args(
        ["export", "-o", str(tmp_path / "out.tachibk"), "--no-export-json"]
    )

    export_command(args)

    assert calls["export_json_flag"] is False


def test_convert_command_without_output_defaults_next_to_input(tmp_path):
    src = tmp_path / "input.json"
    src.write_text('[{"comic": {"path_word": "x", "name": "X"}}]', encoding="utf-8")

    args = build_parser().parse_args(["convert", str(src)])
    convert_command(args)

    assert (tmp_path / "input.tachibk").exists()
