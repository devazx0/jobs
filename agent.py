import os
import json
from dotenv import load_dotenv
import resend
from jobspy import scrape_jobs
import google.generativeai as genai

load_dotenv()

# Monkey-patch: handle missing countries in jobspy's Country enum
import jobspy.model as _jm
_orig_from_string = _jm.Country.from_string.__func__
@classmethod
def _patched_from_string(cls, country_str):
    try:
        return _orig_from_string(cls, country_str)
    except ValueError:
        country_str = country_str.strip().lower()
        fallback = {"kenya": "south africa"}
        if country_str in fallback:
            return _orig_from_string(cls, fallback[country_str])
        raise
_jm.Country.from_string = _patched_from_string

# --- CONFIGURATION ---
JOB_TITLES = ["Backend Engineer", "AI Engineer", "Software Engineer"]
LOCATIONS = [
    ("Remote", True),
    ("Nigeria", False),
    ("United States", False),
    ("United Kingdom", False),
    ("Netherlands", False),
    ("Germany", False),
    ("Kenya", False),
    ("South Africa", False),
]
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER") 
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Resend setup
resend.api_key = os.getenv("RESEND_API_KEY")
SENDER_IDENTITY = "AI Agent <onboarding@resend.dev>" # Update to your verified domain later

def get_jobs():
    print("Scraping jobs...")
    all_jobs = []
    seen_urls = set()
    for title in JOB_TITLES:
        for location, is_remote in LOCATIONS:
            jobs_df = scrape_jobs(
                site_name=["linkedin"],
                search_term=title,
                location=location,
                results_wanted=10,
                is_remote=is_remote,
            )
            if not jobs_df.empty:
                for _, row in jobs_df.iterrows():
                    url = row.get("job_url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_jobs.append({
                            "title": row.get("title", ""),
                            "company": row.get("company", ""),
                            "job_url": url,
                            "description": row.get("description", ""),
                            "job_type": row.get("job_type", ""),
                        })
    return all_jobs

def evaluate_jobs(jobs):
    if not jobs: return []
    print(f"Evaluating {len(jobs)} jobs with Gemini Flash...")
    genai.configure(api_key=GEMINI_API_KEY)
    
    model = genai.GenerativeModel('gemini-flash-latest', generation_config={"response_mime_type": "application/json"})
    
    prompt = f"""
    You are an expert technical recruiter and career advisor.
    My Profile:
    - I am a Backend & AI Engineer.
    - My core stack: Node.js, NestJS, Prisma, TypeORM, PostgreSQL.
    - Infrastructure/DevOps: Docker, WSL2, Git, Railway, Vercel, DigitalOcean.
    - AI/Data: Building LLM Agents, Recommendation Systems (Collaborative Filtering, SVD, KNN).
    - Goal: Looking for remote Full-Time roles OR Freelance/Contract gigs.
    
    Review the following job listings. For each job:
    1. Check if the job type is strictly Full-Time, Contract, or Freelance. If it is unpaid, an internship, or strictly requires legacy enterprise tech, score it 0.
    2. Score the job from 0 to 100 based on how well it aligns with my modern backend (NestJS/Postgres) and AI engineering skills.
    3. Tag it with one of: "Highly Aligned", "Good Match", "Worth a Shot", "Skip".
    4. Write a 1-sentence reasoning for your score.
    
    Return a JSON array of objects with the following keys: "title", "company", "job_url", "score", "tag", "reasoning".
    
    Jobs Data:
    {json.dumps(jobs)}
    """
    
    response = model.generate_content(prompt)
    evaluated_jobs = json.loads(response.text)
    return sorted(evaluated_jobs, key=lambda x: x['score'], reverse=True)

def send_email(sorted_jobs):
    print("Sending email via Resend...")
    if not sorted_jobs:
        print("No highly scored jobs found today. Skipping email.")
        return

    html_content = "<h2>Your Curated Job Matches</h2>"
    for job in sorted_jobs:
        color = "green" if job['score'] >= 80 else "orange"
        html_content += f"""
        <div style="margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 10px; font-family: sans-serif;">
            <h3 style="margin: 0;"><a href="{job['job_url']}" style="color: #0056b3; text-decoration: none;">{job['title']} @ {job['company']}</a></h3>
            <p style="margin: 5px 0;">
                <strong style="color: {color};">Score: {job['score']}/100</strong> | 
                <span style="background: #eee; padding: 2px 6px; border-radius: 4px; font-size: 12px;">{job['tag']}</span>
            </p>
            <p style="margin: 5px 0; color: #444; font-size: 14px;"><em>{job['reasoning']}</em></p>
        </div>
        """

    try:
        r = resend.Emails.send({
            "from": SENDER_IDENTITY,
            "to": [EMAIL_RECEIVER],
            "subject": "Daily AI Job Matches: Backend & AI Engineering",
            "html": html_content
        })
        print(f"Email sent successfully! ID: {r['id']}")
    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == "__main__":
    raw_jobs = get_jobs()
    if raw_jobs:
        scored_jobs = evaluate_jobs(raw_jobs)
        
        # Filter for quality: only send jobs scoring 65 or higher
        good_jobs = [j for j in scored_jobs if j['score'] >= 65]
        
        if good_jobs:
            send_email(good_jobs)
        else:
            print("No jobs passed the score threshold today.")