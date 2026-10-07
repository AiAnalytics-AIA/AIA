"""robots.txt as AIA obeys it: RFC 9309, and never less strict than the first-match reading.

Both readings are AIA's own, so every answer here is the same on every interpreter
(Python 3.13.14 replaced ``urllib.robotparser``'s algorithm in a patch release).
"""

from __future__ import annotations

import urllib.robotparser

import pytest

from aia_core.domain.deep_research.robots import (
    AGENT_TOKEN,
    MAX_ROBOTS_SITEMAPS,
    ROBOTS_DISALLOWED,
    ROBOTS_UNAVAILABLE,
    RobotsPolicy,
    RobotsState,
    _FirstMatchReading,
    policy_for_response,
    sitemap_lines,
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
    # The first-match reading drops the second wildcard group: /b would be allowed by it.
    assert _FirstMatchReading.parse(robots.splitlines()).allows(AGENT_TOKEN, HOST + "/b/1")


def test_the_most_specific_rule_wins_and_allow_wins_a_tie() -> None:
    robots = "User-agent: *\nAllow: /\nDisallow: /private\n"
    assert not _allows(robots, "/private/report")
    # The first-match reading alone would allow it: the first match counts there.
    first_match = _FirstMatchReading.parse(robots.splitlines())
    assert first_match.allows(AGENT_TOKEN, HOST + "/private/report")
    assert _allows("User-agent: *\nAllow: /page\nDisallow: /page\n", "/page")
    # RFC 9309 lets the allow win a tie in either order; the first-match reading takes
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


def test_where_the_first_match_reading_is_stricter_its_answer_stands() -> None:
    # RFC 9309 allows /public (the longer rule); the first-match reading refuses it.
    # AIA requests nothing either reading forbids.
    robots = "User-agent: *\nDisallow: /\nAllow: /public\n"
    assert not _allows(robots, "/public/a")
    # A group whose agent is a substring of AIA's token applies there; RFC 9309 reads
    # only the wildcard group here.
    robots = "User-agent: research\nDisallow: /\n\nUser-agent: *\nAllow: /\n"
    assert not _allows(robots, "/a")


def test_the_decision_does_not_ask_the_standard_librarys_parser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Python 3.13.14 (gh-138907) gave urllib.robotparser RFC 9309's algorithm in a
    # patch release, so asking it made AIA's answer depend on the interpreter.
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("urllib.robotparser was asked")

    for name in ("parse", "can_fetch", "crawl_delay"):
        monkeypatch.setattr(urllib.robotparser.RobotFileParser, name, refuse)
    policy = RobotsPolicy.parse("User-agent: *\nDisallow: /\nAllow: /public\nCrawl-delay: 3\n")
    assert policy.refusal(HOST + "/public/a") == ROBOTS_DISALLOWED
    assert policy.crawl_delay_s == 3.0


def test_a_path_starting_with_two_slashes_is_compared_as_written() -> None:
    # Python 3.13 (gh-85110) re-joins a "//x" path as "////x"; the first-match reading
    # must not, or this rule would stop matching on 3.13.
    robots = "User-agent: research\nDisallow: //x\n"
    assert not _FirstMatchReading.parse(robots.splitlines()).allows(AGENT_TOKEN, HOST + "//x/y")
    assert not _allows(robots, "//x/y")
    assert _allows(robots, "/x/y")


def test_a_file_the_old_parser_could_not_read_is_read() -> None:
    # Python 3.12's robotparser raised ValueError out of the whole parse on both lines.
    policy = policy_for_response(
        200, "User-agent: *\nCrawl-delay: ²\nDisallow: //[y\nDisallow: /x\n".encode()
    )
    assert policy.state is RobotsState.RULES
    assert policy.refusal(HOST + "/x/1") == ROBOTS_DISALLOWED
    assert policy.refusal(HOST + "/a") is None
    assert policy.crawl_delay_s is None


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


def test_sitemap_lines_are_kept_for_every_agent_in_order_and_deduplicated() -> None:
    robots = (
        "Sitemap: https://stats.example/sitemap-index.xml\n"
        "User-agent: OtherBot\nDisallow: /\n"
        "sitemap:https://stats.example/news.xml.gz # the news\n"
        "Sitemap: https://stats.example/sitemap-index.xml\n"
        "Sitemap: ftp://stats.example/old.xml\n"
        "Sitemap: /relative.xml\n"
        "Sitemap:\n"
        "User-agent: *\nDisallow: /x\n"
        "Sitemap: https://cdn.example/stats/sitemap.xml\n"
    )
    policy = RobotsPolicy.parse(robots)
    assert policy.sitemaps == (
        "https://stats.example/sitemap-index.xml",
        "https://stats.example/news.xml.gz",
        "https://cdn.example/stats/sitemap.xml",  # another host: the reader decides
    )
    assert sitemap_lines("Sitemap: https://a.example/" + "x" * 3000) == ()
    many = "".join(f"Sitemap: https://a.example/s{i}.xml\n" for i in range(80))
    assert len(sitemap_lines(many)) == MAX_ROBOTS_SITEMAPS


def test_a_policy_not_read_from_a_file_declares_no_sitemaps() -> None:
    assert policy_for_response(403, b"Sitemap: https://a.example/s.xml").sitemaps == ()
    assert policy_for_response(503, b"Sitemap: https://a.example/s.xml").sitemaps == ()
    assert policy_for_response(404, b"").sitemaps == ()
    assert policy_for_response(200, b"Sitemap: https://a.example/s.xml").sitemaps == (
        "https://a.example/s.xml",
    )
