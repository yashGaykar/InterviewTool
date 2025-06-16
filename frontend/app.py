import streamlit as st
import requests
import tempfile
import time

# --- Welcome Page ---
def welcome_page():
    st.title("👋 Welcome to the Exam!")

    # Upload Resume
    st.markdown("---")
    st.subheader("Please upload your resume to get started.")
    uploaded_file = st.file_uploader("Upload your Resume", type="pdf")

    # Upload Exam Details
    st.markdown("---")
    st.subheader("Please upload file given by examiner.")
    exam_details_file = st.file_uploader("Upload exam details file", type="json")


    if (uploaded_file is not None and exam_details_file is not None):
        files = {"resume": uploaded_file, "exam_details": exam_details_file}
        # Upload the resume to the backend and get the candidate ID
        response = requests.post("http://127.0.0.1:8000/upload_resume", files=files, data= {})
        if response.status_code == 200:
            st.session_state.candidate_id = response.json()['candidate_id']
            st.session_state.page = "Audio Recording"  # Redirect to Audio Recording Page
            st.rerun()  # Trigger the page change


# --- Audio Recording Page ---
def audio_page():
    st.title("🎙️ Record Your Introduction")
    st.title("")

    # Record audio using Streamlit's Audio widget
    audio_file = st.file_uploader("Record your audio introduction (MP3 format)", type=["mp3", "wav"])

    if audio_file is not None:
        # Save the uploaded audio file to a temporary location
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(audio_file.read())
            tmp_file_path = tmp_file.name

        # Display uploaded audio for review
        st.audio(tmp_file_path)

        # Upload the audio to the backend
        if st.button("Upload Audio"):
            files = {"audio": open(tmp_file_path, "rb")}
            upload_response = requests.post(f"http://127.0.0.1:8000/upload_audio/{st.session_state.candidate_id}",
                                            files=files)

            if upload_response.status_code == 200:
                st.success("Audio uploaded successfully!")
                st.session_state.page = "MCQ Page"  # Auto redirect to MCQ Page
                st.rerun()  # Trigger the page change
            else:
                st.error("Failed to upload audio. Please try again.")

def mcq_page():
    st.title("🧠 MCQ Section")

    candidate_id = st.session_state.candidate_id
    max_retries = 10
    retry_delay = 2  # seconds

    with st.spinner("Fetching your MCQs... Please wait."):
        for attempt in range(max_retries):
            response = requests.get(f"http://127.0.0.1:8000/get_mcq/{candidate_id}")

            if response.status_code == 200:
                mcqs = response.json()
                break  # Success, exit the loop
            else:
                time.sleep(retry_delay)
        else:
            st.error("Failed to fetch MCQs after several attempts. Please try again later.")
            return  # Stop further execution of the page

    mcq_answers = []  # To store answers

    for i, mcq in enumerate(mcqs):
        st.markdown("---")
        question_no = i + 1
        question = mcq['question']
        options = mcq['options']
        answer = st.radio(f"**{question_no}. {question}**", options, index=None)
        mcq_answers.append({
            "question": question,
            "options": options,
            "correct_answer": mcq["answer"],
            "submitted_answer": answer
        })

    st.markdown("---")
    if st.button("Submit All Answers"):
        submit_data = {"candidate_id": candidate_id, "submitted_mcqs": mcq_answers}
        submit_response = requests.post(f"http://127.0.0.1:8000/submit_all_mcq_answers/", json=submit_data)

        if submit_response.status_code == 200:
            st.success("All MCQ answers submitted successfully!")
            st.session_state.page = "Theory Question"
            st.rerun()
        else:
            st.error("Failed to submit MCQ answers. Please try again.")

    if st.button("Next to Theory Question"):
        st.session_state.page = "Theory Question"
        st.rerun()


