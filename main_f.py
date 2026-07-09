import os
import uuid
import re
import html
import random
import logging
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components
from google import genai
from google.genai import types
from dotenv import load_dotenv
from database import SentimentVectorDatabase

# Load environment variables
load_dotenv()

# --- Internal logger (never shown to the user) ---
logger = logging.getLogger("jeeva")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(_handler)

# --- Error classification sentinels ---
# Responses from process_user_message() that start with these prefixes
# are NOT real assistant replies — they are structured error signals.
_ERR_TEMPORARY = "__JEEVA_ERR_TEMPORARY__"
_ERR_PERMANENT = "__JEEVA_ERR_PERMANENT__"

# Patterns that indicate a *temporary* Gemini API issue
_TEMPORARY_PATTERNS = [
    "usage limit", "quota", "429", "rate limit", "resource exhausted",
    "too many requests", "service unavailable", "503", "overloaded",
    "temporarily unavailable", "try again", "capacity",
]
# Patterns that indicate a *permanent* configuration issue
_PERMANENT_PATTERNS = [
    "api_key", "invalid key", "403", "permission denied",
    "authentication", "unauthorized", "401",
]


def classify_api_response(response_text):
    """Classify a chatbot response as normal, temporary-error, or permanent-error.

    Returns:
        ("ok", response_text)        – normal reply
        ("temporary", detail_text)   – quota / rate-limit / transient failure
        ("permanent", detail_text)   – bad key / auth failure
    """
    if response_text.startswith(_ERR_TEMPORARY):
        return "temporary", response_text[len(_ERR_TEMPORARY):]
    if response_text.startswith(_ERR_PERMANENT):
        return "permanent", response_text[len(_ERR_PERMANENT):]
    return "ok", response_text


def render_error_recovery_card(error_type, theme="Classic Linen"):
    """Display a themed, user-friendly error card with recovery actions.

    Args:
        error_type: "temporary" or "permanent"
        theme: Current Jeeva theme name (for colour consistency)
    """
    # Resolve colours from the active theme
    if theme == "Sage Meadow":
        card_border = "#7a9a7e"
        accent = "#4a7a50"
    elif theme == "Deep Ocean":
        card_border = "#6b8fa3"
        accent = "#3a7a9a"
    else:  # Classic Linen
        card_border = "#dac1bd"
        accent = "#904639"

    if error_type == "temporary":
        st.markdown(f"""
        <div style="
            background-color: rgba(255, 218, 212, 0.35);
            border: 1px solid {card_border};
            border-left: 4px solid {accent};
            border-radius: var(--radius-lg);
            padding: var(--spacing-md);
            margin: var(--spacing-md) 0;
            animation: fadeIn 0.3s ease-out;
        ">
            <div style="display:flex; align-items:center; gap:var(--spacing-sm); margin-bottom:var(--spacing-sm);">
                <span style="font-size:24px;">🤖</span>
                <h3 style="font-family:'EB Garamond',serif; color:{accent}; margin:0; font-weight:600;">Jeeva is temporarily unavailable</h3>
            </div>
            <p style="font-family:'Be Vietnam Pro',sans-serif; font-size:var(--font-base); color:#59605c; line-height:1.6; margin:0 0 var(--spacing-sm) 0;">
                I'm currently unable to respond because the AI service has reached its temporary usage limit.
                This is usually resolved automatically after a short wait.
            </p>
            <p style="font-family:'Be Vietnam Pro',sans-serif; font-size:var(--font-sm); color:#59605c; line-height:1.6; margin:0;">
                You can:<br>
                • Try again in a few minutes.<br>
                • Continue exploring other sections of Jeeva.<br>
                • Continue writing your journal while AI responses are temporarily unavailable.
            </p>
        </div>
        """, unsafe_allow_html=True)

        # Recovery action buttons
        with st.container(horizontal=True):
            if st.button("🔄 Try Again", key="err_retry", use_container_width=True):
                _retry_last_message()
            if st.button("🆕 New Conversation", key="err_new_convo", use_container_width=True):
                _start_new_conversation()

    else:  # permanent
        st.markdown(f"""
        <div style="
            background-color: rgba(186, 26, 26, 0.06);
            border: 1px solid #ffdad6;
            border-left: 4px solid #ba1a1a;
            border-radius: var(--radius-lg);
            padding: var(--spacing-md);
            margin: var(--spacing-md) 0;
            animation: fadeIn 0.3s ease-out;
        ">
            <div style="display:flex; align-items:center; gap:var(--spacing-sm); margin-bottom:var(--spacing-sm);">
                <span style="font-size:24px;">⚠️</span>
                <h3 style="font-family:'EB Garamond',serif; color:#ba1a1a; margin:0; font-weight:600;">Service configuration issue</h3>
            </div>
            <p style="font-family:'Be Vietnam Pro',sans-serif; font-size:var(--font-base); color:#59605c; line-height:1.6; margin:0 0 var(--spacing-sm) 0;">
                Jeeva is unable to connect to the AI service due to a configuration problem.
                An administrator may need to verify the API key or service credentials.
            </p>
            <p style="font-family:'Be Vietnam Pro',sans-serif; font-size:var(--font-sm); color:#59605c; line-height:1.6; margin:0;">
                In the meantime you can still use the Journal, Exercises, and Insights tabs.
            </p>
        </div>
        """, unsafe_allow_html=True)

        if st.button("🆕 New Conversation", key="err_new_convo_perm", use_container_width=True):
            _start_new_conversation()


def _retry_last_message():
    """Re-send the most recent user message after a transient failure."""
    # Remove the error assistant message that was appended
    if (st.session_state.messages
            and st.session_state.messages[-1].get("error_type")):
        st.session_state.messages.pop()
    # Find the last user message to retry
    last_user_msg = None
    for msg in reversed(st.session_state.messages):
        if msg["role"] == "user":
            last_user_msg = msg["content"]
            break
    if last_user_msg:
        # Remove the user message too — it will be re-appended by the normal flow
        while (st.session_state.messages
               and st.session_state.messages[-1]["role"] == "user"):
            st.session_state.messages.pop()
        st.session_state.pending_retry = last_user_msg
    st.rerun()


def _start_new_conversation():
    """Reset chat history while preserving all app settings."""
    st.session_state.messages = [{
        "role": "assistant",
        "content": "Starting fresh! I'm here and ready to listen. What's on your mind?",
        "detected_mood": "Neutral 🧘‍♀️"
    }]
    # Preserve theme, font_scale, journal_entries, breathing_cycles, etc.
    st.session_state.pop("pending_retry", None)
    st.rerun()


def _send_message_with_error_handling(user_text):
    """Central helper: send a message, detect errors, update session state.

    Returns True if the response was normal, False if an error card should
    be rendered (the error message is already appended to session state).
    """
    with st.spinner("JeevaAI is listening..."):
        response_text = st.session_state.chatbot_instance.process_user_message(user_text)

    status, detail = classify_api_response(response_text)

    if status != "ok":
        # Append a special error-marker message so the renderer can show the card
        st.session_state.messages.append({
            "role": "assistant",
            "content": detail,
            "detected_mood": "Neutral 🧘‍♀️",
            "error_type": status,  # "temporary" | "permanent"
        })
        return False

    # Determine mood via sentiment DB
    detected = "Neutral 🧘‍♀️"
    if 'sentiment_db' in st.session_state:
        try:
            res = st.session_state.sentiment_db.get_most_similar_sentiment(user_text, top_k=1)
            if res:
                mood = res[0][0]
                emoji = SENTIMENT_EMOJIS.get(mood, "🧘‍♀️")
                detected = f"{mood.capitalize()} {emoji}"
        except Exception:
            pass

    st.session_state.messages.append({
        "role": "assistant",
        "content": response_text,
        "detected_mood": detected,
    })
    return True

# --- Sentiment Emojis Map ---
SENTIMENT_EMOJIS = {
    'joy': '🍃',
    'sadness': '☁️',
    'anger': '⚡',
    'fear': '☁️',
    'surprise': '✨',
    'disgust': '☁️',
    'neutral': '🧘‍♀️',
    'anxiety': '🌊',
    'hopelessness': '☁️',
    'gratitude': '🌸',
    'confusion': '☁️',
    'overwhelmed': '⚡'
}

