from src.intelligence.news_brain.news_brain import NewsBrain


def test_news_brain_imports() -> None:
    assert NewsBrain.__name__ == "NewsBrain"
