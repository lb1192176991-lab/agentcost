"""Guard the published distribution name against the README and the packaging.

`agentcost` on PyPI belongs to an unrelated project (author Kushagra Agrawal,
github.com/agentcost-ai/agentcost-sdk), so `pip install agentcost` installs
someone else's package. This distribution ships as `agentcost-py`.

The guard reads `[project] name` from pyproject instead of hardcoding it, so the
next rename fails here rather than in a user's terminal.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"
PYPROJECT = REPO_ROOT / "pyproject.toml"
ACTION_YML = REPO_ROOT / "action.yml"
PRE_COMMIT_HOOKS = REPO_ROOT / ".pre-commit-hooks.yaml"

# The short name is owned by a third party on PyPI. Any install of the bare
# short name is wrong. The negative lookahead is essential: without it
# "pip install agentcost" is a substring of the correct "pip install agentcost-py"
# and this guard would reject the line it exists to protect. All whitespace is
# [ \t] rather than \s so the pattern cannot cross a line boundary and match a
# different line's `agentcost` (e.g. a step named "Run agentcost").
SHORT_NAME_INSTALL = re.compile(
    r"pip(?:3)?[ \t]+install[ \t]+(?:[^\s=!<>]+[ \t]+)*agentcost(?![\w-])"
)

# A from-source install is legitimate and must not be flagged.
SOURCE_INSTALL = re.compile(r"install\s+[^\s]*git\+https?://", re.IGNORECASE)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def project_name() -> str:
    """Extract `[project] name` without tomllib (CI runs Python 3.10)."""
    text = read(PYPROJECT)
    match = re.search(r'^\[project\]\s*$(.*?)(?=^\[|\Z)', text, re.MULTILINE | re.DOTALL)
    assert match, "no [project] table in pyproject.toml"
    name = re.search(r'^\s*name\s*=\s*["\']([^"\']+)["\']', match.group(1), re.MULTILINE)
    assert name, "no [project] name in pyproject.toml"
    return name.group(1)


# `pip install <target>`; the remainder of the line is parsed token by token so
# the two install forms stay distinguishable: a registry name is a bare
# distribution, a VCS/URL install carries a scheme and a URL.
INSTALL_LINE = re.compile(r"pip(?:3)?\s+install\s+(?P<rest>\S.*)$", re.MULTILINE)

# A VCS install names no distribution on the command line -- pip reads the name
# out of the cloned project's metadata. `git+https://`, `git+ssh://`, `hg+`,
# `svn+`, ... all land here, and so does any `<scheme>+<url>` form.
#
# The scheme is matched on `+`, not on a list of version-control names: `+` is
# not a legal character in a distribution name (PEP 508 names are letters,
# digits, `.`, `-` and `_`), so its presence in the target cannot be a registry
# name. Treating a leading `git` as if it were the distribution is what made this
# guard compare 'git' with 'agentcost-py'.
VCS_INSTALL = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*\+")

# Long pip options that consume the following token, so it is an option value
# and not the install target.
OPTIONS_WITH_VALUE = frozenset({
    "--abi", "--cert", "--client-cert", "--config-settings", "--constraint",
    "--editable", "--find-links", "--fingerprint", "--hash", "--implementation",
    "--index-url", "--install-option", "--keyring-provider", "--log",
    "--no-binary", "--only-binary", "--platform", "--prefix", "--proxy",
    "--python-version", "--requirement", "--retries", "--root", "--src",
    "--target", "--timeout", "--trusted-host", "--upgrade-strategy", "--user",
})


def install_target(readme: str) -> str:
    """The first thing after `pip install`, skipping pip options and their values."""
    match = INSTALL_LINE.search(readme)
    assert match, "README has no `pip install <target>` line"
    tokens = match.group("rest").split()
    skip_value = False
    for token in tokens:
        if skip_value:
            skip_value = False
            continue
        if token in OPTIONS_WITH_VALUE:
            skip_value = True
            continue
        if token.startswith("-"):
            continue
        return token.rstrip("\\")
    raise AssertionError(f"`pip install {' '.join(tokens)}` names no install target")


def install_name(readme: str) -> str | None:
    """The distribution name the README tells people to install.

    Returns the bare name for a registry install, and `None` for a VCS/URL
    install: there is no distribution name on that command line to compare, so
    callers must check the URL with `install_url` instead.
    """
    target = install_target(readme)
    return None if VCS_INSTALL.match(target) or "://" in target else target


def install_url(readme: str) -> str:
    """The clone target of a VCS install, e.g. `git+https://host/owner/repo.git`."""
    target = install_target(readme)
    assert VCS_INSTALL.match(target) or "://" in target, (
        f"install target {target!r} is not a VCS or URL install"
    )
    return target


@pytest.fixture(scope="module")
def readme() -> str:
    return read(README)


def project_homepage() -> str:
    """`[project.urls] Homepage` — the authoritative repo location.

    Derived rather than hardcoded so a fork or a rename updates the guard on its
    own; a stale `yunaremaia/agentcost` literal would itself be a lie.
    """
    text = read(PYPROJECT)
    match = re.search(r'^\s*Homepage\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
    assert match, "no [project.urls] Homepage in pyproject.toml"
    return match.group(1).rstrip("/")


def install_name_matches_pyproject(readme: str) -> None:
    """(d) The install line must resolve to this distribution.

    Two shapes, both checked:

    * registry install -- the name on the command line must be `[project] name`,
      exactly as strict as before;
    * VCS install -- there is no distribution name to compare, so the clone URL
      must point at this repository (from `[project.urls] Homepage`). A pasted
      URL for the wrong project fails here.
    """
    name = install_name(readme)
    if name is not None:
        assert name == project_name(), (
            f"README installs {name!r} but [project] name is {project_name()!r}"
        )
        return
    url = install_url(readme)
    homepage = project_homepage()
    assert homepage in url, (
        f"README installs from {url!r}, which is not this repository "
        f"({homepage})"
    )


def test_readme_install_name_matches_pyproject(readme: str) -> None:
    """(d) The install line and [project] name must be the same distribution."""
    install_name_matches_pyproject(readme)


@pytest.mark.parametrize(
    "line",
    [
        "pip install git+https://github.com/yunaremaia/agentcost.git",
        "pip install git+ssh://git@github.com/yunaremaia/agentcost.git",
        "pip3 install hg+https://example.invalid/agentcost",
        "pip install svn+https://example.invalid/agentcost",
        "pip install bzr+https://example.invalid/agentcost",
        "pip install -e git+https://github.com/yunaremaia/agentcost.git",
    ],
)
def test_vcs_install_is_recognised_as_a_url_not_a_name(line: str) -> None:
    """A `<scheme>+<url>` target is a clone URL, never the distribution `git`.

    Locked with a synthetic README so the behaviour is tested without depending
    on the real file's install line.
    """
    synthetic = f"# agentcost\n\n## Install\n\n```bash\n{line}\n```\n"
    assert install_name(synthetic) is None, (
        f"{line!r} was read as the distribution "
        f"{install_name(synthetic)!r} instead of a VCS install"
    )
    assert install_url(synthetic) == line.split()[-1]


def test_registry_install_still_returns_the_bare_name() -> None:
    """The registry form keeps the strict name comparison, not the URL branch."""
    synthetic = "# agentcost\n\n## Install\n\n```bash\npip install agentcost-py\n```\n"
    assert install_name(synthetic) == "agentcost-py"
    with pytest.raises(AssertionError):
        install_url(synthetic)


def test_readme_does_not_advertise_the_conflicting_short_name(readme: str) -> None:
    """(b) `pip install agentcost` installs a different author's package."""
    offenders = [
        line
        for line in readme.splitlines()
        if SHORT_NAME_INSTALL.search(line) and not SOURCE_INSTALL.search(line)
    ]
    assert not offenders, (
        "README still tells users to install the short name `agentcost`, which "
        f"belongs to an unrelated project on PyPI: {offenders}"
    )


