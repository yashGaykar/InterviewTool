from fastapi import FastAPI, UploadFile, File,Form, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from uuid import uuid4
import os
import shutil
import json
from typing import List
import zipfile

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain.chains import LLMChain
import PyPDF2
from langchain_core.runnables.base import RunnableSequence
from pydantic import BaseModel, Field
from typing import List
import json

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}

STORAGE_DIR = "storage"

# --- Utility Functions ---

def create_candidate_folder():
    candidate_id = str(uuid4())
    folder_path = os.path.join(STORAGE_DIR, candidate_id)
    os.makedirs(folder_path, exist_ok=True)
    return candidate_id, folder_path


def save_resume(resume: UploadFile, folder_path: str):
    resume_path = os.path.join(folder_path, "resume.pdf")
    with open(resume_path, "wb") as buffer:
        shutil.copyfileobj(resume.file, buffer)

def save_exam_details(exam_details: UploadFile, folder_path: str):
    exam_details_path = os.path.join(folder_path, "job_desc.json")
    with open(exam_details_path, "wb") as buffer:
        shutil.copyfileobj(exam_details.file, buffer)

def load_exam_details(filepath):
    with open(filepath, "r") as f:
        data = json.load(f)
        return data

def save_audio(audio: UploadFile, folder_path: str):
    audio_path = os.path.join(folder_path, "audio.mp3")
    with open(audio_path, "wb") as buffer:
        shutil.copyfileobj(audio.file, buffer)

def save_test_output(folder_path: str, data: dict):
    output_path = os.path.join(folder_path, "testoutput.json")
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)


def load_test_output(folder_path: str):
    output_path = os.path.join(folder_path, "testoutput.json")
    if not os.path.exists(output_path):
        raise HTTPException(status_code=404, detail="Test output not found")
    with open(output_path, "r") as f:
        return json.load(f)

def read_resume_from_pdf(pdf_path):
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
            return text
    except Exception as e:
        return f"Error reading PDF: {e}"

def clean_resume_text(text):
    import re
    # Replace multiple newlines and bullets
    text = re.sub(r"[•\n]+", "\n", text)
    # Remove leading/trailing whitespace
    return text.strip()

def get_llm_object():
    # if "GOOGLE_API_KEY" not in os.environ:
    #     os.environ["GOOGLE_API_KEY"] = getpass.getpass("Enter your Google AI API key: ")

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-001",
        temperature=0,
        max_tokens=None,
        timeout=None,
        max_retries=2,
        # other params...
    )
    return llm


def extract_required_skills_from_resume_and_jd(resume_path: str, job_description: str) -> dict:

    resume_text = read_resume_from_pdf(resume_path)
    text = clean_resume_text(resume_text)

    llm = get_llm_object()

    template = """
    You are an expert examiner.
    Here is the resume text: {text} and Job Description: {job_desc}
    Filter out Skills that needs to be tested for an interview of a candidate in three sections
    Mandatory skills, important skills, unnecessary skills
    Mandatory contains as per name mandatory skills according to Job Description.
    Important contains skills that can be tested for overall candidate knowledge.
    Unnecessary contains unrelated skills to Job Description.
    Get all these in Exam Skills and also get some more profile details as per requirement
    """

    class Skills(BaseModel):
        mandatory_skills: List[str] = Field(description="List of mandatory skills.")
        important_skills: List[str] = Field(description="List of important skills.")
        unnecessary_skills: List[str] = Field(description="List of unnecessary skills.")
    
    class Profile(BaseModel):
        name: str = Field(description="The name of candidate.")
        qualification: str = Field(description="Highest qualification of a candidate.")
        technical_skills: List[str] = Field(description="Technical skills of a candidate.")
        soft_skills: List[str] = Field(description="Soft skills of a candidate.")
        programming_languages: List[str] = Field(description="Programming Languages that candidate knows.")
        email: str = Field(description="EmailId of a candidate.")
        contact_no: str = Field(description="Contact Number of a candidate.")
        skills_in_jd: List[str] = Field(description="skills required as per JD.")
        exam_skills: List[Skills] = Field(description="Skills obtained for Examination.")

    prompt = PromptTemplate(template=template, input_variables=["text", "job_desc"])
    structured_llm = llm.with_structured_output(Profile)
    llm_chain = RunnableSequence(prompt | structured_llm)
    skills: Skills = llm_chain.invoke(input={"text": text, "job_desc": job_description})

    return skills.model_dump()


