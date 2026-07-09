import os
import streamlit as st
import PyPDF2
import google.generativeai as genai
from dotenv import load_dotenv

# ------------------ LOAD ENV ------------------
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

model = genai.GenerativeModel("gemini-pro")

# ------------------ FUNCTIONS ------------------

# Extract text from PDF
def extract_text(pdf_file):
    reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        if page.extract_text():
            text += page.extract_text()
    return text


# Generate Summary
def get_summary(text):
    prompt = f"Summarize this in simple words:\n{text[:5000]}"
    response = model.generate_content(prompt)
    return response.text


# Generate Key Points
def get_key_points(text):
    prompt = f"Give important key points from this:\n{text[:5000]}"
    response = model.generate_content(prompt)
    return response.text


# Generate Questions
def generate_questions(text):
    prompt = f"Create 5 exam questions from this:\n{text[:5000]}"
    response = model.generate_content(prompt)
    return response.text


# Generate Flashcards
def generate_flashcards(text):
    prompt = f"Create flashcards (Question & Answer) from this:\n{text[:5000]}"
    response = model.generate_content(prompt)
    return response.text


# Ask Question
def ask_question(text, question):
    prompt = f"""
    Answer the question based on the text below:
    
    TEXT:
    {text[:5000]}
    
    QUESTION:
    {question}
    """
    response = model.generate_content(prompt)
    return response.text


# ------------------ UI ------------------

st.set_page_config(page_title="AI Study Assistant", layout="wide")

st.title("📚 AI Study Assistant")
st.write("Upload your study material and let AI help you learn faster 🚀")

uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])

if uploaded_file:
    text = extract_text(uploaded_file)

    st.success("✅ PDF uploaded successfully!")

    col1, col2 = st.columns(2)

    # LEFT SIDE
    with col1:
        if st.button("📄 Generate Summary"):
            with st.spinner("Generating summary..."):
                summary = get_summary(text)
                st.subheader("Summary")
                st.write(summary)

        if st.button("📌 Key Points"):
            with st.spinner("Extracting key points..."):
                points = get_key_points(text)
                st.subheader("Key Points")
                st.write(points)

    # RIGHT SIDE
    with col2:
        if st.button("❓ Generate Questions"):
            with st.spinner("Generating questions..."):
                questions = generate_questions(text)
                st.subheader("Questions")
                st.write(questions)

        if st.button("🧠 Flashcards"):
            with st.spinner("Generating flashcards..."):
                flashcards = generate_flashcards(text)
                st.subheader("Flashcards")
                st.write(flashcards)

    # CHAT SECTION
    st.divider()
    st.subheader("💬 Ask Anything From PDF")

    user_question = st.text_input("Enter your question:")

    if st.button("Ask"):
        if user_question:
            with st.spinner("Thinking..."):
                answer = ask_question(text, user_question)
                st.write(answer)
        else:
            st.warning("Please enter a question!")
