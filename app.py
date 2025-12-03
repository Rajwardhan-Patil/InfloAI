import streamlit as st
import os
from typing import Optional
from io import BytesIO
from google import genai
from google.genai.errors import APIError
from dotenv import load_dotenv   # NEW

# ----------------------------------
# Load Environment (.env)
# ----------------------------------
load_dotenv()
API_KEY = os.getenv("GENAI_API_KEY")

# ----------------------------------
# Document Reader Utilities
# ----------------------------------

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    from docx import Document
except ImportError:
    Document = None


def read_document_content(uploaded_file):
    file_extension = os.path.splitext(uploaded_file.name)[1].lower()

    try:
        if file_extension in ['.txt', '.md']:
            return uploaded_file.getvalue().decode("utf-8")

        elif file_extension == '.pdf':
            if not PdfReader:
                return "Error: Install pypdf to read PDFs."

            reader = PdfReader(uploaded_file)
            text = ""

            for page in reader.pages:
                text += page.extract_text() or ""

            return text

        elif file_extension == '.docx':
            if not Document:
                return "Error: Install python-docx to read DOCX files."

            doc = Document(BytesIO(uploaded_file.getvalue()))
            return "\n".join([p.text for p in doc.paragraphs])

        else:
            return f"Error: Unsupported file type: {file_extension}"

    except Exception as e:
        return f"Error reading file content: {e}"


# -----------------------------
# Gemini API Wrapper
# -----------------------------

class GeminiAPI:
    def __init__(self, api_key: Optional[str] = None):
        if not api_key:
            raise ValueError("API key missing.")
        self.client = genai.Client(api_key=api_key)

    def generate_content(self, model: str, context: str, question: str, system_instruction: str):
        try:
            config = genai.types.GenerateContentConfig(
                system_instruction=system_instruction
            )

            contents = [
                {"parts": [{"text": context}]},
                {"parts": [{"text": question}]}
            ]

            response = self.client.models.generate_content(
                model=model,
                contents=contents,
                config=config
            )

            return response.text

        except APIError as e:
            return f"API Error: {e}"

        except Exception as e:
            return f"Unexpected Error: {e}"


# -----------------------------
# Streamlit UI Setup
# -----------------------------

st.set_page_config(
    page_title="INFLO — Document-Aware Q&A",
    layout="wide",
    page_icon="💠"
)


# -----------------------------
# Custom CSS
# -----------------------------

st.markdown("""
<style>

@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Poppins', sans-serif;
}

.title {
    text-align: center;
    font-size: 46px;
    font-weight: 800;
    margin-top: 10px;
    color: #2C7BE5;
    opacity: 0;
    animation: fadeIn 1s ease forwards;
}

.subtitle {
    text-align: center;
    font-size: 20px;
    margin-bottom: 35px;
    opacity: 0;
    animation: fadeIn 1.5s ease forwards;
    color: #4A4A4A;
}

.upload-box, .answer-box, .card {
    background: white;
    border-radius: 14px;
    padding: 22px;
    border: 1px solid #E5E7EB;
    box-shadow: 0 4px 12px rgba(0,0,0,0.07);
    animation: slideUp 0.6s ease;
}

.answer-box {
    border-left: 5px solid #2C7BE5;
}

button[kind="primary"] {
    transition: 0.3s ease;
}

button[kind="primary"]:hover {
    box-shadow: 0 0 18px rgba(44,123,229,0.6);
    transform: translateY(-2px);
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0px); }
}

@keyframes slideUp {
    from { transform: translateY(12px); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
}

</style>
""", unsafe_allow_html=True)

st.markdown('<div class="title">💠 INFLO</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Intelligent Information Flow — Document Grounded Q&A</div>', unsafe_allow_html=True)


# -----------------------------
# Session State Init
# -----------------------------

st.session_state.setdefault("uploaded_text", "")
st.session_state.setdefault("rag_response", {})
st.session_state.setdefault("user_prompt", "")


# -----------------------------
# File Upload
# -----------------------------

st.markdown("### 1. Upload Your Document")

st.markdown('<div class="upload-box">', unsafe_allow_html=True)
uploaded_file = st.file_uploader("", type=["txt", "md", "pdf", "docx"])
st.markdown('</div>', unsafe_allow_html=True)

if uploaded_file:
    content = read_document_content(uploaded_file)

    if content.startswith("Error"):
        st.error(content)
        st.session_state.uploaded_text = ""
        st.stop()

    st.session_state.uploaded_text = content
    st.success(f"Loaded: {uploaded_file.name} ({len(content)} characters)")

    st.markdown("#### Preview")
    st.markdown('<div class="card">', unsafe_allow_html=True)
    preview = content[:2000] + ("\n[...] truncated ..." if len(content) > 2000 else "")
    st.code(preview, language="text")
    st.markdown('</div>', unsafe_allow_html=True)
else:
    st.info("Upload a document above to continue.")
    st.stop()


# -----------------------------
# Question Input
# -----------------------------

st.markdown("### 2. Ask a Question Grounded in Your Document")
st.text_area(
    "",
    key="user_prompt",
    height=120,
    placeholder="Example: Summarize the purpose of the first section."
)


# -----------------------------
# RAG Logic
# -----------------------------

if not API_KEY:
    st.error("API key not found. Add GENAI_API_KEY=your_key in .env")
    st.stop()

MODEL_NAME = "gemini-2.5-flash-lite"

gemini = GeminiAPI(api_key=API_KEY)


def run_rag():
    question = st.session_state.user_prompt.strip()
    context = st.session_state.uploaded_text

    if not question:
        st.error("Please ask a question.")
        return

    system_instruction = (
        "Answer ONLY using the document context. "
        "If the answer does not exist, respond with "
        "'I cannot find the answer in the provided document.'"
    )

    answer = gemini.generate_content(
        model=MODEL_NAME,
        context=context,
        question=question,
        system_instruction=system_instruction
    )

    st.session_state.rag_response = {
        "question": question,
        "answer": answer
    }


st.button("💠 Get Answer", type="primary", on_click=run_rag)


# -----------------------------
# Output
# -----------------------------

st.markdown("### 3. INFLO Output")

if st.session_state["rag_response"]:
    st.markdown('<div class="answer-box">', unsafe_allow_html=True)
    st.markdown(f"**Question:** {st.session_state['rag_response']['question']}")
    st.markdown(f"**Answer:**\n\n{st.session_state['rag_response']['answer']}")
    st.markdown('</div>', unsafe_allow_html=True)
else:
    st.info("Your answer will appear here.")
