# Importing the Necessary Libraries
from fastapi import FastAPI, File, UploadFile
from pydantic import BaseModel
from ultralytics import YOLO
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_google_genai import GoogleGenerativeAI
import os,markdown
from dotenv import load_dotenv

# Load the environment variables
load_dotenv() 

# API key for the Google API
apikey = os.getenv("API_KEY")
print(apikey)


app= FastAPI()

# Load the YOLO model
model = YOLO("disease/disease.pt")
UPLOAD_FOLDER = 'static/uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)




# Define the request model
class ChatRequest(BaseModel):
    question: str



# CHATBOT API Code Section Starts Here
def is_greeting(query):
    greetings = ["hello", "hi", "hey", "namaste", "नमस्ते", "हेलो", "हाइ"]
    return any(greeting in query.lower() for greeting in greetings)

def get_agriculture_response(query):
    agriculture_keywords = ["farm", "farming", "agriculture", "crop", "plant", "soil", "harvest", "कृषि", "खेती", "बाली"]
    
    if any(keyword in query.lower() for keyword in agriculture_keywords):
        chat_prompt = PromptTemplate.from_template(
            '''You are an AI assistant specialized in agriculture and farming topics. 
            Provide a detailed and informative response to the following query about agriculture: {query}
            
            IMPORTANT: 
            - Respond ONLY in Nepali language.
            - Provide specific information related to the query.
            - If the query is general, give an overview of the topic.
            - Ensure your response is natural, conversational, and informative.'''
        )
    else:
        chat_prompt = PromptTemplate.from_template(
            '''You are an AI assistant specialized in agriculture and plant-related topics. 
            Analyze the following user input: {query}

            If the input is a greeting:
            Respond with a friendly greeting in Nepali and encourage the user to ask an agriculture-related question.

            If the input is not related to agriculture or plants:
            Politely explain in Nepali that you can only answer questions about agriculture and plants, 
            and encourage the user to ask an agriculture-related question.

            IMPORTANT: 
            - Always respond ONLY in Nepali language.
            - Ensure your response is natural and conversational.'''
        )
    
    llm = GoogleGenerativeAI(temperature=0.7, model="gemini-pro", api_key=apikey)
    chain = chat_prompt | llm
    response = chain.invoke({"query": query})
    return response

# POST request for the chat API
@app.post("/chat/")
async def chat(request: ChatRequest):
    try:
        question = (request.question).strip()
        if not question:
            # Prepare the error response data
            data = {
                "status": 400 , 
                "error": "Bad Request! Please provide a valid question!"
            }
            return {"response": data}

        # Defining the template for the AI model
        response = get_agriculture_response(question)

        # Convert the response to markdown
        responsetext=markdown.markdown(response)
        
        # Prepare the response data
        data = {
            "status": 200 ,
            "question": question,
            "response": responsetext
        }

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        # Prepare the error response data
        data = {
            "status": 500 , 
            "error": "Sorry! Something went wrong!"
        }
    
    # Return the response data
    return {"response": data}




# DISEASE DETECTION API Code Section Starts Here
def generate_summary(disease):
    summary_template = PromptTemplate(
        input_variables=['disease'],
        template='''Generate a summary of cures and precautions for the plant disease: {disease}. 
        Include treatment methods and preventive measures. 
        IMPORTANT: Respond ONLY in Nepali language. Do not use any English.
        
        Your response should follow this structure in Nepali:
        1. रोगको नाम (Disease Name)
        2. रोगको कारण (Cause of the Disease)
        3. रोगको लक्षणहरू (Symptoms of the Disease)
        4. उपचार विधिहरू (Treatment Methods)
        5. रोकथामका उपायहरू (Preventive Measures)
        6. थप सुझावहरू (Additional Recommendations)
        '''
    )
    llm = GoogleGenerativeAI(temperature=0.7, model="gemini-pro", api_key=apikey)
    summary_chain = LLMChain(llm=llm, prompt=summary_template, verbose=True)
    summary = summary_chain.run(disease=disease)
    return markdown.markdown(summary)

# POST request for the disease prediction API
@app.post("/predict/")
async def predict_disease(file: UploadFile = File(...)):
    if file:
        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        with open(filepath, "wb") as f:
            f.write(await file.read())
        
        results = model(source=filepath, save=True)
        
        predictions = results[0].boxes.data.tolist()
        class_names = results[0].names
        
        formatted_predictions = []
        for pred in predictions:
            class_id = int(pred[5])
            confidence = pred[4]
            disease = class_names[class_id]
            summary = generate_summary(disease)
            formatted_predictions.append({
                'status' : 200,
                'class': disease,
                'summary': summary,
                'confidence': confidence
            })

        if len(formatted_predictions) == 0:
            return {
                "status": 200,
                "error": "No disease detected"
            }
        return formatted_predictions

    return {
        "status": 400,
        "error": "No file uploaded"
        }
