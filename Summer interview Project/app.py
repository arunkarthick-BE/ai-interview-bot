from flask import Flask, render_template, request, session, redirect, url_for
import os
import pypdf
from google import genai

app = Flask(__name__)
app.secret_key = "super_secret_interview_key_123"

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Gemini Client Initialize
client = genai.Client(
    api_key=os.environ.get("GOOGLE_API_KEY")
)

def extract_text_from_pdf(pdf_path):
    try:
        reader = pypdf.PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text
    except Exception as e:
        print(f"Error parsing PDF: {e}")
        return ""

@app.route('/')
def login():
    session.clear() # Fresh session for new interview
    return render_template('login.html')

@app.route('/interview', methods=['GET', 'POST'])
def interview():
    # Initializing session variables safely
    if 'current_question' not in session:
        session['current_question'] = 0
    if 'questions' not in session:
        session['questions'] = []
    if 'answers' not in session:
        session['answers'] = []

    if request.method == 'POST':
        
        # CONDITION 1: Resume Upload Round
        if 'resume' in request.files and request.files['resume'].filename != '':
            resume = request.files['resume']
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], resume.filename)
            resume.save(filepath)
            
            resume_text = extract_text_from_pdf(filepath)
            
            if resume_text.strip():
                prompt = """You are a very friendly HR and Technical Recruiter. Analyze this candidate's resume text:\n---\n""" + resume_text + """\n---\nTask: Generate exactly 10 friendly, beginner-friendly interview questions based on the candidate's resume and personal attributes.\n\nStrict 10-Question Breakdown Blueprint:\n- Question 1 & 2 (Studies & Education): Ask about their college experience, major, or why they chose this degree.\n- Question 3 & 4 (Technical Skills): Ask simple, fundamental questions strictly based on the programming languages or tools listed in their resume.\n- Question 5 & 6 (Projects): Ask about the functionality or what they learned while building the projects listed in their resume.\n- Question 7 & 8 (Personal Character & Soft Skills): Ask deep behavioral/personal questions about their nature (e.g., 'How do you handle stress or tight deadlines?', 'Are you a team player or do you prefer working alone? Why?').\n- Question 9 & 10 (Favoritism & Future Goals): Ask about their personal choices and goals (e.g., 'What is your favorite programming language and why do you love it?', 'Where do you want to see yourself professionally in the next 3 years?').\n\nGuidelines:\n- Keep all 10 questions very simple, clear, and direct.\n- Format the output exactly like a clear list with each question on a new line.\n- Do not add introductory texts, markdown bullet points, numbers, or extra text. Just return the 10 questions directly, separated by newlines."""
                try:
                    response = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=prompt
                    )
                    
                    ai_output = response.text.strip().split('\n')
                    cleaned_questions = [q.strip() for q in ai_output if q.strip()]
                    
                    # Locking exactly 10 questions into session
                    session['questions'] = cleaned_questions[:10]  
                    session['current_question'] = 0
                    session['answers'] = []
                    session.modified = True 
                    
                except Exception as e:
                    print(f"Gemini Call Failed: {e}")
                    session['questions'] = ["AI Generation Failed. Check API Key in terminal."]

        # CONDITION 2: "Next" button clicked with user answer
        elif request.form.get("answer") is not None:
            answer = request.form.get("answer")
            
            local_answers = list(session.get('answers', []))
            local_answers.append(answer)
            session['answers'] = local_answers
            
            session['current_question'] += 1
            session.modified = True

    # Redirection flow check
    if not session.get('questions'):
        return redirect(url_for('login'))

    if session['current_question'] >= len(session['questions']):
        return redirect(url_for('result'))

    q_idx = session['current_question']
    current_q_text = session['questions'][q_idx]

    return render_template(
        'interview.html',
        question=current_q_text,
        qno=q_idx + 1
    )

@app.route('/result')
def result():
    interview_questions = session.get('questions', [])
    user_answers = session.get('answers', [])
    
    # Debugging logs in your terminal window
    print(f"DEBUG QUESTIONS: {interview_questions}")
    print(f"DEBUG ANSWERS: {user_answers}")

    if not interview_questions or not user_answers:
        return render_template('result.html', evaluation="<h3>Data missing error.</h3><p>Please restart the interview and ensure you answer the questions.</p>")

    interview_data = ""
    for i, (q, a) in enumerate(zip(interview_questions, user_answers)):
        interview_data += f"Question {i+1}: {q}\nCandidate Answer: {a}\n\n"

    evaluation_prompt = f"""
    You are an expert HR Executive and Speech Coach. Evaluate the candidate's performance based on the questions and answers provided below.
    Note: The candidate used Voice Speech-to-Text input, so analyze their answer volume and phrasing for Confidence and Hesitation.
    ---
    {interview_data}
    ---
    Task:
    1. Calculate a Total Score out of 100 based on Technical Accuracy, Quality, and Communication.
    2. Provide a dedicated "Confidence & Communication Metrics" section checking for hesitation, brief answers, or clear expressive delivery.
    3. Provide a detailed, beginner-friendly feedback report for each question. Give practical suggestions if they hesitated, gave very short answers, or missed points.
    
    Format the output exactly using HTML tags like this (Do not add ```html wrapper, just raw HTML string):
    <h3>Total Score: <span style="color: #2563eb;">[Insert Score here]/100</span></h3>
    <br>
    
    <div style="background-color: #eff6ff; padding: 15px; border-left: 5px solid #3b82f6; border-radius: 4px;">
        <h4>🎙️ Confidence & Fluency Analysis:</h4>
        <p><strong>Overall Tone:</strong> [Analyze if they sounded confident, shy, or brief based on answers]</p>
        <p><strong>Hesitation/Fluency Feedback:</strong> [Provide clear advice on where they seemed to hesitate, use filler concepts, or gave too short answers, and how to speak fluently without fear]</p>
    </div>
    <br>
    
    <h4>Question-by-Question Evaluation:</h4>
    <ul>
      <li><strong>Question 1:</strong> [Technical Feedback + Confidence & Phrasing Suggestions]</li>
      <li><strong>Question 2:</strong> [Technical Feedback + Confidence & Phrasing Suggestions]</li>
      ... up to 10 questions ...
    </ul>
    <br>
    <h4>Overall Career & Communication Suggestions:</h4>
    <p>[Insert overall improvements on how to reduce shivering/fear and boost confidence in real interviews]</p>
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=evaluation_prompt
        )
        ai_evaluation_html = response.text.strip()
    except Exception as e:
        print(f"Evaluation Failed: {e}")
        ai_evaluation_html = "<p>AI Evaluation failed to load. Please try again.</p>"

    return render_template('result.html', evaluation=ai_evaluation_html)

if __name__ == '__main__':
    app.run(debug=True)
