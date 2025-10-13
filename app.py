from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import cv2
import pytesseract
import dotenv

from langchain.chains import RetrievalQA
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, OpenAI
from langchain.text_splitter import CharacterTextSplitter
from langchain_community.document_loaders import TextLoader

# Load environment variables
dotenv.load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Preprocess the image for OCR
def preprocess_image(image_path):
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    gray = cv2.medianBlur(gray, 3)
    return gray

# Extract text using Tesseract OCR
def extract_text_from_image(image_path):
    preprocessed_image = preprocess_image(image_path)
    text = pytesseract.image_to_string(preprocessed_image)
    return text.strip()

# Set up the RAG pipeline
def setup_rag():
    loader = TextLoader("food_prefernces.txt")
    documents = loader.load()
    text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
    texts = text_splitter.split_documents(documents)

    openai_key = os.getenv("OPENAI_API_KEY")
    embeddings = OpenAIEmbeddings(openai_api_key=openai_key)
    llm = OpenAI(openai_api_key=openai_key)

    vectorstore = FAISS.from_documents(texts, embeddings)

    qa = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=vectorstore.as_retriever()
    )
    return qa

qa_chain = setup_rag()

# Flask route for image analysis
@app.route('/analyze_image', methods=['POST'])
def analyze_image():
    if 'image' not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    image = request.files['image']
    image_path = "temp_image.jpg"
    image.save(image_path)

    extracted_text = extract_text_from_image(image_path)
    query = f"Based on the following ingredients, is it safe for me to eat? Ingredients: {extracted_text}"
    result = qa_chain.run(query)

    return jsonify({"result": result})

if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=8000)
