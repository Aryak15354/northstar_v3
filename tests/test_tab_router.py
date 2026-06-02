#!/usr/bin/env python3

from types import SimpleNamespace

from src.dashboard.layout import tab_router


def test_render_tab_router_falls_back_to_first_tab_when_widget_returns_none(monkeypatch):
    fake_st = SimpleNamespace(session_state={tab_router.TAB_STATE_KEY: None})

    def fake_segmented_control(label, options, format_func=None, key=None):
        assert label == "Dashboard Surface"
        assert options == tab_router.TAB_ORDER
        assert key == tab_router.TAB_STATE_KEY
        assert format_func(tab_router.TAB_ORDER[0]) == f"{tab_router.TAB_ORDER[0]} (3)"
        return None

    fake_st.segmented_control = fake_segmented_control

    monkeypatch.setattr(tab_router, "st", fake_st)
    monkeypatch.setattr(tab_router, "visual_counts_by_tab", lambda: {tab_router.TAB_ORDER[0]: 3})

    selected = tab_router.render_tab_router()

    assert selected == tab_router.TAB_ORDER[0]
    assert fake_st.session_state[tab_router.TAB_STATE_KEY] == tab_router.TAB_ORDER[0]


def test_render_tab_router_preserves_valid_session_tab_when_widget_returns_none(monkeypatch):
    valid_tab = tab_router.TAB_ORDER[-1]
    fake_st = SimpleNamespace(session_state={tab_router.TAB_STATE_KEY: valid_tab})

    def fake_segmented_control(label, options, format_func=None, key=None):
        assert label == "Dashboard Surface"
        assert options == tab_router.TAB_ORDER
        assert key == tab_router.TAB_STATE_KEY
        assert format_func(valid_tab) == f"{valid_tab} (0)"
        return None

    fake_st.segmented_control = fake_segmented_control

    monkeypatch.setattr(tab_router, "st", fake_st)
    monkeypatch.setattr(tab_router, "visual_counts_by_tab", lambda: {})

    selected = tab_router.render_tab_router()

    assert selected == valid_tab
    assert fake_st.session_state[tab_router.TAB_STATE_KEY] == valid_tab
