"""
RAG Climate Chatbot
====================
Retrieval-Augmented Generation chatbot that answers
climate questions using your actual weather data.

How it works:
1. Weather data is embedded and stored in ChromaDB
2. User asks a question
3. Question is embedded and similar data is retrieved
4. Retrieved data + question sent to LLM
5. LLM generates a grounded answer
"""

import os
import logging
import chromadb
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RAGChatbot")


class ClimateRAGChatbot:
    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = "llama-3.1-8b-instant"

        # Initialize ChromaDB (local vector database)
        self.chroma_client = chromadb.Client()
        self.collection = self.chroma_client.get_or_create_collection(
            name="weather_data",
            metadata={"description": "Weather readings from Gold layer"}
        )
        logger.info("✅ RAG Chatbot initialized")

    def load_weather_data(self):
        """Load Gold layer data into ChromaDB vector store."""
        logger.info("📥 Loading weather data into ChromaDB...")

        from pyspark.sql import SparkSession
        spark = SparkSession.builder.appName("RAG").master("local[*]").getOrCreate()
        spark.sparkContext.setLogLevel("ERROR")
        df = spark.read.parquet("data/gold/weather_features").toPandas()
        spark.stop()

        # Clear existing data
        try:
            self.chroma_client.delete_collection("weather_data")
            self.collection = self.chroma_client.create_collection("weather_data")
        except Exception:
            pass

        # Convert each record to a text document and add to ChromaDB
        documents = []
        metadatas = []
        ids = []

        for i, (_, row) in enumerate(df.iterrows()):
            doc = (
                f"City: {row.get('city', 'Unknown')}, {row.get('state', '')}. "
                f"Temperature: {row.get('temperature_fahrenheit', 'N/A')}°F. "
                f"Humidity: {row.get('humidity_percent', 'N/A')}%. "
                f"Wind: {row.get('wind_speed_mph', 'N/A')} mph. "
                f"Pressure: {row.get('pressure_hpa', 'N/A')} hPa. "
                f"Heat Index: {row.get('heat_index', 'N/A')}°F. "
                f"Condition: {row.get('weather_condition', 'N/A')}. "
                f"Extreme Weather: {'Yes' if row.get('is_extreme_weather', 0) == 1 else 'No'}. "
                f"Anomaly Score: {row.get('temp_anomaly_score', 'N/A')}. "
                f"Season: {row.get('season', 'N/A')}."
            )
            documents.append(doc)
            metadatas.append({
                "city": str(row.get('city', '')),
                "state": str(row.get('state', '')),
                "temperature": float(row.get('temperature_fahrenheit', 0)),
                "is_extreme": int(row.get('is_extreme_weather', 0)),
            })
            ids.append(f"weather_{i}")

        # Add in batches (ChromaDB limit)
        batch_size = 100
        for start in range(0, len(documents), batch_size):
            end = min(start + batch_size, len(documents))
            self.collection.add(
                documents=documents[start:end],
                metadatas=metadatas[start:end],
                ids=ids[start:end],
            )

        logger.info(f"   Loaded {len(documents)} records into ChromaDB")

    def chat(self, question: str, n_results: int = 5) -> str:
        """
        Answer a climate question using RAG.
        
        Steps:
        1. Search ChromaDB for relevant weather data
        2. Build prompt with retrieved context
        3. Send to LLM
        4. Return grounded answer
        """
        # Step 1: Retrieve relevant documents
        results = self.collection.query(
            query_texts=[question],
            n_results=n_results,
        )

        # Step 2: Build context from retrieved documents
        context = "\n".join(results['documents'][0]) if results['documents'] else "No data found."

        # Step 3: Build prompt
        prompt = f"""You are a climate data analyst with access to real weather data.
Answer the user's question based ONLY on the following weather data.
If the data doesn't contain the answer, say so honestly.

RETRIEVED WEATHER DATA:
{context}

USER QUESTION: {question}

INSTRUCTIONS:
- Only use information from the provided data
- Be specific with numbers and city names
- If you're not sure, say "Based on available data..."
- Keep answer under 150 words
"""

        # Step 4: Generate answer
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a climate data analyst. Only answer based on provided data."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.2,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            return f"Error: {e}"


def main():
    print("=" * 60)
    print("💬 RAG CLIMATE CHATBOT")
    print("=" * 60)

    chatbot = ClimateRAGChatbot()

    # Load data into vector store
    chatbot.load_weather_data()

    # Test questions
    questions = [
        "Which city has the highest temperature?",
        "Are there any extreme weather conditions?",
        "What is the weather like in Seattle?",
        "Which cities have high humidity?",
        "Tell me about weather conditions in Phoenix",
    ]

    for q in questions:
        print(f"\n❓ Question: {q}")
        print("-" * 40)
        answer = chatbot.chat(q)
        print(f"🤖 Answer: {answer}")

    # Interactive mode
    print("\n\n" + "=" * 60)
    print("💬 INTERACTIVE MODE (type 'quit' to exit)")
    print("=" * 60)

    while True:
        question = input("\n❓ Your question: ").strip()
        if question.lower() in ['quit', 'exit', 'q']:
            break
        if not question:
            continue
        answer = chatbot.chat(question)
        print(f"🤖 {answer}")

    print("\n✅ Chatbot session ended!")


if __name__ == "__main__":
    main()