def extract_info_from_resume(skills: dict, job_description: dict) -> dict:

    llm = get_llm_object()

    template = """
    You are an expert exam creator.

    ### Skills Overview:
    {skills}

    ### Skill Prioritization:
    - **mandatory_skills** (High priority, 60% weightage)
    - **important_skills** (Medium priority, 40% weightage)
    - **unnecessary_skills** (Ignored)

    ### Test Overview:
    Test Details: {test_details}
    Experience Level & Difficulty: test_details.difficulty_level

    ### Exam Sections:

    1️ MCQs
    - Create test_details['test_details']['MCQ']['no_of_questions'] MCQs.
    - Difficulty must **strictly** align with the specified test_details.difficulty_level. Use the following mapping:
    - Beginner → basic conceptual MCQs
    - Intermediate → practical understanding
    - Advanced → debugging, tricky scenarios
    - Expert → integration and real-world architecture
    - Master → advanced scenarios, optimization, pitfalls
    - Focus: primarily on **mandatory_skills** (70%), some on **important_skills** (30%), ignore **unnecessary_skills**.
    - Each MCQ:
    - Technically correct, unambiguous
    - **Exactly 1 correct answer**
    - Include **corner case** coverage where relevant

    2️ Theory Questions
    - Generate test_details['test_details']['Theory']['no_of_questions'] theory questions.
    - Each answer should require **4-5 lines**.
    - **Difficulty strictly aligned** with test_details.difficulty_level:
    - Beginner → basic definitions
    - Intermediate → explain how it works
    - Advanced → comparisons, pros/cons
    - Expert → architectural decisions
    - Master → advanced pitfalls, security, performance
    - Focus on **why/how**, testing deeper conceptual understanding.

    3️ **Coding Problems**
    - Generate test_details['test_details']['Coding']['no_of_questions'] logical coding problems for difficulty level test_details.difficulty_level.
    - Each question **must**:
        - Be fully testable with clear **input → output → explanation**.
        - **Avoid** using external dependencies like databases, files, APIs, or frameworks.
        - Test core skills: data structures, algorithms, problem-solving, recursion, loops, string manipulation, number theory, etc.
    - Clearly define:
        - **Name**
        - **Description** with detailed constraints
        - **Examples** (at least 2)
        - **Test Cases** (with diverse inputs including edge cases)
    - Ensure **different coding problems for different experience levels**:
        - Beginner → Simple operations, loops, or conditionals
        - Intermediate → String manipulation, arrays
        - Advanced → Recursion, algorithmic thinking
        - Expert → Optimization, complex data structures
        - Master → Algorithm design with multiple edge cases, large input constraints
    """

    class MCQ(BaseModel):
        question: str = Field(description="The multiple choice question.")
        options: List[str] = Field(description="List of four options for the question.")
        answer: str = Field(description="The correct option for the question.")

    class TestCase(BaseModel):
        input: str = Field(description="The input for the program.")
        expected_output: str = Field(description="The output for the program.")
        description: str = Field(description="The description for the program.")

    class CodingQuestion(BaseModel):
        name: str = Field(description="The coding question name.")
        description: str = Field(description="The coding question description.")
        # hints: List[str] = Field(description="hints is required for the question.")
        example: List[TestCase] = Field(description="List of examples.")
        test_cases: List[TestCase] = Field(description="List of all the corner case test cases.")

    class TheroticalQuestions(BaseModel):
        question: str = Field(description="The Therotical question.")
        expected_answer: str = Field(description="The Answer for the question.")

    class MCQSet(BaseModel):
        level: str = Field(description="The difficulty level of the questions.")
        questions: List[MCQ] = Field(description="List of MCQs generated.")
        therotical_questions: List[TheroticalQuestions] = Field(description="List of Therotical questions generated.")
        coding_question: List[CodingQuestion] = Field(description="List of Coding Questions generated.")

    prompt = PromptTemplate(template=template, input_variables=["skills", "test_details"])
    structured_llm = llm.with_structured_output(MCQSet)
    llm_chain = RunnableSequence(prompt | structured_llm)
    mcqSet: MCQSet = llm_chain.invoke(input={"skills": skills, "test_details": job_description})

    return mcqSet.model_dump()

