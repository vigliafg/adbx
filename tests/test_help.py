import pytest

from adbx.shell import help as shell_help


def test_every_command_has_a_topic():
    from adbx.shell.screens import COMMANDS

    for _label, topic_id in COMMANDS:
        assert topic_id in shell_help.TOPICS
        assert shell_help.TOPICS[topic_id].title


def test_every_link_points_to_a_topic():
    for topic in shell_help.TOPICS.values():
        for line in topic.lines:
            for match in shell_help.LINK_RE.finditer(line):
                assert match.group(2) in shell_help.TOPICS, match.group(2)


def test_wrap_respects_width_and_keeps_links():
    lines = shell_help.wrap("one two three [[four five|main_menu]] six", width=12)
    for line in lines:
        assert sum(len(run.text) for run in line) <= 12
    targets = [run.target for line in lines for run in line if run.target]
    assert targets == ["main_menu", "main_menu"]


def test_link_spans_merge_phrases():
    lines = shell_help.wrap_topic(shell_help.topic("help"))
    spans = shell_help.link_spans(lines)
    assert spans
    assert any(span.target == "main_menu" for span in spans)
    for span in spans:
        assert span.column + span.length <= shell_help.DEFAULT_WIDTH


@pytest.mark.parametrize("topic_id", sorted(shell_help.TOPICS))
def test_topic_is_short_and_renders(topic_id):
    lines = shell_help.wrap_topic(shell_help.topic(topic_id))
    assert lines
    assert len(lines) < 40
