

def test_load_dotenv_reads_values_and_skips_comments(tmp_path):
    from indiasearchbench.cli import load_dotenv

    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\n\nSERPER_API_KEY=abc123\nEXA_API_KEY=\"quoted\"\nEMPTY=\nnot a pair\n",
        encoding="utf-8",
    )
    assert load_dotenv(env_file) == {"SERPER_API_KEY": "abc123", "EXA_API_KEY": "quoted"}


def test_load_dotenv_missing_file_is_empty(tmp_path):
    from indiasearchbench.cli import load_dotenv

    assert load_dotenv(tmp_path / "nope.env") == {}