async def call_llm_to_generate_report(final_data, test_details):

    llm = get_llm_object()

    template = """
    You are an expert examiner.
    Here is the Json output of answers submitted by candidate:
    {final_data}
    And the Marks for each question in {test_details}
    Based on the following Data Generate a Report of the candidate in the below format without formatting
    Candidate Name:
    MCQ Score: correct_answers out of total_questions
        - description about candidate regarding skills on basis of MCQ's
        - 


    Theory Questions Attempted:  
        Here answer may not match the expected answer totally, still marks shall be calculated on basis of question. 
        display marks for each coding_questions and description too for each question
        - 
        - 
        -
        
    Coding Questions Attempted:  
        display marks for each coding_questions and description too for each question
        - 
        - 
        -

    Overall Feedback:
        -
        -
        -

    Also shortly summarize how total and obtained marks are calulated and confirm that Last Line is
    Marks: Obtained/Total Marks
    
    The content shall be in above format can include some profile details
    This Report will just summarize the candidate and will give scores to the candidate in above format
    No unwanted stuff required in Final Report
    Give me this in Text Well Formatted
    """


    prompt = PromptTemplate(template=template, input_variables=["final_data", "test_details"])
    llm_chain = RunnableSequence(prompt | llm)
    output = llm_chain.invoke(input={"final_data": final_data, "test_details": test_details})

    return output

# --- Background Task to process Resume ---

def process_resume(folder_path: str):
    resume_path = os.path.join(folder_path, "resume.pdf")
    job_description_path = os.path.join(folder_path, "job_desc.json")
    job_description = load_exam_details(job_description_path)
    profile = extract_required_skills_from_resume_and_jd(resume_path, job_description["requirements"])
    skills = profile["exam_skills"]
    extracted_data = extract_info_from_resume(skills, job_description)
    extracted_data["profile"] = profile

    testoutput_path = os.path.join(folder_path, "testoutput")
    os.mkdir(testoutput_path)

    profile_path = os.path.join(testoutput_path, "profile.json")

    with open(profile_path, "w") as f:
        json.dump(extracted_data["profile"], f, indent=2)

    save_test_output(folder_path, extracted_data)


# --- API Schemas ---

class SubmitAnswer(BaseModel):
    answer: str

class SubmitCodingAnswer(BaseModel):
    code: str

class MCQAnswer(BaseModel):
    question: str
    options: List[str]
    correct_answer: str
    submitted_answer: str

class SubmitMCQRequest(BaseModel):
    candidate_id: str
    submitted_mcqs: List[MCQAnswer]

# --- API Endpoints ---

@app.post("/upload_resume")
async def upload_resume(resume: UploadFile = File(...),
                        exam_details: UploadFile = File(...),
                        background_tasks: BackgroundTasks = None):
    candidate_id, folder_path = create_candidate_folder()
    save_resume(resume, folder_path)
    save_exam_details(exam_details, folder_path)
    # process_resume(folder_path, difficulty_level)
    background_tasks.add_task(process_resume, folder_path)
    return JSONResponse(content={"candidate_id": candidate_id})

@app.post("/upload_audio/{candidate_id}")
async def upload_audio(candidate_id: str, audio: UploadFile = File(...)):
    file_location = os.path.join(STORAGE_DIR, candidate_id)

    file_location = os.path.join(file_location, audio.filename)
    with open(file_location, "wb") as f:
        shutil.copyfileobj(audio.file, f)

    return {"message": "Audio uploaded successfully!"}

