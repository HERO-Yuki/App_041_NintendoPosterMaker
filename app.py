"""
App_041 NintendoPosterMaker
Nintendo Switch ゲーム布教まとめ画像（最大10本紹介）自動生成 Web アプリ
"""

# ── Standard Library ───────────────────────────────────────
import html
import io
import os
import datetime
import urllib.parse
from collections import deque
from functools import lru_cache

# ── Third Party ────────────────────────────────────────────
import requests
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from streamlit_sortables import sort_items


# ═══════════════════════════════════════════════════════════
#  固定定数
# ═══════════════════════════════════════════════════════════

# ── IGDB プラットフォーム ID ──────────────────────────────
# Switch 2 の ID は IGDB 正式登録後に追記する
IGDB_PLATFORM_IDS: list[int] = [130]   # 130 = Nintendo Switch

# ── キャンバス仕様（3 モード）────────────────────────────
CANVAS_SPECS: dict[str, dict] = {
    "horizontal": {"w": 1920, "h": 1080, "cols": 2},
    "vertical":   {"w": 1080, "h": 1920, "cols": 1},
    "square":     {"w": 1080, "h": 1080, "cols": 2},
}

# ── グリッド ──────────────────────────────────────────────
MARGIN    = 4
MAX_GAMES = 10
HEADER_H  = 88
FOOTER_H  = 36

# ── カバーアート ──────────────────────────────────────────
# ボックスアートモード: カード高さの 67%（≈2:3 比）を幅に
BOXART_RATIO = 0.67
BOXART_W_MIN = 100
BOXART_W_MAX = 220
# スクリーンショットモード: 固定幅（横長）
SCREENSHOT_W = 380

# ── カード構造 ────────────────────────────────────────────
CENTER_DIV_W      = 20
ROW_DIV_H         = 6
TEXT_PAD          = 12
ROW_GAP           = 6
TITLE_MAX_H_RATIO = 0.22
TITLE_BOX_MIN_H   = 36
ACCENT_LINE_H     = 4

# ── Metacritic バッジ ─────────────────────────────────────
MC_BADGE_PAD  = 8
MC_BADGE_EDGE = 10
MC_GREEN  = (54,  161, 69)    # score >= 75
MC_YELLOW = (255, 181, 13)    # score 50–74
MC_RED    = (215, 7,   47)    # score < 50

# ── タイポグラフィ ────────────────────────────────────────
HEADER_FONT_PT  = 52
TITLE_V_PAD     = 8
TITLE_FONT_PT   = 28
TITLE_MIN_PT    = 16
REVIEW_FONT_PT  = 26
REVIEW_MIN_PT   = 11
MC_FONT_PT      = 22
SLOT_PH_FONT_PT = 28
WM_FONT_PT      = 22

_actual_header_h: int = HEADER_H

# ── キャッシュ設定 ────────────────────────────────────────
_CACHE_TTL         = 3600
_CACHE_MAX_SEARCH  = 100
_CACHE_MAX_DETAILS = 200
_CACHE_MAX_IMAGES  = 50
_TOKEN_TTL         = 86_400 * 7   # 7日（IGDB トークン有効期限は 60 日）

FONT_FILENAME = "NotoSansCJKjp-Bold.otf"
FONT_URLS = [
    "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/Japanese/NotoSansCJKjp-Bold.otf",
    "https://cdn.jsdelivr.net/gh/googlefonts/noto-cjk/Sans/OTF/Japanese/NotoSansCJKjp-Bold.otf",
]

APP_NAME = "NintendoPosterMaker"
APP_URL  = "https://nintendo-poster-maker.streamlit.app"

_PRIMARY_COLOR = "#E4000F"
_NIN_BG        = "#1a1a2e"
_NIN_BG2       = "#16213e"

_FILENAME_INVALID = set('\\/: *?"<>|\t\n\r')

_X_BUTTON_ICON_HTML = """
<div style="text-align:center;margin:0 0 20px;">
  <a href="https://x.com/Yuki_HERO44" target="_blank" rel="noopener noreferrer" class="x-btn">
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="white">
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.747l7.73-8.835L1.254 2.25H8.08l4.258 5.629 5.906-5.629Zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
    </svg>
    @Yuki_HERO44
  </a>
</div>
"""

_OFUSE_BUTTON_HTML = """
<div style="text-align:center;margin:0 0 20px;">
  <a href="https://ofuse.me/d57de631" target="_blank" rel="noopener noreferrer" class="ofuse-btn">
    OFUSE
  </a>
</div>
"""

_GLOBAL_CSS = """
<style>
div[data-testid='stColumn'] > div[data-testid='stVerticalBlock'] { gap: 2px; }
html, body { overflow-x: hidden !important; }
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none !important; }
section[data-testid="stMain"] { margin-left: 0 !important; }
[data-testid="stMainBlockContainer"] { padding-bottom: 64px; }

.x-btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  min-width: 160px; background: #000; color: #fff !important;
  border: 1px solid #333; border-radius: 6px; padding: 6px 14px;
  font-size: 0.85rem; font-weight: bold; text-decoration: none !important;
  white-space: nowrap; transition: background 0.2s ease, border-color 0.2s ease;
}
.x-btn:hover { background: #1a1a1a; border-color: #666; color: #fff !important; }

.ofuse-btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  min-width: 160px; background: #2882A7; color: #fff !important;
  border: 1px solid #2882A7; border-radius: 6px; padding: 6px 14px;
  font-size: 0.85rem; font-weight: bold; text-decoration: none !important;
  white-space: nowrap; transition: opacity 0.2s ease;
}
.ofuse-btn:hover { opacity: 0.8; color: #fff !important; }

div[data-testid="stButton"] > button { white-space: nowrap !important; }

.npm-copyright {
  background: #000; color: #fff; text-align: center; font-size: 0.75rem;
  padding: 14px 20px; margin: 8px calc(-50vw + 50%) 0; width: 100vw;
}

@media (max-width: 768px) {
  [data-testid="stHorizontalBlock"]:has([data-testid="stVerticalBlockBorderWrapper"]) {
    flex-direction: column !important;
  }
  [data-testid="stHorizontalBlock"]:has(.footer-sep) {
    flex-direction: column !important; align-items: stretch !important;
  }
  .footer-sep {
    border-left: none !important; border-top: 1px solid #444 !important;
    width: 100% !important; height: 1px !important; margin: 0.5rem 0 !important;
  }
  [data-testid="stHorizontalBlock"]:has(.footer-sep) .x-btn,
  [data-testid="stHorizontalBlock"]:has(.footer-sep) .ofuse-btn {
    width: 72% !important; max-width: 280px !important;
  }
  [data-testid="stDialog"] [data-testid="stHorizontalBlock"] { flex-direction: column !important; }
  #npm-sticky-bar > div { padding: 0 12px !important; gap: 8px !important; }
  #npm-sticky-bar-progress { width: 90px !important; }
  #npm-sticky-bar-label { font-size: 0.65rem !important; }
  #npm-sticky-bar-btn { padding: 8px 12px !important; font-size: 0.8rem !important; }
  .npm-copyright { margin: 8px -1rem 0 !important; width: calc(100% + 2rem) !important; }
}

[data-testid="stHorizontalBlock"]:has([data-testid="stVerticalBlockBorderWrapper"]) {
  align-items: stretch !important;
}
[data-testid="stHorizontalBlock"]:has([data-testid="stVerticalBlockBorderWrapper"])
  > [data-testid="column"] {
  display: flex !important; flex-direction: column !important;
}
[data-testid="stHorizontalBlock"]:has([data-testid="stVerticalBlockBorderWrapper"])
  > [data-testid="column"] > div {
  flex: 1 !important; display: flex !important; flex-direction: column !important; height: 100% !important;
}
[data-testid="stHorizontalBlock"]:has([data-testid="stVerticalBlockBorderWrapper"])
  [data-testid="stVerticalBlockBorderWrapper"] {
  flex: 1 !important; height: 100% !important;
}
[data-testid="stHorizontalBlock"]:has([data-testid="stVerticalBlockBorderWrapper"])
  [data-testid="stVerticalBlockBorderWrapper"] > div[data-testid="stVerticalBlock"] {
  height: 100% !important; display: flex !important; flex-direction: column !important;
}
</style>
"""


# ═══════════════════════════════════════════════════════════
#  i18n
# ═══════════════════════════════════════════════════════════

