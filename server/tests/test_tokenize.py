from server.services.tokenize import build_match_query, tokenize_for_bm25


def test_cjk_runs_become_bigrams():
    assert tokenize_for_bm25("连接池") == "连接 接池"


def test_single_cjk_char_kept():
    assert tokenize_for_bm25("池") == "池"


def test_latin_words_lowercased_and_kept_whole():
    assert tokenize_for_bm25("HikariCP Redis") == "hikaricp redis"


def test_mixed_cjk_latin_paths_and_numbers():
    tokens = tokenize_for_bm25("查看 /data/logs/app.log 里的 ERROR 行")
    assert "/data/logs/app.log" in tokens.split()
    assert "error" in tokens.split()
    assert "查看" in tokens.split()


def test_punctuation_breaks_runs():
    tokens = tokenize_for_bm25("内存，泄漏").split()
    assert tokens == ["内存", "泄漏"]  # comma prevents a cross-punctuation bigram


def test_match_query_is_or_of_quoted_tokens():
    query = build_match_query("Redis 内存")
    assert query == '"redis" OR "内存"'


def test_match_query_dedupes_and_caps_tokens():
    query = build_match_query("池 池 池", max_tokens=2)
    assert query == '"池"'


def test_match_query_empty_input():
    assert build_match_query("！！！") == ""
