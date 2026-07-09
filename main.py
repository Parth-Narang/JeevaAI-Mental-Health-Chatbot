import os
import uuid
from datetime import datetime
import streamlit as st
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────
def inject_custom_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        * { font-family: 'Inter', sans-serif; box-sizing: border-box; }

        /* ── App background ── */
        .stApp { background: #f0f4ff; }
        #MainMenu, footer, header { visibility: hidden; }
        .stDeployButton { display: none; }
        [data-testid="stAppViewBlockContainer"] { padding-top: 12px !important; }

        /* ── Header ── */
        .jeeva-header {
            background: linear-gradient(120deg, #1e40af 0%, #2563eb 55%, #3b82f6 100%);
            border-radius: 18px;
            padding: 20px 28px;
            margin-bottom: 14px;
            display: flex;
            align-items: center;
            gap: 18px;
            box-shadow: 0 6px 24px rgba(37,99,235,0.28);
            position: relative;
            overflow: hidden;
        }
        .jeeva-header::after {
            content: '';
            position: absolute;
            right: -30px; top: -40px;
            width: 180px; height: 180px;
            background: rgba(255,255,255,0.07);
            border-radius: 50%;
        }
        .jeeva-header-text h1 {
            color: white !important;
            font-size: 1.65rem !important;
            font-weight: 700 !important;
            margin: 0 0 2px !important;
            line-height: 1.2 !important;
        }
        .jeeva-header-text p {
            color: rgba(255,255,255,0.78) !important;
            font-size: 0.85rem !important;
            margin: 0 0 8px !important;
        }
        .status-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(255,255,255,0.15);
            border: 1px solid rgba(255,255,255,0.28);
            border-radius: 20px;
            padding: 3px 12px;
            font-size: 0.75rem;
            color: white;
        }
        .status-dot {
            width: 7px; height: 7px;
            background: #4ade80;
            border-radius: 50%;
            display: inline-block;
            animation: blink 2s infinite;
        }
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.3} }

        /* ── Intro card ── */
        .intro-card {
            background: white;
            border-radius: 14px;
            padding: 16px 20px;
            margin-bottom: 14px;
            border-left: 4px solid #2563eb;
            box-shadow: 0 2px 10px rgba(0,0,0,0.06);
        }
        .intro-card p {
            color: #374151 !important;
            font-size: 0.875rem !important;
            margin: 0 !important;
            line-height: 1.65 !important;
        }
        .intro-card strong { color: #1e40af !important; }

        /* ── Chat messages ── */
        .stChatMessage {
            border-radius: 14px !important;
            padding: 12px 16px !important;
            margin: 5px 0 !important;
            box-shadow: 0 1px 6px rgba(0,0,0,0.07) !important;
            border: 1px solid transparent !important;
            animation: fadeUp 0.25s ease-out;
        }
        @keyframes fadeUp {
            from { opacity:0; transform:translateY(8px); }
            to   { opacity:1; transform:translateY(0); }
        }

        /* User bubble */
        [data-testid="stChatMessage"][aria-label="user"] {
            background: linear-gradient(135deg, #dbeafe, #bfdbfe) !important;
            border-color: #93c5fd !important;
        }
        [data-testid="stChatMessage"][aria-label="user"] p,
        [data-testid="stChatMessage"][aria-label="user"] span {
            color: #1e3a8a !important;
            font-weight: 500 !important;
            font-size: 0.925rem !important;
        }

        /* Assistant bubble */
        [data-testid="stChatMessage"][aria-label="assistant"] {
            background: white !important;
            border-color: #e5e7eb !important;
        }
        [data-testid="stChatMessage"][aria-label="assistant"] * {
            color: #1f2937 !important;
            font-size: 0.95rem !important;
            line-height: 1.7 !important;
        }

        [data-testid="stChatMessage"][aria-label="assistant"] strong {
            color: #1e40af !important;
            font-weight: 700 !important;
        }

        [data-testid="stChatMessage"][aria-label="assistant"] {
            background: #ffffff !important;
            border: 1px solid #dbe3f0 !important;
        }
        [data-testid="stChatMessage"][aria-label="assistant"] strong {
            color: #1e40af !important;
        }

        /* ── Chat input ── */
        [data-testid="stChatInput"] > div {
            border-radius: 14px !important;
            border: 2px solid #bfdbfe !important;
            background: white !important;
            box-shadow: 0 3px 14px rgba(37,99,235,0.10) !important;
        }
        [data-testid="stChatInput"] > div:focus-within {
            border-color: #2563eb !important;
            box-shadow: 0 3px 18px rgba(37,99,235,0.18) !important;
        }
        [data-testid="stChatInput"] textarea {
            color: #111827 !important;
            font-size: 0.9rem !important;
        }

        /* ── Quick starters ── */
        .qs-label {
            text-align: center;
            color: #6b7280;
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.8px;
            text-transform: uppercase;
            margin: 14px 0 8px;
        }
        div[data-testid="stHorizontalBlock"] .stButton > button {
            width: 100% !important;
            padding: 9px 6px !important;
            background: white !important;
            color: #2563eb !important;
            border: 1.5px solid #bfdbfe !important;
            border-radius: 10px !important;
            font-size: 0.8rem !important;
            font-weight: 500 !important;
            white-space: normal !important;
            height: auto !important;
            min-height: 52px !important;
            line-height: 1.3 !important;
            transition: all 0.18s ease !important;
        }
        div[data-testid="stHorizontalBlock"] .stButton > button:hover {
            background: #2563eb !important;
            color: white !important;
            border-color: #2563eb !important;
            box-shadow: 0 4px 12px rgba(37,99,235,0.25) !important;
            transform: translateY(-2px) !important;
        }

        /* ── Sidebar ── */
        [data-testid="stSidebar"] {
            background: linear-gradient(170deg, #0f172a 0%, #1e3a8a 100%) !important;
        }
        [data-testid="stSidebar"] > div:first-child {
            background: transparent !important;
            padding: 0 14px 20px !important;
        }
        .sb-logo {
            text-align: center;
            padding: 22px 0 14px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            margin-bottom: 16px;
        }
        .sb-logo .sb-icon { font-size: 2.4rem; }
        .sb-logo h2 {
            color: white !important;
            font-size: 1.25rem !important;
            font-weight: 700 !important;
            margin: 6px 0 2px !important;
        }
        .sb-logo p {
            color: rgba(255,255,255,0.5) !important;
            font-size: 0.72rem !important;
            margin: 0 !important;
            letter-spacing: 0.3px;
        }

        /* Stats */
        .sb-stats {
            display: flex;
            gap: 8px;
            margin-bottom: 16px;
        }
        .sb-stat {
            flex: 1;
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 12px;
            padding: 10px 6px;
            text-align: center;
        }
        .sb-stat .sv { color: white; font-size: 1.2rem; font-weight: 700; display: block; }
        .sb-stat .sl { color: rgba(255,255,255,0.5); font-size: 0.68rem; }

        /* Mood */
        .sb-section-label {
            color: rgba(255,255,255,0.45);
            font-size: 0.68rem;
            font-weight: 600;
            letter-spacing: 0.7px;
            text-transform: uppercase;
            margin: 14px 0 8px;
        }
        .mood-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 6px;
            margin-bottom: 16px;
        }
        .mood-chip {
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.13);
            border-radius: 8px;
            padding: 6px 4px;
            text-align: center;
            font-size: 0.75rem;
            color: rgba(255,255,255,0.8);
            cursor: default;
            transition: background 0.15s;
        }
        .mood-chip:hover { background: rgba(255,255,255,0.16); }

        /* Sidebar cards */
        .sb-card {
            background: rgba(255,255,255,0.07);
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 12px;
            padding: 14px;
            margin-bottom: 12px;
        }
        .sb-card h4 {
            color: white !important;
            font-size: 0.82rem !important;
            font-weight: 600 !important;
            margin: 0 0 8px !important;
        }
        .sb-card ul { padding-left: 14px; margin: 0; }
        .sb-card li {
            color: rgba(255,255,255,0.72) !important;
            font-size: 0.78rem !important;
            line-height: 1.7 !important;
        }
        .sb-card a { color: #93c5fd !important; }

        /* Sidebar button */
        [data-testid="stSidebar"] .stButton > button {
            background: rgba(255,255,255,0.1) !important;
            color: white !important;
            border: 1.5px solid rgba(255,255,255,0.22) !important;
            border-radius: 10px !important;
            font-size: 0.85rem !important;
            font-weight: 600 !important;
            width: 100% !important;
            padding: 10px !important;
            transition: all 0.18s ease !important;
        }
        [data-testid="stSidebar"] .stButton > button:hover {
            background: rgba(255,255,255,0.2) !important;
        }

        /* ── Disclaimer ── */
        .disclaimer {
            background: #fffbeb;
            border: 1px solid #fde68a;
            border-radius: 12px;
            padding: 14px 18px;
            margin-top: 20px;
        }
        .disclaimer p {
            color: #78350f !important;
            font-size: 0.78rem !important;
            margin: 0 !important;
            line-height: 1.6 !important;
        }
        .disclaimer strong { color: #92400e !important; }
                
        /* ── FORCE CHAT TEXT VISIBILITY ── */
        [data-testid="stChatMessage"] {
            opacity: 1 !important;
        }

        [data-testid="stChatMessage"] * {
            opacity: 1 !important;
        }

        /* Assistant message text */
        [data-testid="stChatMessageContent"] {
            color: #1f2937 !important;
            opacity: 1 !important;
        }

        [data-testid="stChatMessageContent"] p,
        [data-testid="stChatMessageContent"] span,
        [data-testid="stChatMessageContent"] div,
        [data-testid="stChatMessageContent"] strong {
            color: #1f2937 !important;
            opacity: 1 !important;
        }

        /* Fix markdown rendering */
        .stMarkdown {
            opacity: 1 !important;
        }

        .stMarkdown p {
            color: #1f2937 !important;
            opacity: 1 !important;
        }

        /* Welcome message stronger */
        [data-testid="stChatMessage"][aria-label="assistant"] {
            background: #ffffff !important;
            border: 1px solid #dbe3f0 !important;
            box-shadow: 0 2px 10px rgba(0,0,0,0.06) !important;
        }
        /* ── CHAT INPUT FINAL FIX ── */
        [data-testid="stChatInput"] textarea {
            background: #ffffff !important;
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;

            font-size: 0.95rem !important;
            font-weight: 500 !important;

            caret-color: #2563eb !important;
        }

        /* Placeholder */
        [data-testid="stChatInput"] textarea::placeholder {
            color: #6b7280 !important;
            opacity: 1 !important;
        }

        /* Input container */
        [data-testid="stChatInput"] {
            background: transparent !important;
        }

        /* Actual input wrapper */
        [data-testid="stChatInput"] > div {
            background: #ffffff !important;
            border: 2px solid #3b82f6 !important;
            border-radius: 14px !important;
        }

        /* Remove dark internal layer */
        [data-testid="stChatInput"] div {
            background-color: transparent !important;
        }
    </style>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Chatbot
# ─────────────────────────────────────────────
class MentalHealthChatbot:
    def __init__(self):
        if 'user_id' not in st.session_state:
            st.session_state.user_id = str(uuid.uuid4())
            st.session_state.start_time = datetime.now()
        self.chatbot = self._init()

    def _init(self):
        API_KEY = os.getenv("GEMINI_API_KEY")
        if not API_KEY:
            st.error("GEMINI_API_KEY not found in .env", icon="🚨"); st.stop()

        sys_prompt = (
            "You are JeevaAI, a warm and empathetic mental health support companion. "
            "Listen actively, validate feelings without judgment, and offer gentle support. "
            "Respond to ALL messages including greetings with warmth. "
            "Ask thoughtful follow-up questions. Suggest coping strategies when helpful. "
            "Never diagnose or prescribe. Remind users to seek professional help for serious issues. "
            "Keep responses concise, warm, and conversational. Use short paragraphs."
        )

        class Session:
            def __init__(self, client, model, prompt):
                self.client = client; self.model = model
                self.prompt = prompt; self.history = []

        try:
            client = genai.Client(api_key=API_KEY)
            for name in ["gemini-2.5-flash","gemini-2.5-flash-preview-05-20","gemini-2.0-flash","gemini-1.5-flash"]:
                try:
                    avail = [m.name for m in client.models.list()]
                    match = next((m for m in avail if name in m), None)
                    chosen = match.replace("models/","") if match else name
                    st.session_state['_model'] = chosen
                    return Session(client, chosen, sys_prompt)
                except Exception:
                    continue
            return Session(client, "gemini-2.5-flash", sys_prompt)
        except Exception as e:
            st.error(f"Gemini init failed: {e}", icon="🔥"); st.stop()

    def reply(self, message):
        if not self.chatbot: return "Chatbot unavailable."
        try:
            crisis_kw = ["suicide","kill myself","end my life","want to die",
                         "harm myself","hurt myself","don't want to live","overdose"]
            crisis = any(k in message.lower() for k in crisis_kw)

            s = self.chatbot
            contents = [types.Content(role=h["role"], parts=[types.Part(text=h["content"])])
                        for h in s.history]
            contents.append(types.Content(role="user", parts=[types.Part(text=message)]))

            resp = s.client.models.generate_content(
                model=s.model, contents=contents,
                config=types.GenerateContentConfig(system_instruction=s.prompt, temperature=0.72)
            )
            text = resp.text if resp.text else "I'm here. Could you tell me more?"
            s.history += [{"role":"user","content":message}, {"role":"model","content":text}]

            if crisis:
                text = ("🚨 **You're not alone — please reach out right now:**\n"
                        "- 🇮🇳 iCall (India): **9152987821**\n"
                        "- 🇺🇸 US/Canada: **988**\n"
                        "- 🌍 International: [findahelpline.com](https://findahelpline.com)\n\n") + text
            return text
        except Exception as e:
            import traceback; print(traceback.format_exc())
            err = str(e)
            if "429" in err or "quota" in err.lower():
                return "I'm at my usage limit right now. Please try again in a moment. 💙"
            return f"Error: {err}"


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def _welcome():
    return {"role":"assistant","content":(
        "Hello! I'm really glad you're here. 💙\n\n"
        "This is a safe, judgment-free space. Whether you're anxious, overwhelmed, "
        "or just need someone to listen — I'm here.\n\n**How are you feeling today?**"
    )}

def _send(text):
    st.session_state.messages.append({"role":"user","content":text})
    with st.spinner("JeevaAI is reflecting..."):
        reply = st.session_state.bot.reply(text)
    st.session_state.messages.append({"role":"assistant","content":reply})
    st.rerun()


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    st.set_page_config(
        page_title="JeevaAI – Mental Wellness",
        page_icon="🧠", layout="centered",
        initial_sidebar_state="expanded"
    )
    inject_custom_css()

    # Init
    if 'bot' not in st.session_state:
        with st.spinner("Preparing your space..."):
            st.session_state.bot = MentalHealthChatbot()
    if 'messages' not in st.session_state:
        st.session_state.messages = [_welcome()]

    # ── Sidebar ──────────────────────────────
    with st.sidebar:
        st.markdown("""
        <div class="sb-logo">
            <div class="sb-icon">🧠</div>
            <h2>JeevaAI</h2>
            <p>Mental Wellness Companion</p>
        </div>
        """, unsafe_allow_html=True)

        dur = int((datetime.now() - st.session_state.get('start_time', datetime.now())).total_seconds() / 60)
        u_msgs = sum(1 for m in st.session_state.messages if m['role'] == 'user')
        st.markdown(f"""
        <div class="sb-stats">
            <div class="sb-stat"><span class="sv">{u_msgs}</span><span class="sl">Messages</span></div>
            <div class="sb-stat"><span class="sv">{dur}m</span><span class="sl">Session</span></div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="sb-section-label">How are you feeling?</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="mood-grid">
            <div class="mood-chip">😊 Happy</div>
            <div class="mood-chip">😔 Sad</div>
            <div class="mood-chip">😰 Anxious</div>
            <div class="mood-chip">😤 Angry</div>
            <div class="mood-chip">😐 Neutral</div>
            <div class="mood-chip">😴 Tired</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="sb-section-label">Crisis Support</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="sb-card">
            <h4>🆘 Helplines</h4>
            <ul>
                <li><b>India:</b> iCall — 9152987821</li>
                <li><b>India:</b> Vandrevala — 1800-599-0019</li>
                <li><b>US/Canada:</b> Call or text 988</li>
                <li><b>UK:</b> Samaritans — 116 123</li>
                <li><b>Int'l:</b> <a href="https://findahelpline.com" target="_blank">findahelpline.com</a></li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="sb-section-label">Wellness Tips</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="sb-card">
            <h4>💡 Daily Reminders</h4>
            <ul>
                <li>Take slow, deep breaths 🌬️</li>
                <li>Drink water regularly 💧</li>
                <li>Step outside for 5 min 🌿</li>
                <li>Connect with a trusted person 🤝</li>
                <li>It's okay to ask for help 💙</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("✨ Start New Conversation", key="new_chat", use_container_width=True):
            st.session_state.messages = [_welcome()]
            st.session_state.bot.chatbot.history = []
            st.toast("Fresh start! I'm here for you. 💙", icon="✨")
            st.rerun()

    # ── Main content ─────────────────────────
    # Header
    st.markdown("""
    <div class="jeeva-header">
        <div style="font-size:2.6rem;flex-shrink:0;">🧠</div>
        <div class="jeeva-header-text">
            <h1>JeevaAI</h1>
            <p>Your compassionate mental wellness companion</p>
            <span class="status-pill"><span class="status-dot"></span> Online &amp; Ready to Listen</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Intro
    st.markdown("""
    <div class="intro-card">
        <p>
            👋 <strong>Welcome — you're in a safe space.</strong>
            JeevaAI listens without judgment and helps you explore your feelings.
            Share whatever's on your mind — big or small. <strong>You are not alone.</strong>
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Chat messages
    AVATARS = {
        "user":      "https://cdn-icons-png.flaticon.com/512/1144/1144760.png",
        "assistant": "https://cdn-icons-png.flaticon.com/512/4712/4712035.png"
    }
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar=AVATARS[msg["role"]]):
            st.markdown(msg["content"])

    # Quick starters — only shown after assistant's last reply
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "assistant":
        st.markdown('<div class="qs-label">💬 Quick Starters</div>', unsafe_allow_html=True)
        starters = [
            ("😟", "I'm feeling stressed and overwhelmed"),
            ("😰", "Help me manage my anxiety"),
            ("👂", "I just need someone to listen"),
            ("🧘", "Teach me a mindfulness exercise"),
        ]
        cols = st.columns(4)
        for i, (icon, text) in enumerate(starters):
            if cols[i].button(f"{icon}\n{text}", key=f"qs_{i}"):
                _send(text)

    # Input
    if user_input := st.chat_input("Share what's on your mind..."):
        _send(user_input)

    # Disclaimer
    st.markdown("""
    <div class="disclaimer">
        <p>
            ⚠️ <strong>JeevaAI is not a substitute for professional mental health care.</strong>
            It cannot diagnose or treat conditions. In a crisis, please call emergency services
            or a mental health professional immediately.
        </p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()