TRANSLATIONS: dict[str, dict[str, str]] = {
    "ja": {
        # ヘッダー設定
        "heading_toggle":       "全体見出し",
        "heading_toggle_help":  "OFF にするとポスター上部の見出し帯が非表示になります",
        "heading_placeholder":  "25文字以内",
        "heading_default":      "2026年 神ゲー10選【Switch】",
        "heading_help":         "ポスター上部に表示されるタイトルです。空欄にすると帯のみ残ります。",
        "heading_none_cap":     "見出しなし",
        # ゲーム数ポップオーバー
        "num_games_popover":    "ゲーム数",
        "num_games_label":      "ゲーム数",
        "num_games_help":       "8本: カードが大きめ / 10本: カードが小さめ",
        # キャンバスモード
        "canvas_mode_label":    "出力サイズ",
        "canvas_horizontal":    "横長 1920×1080（X・PC向け）",
        "canvas_vertical":      "縦長 1080×1920（ストーリーズ向け）",
        "canvas_square":        "正方形 1080×1080（Instagram向け）",
        # デザイン設定
        "design_popover":       "デザイン設定",
        "theme_label":          "テーマ",
        "cover_mode_label":     "カバー画像スタイル",
        "cover_boxart":         "ボックスアート（縦長）",
        "cover_screenshot":     "スクリーンショット（横長）",
        "bg_style_label":       "背景スタイル",
        "bg_style_blur":        "ぼかし",
        "bg_style_solid":       "単色",
        "blur_label":           "ぼかし強度",
        "blur_help":            "数値が大きいほどぼかしが強くなります",
        "show_metacritic_label":"Metacriticスコアを表示",
        # スロットエリア
        "slots_header":         "ゲームスロット",
        "slots_count_prefix":   "登録数",
        "sort_btn":             "並び替え",
        "sort_done_btn":        "並び替え完了",
        "clear_all_btn":        "全クリア",
        "sort_drag_info":       "ドラッグして順序を変更し、完了したら「並び替え完了」を押してください。",
        "empty_slot_card":      "スロット {n:02d}",
        # 生成エリア
        "empty_slots_info":     "現在 **{filled}** 本登録済みです。未入力の枠 {n} 個は「空欄カード」として出力されます。",
        "generate_btn":         "ポスターを生成する",
        "regenerate_btn":       "再生成する",
        "download_btn":         "PNG でダウンロード",
        "preview_caption":      "プレビュー（実際はフル解像度で出力）",
        "toast_done":           "ポスターが完成しました。",
        # 生成ステータス
        "status_title":         "ポスターを生成しています...",
        "status_fetch":         "IGDB からゲーム画像を取得しています（{n} 本 / {total} スロット）...",
        "status_compose":       "画像を合成しています...",
        "status_encode":        "PNG ファイルに書き出しています...",
        "status_error":         "生成に失敗しました",
        # 編集ダイアログ
        "slot_caption":         "スロット {n:02d}",
        "reselect_caption":     "現在の選択: {title}　／　新しいゲームを検索してください",
        "search_ph":            "タイトル（日英）または IGDB ゲームID を入力して Enter",
        "search_help":          "IGDB ゲームID（数字）を直接入力することもできます。",
        "search_btn":           "検索",
        "warn_empty_query":     "キーワードを入力してください。",
        "warn_id_notfound":     "ゲームID {id} の情報が取得できませんでした。IDが正しいか確認してください。",
        "warn_notfound":        "該当するゲームが見つかりませんでした。別のキーワードを試してください。",
        "spin_gameid":          "ゲームID {id} のデータを取得しています...",
        "spin_search":          "「{q}」を検索しています...",
        "spin_details":         "「{name}」のデータを取得しています...",
        "confirm_game_btn":     "このゲームに決定",
        "back_to_search_btn":   "検索に戻る",
        "back_to_edit_btn":     "編集に戻る",
        "close_btn":            "閉じる",
        "cancel_btn":           "キャンセル",
        "review_label":         "レビュー文",
        "review_help":          "ポスターに約4行分の文章が収まります。超える場合はフォントサイズが自動縮小されます。",
        "save_btn":             "保存して閉じる",
        "dlg_clear_btn":        "クリア",
        "char_counter_tmpl":    "{n} / {max} 文字",
        "char_counter_suffix":  "文字",
        "over_limit_err":       "{max} 文字を超えています。文字数を減らしてから保存してください。",
        "metacritic_label":     "Metacritic",
        "no_metacritic":        "スコアなし",
        # スロットカード
        "edit_btn":             "編集",
        "empty_slot_sort":      "空きスロット {n:02d}",
        # 全クリアダイアログ
        "clear_all_warning":    "登録されているすべてのゲームを削除します。この操作は取り消せません。",
        "clear_all_confirm":    "すべて削除する",
        # クイック追加
        "quick_add_header":     "ゲームを追加",
        "quick_add_btn":        "追加",
        "slots_full_warn":      "すべてのスロットが埋まっています。スロットを編集するか、全クリアしてください。",
        "duplicate_warn":       "このゲームはすでに登録されています。",
        "added_toast":          "スロット {n} に追加しました",
        # フッター
        "ofuse_header":         "開発者を応援する",
        "author_section":       "開発者をフォローする",
        "disclaimer_unofficial":"本アプリは非公式のファンメイドツールです。",
        "disclaimer_no_relation":"Nintendo とは直接的な関わりはありません。",
        "feedback_header":      "フィードバック",
        "feedback_body":        "バグ報告や機能のご要望はこちら",
        "feedback_btn":         "要望・バグ報告フォーム",
        "tos_expander":         "利用規約・免責事項",
        # スティッキーバー
        "sticky_count":         "{filled} / {num} 本",
        # 言語トグル
        "lang_toggle":          "EN",
        # X シェア
        "share_header":         "作ったポスターをシェアしよう",
        "share_info":           "Xの投稿画面が開いたら、保存したポスター画像を添付して投稿してください。",
        "share_btn":            "X でシェアする",
        "share_tweet_text":     "NintendoPosterMakerで推しゲーのポスターを作りました！Switchのおすすめゲームをまとめた画像を自動生成できるツールです。ぜひ試してみて",
        "share_hashtags":       "Nintendo,NintendoSwitch,NintendoPosterMaker",
    },
    "en": {
        # Header settings
        "heading_toggle":       "Poster Title",
        "heading_toggle_help":  "Turn OFF to hide the title bar at the top of the poster.",
        "heading_placeholder":  "Up to 25 characters",
        "heading_default":      "Top 10 Switch Games of 2026",
        "heading_help":         "Large text shown at the top of the poster. Leave blank to generate without title text.",
        "heading_none_cap":     "No title",
        # Games count popover
        "num_games_popover":    "# Games",
        "num_games_label":      "# of Games",
        "num_games_help":       "8 games: larger cards / 10 games: smaller cards",
        # Canvas mode
        "canvas_mode_label":    "Output Size",
        "canvas_horizontal":    "Horizontal 1920×1080 (X / PC)",
        "canvas_vertical":      "Vertical 1080×1920 (Stories)",
        "canvas_square":        "Square 1080×1080 (Instagram)",
        # Design settings
        "design_popover":       "Design",
        "theme_label":          "Theme",
        "cover_mode_label":     "Cover Image Style",
        "cover_boxart":         "Box Art (vertical)",
        "cover_screenshot":     "Screenshot (landscape)",
        "bg_style_label":       "Background",
        "bg_style_blur":        "Blur",
        "bg_style_solid":       "Solid",
        "blur_label":           "Blur Intensity",
        "blur_help":            "Higher value = stronger blur",
        "show_metacritic_label":"Show Metacritic Score",
        # Slot area
        "slots_header":         "Game Slots",
        "slots_count_prefix":   "Registered",
        "sort_btn":             "Reorder",
        "sort_done_btn":        "Done Reordering",
        "clear_all_btn":        "Clear All",
        "sort_drag_info":       'Drag to reorder, then press "Done Reordering".',
        "empty_slot_card":      "SLOT {n:02d}",
        # Generate area
        "empty_slots_info":     "**{filled}** game(s) registered. {n} empty slot(s) will appear as blank cards.",
        "generate_btn":         "Generate Poster",
        "regenerate_btn":       "Regenerate",
        "download_btn":         "Download PNG",
        "preview_caption":      "Preview (actual output is full resolution)",
        "toast_done":           "Poster ready! Use the download button to save.",
        # Generation status
        "status_title":         "Generating poster...",
        "status_fetch":         "Fetching game images from IGDB ({n} / {total} slots)...",
        "status_compose":       "Compositing canvas...",
        "status_encode":        "Encoding PNG...",
        "status_error":         "Generation failed",
        # Edit dialog
        "slot_caption":         "Slot {n:02d}",
        "reselect_caption":     "Current: {title} — Search to select a different game",
        "search_ph":            "Title or IGDB game ID — press Enter",
        "search_help":          "You can also enter an IGDB game ID (number) directly.",
        "search_btn":           "Search",
        "warn_empty_query":     "Please enter a keyword.",
        "warn_id_notfound":     "Could not find game info for ID {id}. Please verify the ID.",
        "warn_notfound":        "No games found. Try a different keyword.",
        "spin_gameid":          "Fetching data for game ID {id}...",
        "spin_search":          'Searching for "{q}"...',
        "spin_details":         'Fetching data for "{name}"...',
        "confirm_game_btn":     "Select This Game",
        "back_to_search_btn":   "Back to Search",
        "back_to_edit_btn":     "Back to Edit",
        "close_btn":            "Close",
        "cancel_btn":           "Cancel",
        "review_label":         "Review",
        "review_help":          "About 4 lines fit on the poster. Font auto-shrinks if text is too long.",
        "save_btn":             "Save & Close",
        "dlg_clear_btn":        "Clear",
        "char_counter_tmpl":    "{n} / {max} chars",
        "char_counter_suffix":  "chars",
        "over_limit_err":       "Over {max} characters. Please shorten the text before saving.",
        "metacritic_label":     "Metacritic",
        "no_metacritic":        "No score",
        # Slot card
        "edit_btn":             "Edit",
        "empty_slot_sort":      "Empty Slot {n:02d}",
        # Clear all dialog
        "clear_all_warning":    "This will remove all registered games. This cannot be undone.",
        "clear_all_confirm":    "Delete All",
        # Quick add
        "quick_add_header":     "Add Games",
        "quick_add_btn":        "Add",
        "slots_full_warn":      "All slots are full. Edit a slot or clear all to start over.",
        "duplicate_warn":       "This game is already registered.",
        "added_toast":          "Added to Slot {n}",
        # Footer
        "ofuse_header":         "Support the developer",
        "author_section":       "Follow the developer",
        "disclaimer_unofficial":"This is an unofficial fan-made tool.",
        "disclaimer_no_relation":"It has no affiliation with Nintendo.",
        "feedback_header":      "Feedback",
        "feedback_body":        "Bug reports and feature requests welcome",
        "feedback_btn":         "Send Feedback",
        "tos_expander":         "Terms of Use & Disclaimer",
        # Sticky bar
        "sticky_count":         "{filled} / {num}",
        # Language toggle
        "lang_toggle":          "日本語",
        # X share
        "share_header":         "Share Your Poster!",
        "share_info":           "When X opens, attach the downloaded poster image to complete your post!",
        "share_btn":            "Share on X",
        "share_tweet_text":     "I made a game recommendation poster with NintendoPosterMaker! A tool that auto-generates summary images of your favorite Switch games. Check it out",
        "share_hashtags":       "Nintendo,NintendoSwitch,NintendoPosterMaker",
    },
}


