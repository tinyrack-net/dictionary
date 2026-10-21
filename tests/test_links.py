import pytest

from tinydict.links import link_href, rewrite_bword_links


@pytest.mark.parametrize(
    "term, href",
    [
        ("glad", "glad"),
        ("early life check", "early%20life%20check"),
        ("and/or", "and%2For"),
        ("#MeToo", "%23MeToo"),
        ("w:h-dropping", "w%3Ah-dropping"),
        ("does it?", "does%20it%3F"),
        ("café", "caf%C3%A9"),
        ("Murphy's law", "Murphy%27s%20law"),
    ],
)
def test_link_href(term, href):
    assert link_href(term) == href


def test_rewrite_bword_links():
    defi = (
        '<a href="bword://glad">glad</a>, '
        "<a class=\"antonym\" href='bword://sad'>sad</a>, "
        '<a href="bword://&amp; seq.">&amp; seq.</a>, '
        '<a href="bword://Murphy\'s law" class="antonym">Murphy\'s law</a>, '
        '<a href="https://example.com/">web</a>'
    )
    assert rewrite_bword_links(defi) == (
        '<a href="glad">glad</a>, '
        "<a class=\"antonym\" href='sad'>sad</a>, "
        '<a href="%26%20seq.">&amp; seq.</a>, '
        '<a href="Murphy%27s%20law" class="antonym">Murphy\'s law</a>, '
        '<a href="https://example.com/">web</a>'
    )