# --- Theory Question Page ---
def theory_page():
    st.title("💻 Theory Section")

    # Get Coding Questions from backend
    response = requests.get(f"http://127.0.0.1:8000/get_theory_question/{st.session_state.candidate_id}")
    if response.status_code == 200:
        theory_questions = response.json()
        theory_answers = []  # To store coding answers

        for i, theory in enumerate(theory_questions):
            question = theory['question']
            expected_answer = theory['expected_answer']
            st.subheader(f"{i + 1}. {question}")

            # Custom CSS for textarea
            st.markdown(
                """
                <style>
                textarea {
                    border: 2px solid #4A90E2 !important;
                    border-radius: 8px !important;
                    padding: 10px !important;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )
            submitted_answer = st.text_area(f"Answer here", height=150, key=f"question{i}")
            theory_answers.append({
                "question": question,
                "expected_answer": expected_answer,
                "submitted_answer": submitted_answer
            })
            st.write("")
            st.write("")

        # Submit all theory answers at once
        if st.button("Submit All Theory Answers"):
            submit_data = {"candidate_id": st.session_state.candidate_id, "submitted_theory_questions": theory_answers}
            submit_response = requests.post(f"http://127.0.0.1:8000/submit_all_theory_answers/", json=submit_data)

            if submit_response.status_code == 200:
                st.success("All theory answers submitted successfully!")
                st.session_state.page = "Coding Question"
                st.rerun()
            else:
                st.error("Failed to submit theory answers. Please try again.")

    if st.button("Next to Coding Question"):
        st.session_state.page = "Coding Question"
        st.rerun()




# --- Coding Question Page ---
def coding_page():
    st.title("💻 Coding Section")

    st.text("")
    st.text("You can use following compilers to run the test cases.\nPlease copy and paste the code in appropraite block below.")
    st.subheader("Online Compilers")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.link_button("Python Compiler", "https://www.programiz.com/python-programming/online-compiler")
    with col2:
        st.link_button("Java Compiler", "https://www.programiz.com/java-programming/online-compiler")
    with col3:
        st.link_button("C++ Compiler", "https://www.programiz.com/cpp-programming/online-compiler")
    with col4:
        st.link_button("Java Script Compiler", "https://www.programiz.com/javascript/online-compiler")
    st.markdown("---")

    # Get Coding Questions from backend
    response = requests.get(f"http://127.0.0.1:8000/get_coding_question/{st.session_state.candidate_id}")
    if response.status_code == 200:
        coding_questions = response.json()
        coding_answers = []  # To store coding answers

        for i, coding in enumerate(coding_questions):
            question_name = coding['name']
            description = coding['description']
            examples = coding['example']
            st.header(f"{i + 1}. {question_name}")
            st.subheader(description)

            # 👇 Show examples nicely
            st.markdown("**Examples:**")
            for example in examples:
                input_data = example['input']
                expected_output = example['expected_output']
                example_description = example['description']

                with st.expander(f"Example {examples.index(example)+1}"):
                    st.markdown(f"**Input:** `{input_data}`")
                    st.markdown(f"**Expected Output:** `{expected_output}`")
                    st.markdown(f"**Explanation:** {example_description}")

            # Custom CSS for textarea
            st.markdown(
                """
                <style>
                textarea {
                    border: 2px solid #4A90E2 !important;
                    border-radius: 8px !important;
                    padding: 10px !important;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )
            code = st.text_area(f"Enter code for **{question_name}** here", height=200)
            coding_answers.append({
                "question_name": question_name,
                "question_description": description,
                "language": "python",
                "submitted_code": code
            })
            st.write("")
            st.write("")

        # Submit all coding answers at once
        if st.button("Submit All Coding Answers"):
            # Send all coding answers in a single API call
            submit_data = {"candidate_id": st.session_state.candidate_id, "submitted_coding_questions": coding_answers}
            submit_response = requests.post(f"http://127.0.0.1:8000/submit_all_coding_answers/", json=submit_data)

            if submit_response.status_code == 200:
                st.success("All coding answers submitted successfully!")
                st.session_state.page = "Final Result"  # Redirect to Final Result page
                st.rerun()  # Trigger the page change
            else:
                st.error("Failed to submit coding answers. Please try again.")

    if st.button("Finish Test"):
        st.session_state.page = "Final Result"
        st.rerun()

def final_result_page():
    st.title("Download Your Final Result")

    if st.button("Generate and Download Final Result"):
        with st.spinner("Generating Final Result..."):
            generate_response = requests.post(
                f"http://127.0.0.1:8000/generate_final_result/",
                params={"candidate_id": st.session_state.candidate_id}
            )

        if generate_response.status_code == 200:
            st.success("Final result ZIP generated successfully!")
            result_data = generate_response.json()
            candidate_name = result_data["candidate_name"]

            # Download the ZIP
            download_response = requests.get(
                f"http://127.0.0.1:8000/download_zip/",
                params={"candidate_id": st.session_state.candidate_id},
                stream=True
            )

            if download_response.status_code == 200:
                zip_content = download_response.content
                st.download_button(
                    label="Download Final Result ZIP",
                    data=zip_content,
                    file_name=f"{candidate_name}_Final_Result.zip",
                    mime="application/zip"
                )
            else:
                st.error("Failed to download final result ZIP. Please try again.")

            # Fetch and display the Final Report Text
            report_response = requests.get(
                f"http://127.0.0.1:8000/get_final_report/",
                params={"candidate_id": st.session_state.candidate_id}
            )

            if report_response.status_code == 200:
                report_data = report_response.json()
                final_report_text = report_data["final_report"]

                # Clean up code block markers if present
                if final_report_text.startswith("```text") and final_report_text.endswith("```"):
                    final_report_text = final_report_text[7:-3].strip()

                st.header(candidate_name.replace("_", " "))
                import re
                matches = re.findall(r"Marks:\s*(\d+)/(\d+)", final_report_text)
                if matches:
                    obtained_marks, total_marks = matches[-1]  # 👈 pick the last occurrence
                    st.markdown(f"### 🏆 Final Score: **{obtained_marks} / {total_marks}**")
                else:
                    st.warning("Could not extract marks from report.")

                # Show the rest of the report in smaller font
                st.subheader("Final Report Summary")
                st.markdown(
                    f"<div style='font-size: 14px; line-height: 1.6; color: #444;'>{final_report_text.replace(chr(10), '<br>')}</div>",
                    unsafe_allow_html=True
                )
            else:
                st.error("Failed to fetch final report. Please try again.")
        else:
            st.error("Failed to generate final result. Please try again.")

    st.text("")
    if st.button("End Test"):
        st.session_state.page = "Welcome Page"
        st.rerun()


# Define the pages as a dictionary
PAGES = {
    "Welcome Page": welcome_page,
    "Audio Recording": audio_page,
    "MCQ Page": mcq_page,
    "Theory Question": theory_page,
    "Coding Question": coding_page,
    "Final Result": final_result_page
}

# Default page when starting
def main():
    # Initialize session state if not already
    if 'page' not in st.session_state:
        st.session_state.page = "Welcome Page"

    # Display the current page
    page = st.session_state.page
    PAGES[page]()  # Call the corresponding page function


if __name__ == "__main__":
    main()

# streamlit run app.py