# --- Markdown to HTML Helper ---
def markdown_to_html(text):
    """Safely convert basic markdown syntax from LLM output to styled HTML."""
    text = html.escape(text)
    # Bold: **text** -> <strong>text</strong>
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    # Italic: *text* -> <em>text</em>
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
    # Links: [text](url) -> <a href="url" target="_blank">text</a>
    text = re.sub(
        r'\[(.*?)\]\((.*?)\)', 
        r'<a href="\2" target="_blank" style="color:#904639; text-decoration:underline;">\1</a>', 
        text
    )
    # Bullet points: lines starting with "- " or "* " -> list items
    lines = text.split('\n')
    in_list = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('- ') or stripped.startswith('* '):
            content = stripped[2:]
            if not in_list:
                new_lines.append('<ul style="margin: 8px 0; padding-left: 20px; font-family:\'Be Vietnam Pro\', sans-serif;">')
                in_list = True
            new_lines.append(f'<li style="margin: 4px 0;">{content}</li>')
        else:
            if in_list:
                new_lines.append('</ul>')
                in_list = False
            new_lines.append(line)
    if in_list:
        new_lines.append('</ul>')
    text = '\n'.join(new_lines)
    # Line breaks: \n -> <br/>
    text = text.replace('\n', '<br/>')
    return text

