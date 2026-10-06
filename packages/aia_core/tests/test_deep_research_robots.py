"""robots.txt as AIA obeys it: RFC 9309, and never less strict than the standard library."""

from __future__ import annotations

from urllib.robotparser import RobotFileParser

import pytest

from aia_core.domain.deep_research.robots import (
    AGENT_TOKEN,
    ROBOTS_DISALLOWED,
    ROBOTS_UNAVAILABLE,
    RobotsPolicy,
    RobotsState,
    policy_for_response,
)

HOST = "https://stats.example"


def _allows(robots: str, path: str) -> bool:
    return RobotsPolicy.parse(robots).refusal(HOST + path) is None


def test_the_group_for_aias_token_is_chosen_over_the_wildcard() -> None:
    robots = (
        "User-agent: *\nDisallow: /\n\n"
        "User-agent: AIA-research/2.0\nDisallow: /soukrome/\n\n"
        "User-agent: OtherBot\nAllow: /\n"
    )
    assert _allows(robots, "/verejne/tabulka")
    assert not _allows(robots, "/soukrome/x")
    # Another agent's group never applies to AIA; the wildcard group does.
    assert not _allows("User-agent: OtherBot\nAllow: /\n\nUser-agent: *\nDisallow: /\n", "/a")
    assert _allows("User-agent: OtherBot\nDisallow: /\n", "/a")


def test_groups_for_the_same_agent_are_merged() -> None:
    robots = "User-agent: *\nDisallow: /a\n\nUser-agent: *\nDisallow: /b\n"
    assert not _allows(robots, "/a/1") and not _allows(robots, "/b/1") and _allows(robots, "/c")
    # The standard library drops the second wildcard group: /b would be allowed by it.
    stdlib = RobotFileParser()
    stdlib.parse(robots.splitlines())
    assert stdlib.can_fetch(AGENT_TOKEN, HOST + "/b/1")


def test_the_most_specific_rule_wins_and_allow_wins_a_tie() -> None:
    robots = "User-agent: *\nAllow: /\nDisallow: /private\n"
    assert not _allows(robots, "/private/report")
    # The standard library alone would allow it: the first match counts there.
    stdlib = RobotFileParser()
    stdlib.parse(robots.splitlines())
    assert stdlib.can_fetch(AGENT_TOKEN, HOST + "/private/report")
    assert _allows("User-agent: *\nAllow: /page\nDisallow: /page\n", "/page")
    # RFC 9309 lets the allow win a tie in either order; the standard library takes
    # the first, and AIA keeps the stricter answer.
    assert not _allows("User-agent: *\nDisallow: /page\nAllow: /page\n", "/page")


def test_wildcards_and_end_anchors() -> None:
    robots = "User-agent: *\nDisallow: /*.pdf$\nDisallow: /*?session=\n"
    assert not _allows(robots, "/data/report.pdf")
    assert _allows(robots, "/data/report.pdf.html")
    assert _allows(robots, "/search?q=x&session=1")
    assert not _allows(robots, "/list?session=abc")
    assert _allows(robots, "/list?page=2")


def test_paths_compare_after_percent_encoding_normalisation() -> None:
    robots = "User-agent: *\nDisallow: /výzkum\nDisallow: /a%3cb\n"
    assert not _allows(robots, "/v%C3%BDzkum/2025")
    assert not _allows(robots, "/výzkum/2025")
    assert not _allows(robots, "/a%3Cb")
    assert _allows(robots, "/a")
    assert not _allows("User-agent: *\nDisallow: /%7Euser\n", "/~user/home")


def test_where_the_standard_library_is_stricter_its_answer_stands() -> None:
    # RFC 9309 allows /public (the longer rule); the standard library's first match
    # refuses it. AIA requests nothing either reading forbids.
    robots = "User-agent: *\nDisallow: /\nAllow: /public\n"
    assert not _allows(robots, "/public/a")


def test_empty_rules_comments_and_unknown_lines() -> None:
    robots = "﻿# comment\nUser-agent: *  # all\nDisallow:\nSitemap: /s.xml\nNoise\n"
    assert _allows(robots, "/anything")
    assert _allows("", "/anything")
    assert _allows("Disallow: /\n", "/anything")  # a rule outside any group is ignored


def test_robots_txt_itself_is_always_allowed() -> None:
    assert RobotsPolicy.disallow_all("http_403").refusal(HOST + "/robots.txt") is None
    assert RobotsPolicy.parse("User-agent: *\nDisallow: /\n").refusal(HOST + "/robots.txt") is None


def test_crawl_delay_takes_the_longest_declared() -> None:
    policy = RobotsPolicy.parse(
        "User-agent: *\nCrawl-delay: 2.5\n\nUser-agent: AIA-research\nCrawl-delay: 4\n"
    )
    assert policy.crawl_delay_s == 4.0
    assert RobotsPolicy.parse("User-agent: *\nCrawl-delay: 1.5\n").crawl_delay_s == 1.5
    assert RobotsPolicy.parse("User-agent: *\nCrawl-delay: soon\n").crawl_delay_s is None
    assert RobotsPolicy.parse("User-agent: *\nDisallow: /x\n").crawl_delay_s is None


@pytest.mark.parametrize(
    ("status", "state", "refusal"),
    [
        (404, RobotsState.ALLOW_ALL, None),
        (410, RobotsState.ALLOW_ALL, None),
        (401, RobotsState.DISALLOW_ALL, ROBOTS_DISALLOWED),
        (403, RobotsState.DISALLOW_ALL, ROBOTS_DISALLOWED),
        (429, RobotsState.UNAVAILABLE, ROBOTS_UNAVAILABLE),
        (500, RobotsState.UNAVAILABLE, ROBOTS_UNAVAILABLE),
        (503, RobotsState.UNAVAILABLE, ROBOTS_UNAVAILABLE),
        (302, RobotsState.UNAVAILABLE, ROBOTS_UNAVAILABLE),
    ],
)
def test_an_answer_that_is_not_a_file_sets_the_conservative_policy(
    status: int, state: RobotsState, refusal: str | None
) -> None:
    policy = policy_for_response(status, b"User-agent: *\nAllow: /\n")
    assert policy.state is state and policy.detail == f"http_{status}"
    assert policy.refusal(HOST + "/a") == refusal


def test_a_file_is_read_up_to_its_cap() -> None:
    body = b"User-agent: *\nDisallow: /a\n" + b"#" * 600_000 + b"\nDisallow: /b\n"
    policy = policy_for_response(200, body)
    assert policy.state is RobotsState.RULES
    assert policy.refusal(HOST + "/a") == ROBOTS_DISALLOWED
    assert policy.refusal(HOST + "/b") is None  # beyond the cap, as RFC 9309 allows