@app.get("/get_mcq/{candidate_id}")
async def get_mcq(candidate_id: str):
    folder_path = os.path.join(STORAGE_DIR, candidate_id)
    if not os.path.exists(os.path.join(folder_path, "testoutput.json")):
        raise HTTPException(status_code=202, detail="Test generation in progress. Please retry.")
    data = load_test_output(folder_path)
    try:
        question = data["questions"]
        return question
    except (IndexError, KeyError):
        raise HTTPException(status_code=404, detail="MCQs not found or improperly generated.")


@app.post("/submit_all_mcq_answers/")
async def submit_all_mcq_answers(data: SubmitMCQRequest):
    candidate_id = data.candidate_id
    submitted_mcqs = data.submitted_mcqs
    output_folder = os.path.join(STORAGE_DIR, candidate_id, "testoutput")
    os.makedirs(output_folder, exist_ok=True)
    mcq_answers_path = os.path.join(output_folder, "submitted_mcq_answers.json")
    # Save the submitted answers into mcq_answers.json
    try:
        with open(mcq_answers_path, "w") as f:
            json.dump([mcq.dict() for mcq in submitted_mcqs], f, indent=4)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save MCQ answers: {str(e)}")
    return {"message": "All MCQ answers submitted successfully!"}

@app.get("/get_theory_question/{candidate_id}")
async def get_theory_question(candidate_id: str):
    folder_path = os.path.join(STORAGE_DIR, candidate_id)
    data = load_test_output(folder_path)
    try:
        theory = data["therotical_questions"]
        return theory
    except IndexError:
        raise HTTPException(status_code=404, detail="Coding question not found")

class TheoryAnswer(BaseModel):
    question: str
    submitted_answer: str
    expected_answer: str
class SubmitTheoryRequest(BaseModel):
    candidate_id: str
    submitted_theory_questions: List[TheoryAnswer]


@app.post("/submit_all_theory_answers/")
async def submit_all_theory_answers(data: SubmitTheoryRequest):
    candidate_id = data.candidate_id
    submitted_theory_questions = data.submitted_theory_questions
    output_folder = os.path.join(STORAGE_DIR, candidate_id, "testoutput")
    os.makedirs(output_folder, exist_ok=True)
    theory_answers_path = os.path.join(output_folder, "theory_answers.json")
    try:
        with open(theory_answers_path, "w") as f:
            json.dump([theory.dict() for theory in submitted_theory_questions], f, indent=4)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save theory answers: {str(e)}")
    return {"message": "All theory answers submitted successfully!"}

@app.get("/get_coding_question/{candidate_id}")
async def get_coding_question(candidate_id: str):
    folder_path = os.path.join(STORAGE_DIR, candidate_id)
    data = load_test_output(folder_path)
    try:
        coding = data["coding_question"]
        return coding
    except IndexError:
        raise HTTPException(status_code=404, detail="Coding question not found")

class CodingAnswer(BaseModel):
    question_name: str
    question_description: str
    submitted_code: str
    language: str
class SubmitCodingRequest(BaseModel):
    candidate_id: str
    submitted_coding_questions: List[CodingAnswer]

@app.post("/submit_all_coding_answers/")
async def submit_all_coding_answers(data: SubmitCodingRequest):
    candidate_id = data.candidate_id
    submitted_coding_questions = data.submitted_coding_questions
    output_folder = os.path.join(STORAGE_DIR, candidate_id, "testoutput")
    os.makedirs(output_folder, exist_ok=True)
    coding_answers_path = os.path.join(output_folder, "coding_answers.json")
    try:
        with open(coding_answers_path, "w") as f:
            json.dump([coding.dict() for coding in submitted_coding_questions], f, indent=4)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save coding answers: {str(e)}")
    return {"message": "All coding answers submitted successfully!"}