def test_readme_documents_the_name_conflict(readme: str) -> None:
    """(c) Say plainly which name belongs to whom, so nobody falls in again."""
    paragraphs = [p.strip() for p in readme.split("\n\n") if p.strip()]
    notes = [
        p
        for p in paragraphs
        if re.search(r"`agentcost`", p)
        and re.search(r"another|different|unrelated|not this", p, re.IGNORECASE)
    ]
    assert notes, (
        "README must explain that the short PyPI name `agentcost` belongs to "
        "another project and that this tool is installed as "
        f"`{project_name()}`"
    )


def test_composite_action_installs_the_distribution(readme: str) -> None:
    """action.yml runs at install time for anyone using the repo as an Action."""
    action = read(ACTION_YML)
    installed = re.findall(r"pip(?:3)?\s+install\s+([A-Za-z0-9._-]+)", action)
    assert installed, "action.yml no longer installs agentcost from PyPI"
    assert all(name == project_name() for name in installed), (
        f"action.yml must install {project_name()!r}, found {installed}"
    )
    assert not SHORT_NAME_INSTALL.search(action)


def test_pre_commit_hook_installs_the_distribution() -> None:
    """`additional_dependencies` is handed straight to pip by pre-commit."""
    hooks = read(PRE_COMMIT_HOOKS)
    block = re.search(
        r"^\s*additional_dependencies:\s*$(.*?)(?=^\S|\Z)",
        hooks,
        re.MULTILINE | re.DOTALL,
    )
    assert block, "no additional_dependencies in .pre-commit-hooks.yaml"
    # Only the requirements under additional_dependencies; `- id:` is a hook id.
    deps = re.findall(r"^\s*-\s*[\"']?([A-Za-z0-9._-]+)", block.group(1), re.MULTILINE)
    assert deps, "additional_dependencies block is empty"
    assert all(
        re.split(r"[<>=!\[ ]", dep)[0] == project_name() for dep in deps
    ), f"pre-commit hook must depend on {project_name()!r}, found {deps}"


def test_only_the_distribution_name_changed() -> None:
    """The importable package, the CLI entry point and the repo name are unchanged."""
    pyproject = read(PYPROJECT)
    assert '[project.scripts]\nagentcost = "agentcost.cli:cli"' in pyproject
    assert 'include = ["agentcost*"]' in pyproject
    assert project_name() != "agentcost", (
        "the distribution must not be published under the conflicting short name"
    )


def test_version_flag_resolves_the_distribution() -> None:
    """`version_option(package_name=...)` is a distribution lookup, not a module one.

    Click resolves it via importlib.metadata.version(); when it does not match an
    installed distribution Click 8.5 falls back to scanning distributions for a
    top-level module of that name and raises if several provide it. Keeping this
    string in sync with [project] name is what prevents that.
    """
    cli = read(REPO_ROOT / "src" / "agentcost" / "cli.py")
    names = re.findall(r'package_name=["\']([^"\']+)["\']', cli)
    assert names, "version_option no longer declares an explicit package_name"
    assert all(name == project_name() for name in names), (
        f"version_option package_name must be the distribution {project_name()!r}, "
        f"found {names}"
    )


def test_no_pypi_badge_while_unpublished(readme: str) -> None:
    """A badge for a package that is not on PyPI renders 'not found'."""
    assert "img.shields.io/pypi" not in readme, (
        "no PyPI badge until the package is actually published"
    )