def t(key: str, **kwargs) -> str:
    """現在の言語設定でキーに対応する文字列を返す。"""
    lang = st.session_state.get("lang", "ja")
    text = TRANSLATIONS.get(lang, TRANSLATIONS["ja"]).get(key) \
           or TRANSLATIONS["ja"].get(key, key)
    return text.format(**kwargs) if kwargs else text


# ═══════════════════════════════════════════════════════════
#  スティッキーボトムバー
# ═══════════════════════════════════════════════════════════

def _render_sticky_bar(filled: int, num_games: int, already_generated: bool) -> None:
    btn_label  = t("regenerate_btn") if already_generated else t("generate_btn")
    btn_icon   = "refresh"           if already_generated else "palette"
    pct        = int(filled / num_games * 100) if num_games > 0 else 0
    btn_bg     = "#555"          if filled == 0 else _PRIMARY_COLOR
    btn_color  = "#999"          if filled == 0 else "#fff"
    btn_cursor = "not-allowed"   if filled == 0 else "pointer"
    disabled   = 'disabled=""'   if filled == 0 else ""
    onclick    = "" if filled == 0 else (
        "var u=new URL(window.location.href);"
        "u.searchParams.set('_sg',Date.now());"
        "window.location.href=u.toString();"
    )
    st.markdown(
        f"""
<div id="npm-sticky-bar" style="
  position:fixed;bottom:0;left:0;right:0;z-index:9999;
  background:{_NIN_BG};border-top:2px solid {_NIN_BG2};
  padding:8px 0 10px;box-shadow:0 -2px 12px rgba(0,0,0,.5);
  display:flex;justify-content:center;
  opacity:1;transition:opacity 0.4s ease;
">
  <div style="display:inline-flex;align-items:center;gap:16px;padding:0 40px;">
    <div id="npm-sticky-bar-progress" style="width:120px;flex-shrink:0;">
      <div id="npm-sticky-bar-label" style="font-size:0.7rem;color:#aaa;margin-bottom:3px;white-space:nowrap;">
        {t("sticky_count", filled=filled, num=num_games)}
      </div>
      <div style="background:{_NIN_BG2};border-radius:4px;height:6px;overflow:hidden;">
        <div style="background:{_PRIMARY_COLOR};width:{pct}%;height:100%;
                    border-radius:4px;transition:width .3s;"></div>
      </div>
    </div>
    <button id="npm-sticky-bar-btn" {disabled} onclick="{onclick}"
      style="display:inline-flex;align-items:center;gap:6px;
             background:{btn_bg};color:{btn_color};border:none;
             border-radius:6px;padding:9px 22px;font-size:0.9rem;
             font-weight:bold;cursor:{btn_cursor};white-space:nowrap;
             transition:opacity .2s;font-family:inherit;"
      onmouseover="if(!this.disabled)this.style.opacity='.8'"
      onmouseout="this.style.opacity='1'"
    >
      <span style="font-family:'Material Symbols Rounded';font-size:1.15rem;
                   font-variation-settings:'FILL' 1,'wght' 400,'GRAD' 0,'opsz' 24;
                   line-height:1;vertical-align:middle;">{btn_icon}</span>
      {btn_label}
    </button>
  </div>
</div>
<link rel="stylesheet"
  href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200">
""",
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════
#  ユーティリティ
# ═══════════════════════════════════════════════════════════

def _safe_filename(title: str) -> str:
    safe = "".join("_" if c in _FILENAME_INVALID else c for c in title.strip())
    safe = safe.strip("_")
    return safe[:20] or "poster"


# ═══════════════════════════════════════════════════════════
#  IGDB API
# ═══════════════════════════════════════════════════════════

def _check_secrets() -> bool:
    """IGDB 認証情報が Streamlit Secrets に設定されているか確認する。"""
    try:
        _ = st.secrets["IGDB_CLIENT_ID"]
        _ = st.secrets["IGDB_CLIENT_SECRET"]
        return True
    except (KeyError, FileNotFoundError):
        return False


@st.cache_data(ttl=_TOKEN_TTL)
def _get_igdb_token(client_id: str, client_secret: str) -> str:
    """Twitch OAuth2 経由で IGDB アクセストークンを取得する。7日間キャッシュ。"""
    resp = requests.post(
        "https://id.twitch.tv/oauth2/token",
        params={
            "client_id":     client_id,
            "client_secret": client_secret,
            "grant_type":    "client_credentials",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _igdb_headers() -> dict:
    cid = st.secrets["IGDB_CLIENT_ID"]
    csc = st.secrets["IGDB_CLIENT_SECRET"]
    token = _get_igdb_token(cid, csc)
    return {"Client-ID": cid, "Authorization": f"Bearer {token}"}


def igdb_image_url(image_id: str, size: str = "cover_big_2x") -> str:
    """IGDB 画像 ID から CDN URL を生成する。"""
    if not image_id:
        return ""
    return f"https://images.igdb.com/igdb/image/upload/t_{size}/{image_id}.jpg"


def _parse_igdb_game(g: dict) -> dict:
    """IGDB レスポンスの1ゲームエントリを内部 dict に変換する。"""
    cover_id  = g.get("cover", {}).get("image_id", "") if g.get("cover") else ""
    shots     = g.get("screenshots", [])
    shot_id   = shots[0].get("image_id", "") if shots else ""
    mc_raw    = g.get("aggregated_rating")
    return {
        "game_id":             g["id"],
        "title":               g.get("name", ""),
        "cover_image_id":      cover_id,
        "screenshot_image_id": shot_id,
        "metacritic":          int(mc_raw) if mc_raw else None,
        "review":              "",
    }


@st.cache_data(ttl=_CACHE_TTL, max_entries=_CACHE_MAX_SEARCH)
def search_igdb(query: str) -> list[dict]:
    """IGDB でゲームをキーワード検索する。
    英語タイトルは通常の search エンドポイント、
    日本語等の非 ASCII を含む場合は alternative_names も検索してマージする。
    """
    platform_str = "(" + ",".join(str(p) for p in IGDB_PLATFORM_IDS) + ")"
    headers = _igdb_headers()
    results: dict[int, dict] = {}   # game_id → parsed dict（重複排除用）

    # ── 1. 通常検索（英語タイトル向け full-text search）────────────────
    body = (
        "fields id, name, cover.image_id, screenshots.image_id, "
        "aggregated_rating, aggregated_rating_count; "
        f'search "{query}"; '
        f"where platforms = {platform_str}; "
        "limit 10;"
    )
    try:
        resp = requests.post(
            "https://api.igdb.com/v4/games",
            headers=headers,
            data=body,
            timeout=10,
        )
        resp.raise_for_status()
        for g in resp.json():
            results[g["id"]] = _parse_igdb_game(g)
    except Exception:
        pass

    # ── 2. 日本語など非 ASCII を含む場合 → alternative_names も検索 ────
    if any(ord(c) > 127 for c in query):
        alt_body = f'fields game; where name ~ *"{query}"*; limit 20;'
        try:
            alt_resp = requests.post(
                "https://api.igdb.com/v4/alternative_names",
                headers=headers,
                data=alt_body,
                timeout=10,
            )
            alt_resp.raise_for_status()
            # まだ results に入っていないゲーム ID を収集
            new_ids = [
                item["game"]
                for item in alt_resp.json()
                if "game" in item and item["game"] not in results
            ]
            if new_ids:
                ids_str = "(" + ",".join(str(i) for i in new_ids[:10]) + ")"
                games_body = (
                    "fields id, name, cover.image_id, screenshots.image_id, "
                    "aggregated_rating, aggregated_rating_count; "
                    f"where id = {ids_str} & platforms = {platform_str}; "
                    "limit 10;"
                )
                games_resp = requests.post(
                    "https://api.igdb.com/v4/games",
                    headers=headers,
                    data=games_body,
                    timeout=10,
                )
                games_resp.raise_for_status()
                for g in games_resp.json():
                    if g["id"] not in results:
                        results[g["id"]] = _parse_igdb_game(g)
        except Exception:
            pass

    return list(results.values())


@st.cache_data(ttl=_CACHE_TTL, max_entries=_CACHE_MAX_DETAILS)
def get_game_details(game_id: int) -> dict:
    """IGDB ゲーム ID からゲーム詳細を取得する。"""
    body = (
        "fields id, name, cover.image_id, screenshots.image_id, "
        "aggregated_rating, aggregated_rating_count; "
        f"where id = {game_id};"
    )
    try:
        resp = requests.post(
            "https://api.igdb.com/v4/games",
            headers=_igdb_headers(),
            data=body,
            timeout=10,
        )
        resp.raise_for_status()
        games = resp.json()
        return _parse_igdb_game(games[0]) if games else {}
    except Exception:
        return {}


# ═══════════════════════════════════════════════════════════
#  フォント管理
# ═══════════════════════════════════════════════════════════

def ensure_font() -> bool:
    global _actual_header_h
    if os.path.exists(FONT_FILENAME):
        _update_actual_header_h()
        return True
    if st.session_state.get("_font_failed"):
        return False
    with st.spinner("フォントをセットアップしています（初回のみ）..."):
        for url in FONT_URLS:
            try:
                resp = requests.get(url, timeout=120)
                resp.raise_for_status()
                with open(FONT_FILENAME, "wb") as f:
                    f.write(resp.content)
                _update_actual_header_h()
                return True
            except Exception:
                continue
    st.warning("フォントのダウンロードに失敗しました。システムフォントで代替します。")
    st.session_state["_font_failed"] = True
    _update_actual_header_h()
    return False


def _update_actual_header_h() -> None:
    global _actual_header_h
    try:
        f  = get_font(HEADER_FONT_PT)
        bb = f.getbbox("Agあ|")
        fh = bb[3] - bb[1]
        _actual_header_h = TITLE_V_PAD + fh + TITLE_V_PAD + ACCENT_LINE_H
    except Exception:
        _actual_header_h = HEADER_H


@lru_cache(maxsize=32)
def get_font(size: int) -> ImageFont.FreeTypeFont:
    if os.path.exists(FONT_FILENAME):
        try:
            return ImageFont.truetype(FONT_FILENAME, size)
        except Exception:
            pass
    try:
        return ImageFont.load_default(size=size)   # type: ignore[call-arg]
    except TypeError:
        return ImageFont.load_default()


# ═══════════════════════════════════════════════════════════
#  画像ユーティリティ
# ═══════════════════════════════════════════════════════════

@st.cache_data(ttl=_CACHE_TTL, max_entries=_CACHE_MAX_IMAGES)
def _fetch_raw_image(url: str) -> bytes:
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.content
    except Exception:
        return b""


def load_pil_image(url: str, target_w: int, target_h: int) -> Image.Image:
    """cover（クロップ）モードで画像を読み込む。背景ぼかし用。"""
    dummy = Image.new("RGB", (target_w, target_h), (70, 70, 70))
    raw = _fetch_raw_image(url)
    if not raw:
        return dummy
    try:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        src_w, src_h = img.size
        scale = max(target_w / src_w, target_h / src_h)
        new_w = max(1, int(src_w * scale))
        new_h = max(1, int(src_h * scale))
        img   = img.resize((new_w, new_h), Image.LANCZOS)
        left  = (new_w - target_w) // 2
        top   = (new_h - target_h) // 2
        return img.crop((left, top, left + target_w, top + target_h))
    except Exception:
        return dummy


def load_pil_image_contain(
    url: str, target_w: int, target_h: int, bg_color: tuple = (0, 0, 0),
) -> Image.Image:
    """contain（レターボックス）モードで画像を読み込む。ボックスアート表示用。"""
    canvas = Image.new("RGB", (target_w, target_h), bg_color)
    raw = _fetch_raw_image(url)
    if not raw:
        return canvas
    try:
        img   = Image.open(io.BytesIO(raw)).convert("RGB")
        src_w, src_h = img.size
        scale = min(target_w / src_w, target_h / src_h)
        new_w = max(1, int(src_w * scale))
        new_h = max(1, int(src_h * scale))
        img   = img.resize((new_w, new_h), Image.LANCZOS)
        canvas.paste(img, ((target_w - new_w) // 2, (target_h - new_h) // 2))
        return canvas
    except Exception:
        return canvas


def _no_cover_placeholder(w: int, h: int) -> Image.Image:
    """カバー画像がないゲーム用のプレースホルダ。"""
    img = Image.new("RGB", (w, h), (30, 30, 40))
    drw = ImageDraw.Draw(img)
    font = get_font(max(11, min(20, h // 6)))
    label = "NO IMAGE"
    lw = int(drw.textlength(label, font=font))
    drw.text(((w - lw) // 2, (h - 20) // 2), label, font=font, fill=(80, 80, 100))
    drw.rectangle([0, 0, w - 1, h - 1], outline=(55, 55, 75), width=2)
    return img


# ═══════════════════════════════════════════════════════════
#  テーマ
# ═══════════════════════════════════════════════════════════

THEMES: dict[str, dict] = {
    "Nintendo Red": {
        "bg":      (20,  5,   5),
        "accent":  (228, 0,   15),
        "header":  (10,  0,   0),
        "text1":   (255, 255, 255),
        "text2":   (220, 200, 200),
        "card_bg": (55,  12,  12),
    },
    "Zelda Gold": {
        "bg":      (18,  14,  2),
        "accent":  (200, 160, 30),
        "header":  (8,   6,   0),
        "text1":   (245, 225, 170),
        "text2":   (185, 155, 95),
        "card_bg": (38,  30,  5),
    },
    "Splatoon Neon": {
        "bg":      (12,  0,   22),
        "accent":  (0,   255, 150),
        "header":  (6,   0,   12),
        "text1":   (255, 255, 255),
        "text2":   (170, 255, 220),
        "card_bg": (28,  0,   50),
    },
    "Metroid Dark": {
        "bg":      (5,   8,   18),
        "accent":  (255, 110, 0),
        "header":  (2,   4,   10),
        "text1":   (255, 255, 255),
        "text2":   (205, 180, 150),
        "card_bg": (15,  22,  40),
    },
    "Mario Sky": {
        "bg":      (5,   22,  65),
        "accent":  (255, 212, 0),
        "header":  (2,   12,  45),
        "text1":   (255, 255, 255),
        "text2":   (200, 228, 255),
        "card_bg": (18,  45,  100),
    },
}


# ═══════════════════════════════════════════════════════════
#  レイアウト計算
# ═══════════════════════════════════════════════════════════

def compute_layout(
    canvas_mode: str,
    show_title:  bool,
    num_games:   int = MAX_GAMES,
    cover_mode:  str = "boxart",
) -> dict:
    """
    キャンバスモード・ゲーム数・カバーモードに応じてレイアウト定数を計算する。
    vertical モードは 1 列、horizontal / square は 2 列固定。
    """
    spec  = CANVAS_SPECS[canvas_mode]
    W     = spec["w"]
    H     = spec["h"]
    cols  = spec["cols"]
    hdr_h = (_actual_header_h if show_title else 0)
    rows  = (num_games + cols - 1) // cols
    grid_h = H - hdr_h - FOOTER_H

    card_w = (W - MARGIN * (cols + 1)) // cols
    card_h = (grid_h - MARGIN * (rows + 1)) // rows

    if cover_mode == "boxart":
        thumb_w = max(BOXART_W_MIN, min(BOXART_W_MAX, int(card_h * BOXART_RATIO)))
    else:
        thumb_w = min(SCREENSHOT_W, int(card_w * 0.40))

    text_x_offset = thumb_w + TEXT_PAD
    text_area_w   = card_w - text_x_offset - TEXT_PAD

    title_max_h  = max(TITLE_BOX_MIN_H, int(card_h * TITLE_MAX_H_RATIO))
    title_y      = TEXT_PAD
    review_y     = title_y + title_max_h + ROW_GAP
    review_max_h = card_h - review_y - TEXT_PAD

    return {
        "canvas_w":      W,
        "canvas_h":      H,
        "cols":          cols,
        "header_h":      hdr_h,
        "num_games":     num_games,
        "rows":          rows,
        "card_w":        card_w,
        "card_h":        card_h,
        "thumb_w":       thumb_w,
        "text_x_offset": text_x_offset,
        "text_area_w":   text_area_w,
        "title_y":       title_y,
        "title_max_h":   title_max_h,
        "review_y":      review_y,
        "review_max_h":  review_max_h,
    }


# ═══════════════════════════════════════════════════════════
#  テキスト描画
# ═══════════════════════════════════════════════════════════

def wrap_text_pixels(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_w: int,
) -> str:
    lines: list[str] = []
    current = ""
    for char in text:
        if char == "\n":
            lines.append(current)
            current = ""
            continue
        candidate = current + char
        if int(draw.textlength(candidate, font=font)) <= max_w:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = char
    if current:
        lines.append(current)
    return "\n".join(lines)


def fit_text_in_box(
    draw: ImageDraw.ImageDraw,
    text: str,
    initial_size: int,
    max_w: int,
    max_h: int,
    min_size: int = 11,
) -> tuple[ImageFont.FreeTypeFont, str]:
    size = initial_size
    while size >= min_size:
        font    = get_font(size)
        wrapped = wrap_text_pixels(draw, text, font, max_w)
        bbox    = draw.textbbox((0, 0), wrapped, font=font)
        if (bbox[3] - bbox[1]) <= max_h:
            return font, wrapped
        size -= 1
    font = get_font(min_size)
    return font, wrap_text_pixels(draw, text, font, max_w)


# ═══════════════════════════════════════════════════════════
#  カード描画
# ═══════════════════════════════════════════════════════════

def _mc_badge_color(score: int) -> tuple[int, int, int]:
    if score >= 75:
        return MC_GREEN
    if score >= 50:
        return MC_YELLOW
    return MC_RED


def _get_thumb_url(game: dict, cover_mode: str) -> str:
    """カバーモードに応じて適切な IGDB 画像 URL を返す。"""
    if cover_mode == "screenshot" and game.get("screenshot_image_id"):
        return igdb_image_url(game["screenshot_image_id"], "screenshot_huge")
    if game.get("cover_image_id"):
        return igdb_image_url(game["cover_image_id"], "cover_big_2x")
    return ""


def _get_blur_bg_url(game: dict) -> str:
    """ぼかし背景用: スクリーンショット優先、なければカバーアート。"""
    if game.get("screenshot_image_id"):
        return igdb_image_url(game["screenshot_image_id"], "screenshot_huge")
    if game.get("cover_image_id"):
        return igdb_image_url(game["cover_image_id"], "cover_big_2x")
    return ""


def draw_card(
    canvas:          Image.Image,
    draw:            ImageDraw.ImageDraw,
    idx:             int,
    game:            dict | None,
    theme:           dict,
    bg_style:        str,
    blur_r:          int,
    layout:          dict,
    cover_mode:      str = "boxart",
    show_metacritic: bool = True,
) -> None:
    L    = layout
    cols = L["cols"]
    col  = idx % cols
    row  = idx // cols
    x0   = MARGIN + col * (L["card_w"] + MARGIN)
    y0   = L["header_h"] + MARGIN + row * (L["card_h"] + MARGIN)

    # ─── カード背景 ────────────────────────────────────────
    use_blur = game and bg_style == "blur"
    if use_blur:
        bg_url  = _get_blur_bg_url(game)
        if bg_url:
            bg_img  = load_pil_image(bg_url, L["card_w"], L["card_h"])
            blurred = bg_img.filter(ImageFilter.GaussianBlur(radius=max(1, blur_r)))
            overlay = Image.new("RGBA", (L["card_w"], L["card_h"]), (0, 0, 0, 165))
            card_bg = Image.alpha_composite(blurred.convert("RGBA"), overlay).convert("RGB")
        else:
            card_bg = Image.new("RGB", (L["card_w"], L["card_h"]), theme["card_bg"])
    else:
        bg_color = theme["card_bg"] if game else (45, 45, 45)
        card_bg  = Image.new("RGB", (L["card_w"], L["card_h"]), bg_color)
    canvas.paste(card_bg, (x0, y0))

    # ─── 空スロット ─────────────────────────────────────────
    if game is None:
        ph_font = get_font(SLOT_PH_FONT_PT)
        ph_text = f"SLOT  {idx + 1:02d}"
        pw = int(draw.textlength(ph_text, font=ph_font))
        draw.text(
            (x0 + (L["card_w"] - pw) // 2, y0 + (L["card_h"] - 32) // 2),
            ph_text, font=ph_font, fill=(85, 85, 85),
        )
        draw.rectangle(
            [x0 + 2, y0 + 2, x0 + L["card_w"] - 3, y0 + L["card_h"] - 3],
            outline=(65, 65, 65), width=2,
        )
        return

    # ─── サムネイル ─────────────────────────────────────────
    thumb_url = _get_thumb_url(game, cover_mode)
    if thumb_url:
        if cover_mode == "boxart":
            thumb = load_pil_image_contain(thumb_url, L["thumb_w"], L["card_h"])
        else:
            thumb = load_pil_image(thumb_url, L["thumb_w"], L["card_h"])
    else:
        thumb = _no_cover_placeholder(L["thumb_w"], L["card_h"])
    canvas.paste(thumb, (x0, y0))

    # ─── Metacritic バッジ ────────────────────────────────
    if show_metacritic and game.get("metacritic") is not None:
        score      = game["metacritic"]
        badge_text = str(score)
        mc_font    = get_font(MC_FONT_PT)
        mc_bb      = draw.textbbox((0, 0), badge_text, font=mc_font)
        mc_tw      = mc_bb[2] - mc_bb[0]
        mc_th      = mc_bb[3] - mc_bb[1]
        bx1 = x0 + L["thumb_w"] - mc_tw - MC_BADGE_PAD * 2 - MC_BADGE_EDGE
        bx2 = x0 + L["thumb_w"] - MC_BADGE_EDGE
        by1 = y0 + L["card_h"] - mc_th - MC_BADGE_PAD * 2 - MC_BADGE_EDGE
        by2 = y0 + L["card_h"] - MC_BADGE_EDGE
        badge_w  = bx2 - bx1
        badge_h  = by2 - by1
        mc_color = _mc_badge_color(score)
        badge_bg = Image.new("RGBA", (badge_w, badge_h), (*mc_color, 220))
        section  = canvas.crop((bx1, by1, bx2, by2)).convert("RGBA")
        canvas.paste(Image.alpha_composite(section, badge_bg).convert("RGB"), (bx1, by1))
        draw.text(
            (bx1 + MC_BADGE_PAD - mc_bb[0], by1 + MC_BADGE_PAD - mc_bb[1]),
            badge_text, font=mc_font, fill=(255, 255, 255),
        )

    # ─── タイトル ───────────────────────────────────────────
    tx = x0 + L["text_x_offset"]
    ty = y0
    t_font, t_wrapped = fit_text_in_box(
        draw, game["title"], TITLE_FONT_PT, L["text_area_w"], L["title_max_h"],
        min_size=TITLE_MIN_PT,
    )
    draw.text((tx, ty + L["title_y"]), t_wrapped, font=t_font, fill=theme["text1"])

    # ─── レビュー文 ─────────────────────────────────────────
    review = game.get("review", "").strip()
    if review and L["review_max_h"] > 0:
        r_font, r_wrapped = fit_text_in_box(
            draw, review, REVIEW_FONT_PT, L["text_area_w"], L["review_max_h"],
            min_size=REVIEW_MIN_PT,
        )
        draw.text((tx, ty + L["review_y"]), r_wrapped, font=r_font, fill=theme["text2"])


# ═══════════════════════════════════════════════════════════
#  ポスター生成
# ═══════════════════════════════════════════════════════════

def generate_poster(
    games:           list[dict | None],
    poster_title:    str,
    theme_name:      str,
    bg_style:        str,
    blur_r:          int,
    show_title:      bool,
    canvas_mode:     str = "horizontal",
    cover_mode:      str = "boxart",
    num_games:       int = MAX_GAMES,
    show_metacritic: bool = True,
) -> Image.Image:
    layout  = compute_layout(canvas_mode, show_title, num_games, cover_mode)
    theme   = THEMES[theme_name]
    W       = layout["canvas_w"]
    H       = layout["canvas_h"]
    canvas  = Image.new("RGB", (W, H), theme["bg"])
    draw    = ImageDraw.Draw(canvas)

    # ヘッダー帯
    if show_title:
        draw.rectangle([0, 0, W, layout["header_h"]], fill=theme["header"])
        draw.rectangle(
            [0, layout["header_h"] - ACCENT_LINE_H, W, layout["header_h"]],
            fill=theme["accent"],
        )
        if poster_title.strip():
            h_font = get_font(HEADER_FONT_PT)
            tb     = draw.textbbox((0, 0), poster_title, font=h_font)
            tw     = tb[2] - tb[0]
            content_h = layout["header_h"] - ACCENT_LINE_H
            text_y    = (content_h - (tb[3] - tb[1])) // 2 - tb[1]
            draw.text(((W - tw) // 2, text_y), poster_title, font=h_font, fill=theme["text1"])

    # グリッド中央縦罫線（2列モードのみ）
    if layout["cols"] == 2:
        cx     = W // 2
        div_x0 = cx - CENTER_DIV_W // 2
        div_x1 = cx + CENTER_DIV_W // 2
        div_y0 = layout["header_h"] + MARGIN
        div_y1 = H - FOOTER_H - MARGIN
        draw.rectangle([div_x0, div_y0, div_x1, div_y1], fill=theme["accent"])

    # ゲームカード
    for i, game in enumerate(games[: layout["num_games"]]):
        draw_card(canvas, draw, i, game, theme, bg_style, blur_r, layout, cover_mode, show_metacritic)

    # 行間横罫線
    for row in range(layout["rows"] - 1):
        ry = layout["header_h"] + MARGIN + (row + 1) * (layout["card_h"] + MARGIN) - ROW_DIV_H // 2
        draw.rectangle([MARGIN, ry, W - MARGIN, ry + ROW_DIV_H], fill=theme["accent"])

    # フッター帯
    footer_y = H - FOOTER_H
    draw.rectangle([0, footer_y, W, H], fill=theme["header"])
    draw.rectangle([0, footer_y, W, footer_y + ACCENT_LINE_H], fill=theme["accent"])

    # ウォーターマーク
    wm_font = get_font(WM_FONT_PT)
    wm_text = f"Generated by {APP_NAME}  |  {APP_URL}"
    wm_bb   = draw.textbbox((0, 0), wm_text, font=wm_font)
    wm_tw   = wm_bb[2] - wm_bb[0]
    wm_th   = wm_bb[3] - wm_bb[1]
    content_y = footer_y + ACCENT_LINE_H
    content_h = FOOTER_H - ACCENT_LINE_H
    wm_y = content_y + (content_h - wm_th) // 2
    draw.text(
        (W - wm_tw - 20 - wm_bb[0], wm_y - wm_bb[1]),
        wm_text, font=wm_font, fill=(90, 90, 90),
    )

    return canvas


# ═══════════════════════════════════════════════════════════
#  UI ヘルパー
# ═══════════════════════════════════════════════════════════

def _metacritic_badge_html(score: int | None) -> str:
    """Metacritic スコアを色付きバッジ HTML に変換する（UI 用）。"""
    if score is None:
        return f"<span style='font-size:0.8rem;color:#666'>{t('no_metacritic')}</span>"
    r, g, b = _mc_badge_color(score)
    return (
        f"<span style='display:inline-block;padding:2px 10px;"
        f"background:rgb({r},{g},{b});border-radius:4px;"
        f"font-size:0.85rem;font-weight:bold;color:#fff;"
        f"white-space:nowrap'>{score}</span>"
    )


# ═══════════════════════════════════════════════════════════
#  セッション状態・共通ロジック
# ═══════════════════════════════════════════════════════════

def _commit_game_selection(i: int, game_data: dict) -> None:
    """選択ゲームをスロット i に確定し、ダイアログ関連のセッション変数をリセットする。"""
    st.session_state.games[i] = {
        "game_id":             game_data["game_id"],
        "title":               game_data["title"],
        "cover_image_id":      game_data.get("cover_image_id", ""),
        "screenshot_image_id": game_data.get("screenshot_image_id", ""),
        "metacritic":          game_data.get("metacritic"),
        "review":              "",
    }
    st.session_state[f"dlg_review_{i}"] = ""
    st.session_state.search_results[i]  = []
    st.session_state.pop(f"dlg_search_back_{i}", None)


def init_session() -> None:
    if "games" not in st.session_state:
        st.session_state.games = [None] * MAX_GAMES
    if "search_results" not in st.session_state:
        st.session_state.search_results = [[] for _ in range(MAX_GAMES)]
    if "reorder_mode" not in st.session_state:
        st.session_state["reorder_mode"] = False
    if "num_games_sel" not in st.session_state:
        st.session_state["num_games_sel"] = 8
    if "canvas_mode" not in st.session_state:
        st.session_state["canvas_mode"] = "horizontal"
    if "lang" not in st.session_state:
        st.session_state["lang"] = "ja"
    if "show_metacritic" not in st.session_state:
        st.session_state["show_metacritic"] = True
    if "top_search_results" not in st.session_state:
        st.session_state["top_search_results"] = []


# ═══════════════════════════════════════════════════════════
#  全スロットクリア確認ダイアログ
# ═══════════════════════════════════════════════════════════

def _clear_all_body() -> None:
    st.warning(t("clear_all_warning"), icon=":material/warning:")
    col_yes, col_no = st.columns(2)
    with col_yes:
        if st.button(t("clear_all_confirm"), key="dlg_clear_all_yes",
                     icon=":material/delete_forever:", type="primary",
                     use_container_width=True):
            st.session_state.games = [None] * MAX_GAMES
            st.session_state.search_results = [[] for _ in range(MAX_GAMES)]
            for idx in range(MAX_GAMES):
                for k in [f"dlg_review_{idx}", f"dlg_q_{idx}", f"dlg_search_back_{idx}"]:
                    st.session_state.pop(k, None)
            st.session_state["top_search_results"] = []
            st.session_state.pop("top_q", None)
            st.session_state.pop("top_sel", None)
            st.session_state.pop("_confirm_clear_all", None)
            st.rerun()
    with col_no:
        if st.button(t("cancel_btn"), key="dlg_clear_all_no",
                     icon=":material/close:", use_container_width=True):
            st.session_state.pop("_confirm_clear_all", None)
            st.rerun()


@st.dialog("全スロットをクリア")
def _clear_all_dialog_ja() -> None:
    _clear_all_body()


@st.dialog("Clear All Slots")
def _clear_all_dialog_en() -> None:
    _clear_all_body()


def clear_all_dialog() -> None:
    if st.session_state.get("lang", "ja") == "en":
        _clear_all_dialog_en()
    else:
        _clear_all_dialog_ja()


# ═══════════════════════════════════════════════════════════
#  編集ダイアログ
# ═══════════════════════════════════════════════════════════

@st.dialog("ゲームを編集", width="large")
def _edit_dialog_ja(i: int) -> None:
    _edit_dialog_body(i)


@st.dialog("Edit Game", width="large")
def _edit_dialog_en(i: int) -> None:
    _edit_dialog_body(i)


def edit_dialog(i: int) -> None:
    if st.session_state.get("lang", "ja") == "en":
        _edit_dialog_en(i)
    else:
        _edit_dialog_ja(i)


def _edit_dialog_body(i: int) -> None:
    game            = st.session_state.games[i]
    in_search_phase = game is None or f"dlg_search_back_{i}" in st.session_state

    st.caption(t("slot_caption", n=i + 1))

    # ════════════════════════════════════════════════════════
    # 検索フェーズ
    # ════════════════════════════════════════════════════════
    if in_search_phase:
        if game is not None:
            st.caption(t("reselect_caption", title=game["title"]))
        st.divider()

        with st.form(key=f"dlg_form_{i}", border=False):
            col_q, col_btn = st.columns([5, 1])
            with col_q:
                st.text_input(
                    t("search_btn"), key=f"dlg_q_{i}",
                    placeholder=t("search_ph"), label_visibility="collapsed",
                    help=t("search_help"),
                )
            with col_btn:
                search_clicked = st.form_submit_button(
                    t("search_btn"), icon=":material/search:", use_container_width=True,
                )

        if search_clicked:
            q = st.session_state.get(f"dlg_q_{i}", "").strip()
            if not q:
                st.warning(t("warn_empty_query"))
            elif q.isdigit():
                # IGDB ゲームID 直接入力
                game_id = int(q)
                with st.spinner(t("spin_gameid", id=game_id)):
                    details = get_game_details(game_id)
                if not details:
                    st.warning(t("warn_id_notfound", id=game_id), icon=":material/error:")
                else:
                    _commit_game_selection(i, details)
            else:
                with st.spinner(t("spin_search", q=q)):
                    results = search_igdb(q)
                st.session_state.search_results[i] = results
                st.session_state.pop(f"dlg_sel_{i}", None)
                if not results:
                    st.warning(t("warn_notfound"))

        # 検索結果
        results = st.session_state.search_results[i]
        if results:
            options_map = {
                f"{r['title']}  (ID: {r['game_id']})": r
                for r in results[:10]
            }
            col_drop, col_prev = st.columns([3, 2])
            with col_drop:
                sel_key = st.selectbox(
                    "candidates", list(options_map.keys()),
                    key=f"dlg_sel_{i}", label_visibility="collapsed",
                )
                confirm_clicked = st.button(
                    t("confirm_game_btn"), key=f"dlg_confirm_{i}",
                    icon=":material/check_circle:",
                )
            with col_prev:
                chosen_prev = options_map[sel_key]
                prev_url = igdb_image_url(chosen_prev.get("cover_image_id", ""), "cover_big_2x")
                if prev_url:
                    st.image(prev_url, use_container_width=True, caption=chosen_prev["title"])

            if confirm_clicked:
                chosen = options_map[sel_key]
                with st.spinner(t("spin_details", name=chosen["title"])):
                    details = get_game_details(chosen["game_id"])
                if details:
                    _commit_game_selection(i, details)
                else:
                    _commit_game_selection(i, chosen)

        # フッターボタン
        st.divider()
        if game is not None:
            col_back, col_close = st.columns([1, 1])
            with col_back:
                if st.button(t("back_to_edit_btn"), key=f"dlg_editback_{i}",
                             icon=":material/arrow_back:", use_container_width=True):
                    st.session_state.pop(f"dlg_search_back_{i}", None)
                    st.rerun()
            with col_close:
                if st.button(t("cancel_btn"), key=f"dlg_close_{i}",
                             icon=":material/close:", use_container_width=True):
                    del st.session_state["editing_slot"]
                    st.rerun()
        else:
            if st.button(t("close_btn"), key=f"dlg_close_{i}", icon=":material/close:"):
                del st.session_state["editing_slot"]
                st.rerun()

    # ════════════════════════════════════════════════════════
    # 編集フェーズ
    # ════════════════════════════════════════════════════════
    else:
        if st.button(t("back_to_search_btn"), key=f"dlg_back_{i}", icon=":material/search:"):
            st.session_state[f"dlg_search_back_{i}"] = True
            st.session_state.search_results[i] = []
            st.rerun()

        st.divider()
        col_img, col_form = st.columns([1, 2])

        with col_img:
            cover_url = igdb_image_url(game.get("cover_image_id", ""), "cover_big_2x")
            if cover_url:
                st.image(cover_url, use_container_width=True)
            else:
                st.markdown(
                    "<div style='background:#1e1e2e;border:1px solid #333;"
                    "border-radius:6px;padding:20px;text-align:center;color:#666;'>"
                    "NO IMAGE</div>",
                    unsafe_allow_html=True,
                )

        with col_form:
            st.markdown(f"### {game['title']}")
            st.markdown(_metacritic_badge_html(game.get("metacritic")), unsafe_allow_html=True)

            review_now = st.text_area(
                t("review_label"), height=160,
                key=f"dlg_review_{i}", help=t("review_help"),
            )
            review_len = len(review_now or "")

            _show_title = st.session_state.get("show_title", True)
            _num_g      = st.session_state.get("num_games_sel", 8)
            _cm         = st.session_state.get("canvas_mode", "horizontal")
            _cvm        = st.session_state.get("cover_mode_sel", "boxart")
            _L          = compute_layout(_cm, _show_title, _num_g, _cvm)
            max_chars   = max(60, int(_L["review_max_h"] * _L["text_area_w"] // (REVIEW_FONT_PT ** 2)))

            over_limit   = review_len > max_chars
            counter_id   = f"dlg-rc-{i}"
            color_init   = "#e74c3c" if over_limit else "#aaa"
            counter_text = t("char_counter_tmpl", n=review_len, max=max_chars)
            st.markdown(
                f"<p id='{counter_id}' style='text-align:right;font-size:0.8rem;"
                f"color:{color_init};margin-top:-12px'>{counter_text}</p>",
                unsafe_allow_html=True,
            )
            if over_limit:
                st.error(t("over_limit_err", max=max_chars))

            lang_suffix = t("char_counter_suffix")
            components.html(
                f"""<script>
(function(){{
  var CID = '{counter_id}';
  var MAX = {max_chars};
  var SUFFIX = ' / {max_chars} {lang_suffix}';
  function attach() {{
    var doc = window.parent.document;
    var ta = doc.querySelector('[data-testid="stTextArea"] textarea');
    if (!ta) return false;
    if (ta._rt) ta.removeEventListener('input', ta._rt);
    ta._rt = function() {{
      var n = this.value.length;
      var c = doc.getElementById(CID);
      if (!c) return;
      c.textContent = n + SUFFIX;
      c.style.color = n > MAX ? '#e74c3c' : '#aaa';
    }};
    ta.addEventListener('input', ta._rt);
    return true;
  }}
  if (!attach()) {{
    var tries = 0;
    var iv = setInterval(function() {{
      if (attach() || ++tries > 20) clearInterval(iv);
    }}, 150);
  }}
}})();
</script>""",
                height=0, scrolling=False,
            )

        st.divider()
        col_save, col_clear, col_cancel = st.columns([3, 2, 2])
        with col_save:
            if st.button(t("save_btn"), key=f"dlg_save_{i}",
                         icon=":material/save:", type="primary",
                         use_container_width=True, disabled=over_limit):
                st.session_state.games[i]["review"] = st.session_state.get(f"dlg_review_{i}", "")
                st.session_state.pop(f"dlg_search_back_{i}", None)
                del st.session_state["editing_slot"]
                st.rerun()
        with col_clear:
            if st.button(t("dlg_clear_btn"), key=f"dlg_clear_{i}",
                         icon=":material/delete:", use_container_width=True):
                st.session_state.games[i] = None
                st.session_state.search_results[i] = []
                for k in [f"dlg_review_{i}", f"dlg_q_{i}", f"dlg_search_back_{i}"]:
                    st.session_state.pop(k, None)
                del st.session_state["editing_slot"]
                st.rerun()
        with col_cancel:
            if st.button(t("cancel_btn"), key=f"dlg_cancel_{i}",
                         icon=":material/close:", use_container_width=True):
                st.session_state.pop(f"dlg_search_back_{i}", None)
                del st.session_state["editing_slot"]
                st.rerun()


# ═══════════════════════════════════════════════════════════
#  スロットカード（グリッド表示用）
# ═══════════════════════════════════════════════════════════

def render_slot_card(i: int, disabled: bool = False) -> None:
    game = st.session_state.games[i]

    with st.container(border=True):
        if game:
            col_thumb, col_info = st.columns([2, 3])
            with col_thumb:
                cover_url = igdb_image_url(game.get("cover_image_id", ""), "cover_big_2x")
                if cover_url:
                    st.image(cover_url, use_container_width=True)
                else:
                    st.markdown(
                        "<div style='background:#1e1e2e;border:1px solid #333;"
                        "border-radius:6px;padding:16px 0;text-align:center;"
                        "color:#666;font-size:0.8rem;'>NO IMAGE</div>",
                        unsafe_allow_html=True,
                    )
            with col_info:
                mc_badge = _metacritic_badge_html(game.get("metacritic"))
                st.markdown(
                    f"<p style='margin:0 0 4px;font-weight:bold;font-size:0.95rem;line-height:1.3'>{game['title']}</p>"
                    f"<p style='margin:0'>{mc_badge}</p>",
                    unsafe_allow_html=True,
                )
            review = game.get("review", "")
            if review:
                review_escaped = html.escape(review).replace("\n", "<br>")
                st.markdown(
                    f"<p style='margin:4px 0 0;font-size:0.8rem;"
                    f"color:#aaa;line-height:1.5'>{review_escaped}</p>",
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                f"<div style='text-align:center;padding:20px 0;"
                f"color:#555;font-size:0.85rem;'>{t('empty_slot_card', n=i+1)}</div>",
                unsafe_allow_html=True,
            )

        if st.button(t("edit_btn"), key=f"btn_edit_{i}",
                     icon=":material/edit:", use_container_width=True, disabled=disabled):
            st.session_state["editing_slot"] = i
            if game:
                st.session_state[f"dlg_review_{i}"] = game.get("review", "")


# ═══════════════════════════════════════════════════════════
#  クイック追加セクション
# ═══════════════════════════════════════════════════════════

def _render_quick_add_section(num_games: int) -> None:
    """
    ページ上部に表示するクイック追加 UI。
    検索 → 候補選択 → 「追加」ボタンで次の空きスロットに自動割り当てる。
    IGDB ゲームID 入力時は即追加。
    """
    st.subheader(t("quick_add_header"), anchor=False)

    next_slot = next(
        (idx for idx, g in enumerate(st.session_state.games[:num_games]) if g is None),
        None,
    )

    if next_slot is None:
        st.info(t("slots_full_warn"), icon=":material/check_circle:")
        return

    existing_ids: set[int] = {
        g["game_id"] for g in st.session_state.games[:num_games] if g is not None
    }

    # ── 検索フォーム ──────────────────────────────────────────
    with st.form(key="top_search_form", border=False):
        col_q, col_btn = st.columns([5, 1])
        with col_q:
            st.text_input(
                t("search_btn"), key="top_q",
                placeholder=t("search_ph"), label_visibility="collapsed",
                help=t("search_help"),
            )
        with col_btn:
            search_clicked = st.form_submit_button(
                t("search_btn"), icon=":material/search:", use_container_width=True,
            )

    if search_clicked:
        q = st.session_state.get("top_q", "").strip()
        if not q:
            st.warning(t("warn_empty_query"))
        elif q.isdigit():
            # IGDB ゲームID: 即追加パス
            game_id = int(q)
            with st.spinner(t("spin_gameid", id=game_id)):
                details = get_game_details(game_id)
            if not details:
                st.warning(t("warn_id_notfound", id=game_id), icon=":material/error:")
            elif details["game_id"] in existing_ids:
                st.warning(t("duplicate_warn"), icon=":material/warning:")
            else:
                _commit_game_selection(next_slot, details)
                st.toast(t("added_toast", n=next_slot + 1))
                st.session_state["top_search_results"] = []
                st.rerun()
        else:
            # テキスト検索: 候補一覧を表示
            with st.spinner(t("spin_search", q=q)):
                results = search_igdb(q)
            st.session_state["top_search_results"] = results
            st.session_state.pop("top_sel", None)
            if not results:
                st.warning(t("warn_notfound"))

    # ── 検索結果 → 候補選択 → 追加 ──────────────────────────
    results = st.session_state.get("top_search_results", [])
    if results:
        options_map = {
            f"{r['title']}  (ID: {r['game_id']})": r
            for r in results[:10]
        }
        col_drop, col_prev = st.columns([3, 2])
        with col_drop:
            sel_key = st.selectbox(
                "candidates", list(options_map.keys()),
                key="top_sel", label_visibility="collapsed",
            )
            chosen = options_map[sel_key]
            already_registered = chosen["game_id"] in existing_ids
            if already_registered:
                st.caption(t("duplicate_warn"))
            add_clicked = st.button(
                t("quick_add_btn"), key="top_add_btn",
                icon=":material/add:", use_container_width=True,
                disabled=already_registered, type="primary",
            )
        with col_prev:
            prev_url = igdb_image_url(chosen.get("cover_image_id", ""), "cover_big_2x")
            if prev_url:
                st.image(prev_url, use_container_width=True, caption=chosen["title"])

        if add_clicked:
            with st.spinner(t("spin_details", name=chosen["title"])):
                details = get_game_details(chosen["game_id"])
            _commit_game_selection(next_slot, details if details else chosen)
            st.toast(t("added_toast", n=next_slot + 1))
            st.session_state["top_search_results"] = []
            st.session_state.pop("top_sel", None)
            st.rerun()


# ═══════════════════════════════════════════════════════════
#  メイン
# ═══════════════════════════════════════════════════════════

def main() -> None:
    st.set_page_config(
        page_title="NintendoPosterMaker",
        page_icon="🎮",
        layout="wide",
    )

    init_session()

    # IGDB 認証チェック（未設定なら操作不可のエラー画面を表示）
    if not _check_secrets():
        st.error(
            "IGDB API の認証情報が設定されていません。\n\n"
            "Streamlit Secrets に以下のキーを設定してください：",
            icon=":material/lock:",
        )
        st.code(
            "# .streamlit/secrets.toml\n"
            'IGDB_CLIENT_ID = "your_client_id"\n'
            'IGDB_CLIENT_SECRET = "your_client_secret"',
            language="toml",
        )
        st.markdown(
            "Twitch Developer Console（https://dev.twitch.tv/console）で"
            "アプリを登録し、Client ID と Client Secret を取得してください。"
        )
        st.stop()

    ensure_font()
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)

    st.markdown(
        "<h1 style='text-align:center;'>🎮 NintendoPosterMaker</h1>",
        unsafe_allow_html=True,
    )

    # ── 言語トグル ───────────────────────────────────────────
    col_spacer, col_lang = st.columns([8, 2])
    with col_lang:
        if st.button(t("lang_toggle"), key="lang_toggle_btn",
                     icon=":material/language:", use_container_width=True):
            st.session_state["lang"] = "en" if st.session_state.get("lang", "ja") == "ja" else "ja"
            st.rerun()

    # ── レイアウト・進捗を先に計算 ────────────────────────────
    show_title     = st.session_state.get("show_title", True)
    num_games_sel  = st.session_state.get("num_games_sel", 8)
    canvas_mode    = st.session_state.get("canvas_mode", "horizontal")
    cover_mode     = st.session_state.get("cover_mode_sel", "boxart")
    layout         = compute_layout(canvas_mode, show_title, num_games_sel, cover_mode)
    num_games      = layout["num_games"]
    filled         = sum(1 for g in st.session_state.games[:num_games] if g is not None)
    already_generated = "last_poster_bytes" in st.session_state

    # ── スティッキーボトムバー ────────────────────────────────
    _sticky_triggered = st.session_state.pop("_sticky_generate", False)
    if st.query_params.get("_sg"):
        st.query_params.clear()
        st.session_state["_sticky_generate"] = True
        st.rerun()

    _render_sticky_bar(filled, num_games, already_generated)

    st.divider()

    # ── 見出し設定 + 表示設定ポップオーバー ──────────────────
    col_tog, col_ttl, col_pop = st.columns([1, 3, 1])
    with col_tog:
        show_title = st.toggle(
            t("heading_toggle"), value=True, key="show_title",
            help=t("heading_toggle_help"),
        )
    with col_ttl:
        if show_title:
            poster_title = st.text_input(
                t("heading_toggle"), value=t("heading_default"),
                max_chars=25, placeholder=t("heading_placeholder"),
                key="poster_title", label_visibility="collapsed",
                help=t("heading_help"),
            )
        else:
            poster_title = st.session_state.get("poster_title", "")
            st.caption(t("heading_none_cap"))
    with col_pop:
        with st.popover(t("num_games_popover"), icon=":material/grid_view:", use_container_width=True):
            st.radio(t("num_games_label"), [8, 10], horizontal=True,
                     key="num_games_sel", help=t("num_games_help"))
            st.radio(
                t("canvas_mode_label"),
                ["horizontal", "vertical", "square"],
                format_func=lambda x: t(f"canvas_{x}"),
                key="canvas_mode",
            )
            st.caption(f"Card {layout['card_w']} × {layout['card_h']} px")

    st.divider()

    # ── クイック追加 ─────────────────────────────────────────
    _render_quick_add_section(num_games)

    st.divider()

    # ── ゲームスロット ────────────────────────────────────────
    col_hdr, col_cnt, col_clear, col_sort = st.columns([3, 1, 1, 1], vertical_alignment="center")
    with col_hdr:
        st.subheader(t("slots_header"))
    with col_cnt:
        st.markdown(
            f"<p style='margin:0;text-align:right;white-space:nowrap;'>"
            f"<span style='font-size:0.8rem;color:#aaa;margin-right:6px;'>{t('slots_count_prefix')}</span>"
            f"<span style='font-size:1.15rem;font-weight:bold;'>{filled} / {num_games}</span>"
            f"</p>",
            unsafe_allow_html=True,
        )
    with col_clear:
        if st.button(t("clear_all_btn"), key="btn_clear_all",
                     icon=":material/delete_sweep:", use_container_width=True,
                     disabled=filled == 0):
            st.session_state["_confirm_clear_all"] = True
            st.rerun()
    with col_sort:
        sort_label = t("sort_done_btn") if st.session_state["reorder_mode"] else t("sort_btn")
        sort_icon  = ":material/done_all:" if st.session_state["reorder_mode"] else ":material/swap_vert:"
        sort_type  = "primary" if st.session_state["reorder_mode"] else "secondary"
        if st.button(sort_label, icon=sort_icon, use_container_width=True, type=sort_type):
            st.session_state["reorder_mode"] = not st.session_state["reorder_mode"]
            st.rerun()

    if st.session_state["reorder_mode"]:
        st.info(t("sort_drag_info"), icon=":material/swap_vert:")
        sort_labels = [
            g["title"] if g else t("empty_slot_sort", n=idx + 1)
            for idx, g in enumerate(st.session_state.games[:num_games])
        ]
        sorted_labels = sort_items(sort_labels, key="slot_sorter")
        if sorted_labels != sort_labels:
            remaining: dict[str, deque] = {}
            for idx, label in enumerate(sort_labels):
                remaining.setdefault(label, deque()).append(idx)
            new_order = [remaining[label].popleft() for label in sorted_labels]
            old_g = st.session_state.games[:num_games]
            old_r = st.session_state.search_results[:num_games]
            st.session_state.games          = [old_g[j] for j in new_order] + st.session_state.games[num_games:]
            st.session_state.search_results = [old_r[j] for j in new_order] + st.session_state.search_results[num_games:]
            st.rerun()

    is_reorder = st.session_state["reorder_mode"]
    num_rows   = (num_games + 1) // 2
    for row in range(num_rows):
        grid_cols = st.columns(2, gap="small")
        for col_idx, gcol in enumerate(grid_cols):
            slot_idx = row * 2 + col_idx
            if slot_idx < num_games:
                with gcol:
                    render_slot_card(slot_idx, disabled=is_reorder)

    st.divider()

    # ── ポスター生成 ─────────────────────────────────────────
    st.markdown('<div id="poster-gen-sentinel"></div>', unsafe_allow_html=True)
    components.html(
        """<script>
(function() {
  var BAR_ID = 'npm-sticky-bar';
  var SEN_ID = 'poster-gen-sentinel';
  var doc = window.parent.document;
  var win = window.parent;
  function updateBar() {
    var bar = doc.getElementById(BAR_ID);
    var sen = doc.getElementById(SEN_ID);
    if (!bar || !sen) return;
    var reached = sen.getBoundingClientRect().top <= win.innerHeight;
    bar.style.opacity       = reached ? '0' : '1';
    bar.style.pointerEvents = reached ? 'none' : 'auto';
    var mc = doc.querySelector('[data-testid="stMainBlockContainer"]');
    if (mc) mc.style.paddingBottom = reached ? '0px' : '64px';
  }
  win.addEventListener('scroll', updateBar, { passive: true });
  try { win.document.documentElement.addEventListener('scroll', updateBar, { passive: true }); } catch(e) {}
  setInterval(updateBar, 150);
})();
</script>""",
        height=0, scrolling=False,
    )

    if filled > 0 and filled < num_games:
        st.info(t("empty_slots_info", filled=filled, n=num_games - filled), icon=":material/info:")

    col_design, col_gen = st.columns([1, 2])
    with col_design:
        with st.popover(t("design_popover"), icon=":material/settings:", use_container_width=True):
            theme_name = st.selectbox(t("theme_label"), list(THEMES.keys()), key="theme_sel")
            theme_colors = THEMES[theme_name]
            _swatch_html = "".join(
                f"<span title='{label}' style='display:inline-block;width:22px;height:22px;"
                f"border-radius:5px;background:rgb{color};margin-right:5px;"
                f"border:1px solid #555;vertical-align:middle'></span>"
                for label, color in [
                    ("bg", theme_colors["bg"]),
                    ("accent", theme_colors["accent"]),
                    ("card", theme_colors["card_bg"]),
                ]
            )
            st.markdown(_swatch_html, unsafe_allow_html=True)
            st.radio(
                t("cover_mode_label"),
                ["boxart", "screenshot"],
                format_func=lambda x: t(f"cover_{x}"),
                horizontal=True,
                key="cover_mode_sel",
            )
            bg_style = st.radio(
                t("bg_style_label"),
                ["blur", "solid"],
                format_func=lambda x: t("bg_style_blur") if x == "blur" else t("bg_style_solid"),
                horizontal=True,
                key="bg_style_sel",
            )
            blur_r = 0
            if bg_style == "blur":
                blur_r = st.slider(
                    t("blur_label"), min_value=1, max_value=40, value=15,
                    key="blur_r_val", help=t("blur_help"),
                )
            st.toggle(t("show_metacritic_label"), value=True, key="show_metacritic")
    with col_gen:
        generate_btn = st.button(
            t("regenerate_btn") if already_generated else t("generate_btn"),
            icon=":material/refresh:" if already_generated else ":material/palette:",
            type="primary", use_container_width=True, disabled=(filled == 0),
        )

    if generate_btn or _sticky_triggered:
        games_slice     = st.session_state.games[:num_games]
        show_metacritic = st.session_state.get("show_metacritic", True)

        for _key in ("last_poster_bytes", "last_poster_meta"):
            st.session_state.pop(_key, None)

        with st.status(t("status_title"), expanded=True) as gen_status:
            try:
                fetchable = [g for g in games_slice if g is not None]
                if fetchable:
                    st.write(t("status_fetch", n=len(fetchable), total=num_games))
                    for g in fetchable:
                        url = _get_thumb_url(g, cover_mode)
                        if url:
                            _fetch_raw_image(url)

                st.write(t("status_compose"))
                poster = generate_poster(
                    games_slice, poster_title, theme_name,
                    bg_style, blur_r, show_title,
                    canvas_mode, cover_mode, num_games, show_metacritic,
                )

                st.write(t("status_encode"))
                buf = io.BytesIO()
                poster.save(buf, format="PNG", compress_level=1)
                poster.close()
                st.session_state["last_poster_bytes"] = buf.getvalue()
                date_str   = datetime.date.today().strftime("%Y%m%d")
                pick_label = f"{num_games}pick"
                title_part = _safe_filename(poster_title) if show_title and poster_title.strip() else ""
                parts      = ["nintendo", pick_label] + ([title_part] if title_part else []) + [date_str]
                st.session_state["last_poster_meta"] = {"filename": "_".join(parts) + ".png"}
                st.session_state["_poster_complete"] = True
                gen_status.update(state="complete")
                st.toast(t("toast_done"))
            except Exception as e:
                gen_status.update(label=t("status_error"), state="error")
                st.error(f"{e}")

    if "last_poster_bytes" in st.session_state:
        poster_bytes = st.session_state["last_poster_bytes"]
        meta         = st.session_state["last_poster_meta"]
        st.image(poster_bytes, caption=t("preview_caption"), use_container_width=True)
        st.download_button(
            label=t("download_btn"), icon=":material/download:",
            data=poster_bytes, file_name=meta["filename"],
            mime="image/png", use_container_width=True,
        )

        _tweet_params = urllib.parse.urlencode(
            {"text": t("share_tweet_text"), "url": APP_URL},
            quote_via=urllib.parse.quote,
        )
        _tweet_url = (
            "https://x.com/intent/tweet?"
            + _tweet_params
            + "&hashtags=" + urllib.parse.quote(t("share_hashtags"), safe=",")
        )
        st.divider()
        st.markdown(
            f"<p style='text-align:center;font-weight:bold;font-size:0.95rem;"
            f"margin:0 0 6px;'>{t('share_header')}</p>",
            unsafe_allow_html=True,
        )
        st.info(t("share_info"), icon=":material/attach_file:")
        st.link_button(t("share_btn"), _tweet_url, icon=":material/share:", use_container_width=True)

    st.divider()

    # ── フッター ─────────────────────────────────────────────
    col_x, sep, col_of, sep2, col_fb = st.columns([2, 0.1, 2, 0.1, 2])
    with col_x:
        st.markdown(f"**{t('author_section')}**")
        st.markdown(_X_BUTTON_ICON_HTML, unsafe_allow_html=True)
    with sep:
        st.markdown("<div class='footer-sep' style='border-left:1px solid #444;height:80px;'></div>",
                    unsafe_allow_html=True)
    with col_of:
        st.markdown(f"**{t('ofuse_header')}**")
        st.markdown(_OFUSE_BUTTON_HTML, unsafe_allow_html=True)
    with sep2:
        st.markdown("<div class='footer-sep' style='border-left:1px solid #444;height:80px;'></div>",
                    unsafe_allow_html=True)
    with col_fb:
        st.markdown(f"**{t('feedback_header')}**")
        st.markdown(t("feedback_body"))
        st.link_button(t("feedback_btn"), "https://forms.gle/GpBA3PHgZHsze82r8",
                       icon=":material/feedback:", use_container_width=True)

    with st.expander(t("tos_expander"), icon=":material/gavel:"):
        st.markdown(
            f"- {t('disclaimer_unofficial')}\n"
            f"- {t('disclaimer_no_relation')}\n"
            f"- Nintendo の商標・ロゴは任天堂株式会社の財産です。\n"
            f"- 生成した画像の利用は個人利用・SNS での紹介目的の範囲に限ります。商用利用はお控えください。\n"
            f"- IGDB API の仕様変更により、一部機能が正常に動作しない場合があります。"
        )

    st.markdown(
        f"<div class='npm-copyright'>"
        f"© {datetime.date.today().year} {APP_NAME} — Unofficial Fan-Made Tool"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── ダイアログ呼び出し ────────────────────────────────────
    if "editing_slot" in st.session_state:
        edit_dialog(st.session_state["editing_slot"])

    if st.session_state.get("_confirm_clear_all"):
        clear_all_dialog()


if __name__ == "__main__":
    main()