def load_json(filepath):
    with open(filepath, "r") as f:
        return json.load(f)
def build_consolidated_json(profile, mcq_answers, coding_answers, theory_answers):
    # Calculate is_correct for each MCQ
    mcq_results = []
    for mcq in mcq_answers:
        mcq_result = {
            "question": mcq["question"],
            "options": mcq["options"],
            "correct_answer": mcq["correct_answer"],
            "submitted_answer": mcq["submitted_answer"],
            "is_correct": mcq["correct_answer"] == mcq["submitted_answer"]
        }
        mcq_results.append(mcq_result)
    consolidated = {
        "profile": profile,
        "mcq_results": mcq_results,
        "coding_results": coding_answers,
        "theory_results": theory_answers
    }
    return consolidated

@app.post("/generate_final_result/")
async def generate_final_result(candidate_id: str):
    storage_path = os.path.join(STORAGE_DIR, candidate_id)
    testoutput_path = os.path.join(storage_path, "testoutput")

    # Load data
    profile_path = os.path.join(testoutput_path, "profile.json")
    mcq_answers_path = os.path.join(testoutput_path, "submitted_mcq_answers.json")
    theory_answers_path = os.path.join(testoutput_path, "theory_answers.json")
    coding_answers_path = os.path.join(testoutput_path, "coding_answers.json")
    profile = load_json(profile_path)
    mcq_answers = load_json(mcq_answers_path)
    coding_answers = load_json(coding_answers_path)
    theory_answers = load_json(theory_answers_path)

    job_description_path = os.path.join(storage_path, "job_desc.json")
    job_description = load_exam_details(job_description_path)
    # Build Consolidated JSON
    final_data = build_consolidated_json(profile, mcq_answers, coding_answers, theory_answers)

    # Call LLM to generate final report text
    final_report_text = await call_llm_to_generate_report(final_data, job_description["test_details"])

    # Save the final report text
    final_report_path = os.path.join(testoutput_path, "Final_Report.txt")
    with open(final_report_path, "w") as f:
        f.write(final_report_text.content)

    # Prepare candidate name safely
    candidate_name = profile.get("name", "Candidate").replace(" ", "_")

    # Now create ZIP file
    zip_filename = os.path.join(storage_path, f"{candidate_name}.zip")
    with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
        for foldername, subfolders, filenames in os.walk(storage_path):
            for filename in filenames:
                if not filename.endswith('.zip'):  # Avoid including the zip itself
                    file_path = os.path.join(foldername, filename)
                    arcname = os.path.relpath(file_path, storage_path)
                    zipf.write(file_path, arcname)

    return {
        "message": "Final result ZIP generated successfully!",
        "zip_path": zip_filename,
        "candidate_name": candidate_name
    }

@app.get("/download_zip/")
async def download_zip(candidate_id: str):
    storage_path = os.path.join(STORAGE_DIR, candidate_id)
    testoutput_path = os.path.join(storage_path, "testoutput")

    # Load profile to get candidate name
    profile_path = os.path.join(testoutput_path, "profile.json")
    profile = load_json(profile_path)
    candidate_name = profile.get("name", "Candidate").replace(" ", "_")

    zip_path = os.path.join(storage_path, f"{candidate_name}.zip")

    if not os.path.exists(zip_path):
        return {"error": "ZIP file not found. Please generate it first."}

    return FileResponse(
        path=zip_path,
        filename=f"{candidate_name}.zip",
        media_type='application/zip'
    )

@app.get("/get_final_report/")
async def get_final_report(candidate_id: str):
    storage_path = os.path.join(STORAGE_DIR, candidate_id, "testoutput")
    final_report_path = os.path.join(storage_path, "Final_Report.txt")

    if not os.path.exists(final_report_path):
        raise HTTPException(status_code=404, detail="Final report not found. Please generate it first.")

    with open(final_report_path, "r", encoding="utf-8") as f:
        report_text = f.read()

    return {
        "candidate_id": candidate_id,
        "final_report": report_text
    }

# python -m uvicorn main:app --reload