"""Tests for the DepartmentLoader."""
import tempfile
from pathlib import Path

import pytest

from alterego.kernel.departments import DepartmentLoader, DepartmentSpec


@pytest.fixture
def departments_dir():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "engineering.yaml").write_text("""
name: engineering
description: Software engineering
capabilities: [github, docker, filesystem]
subscribes: [mission.created]
publishes: [pr.created]
roles: [architect, coder, reviewer]
""")
        (d / "research.yaml").write_text("""
name: research
description: Research
capabilities: [browser, llm.chat]
subscribes: [mission.created]
publishes: [research.report_ready]
roles: [researcher]
""")
        yield d


def test_load_all(departments_dir):
    loader = DepartmentLoader(departments_dir)
    depts = loader.load_all()
    assert len(depts) == 2
    names = {d.name for d in depts}
    assert names == {"engineering", "research"}


def test_get_by_name(departments_dir):
    loader = DepartmentLoader(departments_dir)
    loader.load_all()
    eng = loader.get("engineering")
    assert eng is not None
    assert eng.description == "Software engineering"
    assert "github" in eng.capabilities


def test_get_nonexistent(departments_dir):
    loader = DepartmentLoader(departments_dir)
    loader.load_all()
    assert loader.get("nonexistent") is None


def test_find_for_capability(departments_dir):
    loader = DepartmentLoader(departments_dir)
    loader.load_all()
    github_depts = loader.find_for_capability("github")
    assert len(github_depts) == 1
    assert github_depts[0].name == "engineering"

    llm_depts = loader.find_for_capability("llm.chat")
    assert len(llm_depts) == 1
    assert llm_depts[0].name == "research"


def test_describe(departments_dir):
    loader = DepartmentLoader(departments_dir)
    loader.load_all()
    desc = loader.describe()
    assert "engineering" in desc
    assert "research" in desc
    assert "github" in desc


def test_load_nonexistent_dir():
    loader = DepartmentLoader(Path("/nonexistent/path"))
    depts = loader.load_all()
    assert depts == []


def test_load_invalid_yaml(departments_dir):
    """Invalid YAML should not crash the loader."""
    (departments_dir / "broken.yaml").write_text("invalid: yaml: content: [")
    loader = DepartmentLoader(departments_dir)
    depts = loader.load_all()
    # Should still load the valid ones
    assert len(depts) == 2


def test_department_spec_defaults():
    spec = DepartmentSpec(name="test")
    assert spec.description == ""
    assert spec.capabilities == []
    assert spec.subscribes == []
    assert spec.publishes == []
    assert spec.roles == []
