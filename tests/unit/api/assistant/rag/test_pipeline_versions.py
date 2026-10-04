"""Unit tests for pipeline.py's git version lookup, run against throwaway repositories."""

import subprocess

from api.assistant.rag.pipeline import git_version


def _git(repo, *args):
    """Run one git command in repo with a fixed identity; CI runners have none configured."""
    subprocess.run(  # noqa: S603 - fixed git argv plus a pytest tmp_path
        [  # noqa: S607 - fixed argv, no shell
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "-C",
            str(repo),
            *args,
        ],
        check=True,
        capture_output=True,
    )


def _tagged_repo(repo):
    """Make repo a git repository with one commit tagged wave-1."""
    _git(repo, "init")
    (repo / "manifest.json").write_text("[]", encoding="utf-8")
    _git(repo, "add", "manifest.json")
    _git(repo, "commit", "-m", "wave 1")
    _git(repo, "tag", "wave-1")


class TestGitVersion:
    """git_version names the commit a repository root is at, or None when it cannot."""

    def test_names_the_tag_of_a_clean_checkout(self, tmp_path):
        """
        GIVEN a repository whose only commit is tagged wave-1
        WHEN git_version runs on its root
        THEN it returns "wave-1"
        """
        # GIVEN
        _tagged_repo(tmp_path)

        # WHEN/THEN
        assert git_version(tmp_path) == "wave-1"

    def test_marks_uncommitted_changes_as_dirty(self, tmp_path):
        """
        GIVEN the tagged repository with an uncommitted edit to a tracked file
        WHEN git_version runs
        THEN the version carries the -dirty suffix
        """
        # GIVEN
        _tagged_repo(tmp_path)
        (tmp_path / "manifest.json").write_text('[{"path": "wave-1/new.txt"}]', encoding="utf-8")

        # WHEN/THEN
        assert git_version(tmp_path) == "wave-1-dirty"

    def test_a_folder_inside_another_repository_has_no_version(self, tmp_path):
        """
        GIVEN a plain folder inside a repository, the way the corpus folder sits inside
            the BeCoMe checkout before anyone runs git init there
        WHEN git_version runs on the folder
        THEN it returns None instead of describing the enclosing repository
        """
        # GIVEN
        _tagged_repo(tmp_path)
        corpus = tmp_path / "supplementary" / "assistant" / "corpus"
        corpus.mkdir(parents=True)

        # WHEN/THEN
        assert git_version(corpus) is None

    def test_no_git_on_path_means_no_version(self, tmp_path, monkeypatch):
        """
        GIVEN a repository, but no git executable on PATH
        WHEN git_version runs
        THEN it returns None rather than failing the build
        """
        # GIVEN
        _tagged_repo(tmp_path)
        monkeypatch.setattr("api.assistant.rag.pipeline.shutil.which", lambda _name: None)

        # WHEN/THEN
        assert git_version(tmp_path) is None