# --- Custom CSS Injection with Theme Customization ---
def inject_custom_css(theme, font_scale="Spacious"):
    if theme == "Sage Meadow":
        bg = "#e8efe9"
        text = "#2c3531"
        sidebar_bg = "#d0dbd3"
        active_bg = "#b0c2b5"
        primary = "#763226"
        outline = "#a8bdae"
        card_bg = "rgba(176, 194, 181, 0.4)"
        banner_bg = "#f3eee3"
        banner_text = "#4a322c"
    elif theme == "Deep Ocean":
        bg = "#0f172a"
        text = "#f1f5f9"
        sidebar_bg = "#1e293b"
        active_bg = "#334155"
        primary = "#c06c5d"
        outline = "#334155"
        card_bg = "rgba(51, 65, 85, 0.4)"
        banner_bg = "#1e293b"
        banner_text = "#f1f5f9"
    else: # Classic Linen (Cream)
        bg = "#fbf9f6"
        text = "#1b1c1a"
        sidebar_bg = "#f5f3f0"
        active_bg = "#dac1bd"
        primary = "#904639"
        outline = "#dac1bd"
        card_bg = "rgba(218, 225, 220, 0.4)"
        banner_bg = "#ffdad4"
        banner_text = "#3c0702"
        
    line_height = "1.5"
    font_size_msg = "15px"
    if font_scale == "Compact":
        line_height = "1.3"
        font_size_msg = "14px"
    elif font_scale == "Generous":
        line_height = "1.8"
        font_size_msg = "16px"

    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600&family=EB+Garamond:wght@500;600;700&display=swap');

        /* CSS Variables for Spacing System & Typography */
        :root {{
            --spacing-xs: clamp(4px, 0.5vw, 8px);
            --spacing-sm: clamp(8px, 1vw, 12px);
            --spacing-md: clamp(16px, 2vw, 24px);
            --spacing-lg: clamp(24px, 3vw, 32px);
            --spacing-xl: clamp(32px, 4vw, 48px);
            --radius-md: 12px;
            --radius-lg: 24px;
            --radius-pill: 9999px;
            --font-sm: clamp(11px, 1vw + 7px, 13px);
            --font-base: clamp(14px, 1.2vw + 10px, 16px);
            --font-lg: clamp(18px, 1.5vw + 12px, 22px);
            --font-xl: clamp(24px, 2.5vw + 16px, 32px);
        }}

        /* Global App Setup */
        .stApp {{
            background-color: {bg} !important;
            color: {text} !important;
            font-family: 'Be Vietnam Pro', sans-serif !important;
        }}
        [data-testid="stAppViewBlockContainer"] {{
            max-width: 100% !important; /* Fluid responsiveness */
            margin: 0 auto !important; 
            padding: 0px var(--spacing-lg) var(--spacing-lg) var(--spacing-lg) !important;
        }}

        /* Typography globally scaled */
        h1 {{ font-size: var(--font-xl) !important; margin-bottom: var(--spacing-sm) !important; }}
        h2 {{ font-size: var(--font-lg) !important; margin-bottom: var(--spacing-sm) !important; }}
        h3 {{ font-size: var(--font-base) !important; font-weight: 600 !important; margin-bottom: var(--spacing-xs) !important; }}
        p, span, label, div {{ font-size: var(--font-base); }}

        /* Sidebar Styling */
        [data-testid="stSidebar"] {{
            background-color: {sidebar_bg} !important;
            border-right: 1px solid {outline} !important;
            padding: 0 !important;
        }}
        [data-testid="stSidebarContent"] {{
            background-color: {sidebar_bg} !important;
            padding: var(--spacing-md) !important;
            gap: var(--spacing-sm) !important;
        }}
        
        /* Hide Default Streamlit Header options & deploy buttons */
        [data-testid="stHeader"] {{
            background-color: transparent !important;
            z-index: 999990 !important;
        }}
        [data-testid="stHeader"] [data-testid="stDeployButton"],
        [data-testid="stHeader"] button[title="View developer options"],
        [data-testid="stHeader"] [data-testid="stMainMenu"],
        [data-testid="stHeader"] button[kind="headerNoPadding"],
        button:has(+ button[kind="headerNoPadding"]),
        [data-testid="stHeader"] > div > div:nth-child(1) {{
            display: none !important;
            visibility: hidden !important;
            width: 0 !important;
            height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
            pointer-events: none !important;
        }}

        /* Hide Native Streamlit Sidebar Toggle (Hamburger Button) as it is handled by the custom header menu button */
        [data-testid="stSidebarCollapsedControl"] {{
            display: none !important;
        }}

        /* Sidebar close button — same base style as the open toggle */
        [data-testid="stSidebarHeader"] {{
            padding: var(--spacing-sm) var(--spacing-sm) 0 0 !important;
            display: flex !important;
            justify-content: flex-end !important;
        }}
        [data-testid="stSidebarHeader"] button {{
            background-color: {active_bg} !important;
            color: {primary} !important;
            border-radius: 50% !important;
            width: 44px !important;
            height: 44px !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            border: 1px solid {outline} !important;
            cursor: pointer !important;
            transition: all 0.2s ease-in-out !important;
            font-size: 0 !important;
        }}
        [data-testid="stSidebarHeader"] button:hover,
        [data-testid="stSidebarHeader"] button:focus-visible {{
            transform: scale(1.05) !important;
            background-color: {sidebar_bg} !important;
            outline: 2px solid {primary} !important;
        }}
        [data-testid="stSidebarHeader"] button * {{ 
            display: none !important;
        }}
        [data-testid="stSidebarHeader"] button::before {{
            content: "✕" !important;
            font-size: 18px !important;
            font-weight: bold !important;
            color: {primary} !important;
            display: block !important;
            line-height: 1 !important;
        }}

        /* Hide Default Footer */
        footer {{
            visibility: hidden !important;
            height: 0px !important;
        }}

        /* Buttons globally styled */
        .stButton>button {{
            border-radius: var(--radius-pill) !important;
            font-family: 'Be Vietnam Pro', sans-serif !important;
            font-weight: 500 !important;
            font-size: var(--font-base) !important;
            padding: var(--spacing-sm) var(--spacing-md) !important;
            border: 1px solid {outline} !important;
            background-color: {bg} !important;
            color: {text} !important;
            transition: all 0.2s ease-in-out !important;
            min-height: 44px !important; /* Accessibility */
        }}
        .stButton>button:hover, .stButton>button:focus-visible {{
            background-color: rgba(144, 70, 57, 0.08) !important;
            color: {primary} !important;
            border-color: {primary} !important;
        }}

        /* Active nav button styling */
        [data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"] {{
            color: {primary} !important;
            background-color: {active_bg} !important;
            border-radius: var(--radius-md) !important;
            font-weight: 600 !important;
            text-align: left !important;
            border: none !important;
            width: 100% !important;
            justify-content: flex-start !important;
        }}
        [data-testid="stSidebar"] [data-testid="stButton"] button[kind="secondary"] {{
            color: {text} !important;
            background-color: transparent !important;
            border-radius: var(--radius-md) !important;
            font-weight: 400 !important;
            text-align: left !important;
            border: none !important;
            width: 100% !important;
            justify-content: flex-start !important;
            transition: background-color 0.15s ease, color 0.15s ease !important;
        }}
        [data-testid="stSidebar"] [data-testid="stButton"] button[kind="secondary"]:hover,
        [data-testid="stSidebar"] [data-testid="stButton"] button[kind="secondary"]:focus-visible {{
            background-color: {active_bg} !important;
            color: {primary} !important;
        }}

        /* Ensure Reset Button stays styled correctly */
        div.sidebar-reset-btn [data-testid="stButton"] button {{
            background-color: {primary} !important;
            color: #ffffff !important;
            border: none !important;
            justify-content: center !important;
        }}

        /* Footer link buttons — styled as text links, not pill buttons */
        .st-key-footer_links .stButton>button {{
            background: transparent !important;
            border: none !important;
            color: {primary} !important;
            font-size: var(--font-sm) !important;
            font-weight: 500 !important;
            padding: 4px 8px !important;
            min-height: unset !important;
            border-radius: var(--radius-md) !important;
            text-decoration: underline !important;
            text-underline-offset: 3px !important;
        }}
        .st-key-footer_links .stButton>button:hover,
        .st-key-footer_links .stButton>button:focus-visible {{
            background-color: rgba(144, 70, 57, 0.08) !important;
            text-decoration: underline !important;
        }}
        .st-key-footer_links {{
            justify-content: center !important;
            padding-bottom: var(--spacing-xl) !important;
        }}

        /* Header Container */
        .st-key-main_header {{
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            align-items: center !important;
            justify-content: flex-start !important;
            gap: var(--spacing-md) !important;
            padding: var(--spacing-sm) 0 !important;
            border-bottom: 1px solid {outline} !important;
            margin-bottom: var(--spacing-lg) !important;
            min-height: 44px !important;
        }}
        
        /* All element containers should center vertically */
        .st-key-main_header > div {{
            display: flex !important;
            align-items: center !important;
            height: 100% !important;
            margin: 0 !important;
            padding: 0 !important;
        }}
        
        /* Header markdown content */
        .st-key-main_header [data-testid="stMarkdownContainer"] {{
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            flex: 1 !important;
            margin: 0 !important;
        }}
        
        .st-key-main_header [data-testid="stMarkdownContainer"] h2 {{
            margin: 0 !important;
            padding: 0 !important;
        }}
        
        /* Header icon buttons override style */
        .st-key-main_header .stButton {{
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            margin: 0 !important;
        }}
        
        .st-key-main_header .stButton>button {{
            border: none !important;
            background: transparent !important;
            font-size: 20px !important;
            padding: 0 !important;
            margin: 0 !important;
            width: 44px !important;
            height: 44px !important;
            border-radius: 50% !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            color: {text} !important;
            line-height: 1 !important;
        }}
        .st-key-main_header .stButton>button:hover {{
            background-color: {active_bg} !important;
        }}
        
        /* Chat Inputs custom CSS */
        [data-testid="stChatInput"] {{
            background-color: transparent !important;
            padding: 0 !important;
            margin-bottom: 0px !important;
        }}
        [data-testid="stChatInput"] > div {{
            border-radius: var(--radius-lg) !important;
            border: 1px solid {outline} !important;
            background-color: {bg} !important;
            padding: var(--spacing-sm) var(--spacing-md) !important;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
        }}
        [data-testid="stChatInput"] input,
        [data-testid="stChatInput"] textarea {{
            background-color: {bg} !important;
            color: {text} !important;
            font-family: 'Be Vietnam Pro', sans-serif !important;
            font-size: var(--font-base) !important;
            border: none !important;
        }}
        [data-testid="stChatInput"] textarea {{
            background-color: {bg} !important;
        }}
        
        /* Placeholder text styling - make it visible */
        [data-testid="stChatInput"] input::placeholder,
        [data-testid="stChatInput"] textarea::placeholder {{
            color: {primary} !important;
            opacity: 0.7 !important;
            font-weight: 500 !important;
        }}
        
        /* Checkbox list wrapper styles */
        .checklist-item {{
            margin-bottom: var(--spacing-xs);
        }}

        /* Remove aggressive padding on sticky bottom */
        [data-testid="stBottom"] {{
            background-color: transparent !important;
            padding-bottom: 0px !important;
            padding-top: 0px !important;
            margin: 0 !important;
            height: auto !important;
        }}
        [data-testid="stBottom"] > div {{
            padding: 0 !important;
            margin: 0 !important;
            height: auto !important;
        }}
        
        /* Reduce the artificial empty space injected by Streamlit below content */
        .st-emotion-cache-1rq2xuz {{
            display: none !important;
        }}

        /* Animations */
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(8px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        @keyframes pulse-gentle {{
            0%, 100% {{ opacity: 1; transform: scale(1); }}
            50% {{ opacity: 0.6; transform: scale(0.9); }}
        }}
        
        .organic-shape {{ border-radius: 60% 40% 30% 70% / 60% 30% 70% 40%; }}
        
        .tab-card, .privacy-banner {{
            background-color: {card_bg};
            padding: var(--spacing-md);
            border-radius: var(--radius-lg);
            margin-bottom: var(--spacing-md);
            box-shadow: 0 2px 6px rgba(0,0,0,0.05);
        }}
        .tab-card {{ border-left: 4px solid {primary}; }}
        .privacy-banner {{ 
            background-color: {banner_bg} !important;
            color: {banner_text} !important;
            border: 1px solid {outline} !important;
            display: flex;
            align-items: center;
            gap: var(--spacing-md);
        }}

        /* Chat Containers */
        .chat-bubble-container {{
            display: flex;
            margin-bottom: var(--spacing-md);
            animation: fadeIn 0.3s ease-out;
            gap: var(--spacing-sm);
        }}
        .user-chat-container {{ justify-content: flex-end; align-items: flex-end; }}
        .assistant-chat-container {{ justify-content: flex-start; align-items: flex-start; }}
        
        .chat-bubble {{
            font-family: 'Be Vietnam Pro', sans-serif !important;
            font-size: {font_size_msg} !important;
            line-height: {line_height} !important;
            padding: var(--spacing-sm) var(--spacing-md);
        }}
        .user-chat-bubble {{
            max-width: 80%;
            background-color: {sidebar_bg} !important;
            border-radius: var(--radius-lg) var(--radius-lg) 0px var(--radius-lg);
            border: 1px solid {outline} !important;
        }}
        .user-chat-text {{ color: {text} !important; margin: 0 !important; white-space: pre-line; }}
        
        .assistant-bubble-wrap {{
            max-width: 85%;
            display: flex;
            flex-direction: column;
            gap: var(--spacing-xs);
        }}
        .assistant-chat-bubble {{
            background-color: {card_bg} !important;
            border-radius: 0px var(--radius-lg) var(--radius-lg) var(--radius-lg);
            border: 1px solid {outline} !important;
            border-left: 4px solid {primary} !important;
            backdrop-filter: blur(4px);
        }}
        .assistant-chat-text, .assistant-chat-text ul, .assistant-chat-text li {{
            color: {text} !important;
            margin: 0 0 8px 0 !important;
        }}
        
        .chat-avatar {{
            width: 36px;
            height: 36px;
            flex-shrink: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
        }}
        .user-chat-avatar {{
            background-color: {active_bg} !important;
            font-size: var(--font-sm);
            color: {primary} !important;
            font-weight: bold;
        }}
        .assistant-chat-avatar {{ background-color: {sidebar_bg} !important; overflow: hidden; }}
        .assistant-chat-avatar img {{ width: 100%; height: 100%; object-fit: cover; }}
        
        .mood-detected-tag {{
            display: inline-flex;
            align-items: center;
            padding: 4px var(--spacing-sm);
            background-color: {bg} !important;
            border-radius: var(--radius-pill);
            border: 1px solid {outline} !important;
            font-size: var(--font-sm);
            opacity: 0.9;
        }}

        @media (max-width: 768px) {{
            .hide-on-mobile {{ display: none !important; }}
            [data-testid="stAppViewBlockContainer"] {{ padding: var(--spacing-sm) !important; }}
            .user-chat-bubble, .assistant-bubble-wrap {{ max-width: 95% !important; }}
            .st-key-main_header {{ flex-wrap: wrap !important; justify-content: center !important; gap: var(--spacing-sm) !important; }}

            /* Mobile: sidebar becomes a full-screen overlay */
            [data-testid="stSidebar"][aria-expanded="true"] {{
                width: 100vw !important;
                max-width: 100vw !important;
                min-width: 100vw !important;
                height: 100vh !important;
                position: fixed !important;
                top: 0 !important;
                left: 0 !important;
                z-index: 999998 !important;
            }}
            [data-testid="stSidebar"][aria-expanded="true"] [data-testid="stSidebarContent"] {{
                width: 100% !important;
                max-width: 100% !important;
                overflow-y: auto !important;
            }}
        }}
    </style>
    """, unsafe_allow_html=True)

# --- Chatbot API and Session Logic ---
class MentalHealthChatbot:
    def __init__(self):
        """Initialize the chatbot application."""
        if 'user_id' not in st.session_state:
            st.session_state.user_id = str(uuid.uuid4())
            st.session_state.start_time = datetime.now()
        self.chatbot = self.initialize_chatbot()

    def initialize_chatbot(self):
        """Initialize and return the Gemini chatbot instance."""
        API_KEY = os.getenv("GEMINI_API_KEY")
        if not API_KEY:
            st.error("Gemini API key not found. Please set the GEMINI_API_KEY environment variable in your .env file.", icon="🚨")
            st.stop()

        system_instruction = (
            "You are JeevaAI, a warm, empathetic AI mental health support companion. "
            "Your role is to listen, validate feelings, and offer gentle emotional support. "
            "You respond to ALL messages — including short greetings like hi or hello — with warmth and care. "
            "You ask thoughtful follow-up questions to understand how the user is feeling. "
            "You suggest evidence-based coping strategies when appropriate. "
            "You always remind users you are not a substitute for professional help when discussing serious issues. "
            "You never diagnose, prescribe, or give medical advice. "
            "Keep responses concise, warm, and conversational."
        )

        self._api_key = API_KEY
        self._system_instruction = system_instruction
        
        try:
            client = genai.Client(api_key=API_KEY)
            model_names = [
                "gemini-2.5-flash",
                "gemini-2.5-flash-preview-05-20",
                "gemini-2.0-flash",
                "gemini-1.5-flash",
            ]
            class ChatSession:
                def __init__(self, client, model, sys_prompt):
                    self.client = client
                    self.model = model
                    self.sys_prompt = sys_prompt
                    self.history = []

            # Check and select the first available model
            try:
                available = [m.name for m in client.models.list()]
                for model_name in model_names:
                    match = next((m for m in available if model_name in m), None)
                    if match:
                        chosen = match.replace("models/", "")
                        return ChatSession(client, chosen, system_instruction)
            except Exception:
                pass

            # Fallback
            return ChatSession(client, "gemini-2.5-flash", system_instruction)
        except Exception as e:
            st.error(f"Could not initialize Gemini client: {e}", icon="🔥")
            st.stop()

    def process_user_message(self, message):
        """Process a user message and generate a response."""
        if not self.chatbot:
            return "Sorry, the chatbot is not available right now."
        try:
            crisis_keywords = [
                "suicide", "kill myself", "end my life", "want to die",
                "harm myself", "hurt myself", "don't want to live", "no reason to live",
                "overdose", "hopeless and want out"
            ]
            crisis_detected = any(keyword in message.lower() for keyword in crisis_keywords)

            session = self.chatbot
            # Build conversation history
            contents = []
            for h in session.history:
                contents.append(types.Content(role=h["role"], parts=[types.Part(text=h["content"])]))
            contents.append(types.Content(role="user", parts=[types.Part(text=message)]))

            response = session.client.models.generate_content(
                model=session.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=session.sys_prompt,
                    temperature=0.7,
                )
            )
            response_text = response.text if response.text else "I'm here to listen. Could you tell me a bit more about that?"
            
            # Update history
            session.history.append({"role": "user", "content": message})
            session.history.append({"role": "model", "content": response_text})

            if crisis_detected:
                crisis_message = (
                    "**🚨 Important:** It sounds like you're going through immense pain right now. "
                    "Please know that you're not alone and help is available. "
                    "Reaching out is a sign of strength. Here are some resources that can provide immediate support:\n\n"
                    "- **Emergency:** Call **911** (US/Canada) or **112** (India) immediately.\n"
                    "- **988 Suicide & Crisis Lifeline:** Call or text **988** (US).\n"
                    "- **Crisis Text Line:** Text **HOME** to **741741**.\n"
                    "- **Befrienders Worldwide:** Find a helpline in your country: [https://www.befrienders.org](https://www.befrienders.org)\n\n"
                    "**Please reach out to one of these resources now.**"
                )
                response_text = crisis_message + "\n\n" + response_text

            return response_text

        except Exception as e:
            error_details = str(e).lower()
            logger.error("Gemini API error: %s", e, exc_info=True)

            # Classify as temporary or permanent
            if any(p in error_details for p in _TEMPORARY_PATTERNS):
                return _ERR_TEMPORARY + "The AI service has reached its temporary usage limit."
            elif any(p in error_details for p in _PERMANENT_PATTERNS):
                return _ERR_PERMANENT + "There is a configuration issue with the AI service credentials."
            else:
                # Unknown errors are treated as temporary to keep the UI recoverable
                return _ERR_TEMPORARY + "An unexpected issue occurred while contacting the AI service."

# --- Trigger Mood Response via Chip ---
def trigger_mood_response(mood_name):
    """Directly insert a mood entry and request response."""
    user_prompt = f"I'm feeling {mood_name} today."
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    _send_message_with_error_handling(user_prompt)
    st.rerun()

# --- Main App Presentation ---
def main():
    # Session state settings defaults
    if 'theme' not in st.session_state:
        st.session_state.theme = "Classic Linen"
    if 'font_scale' not in st.session_state:
        st.session_state.font_scale = "Spacious"
    if 'active_tab' not in st.session_state:
        st.session_state.active_tab = "Sanctuary"
    if 'journal_entries' not in st.session_state:
        st.session_state.journal_entries = []
    if 'breathing_cycles' not in st.session_state:
        st.session_state.breathing_cycles = 0
    if 'grounding_completed' not in st.session_state:
        st.session_state.grounding_completed = 0
    if 'ambiance_sound' not in st.session_state:
        st.session_state.ambiance_sound = "Silence"
    if 'show_menu' not in st.session_state:
        st.session_state.show_menu = True
    if 'sidebar_state' not in st.session_state:
        st.session_state.sidebar_state = "collapsed"

    st.set_page_config(
        page_title="Jeeva | Your Digital Sanctuary",
        page_icon="🧘‍♀️",
        layout="wide",
        initial_sidebar_state=st.session_state.sidebar_state
    )

    inject_custom_css(st.session_state.theme, st.session_state.font_scale)

    # --- Initialize Databases and Clients ---
    needs_init = 'sentiment_db' not in st.session_state or 'chatbot_instance' not in st.session_state
    
    if needs_init:
        loading_placeholder = st.empty()
        with loading_placeholder.container():
            st.markdown("""
            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 60vh;">
                <div class="organic-shape" style="width: 80px; height: 80px; background-color: #dae1dc; display: flex; align-items: center; justify-content: center; margin-bottom: var(--spacing-lg); animation: pulse-gentle 2s infinite ease-in-out;">
                    <img style="width: 50px; height: 50px; object-fit: contain;" src="https://lh3.googleusercontent.com/aida-public/AB6AXuBQY_GSE4_mVilWsvM9XIyTVBkeDrSxPibyX7Lqk2F22p04HkG0vXBqWM9FZRx6I60X_0Hg8OsbIAhfMrz6BGhWRZFl-QBI6b5Tl_l9-t_EkeWkenCe_BHwWC7g0ftn-dWeHAtsyh0-wrJWp8aQXjQD3czsoI9j5eOyhYlXkdoe4lz06vOAEDYDmGxJyHaGFH_KHh5yRiANIMEuxCoG2Q-6S7IxDbLiQ8HCuMbUXvuoaSdnxoN_nmY5DA" alt="Logo"/>
                </div>
                <h2 style="font-family: 'EB Garamond', serif; font-weight: 500; color: #904639; margin-bottom: var(--spacing-xs);">Preparing your Sanctuary...</h2>
                <p style="font-family: 'Be Vietnam Pro', sans-serif; color: #59605c;">Breathing life into the space.</p>
            </div>
            """, unsafe_allow_html=True)
            
        if 'sentiment_db' not in st.session_state:
            try:
                db = SentimentVectorDatabase()
                db.load_database()
                st.session_state.sentiment_db = db
            except Exception as e:
                # Fallback: create database without loading external models
                logger.warning(f"Error initializing SentimentVectorDatabase: {e}")
                st.session_state.sentiment_db = None
                st.warning("⚠️ Sentiment analysis temporarily unavailable. Core chat features are still working!")

        if 'chatbot_instance' not in st.session_state:
            st.session_state.chatbot_instance = MentalHealthChatbot()

        if 'messages' not in st.session_state:
            st.session_state.messages = [{
                "role": "assistant",
                "content": "Hello there! I'm JeevaAI, ready to listen whenever you'd like to share.\n\nHow are you feeling today? Remember to take a deep breath as you write.",
                "detected_mood": "Neutral 🧘‍♀️"
            }]
            
        loading_placeholder.empty()

    # --- SIDEBAR PRESENTATION ---
    with st.sidebar:
        # Brand Header
        st.markdown("""
        <div style="text-align: center; margin-bottom: 16px; border-bottom: 1px solid #dac1bd; padding-bottom: 16px;">
            <div class="organic-shape" style="width: 60px; height: 60px; background-color: #eae8e5; display: flex; align-items: center; justify-content: center; margin: 0 auto 12px auto; overflow: hidden;">
                <img style="width: 36px; height: 36px; object-fit: contain;" src="https://lh3.googleusercontent.com/aida-public/AB6AXuBQY_GSE4_mVilWsvM9XIyTVBkeDrSxPibyX7Lqk2F22p04HkG0vXBqWM9FZRx6I60X_0Hg8OsbIAhfMrz6BGhWRZFl-QBI6b5Tl_l9-t_EkeWkenCe_BHwWC7g0ftn-dWeHAtsyh0-wrJWp8aQXjQD3czsoI9j5eOyhYlXkdoe4lz06vOAEDYDmGxJyHaGFH_KHh5yRiANIMEuxCoG2Q-6S7IxDbLiQ8HCuMbUXvuoaSdnxoN_nmY5DA" alt="Logo"/>
            </div>
            <h1 style="font-family: 'EB Garamond', serif; font-size: 28px; font-weight: 500; color: #904639; margin: 0;">Jeeva</h1>
            <p style="font-family: 'Be Vietnam Pro', sans-serif; font-size: 13px; color: #59605c; margin: 4px 0 0 0; letter-spacing: 0.05em; font-weight: 600;">YOUR DIGITAL SANCTUARY</p>
        </div>
        """, unsafe_allow_html=True)

        # Nav Links rendered as interactive State Buttons
        tabs = [
            ("Sanctuary", "🌱 Sanctuary"),
            ("Journal", "📝 Journal"),
            ("Resources", "🤝 Resources"),
            ("Stats", "📊 Stats"),
            ("Settings", "⚙️ Settings")
        ]
        for tab_id, tab_label in tabs:
            is_active = (st.session_state.active_tab == tab_id)
            btn_type = "primary" if is_active else "secondary"
            if st.button(tab_label, key=f"nav_tab_{tab_id}", use_container_width=True, type=btn_type):
                st.session_state.active_tab = tab_id
                st.rerun()

        # Today's Pulse Widget
        mins_active = int((datetime.now() - st.session_state.start_time).total_seconds() / 60)
        feelings_count = len([m for m in st.session_state.messages if m["role"] == "user"])
        
        st.markdown(f"""
        <div style="background-color: #ffffff; padding: 14px; border-radius: 14px; border: 1px solid rgba(218, 225, 220, 0.7); margin-top: 12px; margin-bottom: 16px;">
            <h3 style="font-family: 'Be Vietnam Pro', sans-serif; font-size: 11px; color: #5d6460; text-transform: uppercase; tracking-wider: 0.05em; margin: 0 0 10px 0; font-weight: 600;">Today's Pulse</h3>
            <div style="display: flex; align-items: center; gap: 8px; font-size: 13px; margin-bottom: 6px; color: #1b1c1a;">
                <span>⏱️</span> Session Time: {mins_active} mins active
            </div>
            <div style="display: flex; align-items: center; gap: 8px; font-size: 13px; color: #1b1c1a;">
                <span>💖</span> Feelings Shared: {feelings_count}
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Mood Check-in
        st.markdown('<p style="font-family: \'Be Vietnam Pro\', sans-serif; font-size: 13px; font-weight: 600; color: #5d6460; margin-bottom: 8px;">Checking in: How is your mind today?</p>', unsafe_allow_html=True)
        with st.container(horizontal=True):
            if st.button("🍃 Peaceful", key="sc_peaceful", use_container_width=True):
                trigger_mood_response("Peaceful 🍃")
            if st.button("☁️ Heavy", key="sc_heavy", use_container_width=True):
                trigger_mood_response("Heavy ☁️")
            if st.button("☀️ Bright", key="sc_bright", use_container_width=True):
                trigger_mood_response("Bright ☀️")
            if st.button("🌊 Calm", key="sc_calm", use_container_width=True):
                trigger_mood_response("Calm 🌊")
            if st.button("⚡ Restless", key="sc_restless", use_container_width=True):
                trigger_mood_response("Restless ⚡")

        # Self-Care Checklist
        st.markdown('<p style="font-family: \'Be Vietnam Pro\', sans-serif; font-size: 13px; font-weight: 600; color: #5d6460; margin-top: 12px; margin-bottom: 8px;">Self-Care Checklist</p>', unsafe_allow_html=True)
        task_1 = st.checkbox("Deep breathing exercise", value=st.session_state.breathing_cycles > 0, key="chk_1")
        task_2 = st.checkbox("Hydrate mindfully", value=False, key="chk_2")

        # Crisis Support Panel
        st.markdown("""
        <div style="background-color: rgba(186, 26, 26, 0.08); border: 1px solid #ffdad6; border-radius: 14px; padding: 14px; margin-top: 12px; margin-bottom: 16px;">
            <h4 style="font-family: 'Be Vietnam Pro', sans-serif; font-size: 13px; color: #ba1a1a; margin: 0 0 6px 0; font-weight: 600; display: flex; align-items: center; gap: 6px;">
                🚨 Immediate Support
            </h4>
            <ul style="margin: 0; padding: 0; list-style: none; font-size: 11px; color: #93000a; line-height: 1.5;">
                <li style="display:flex; justify-content:space-between;"><span>India</span> <strong>1800-599-0019</strong></li>
                <li style="display:flex; justify-content:space-between;"><span>US/Canada: Helpline</span> <strong>988</strong></li>
                <li style="display:flex; justify-content:space-between;"><span>UK: Emergency</span> <strong>111</strong></li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

        # Reset button
        st.markdown('<div class="sidebar-reset-btn">', unsafe_allow_html=True)
        if st.button("🔄 Reset Session", key="reset_chat_session"):
            st.session_state.messages = [{
                "role": "assistant",
                "content": "Starting fresh! I'm here and ready to listen. What's on your mind?",
                "detected_mood": "Neutral 🧘‍♀️"
            }]
            st.session_state.journal_entries = []
            st.session_state.breathing_cycles = 0
            st.session_state.grounding_completed = 0
            st.session_state.start_time = datetime.now()
            st.session_state.active_tab = "Sanctuary"
            st.toast("Sanctuary session reset successfully!", icon="🍃")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # --- MAIN HEADER BAR (TopAppBar) ---
    with st.container(horizontal=True, key="main_header"):
        # Menu button on the left
        if st.button("☰", key="btn_menu"):
            st.session_state.sidebar_state = (
                "collapsed" if st.session_state.sidebar_state == "expanded" else "expanded"
            )
            st.rerun()
        
        st.markdown("""
        <div style="display: flex; align-items: center; justify-content: center; flex: 1;">
            <h2 style="font-family: 'EB Garamond', serif; font-weight: 500; color: #904639; margin: 0; padding: 0;">Jeeva <span style="color: #59605c; font-size: var(--font-sm); font-weight: normal; font-style: italic;" class="hide-on-mobile">• Sitting with you</span></h2>
        </div>
        """, unsafe_allow_html=True)
        
        # We add the buttons directly. The CSS header-btn-wrap class handles their specific overrides.
        if st.button("🔔", key="btn_notify"):
            st.toast("Self-care tip: Take a slow deep breath in for 4 seconds, and release.", icon="🍃")
            
        if st.button("👤", key="btn_profile"):
            st.toast("Privacy Mode Active: No tracking or data is stored on a server.", icon="🔒")

    # --- CONDITIONAL CANVAS RENDERING ---
    active_tab = st.session_state.active_tab

    # 1. SANCTUARY TAB (CHAT COMPONENT)
    if active_tab == "Sanctuary":
        # Privacy Banner
        st.markdown("""
        <div class="privacy-banner" style="display: flex; align-items: center; gap: 20px; position: relative; overflow: hidden; margin-bottom: 24px; padding: 20px;">
            <div style="position: relative; z-index: 10; flex: 1;">
                <h3 style="font-family: 'EB Garamond', serif; font-size: 20px; font-weight: 500; margin: 0 0 4px 0;">Your space, your rules.</h3>
                <p style="font-family: 'Be Vietnam Pro', sans-serif; font-size: 14px; margin: 0; opacity: 0.9; line-height: 1.5;">Every word shared here is anchored in total anonymity. We do not store your identity, only your progress toward peace. You are safe to be seen as you are.</p>
            </div>
            <div style="font-size: 48px; opacity: 0.15; flex-shrink: 0;">🛡️</div>
        </div>
        """, unsafe_allow_html=True)

        # Render Chat logs
        for message in st.session_state.messages:
            if message["role"] == "user":
                safe_msg = html.escape(message["content"])
                st.markdown(f"""
                <div class="chat-bubble-container user-chat-container">
                    <div class="chat-bubble user-chat-bubble">
                        <p class="chat-text user-chat-text">{safe_msg}</p>
                    </div>
                    <div class="chat-avatar user-chat-avatar">ME</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                # Check if this is an error-marker message
                err_type = message.get("error_type")
                if err_type:
                    render_error_recovery_card(err_type, theme=st.session_state.theme)
                else:
                    formatted_html = markdown_to_html(message["content"])
                    detected_mood = message.get("detected_mood", "Neutral 🧘‍♀️")
                    st.markdown(f"""
                    <div class="chat-bubble-container assistant-chat-container">
                        <div class="organic-shape chat-avatar assistant-chat-avatar">
                            <img src="https://lh3.googleusercontent.com/aida-public/AB6AXuCCurhPkDhZwxbyxMQLgheyl4Nsdu6tTk8Ny9AA6MSJae5j0eDDOhexuS6SOBVJJH6pPi3fGkg_BPeWJ2GUU6A--eMqu3pvqqWtH_LQm6WFqf-EpQpLsTPcwCy9fN2L4dtG-VKw3WUOIg1QcK2NAsn1m_dQ2JQDD43y3itiDxHnpRaEqAMNeYNei2YTp2X6lQRZRHvYiGHdynTMIDMjqmcRAuiHegSLzIAix3M2X0DpEyvqxq8KE0TP_Q"/>
                        </div>
                        <div class="assistant-bubble-wrap">
                            <div class="chat-bubble assistant-chat-bubble">
                                <p class="chat-text assistant-chat-text">{formatted_html}</p>
                                <div class="mood-detected-tag">
                                    <span>Primary mood detected: {detected_mood}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

        # suggestions — only show when the last message is NOT an error
        last_msg = st.session_state.messages[-1] if st.session_state.messages else None
        if last_msg and last_msg["role"] == "assistant" and not last_msg.get("error_type"):
            st.markdown("<p style='font-family: \"Be Vietnam Pro\", sans-serif; font-size: 13px; font-weight: 600; color: #904639; margin: 24px 0 8px 0; text-transform: uppercase; letter-spacing: 0.05em;'>Reflective Steps:</p>", unsafe_allow_html=True)
            suggestions = [
                ("🧘 Try grounding exercise", "Let's do a quick grounding exercise together."),
                ("🌊 I feel overwhelmed", "I'm feeling really overwhelmed right now."),
                ("💡 Tell me more about coping", "Can you tell me more about coping strategies?")
            ]
            with st.container(horizontal=True):
                for idx, (label, prompt) in enumerate(suggestions):
                    if st.button(label, key=f"sugg_{idx}", use_container_width=True):
                        st.session_state.messages.append({"role": "user", "content": prompt})
                        _send_message_with_error_handling(prompt)
                        st.rerun()

        # Chat Input Box
        if user_input := st.chat_input(placeholder="Talk to Jeeva about how you're feeling today..."):
            st.session_state.messages.append({"role": "user", "content": user_input})
            _send_message_with_error_handling(user_input)
            st.rerun()

        # Handle pending retry from error recovery button
        if st.session_state.get("pending_retry"):
            retry_msg = st.session_state.pop("pending_retry")
            st.session_state.messages.append({"role": "user", "content": retry_msg})
            _send_message_with_error_handling(retry_msg)
            st.rerun()

    # 2. JOURNAL TAB (INTERACTIVE COMPONENT)
    elif active_tab == "Journal":
        st.markdown("<h2 style='font-family: \"EB Garamond\", serif; font-size: 28px; color: #904639; margin-bottom: 8px;'>Sanctuary Journal</h2>", unsafe_allow_html=True)
        st.markdown("<p style='font-size: 15px; color:#59605c; line-height:1.6;'>Writing helps externalize thoughts. Use this private canvas to log your feelings and keep a history of your reflections.</p>", unsafe_allow_html=True)
        
        # Form to add entry
        with st.form("journal_form", clear_on_submit=True):
            j_title = st.text_input("Reflection Title", placeholder="Give your entry a title...")
            j_content = st.text_area("Your thoughts...", placeholder="Write freely, without judgment or filters...", height=150)
            j_mood = st.select_slider("Primary tone of this entry", options=["Sadness", "Heavy", "Anxiety", "Neutral", "Calm", "Peaceful", "Bright", "Joy"], value="Neutral")
            
            submit_journal = st.form_submit_button("📁 Save Reflection")
            if submit_journal:
                if j_title.strip() == "" or j_content.strip() == "":
                    st.error("Please fill in both the title and content before saving.", icon="⚠️")
                else:
                    st.session_state.journal_entries.insert(0, {
                        "title": j_title,
                        "content": j_content,
                        "mood": j_mood,
                        "date": datetime.now().strftime("%B %d, %Y at %I:%M %p")
                    })
                    st.toast("Journal entry saved successfully!", icon="📝")
                    st.rerun()

        # Display history
        st.markdown("<h3 style='font-family: \"EB Garamond\", serif; font-size: 22px; color: #904639; margin: 24px 0 12px 0;'>Previous Reflections</h3>", unsafe_allow_html=True)
        if not st.session_state.journal_entries:
            st.markdown("<div style='text-align:center; padding: 30px; color:#59605c; border: 1px dashed #dac1bd; border-radius: 16px;'>Your journal is currently empty. Complete your first entry above to see it logged.</div>", unsafe_allow_html=True)
        else:
            for entry in st.session_state.journal_entries:
                st.markdown(f"""
                <div class="tab-card">
                    <h4 style="font-family: 'EB Garamond', serif; font-size: 20px; font-weight: 600; color: #904639; margin: 0 0 4px 0;">{entry['title']}</h4>
                    <p style="font-size: 12px; color: #59605c; margin: 0 0 12px 0;">{entry['date']} • Feeling: <strong>{entry['mood']}</strong></p>
                    <p style="font-size: 14px; line-height: 1.6; margin: 0; white-space: pre-line;">{entry['content']}</p>
                </div>
                """, unsafe_allow_html=True)

    # 3. RESOURCES TAB (INTERACTIVE EXERCISES)
    elif active_tab == "Resources":
        st.markdown("<h2 style='font-family: \"EB Garamond\", serif; font-size: 28px; color: #904639; margin-bottom: 8px;'>Wellness & Grounding Space</h2>", unsafe_allow_html=True)
        st.markdown("<p style='font-size: 15px; color:#59605c; line-height:1.6;'>When anxiety peaks or your mind wanders, grounding exercises help anchor you back to the present moment.</p>", unsafe_allow_html=True)

        res_tabs = st.tabs(["🌬️ Box Breathing", "🧠 5-4-3-2-1 Grounding"])
        
        # 3a. Box Breathing Guide
        with res_tabs[0]:
            st.markdown("<h3 style='font-family: \"EB Garamond\", serif; font-size: 22px; color: #904639; margin: 12px 0;'>Interactive Box Breathing</h3>", unsafe_allow_html=True)
            st.markdown("""
            A powerful technique used to reset the nervous system. Follow these four simple steps:
            1. **Inhale** slowly for **4 seconds** 🌬️
            2. **Hold** your breath for **4 seconds** 🛑
            3. **Exhale** fully for **4 seconds** 💨
            4. **Hold** empty for **4 seconds** 🛑
            """)
            
            b_cols = st.columns(2)
            with b_cols[0]:
                st.markdown(f"""
                <div style="background-color:rgba(144, 70, 57, 0.05); border: 2px solid #dac1bd; padding:20px; border-radius:24px; text-align:center;">
                    <div style="font-size: 32px;">🧘‍♀️</div>
                    <h4 style="margin: 8px 0; color:#904639;">Breathing Cycle</h4>
                    <p style="font-size: 14px; color:#59605c; margin: 0;">Completed Cycles: <strong>{st.session_state.breathing_cycles}</strong></p>
                </div>
                """, unsafe_allow_html=True)
            
            with b_cols[1]:
                st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
                if st.button("💨 Complete One Breathing Cycle", use_container_width=True):
                    st.session_state.breathing_cycles += 1
                    st.toast("Great job! Keep breathing mindfully.", icon="🧘‍♀️")
                    st.rerun()
                if st.button("🔄 Reset Breathing Tracker", use_container_width=True):
                    st.session_state.breathing_cycles = 0
                    st.rerun()

        # 3b. 5-4-3-2-1 Grounding Exercise
        with res_tabs[1]:
            st.markdown("<h3 style='font-family: \"EB Garamond\", serif; font-size: 22px; color: #904639; margin: 12px 0;'>5-4-3-2-1 Grounding Technique</h3>", unsafe_allow_html=True)
            st.markdown("Anchor yourself by engaging your five senses. Focus on your surroundings and fill out the fields below:")
            
            with st.form("grounding_form"):
                g1 = st.text_input("👁️ 5 things you can SEE around you", placeholder="e.g. A green plant, a window, a coffee cup...")
                g2 = st.text_input("🖐️ 4 things you can TOUCH/FEEL", placeholder="e.g. Smooth desk surface, keys, texture of my shirt...")
                g3 = st.text_input("👂 3 things you can HEAR", placeholder="e.g. Distant traffic, hum of the AC, birds chirping...")
                g4 = st.text_input("👃 2 things you can SMELL", placeholder="e.g. Coffee brewing, fresh laundry, rain...")
                g5 = st.text_input("👅 1 thing you can TASTE", placeholder="e.g. Mint, toothpaste, water...")
                
                submit_grounding = st.form_submit_button("🌱 Complete Grounding Exercise")
                if submit_grounding:
                    if not (g1 and g2 and g3 and g4 and g5):
                        st.error("Please fill out all five sensory inputs to complete the grounding cycle.", icon="⚠️")
                    else:
                        st.session_state.grounding_completed += 1
                        st.toast("You are grounded. You are present. You are safe. 💖", icon="🌸")
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": f"**Grounding Completed:** Good job checking in with your senses. You observed:\n- **Sight:** {g1}\n- **Touch:** {g2}\n- **Hearing:** {g3}\n- **Smell:** {g4}\n- **Taste:** {g5}\n\nHow do you feel after anchoring yourself?",
                            "detected_mood": "Calm 🌊"
                        })
                        st.session_state.active_tab = "Sanctuary"
                        st.rerun()

    # 4. STATS TAB (DYNAMIC ANALYTICS)
    elif active_tab == "Stats":
        st.markdown("<h2 style='font-family: \"EB Garamond\", serif; font-size: 28px; color: #904639; margin-bottom: 8px;'>Your Sanctuary Pulse</h2>", unsafe_allow_html=True)
        st.markdown("<p style='font-size: 15px; color:#59605c; line-height:1.6;'>Review the patterns of your session. This data is calculated dynamically and stays entirely private in this window.</p>", unsafe_allow_html=True)

        s_col1, s_col2 = st.columns(2)
        with s_col1:
            st.markdown(f"""
            <div class="tab-card" style="text-align:center;">
                <div style="font-size: 32px;">⏱️</div>
                <h4 style="margin: 8px 0; color:#904639;">Session Duration</h4>
                <h2 style="margin: 0; font-size: 28px;">{mins_active} <span style="font-size:16px; color:#59605c;">mins</span></h2>
            </div>
            """, unsafe_allow_html=True)
        
        with s_col2:
            checklist_items_done = sum([1 if task_1 else 0, 1 if task_2 else 0])
            total_actions = st.session_state.breathing_cycles + st.session_state.grounding_completed + checklist_items_done
            st.markdown(f"""
            <div class="tab-card" style="text-align:center;">
                <div style="font-size: 32px;">🌱</div>
                <h4 style="margin: 8px 0; color:#904639;">Self-Care Actions</h4>
                <h2 style="margin: 0; font-size: 28px;">{total_actions} <span style="font-size:16px; color:#59605c;">completed</span></h2>
            </div>
            """, unsafe_allow_html=True)

        # Mood Distribution Analysis
        st.markdown("<h3 style='font-family: \"EB Garamond\", serif; font-size: 22px; color: #904639; margin: 20px 0 12px 0;'>Emotional Distribution</h3>", unsafe_allow_html=True)
        mood_counts = {}
        total_moods = 0
        for m in st.session_state.messages:
            if m["role"] == "assistant" and "detected_mood" in m:
                mood_clean = m["detected_mood"].split(" ")[0].capitalize()
                mood_counts[mood_clean] = mood_counts.get(mood_clean, 0) + 1
                total_moods += 1
        
        if total_moods == 0:
            st.markdown("<div style='text-align:center; padding: 20px; color:#59605c; border: 1px dashed #dac1bd; border-radius: 12px;'>Share some feelings in the Sanctuary to see a breakdown of your moods.</div>", unsafe_allow_html=True)
        else:
            for mood_name, count in mood_counts.items():
                percentage = int((count / total_moods) * 100)
                st.write(f"**{mood_name}** ({percentage}%)")
                st.progress(count / total_moods)

    # 5. SETTINGS TAB (PERSONALIZATION)
    elif active_tab == "Settings":
        st.markdown("<h2 style='font-family: \"EB Garamond\", serif; font-size: 28px; color: #904639; margin-bottom: 8px;'>Sanctuary Settings</h2>", unsafe_allow_html=True)
        st.markdown("<p style='font-size: 15px; color:#59605c; line-height:1.6;'>Adjust the sanctuary aesthetics and line parameters to suit your cognitive load.</p>", unsafe_allow_html=True)
        
        st.markdown("<h3 style='font-family: \"EB Garamond\", serif; font-size: 22px; color: #904639; margin: 20px 0 12px 0;'>Theme Options</h3>", unsafe_allow_html=True)
        theme_opt = st.selectbox(
            "Sanctuary Aesthetic Palette", 
            options=["Classic Linen", "Sage Meadow", "Deep Ocean"],
            index=["Classic Linen", "Sage Meadow", "Deep Ocean"].index(st.session_state.theme)
        )
        if theme_opt != st.session_state.theme:
            st.session_state.theme = theme_opt
            st.rerun()

        st.markdown("<h3 style='font-family: \"EB Garamond\", serif; font-size: 22px; color: #904639; margin: 20px 0 12px 0;'>Typography & Layout</h3>", unsafe_allow_html=True)
        font_opt = st.select_slider(
            "Line Spacing & Density Scale", 
            options=["Compact", "Spacious", "Generous"],
            value=st.session_state.font_scale
        )
        if font_opt != st.session_state.font_scale:
            st.session_state.font_scale = font_opt
            st.rerun()

        st.markdown("<h3 style='font-family: \"EB Garamond\", serif; font-size: 22px; color: #904639; margin: 20px 0 12px 0;'>Audio Ambience Simulation</h3>", unsafe_allow_html=True)
        aud_opt = st.selectbox(
            "Select comforting background simulator sound", 
            options=["Silence", "Forest Birds", "Wind Chimes", "Gentle Rain"],
            index=["Silence", "Forest Birds", "Wind Chimes", "Gentle Rain"].index(st.session_state.ambiance_sound)
        )
        if aud_opt != st.session_state.ambiance_sound:
            st.session_state.ambiance_sound = aud_opt
            if aud_opt != "Silence":
                st.toast(f"Comforting sound: Simulating '{aud_opt}' in the background.", icon="🎵")
            st.rerun()

        # Wipe option
        st.markdown("<h3 style='font-family: \"EB Garamond\", serif; font-size: 22px; color: #ba1a1a; margin: 30px 0 12px 0;'>Danger Zone</h3>", unsafe_allow_html=True)
        if st.button("🗑️ Wipe All Session Data Permanently", key="danger_wipe"):
            st.session_state.messages = [{
                "role": "assistant",
                "content": "All data wiped. Let's start fresh together. How are you feeling today?",
                "detected_mood": "Neutral 🧘‍♀️"
            }]
            st.session_state.journal_entries = []
            st.session_state.breathing_cycles = 0
            st.session_state.grounding_completed = 0
            st.session_state.start_time = datetime.now()
            st.session_state.theme = "Classic Linen"
            st.session_state.font_scale = "Spacious"
            st.session_state.active_tab = "Sanctuary"
            st.toast("All session data wiped completely!", icon="🗑️")
            st.rerun()

    # 6. TERMS OF SERVICE (Hidden page — accessible via footer)
    elif active_tab == "Terms":
        if st.button("← Back", key="back_from_terms"):
            st.session_state.active_tab = "Sanctuary"
            st.rerun()
        st.markdown("<h2 style='font-family: \"EB Garamond\", serif; font-size: 28px; color: #904639; margin-bottom: 8px;'>Terms of Service</h2>", unsafe_allow_html=True)
        st.markdown("""
        <div class="tab-card">
            <h3 style="font-family: 'EB Garamond', serif; color: #904639; margin-bottom: var(--spacing-sm);">1. Acceptance of Terms</h3>
            <p style="color: #59605c; line-height: 1.6;">By accessing and using Jeeva, you agree to be bound by these Terms of Service. If you do not agree to these terms, please discontinue use of the application.</p>
        </div>
        <div class="tab-card">
            <h3 style="font-family: 'EB Garamond', serif; color: #904639; margin-bottom: var(--spacing-sm);">2. Nature of the Service</h3>
            <p style="color: #59605c; line-height: 1.6;">Jeeva is an AI-powered emotional support companion. It is <strong>not</strong> a licensed mental health provider, therapist, or medical service. It does not diagnose, treat, or cure any medical or psychological condition. Always consult a qualified professional for clinical needs.</p>
        </div>
        <div class="tab-card">
            <h3 style="font-family: 'EB Garamond', serif; color: #904639; margin-bottom: var(--spacing-sm);">3. User Responsibilities</h3>
            <p style="color: #59605c; line-height: 1.6;">You are solely responsible for the content you share. You agree not to use Jeeva to generate harmful, abusive, or illegal content. If you are in crisis, please contact emergency services or a crisis helpline immediately.</p>
        </div>
        <div class="tab-card">
            <h3 style="font-family: 'EB Garamond', serif; color: #904639; margin-bottom: var(--spacing-sm);">4. Limitation of Liability</h3>
            <p style="color: #59605c; line-height: 1.6;">Jeeva and its creators are not liable for any actions taken based on the AI's responses. Use the service at your own discretion. The service is provided "as is" without warranty of any kind.</p>
        </div>
        """, unsafe_allow_html=True)

    # 7. PRIVACY POLICY (Hidden page — accessible via footer)
    elif active_tab == "Privacy":
        if st.button("← Back", key="back_from_privacy"):
            st.session_state.active_tab = "Sanctuary"
            st.rerun()
        st.markdown("<h2 style='font-family: \"EB Garamond\", serif; font-size: 28px; color: #904639; margin-bottom: 8px;'>Privacy Policy</h2>", unsafe_allow_html=True)
        st.markdown("""
        <div class="tab-card">
            <h3 style="font-family: 'EB Garamond', serif; color: #904639; margin-bottom: var(--spacing-sm);">Your Privacy Matters</h3>
            <p style="color: #59605c; line-height: 1.6;">Jeeva is designed with privacy at its core. We believe your emotional well-being journey should remain entirely yours.</p>
        </div>
        <div class="tab-card">
            <h3 style="font-family: 'EB Garamond', serif; color: #904639; margin-bottom: var(--spacing-sm);">Data Collection</h3>
            <p style="color: #59605c; line-height: 1.6;">
                <strong>Session-only data:</strong> All conversation history, journal entries, and settings exist only within your current browser session. Nothing is transmitted to or stored on any external server.<br><br>
                <strong>No personal identifiers:</strong> Jeeva does not collect your name, email, location, IP address, or any personally identifiable information.<br><br>
                <strong>No tracking or analytics:</strong> We do not use cookies, analytics trackers, or advertising pixels.
            </p>
        </div>
        <div class="tab-card">
            <h3 style="font-family: 'EB Garamond', serif; color: #904639; margin-bottom: var(--spacing-sm);">AI Interactions</h3>
            <p style="color: #59605c; line-height: 1.6;">Your messages are processed by the Google Gemini API to generate responses. Messages are sent in real-time and are subject to Google's own data handling policies. We do not store or log these conversations on our end.</p>
        </div>
        <div class="tab-card">
            <h3 style="font-family: 'EB Garamond', serif; color: #904639; margin-bottom: var(--spacing-sm);">Data Retention</h3>
            <p style="color: #59605c; line-height: 1.6;">When you close your browser tab or reset your session, all data is permanently erased. There is no server-side backup or recovery mechanism.</p>
        </div>
        """, unsafe_allow_html=True)

    # 8. CRISIS RESOURCES (Hidden page — accessible via footer)
    elif active_tab == "Crisis":
        if st.button("← Back", key="back_from_crisis"):
            st.session_state.active_tab = "Sanctuary"
            st.rerun()
        st.markdown("<h2 style='font-family: \"EB Garamond\", serif; font-size: 28px; color: #904639; margin-bottom: 8px;'>Crisis Resources</h2>", unsafe_allow_html=True)
        st.markdown("<p style='font-size: 15px; color:#59605c; line-height:1.6; margin-bottom: var(--spacing-md);'>If you or someone you know is in immediate danger, please contact emergency services. Below are trusted crisis support resources available around the clock.</p>", unsafe_allow_html=True)

        st.markdown("""
        <div class="tab-card" style="border-left-color: #ba1a1a;">
            <h3 style="font-family: 'EB Garamond', serif; color: #ba1a1a; margin-bottom: var(--spacing-sm);">🚨 Emergency Services</h3>
            <p style="color: #59605c; line-height: 1.8;">
                <strong>India:</strong> 112 (Emergency) · iCall: 9152987821<br>
                <strong>US / Canada:</strong> 911 (Emergency) · 988 (Suicide & Crisis Lifeline)<br>
                <strong>UK:</strong> 999 (Emergency) · 116 123 (Samaritans)<br>
                <strong>Australia:</strong> 000 (Emergency) · 13 11 14 (Lifeline)
            </p>
        </div>
        <div class="tab-card" style="border-left-color: #ba1a1a;">
            <h3 style="font-family: 'EB Garamond', serif; color: #ba1a1a; margin-bottom: var(--spacing-sm);">📞 Crisis Helplines</h3>
            <p style="color: #59605c; line-height: 1.8;">
                <strong>Vandrevala Foundation (India):</strong> 1800-599-0019 (24/7, toll-free)<br>
                <strong>AASRA (India):</strong> 91-22-27546669<br>
                <strong>Crisis Text Line (US):</strong> Text HOME to 741741<br>
                <strong>Befrienders Worldwide:</strong> <a href="https://www.befrienders.org" target="_blank" style="color: #904639;">befrienders.org</a> — Find a helpline in your country
            </p>
        </div>
        <div class="tab-card">
            <h3 style="font-family: 'EB Garamond', serif; color: #904639; margin-bottom: var(--spacing-sm);">💡 What to Do in a Crisis</h3>
            <p style="color: #59605c; line-height: 1.8;">
                • <strong>Call for help:</strong> Reach out to a helpline or emergency service above.<br>
                • <strong>Tell someone you trust:</strong> A friend, family member, teacher, or counselor.<br>
                • <strong>Go to a safe place:</strong> If you feel unsafe, move to a public area or hospital.<br>
                • <strong>Breathe:</strong> Try slow, deep breaths — inhale for 4, hold for 4, exhale for 4.<br>
                • <strong>Remember:</strong> You are not alone. Help is available. This moment will pass.
            </p>
        </div>
        """, unsafe_allow_html=True)

    # Footer
    st.markdown("""
    <div style="text-align: center; margin-top: var(--spacing-xl); padding-top: var(--spacing-md); border-top: 1px solid #dac1bd; font-family: 'Be Vietnam Pro', sans-serif;">
        <p style="font-size: var(--font-sm); color: #59605c; line-height: 1.6; max-width: 600px; margin: 0 auto var(--spacing-sm) auto;">
            <strong>Medical Disclaimer:</strong> Jeeva is an emotional support tool, not a replacement for professional clinical care. If you are in crisis, please contact emergency services immediately.
        </p>
    </div>
    """, unsafe_allow_html=True)
    with st.container(horizontal=True, key="footer_links"):
        if st.button("Terms of Service", key="footer_tos"):
            st.session_state.active_tab = "Terms"
            st.rerun()
        if st.button("Privacy Policy", key="footer_privacy"):
            st.session_state.active_tab = "Privacy"
            st.rerun()
        if st.button("Crisis Resources", key="footer_crisis"):
            st.session_state.active_tab = "Crisis"
            st.rerun()

    # Inject JavaScript to intercept clicks on the custom menu button
    # and programmatically click the native sidebar toggle controls,
    # achieving instantaneous, synchronized client-side toggling.
    components.html("""
    <script>
        const parentDoc = window.parent.document;
        const interval = setInterval(() => {
            const buttons = Array.from(parentDoc.querySelectorAll('button'));
            const customBtn = buttons.find(btn => {
                return btn.innerText && btn.innerText.trim() === '☰';
            });
            
            if (customBtn) {
                if (!customBtn.dataset.boundToggle) {
                    customBtn.dataset.boundToggle = "true";
                    customBtn.addEventListener('click', (e) => {
                        const nativeToggle = parentDoc.querySelector('[data-testid="stSidebarCollapsedControl"]');
                        if (nativeToggle) {
                            nativeToggle.click();
                        } else {
                            const closeBtn = parentDoc.querySelector('[data-testid="stSidebarHeader"] button');
                            if (closeBtn) {
                                closeBtn.click();
                            }
                        }
                        e.preventDefault();
                        e.stopPropagation();
                    }, true);
                }
            }
        }, 100);
    </script>
    """, height=0, width=0)


if __name__ == "__main__":
    main()