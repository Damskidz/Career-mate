import os
import re
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Tuple

import gradio as gr

DB_PATH = Path(__file__).with_name('careermate.db')

GRADE_POINTS = {"A1": 8, "B2": 7, "B3": 6, "C4": 5, "C5": 4, "C6": 3, "D7": 0, "E8": 0, "F9": 0}
GRADE_PATTERN = re.compile(r"\b(A1|B2|B3|C4|C5|C6|D7|E8|F9)\b", re.I)
WEIGHTS = {"subject": 0.30, "grade": 0.25, "interest": 0.20, "margin": 0.15, "availability": 0.10}

INTEREST_TAGS = {
    "building": "R", "repair": "R", "machines": "R", "engineering": "R",
    "science": "I", "research": "I", "analysis": "I", "technology": "I", "coding": "I",
    "art": "A", "design": "A", "writing": "A", "creative": "A",
    "helping": "S", "teaching": "S", "health": "S", "people": "S",
    "business": "E", "leadership": "E", "sales": "E", "entrepreneurship": "E",
    "records": "C", "accounting": "C", "organisation": "C", "data": "C"
}

SUBJECT_ALIASES = {
    "maths": "Mathematics", "mathematics": "Mathematics", "english": "English Language",
    "physics": "Physics", "chemistry": "Chemistry", "biology": "Biology",
    "further maths": "Further Mathematics", "f/maths": "Further Mathematics",
    "government": "Government", "economics": "Economics", "computer": "Computer Science",
    "computer science": "Computer Science", "agric": "Agricultural Science",
    "agricultural science": "Agricultural Science", "literature": "Literature in English",
    "accounting": "Financial Accounting"
}

CSS = """
:root {--cm-purple:#4f46e5; --cm-deep:#24185f; --cm-bg:#f5f7fb; --cm-card:#ffffff;}
.gradio-container {max-width: 1520px !important; margin:0 auto !important; background:var(--cm-bg) !important;}
body {background:var(--cm-bg) !important;}
#hero {background:linear-gradient(135deg,#3825b9 0%,#675cf6 60%,#6d63ff 100%); color:white; padding:24px 30px; border-radius:18px; margin:4px 0 16px; box-shadow:0 12px 30px rgba(62,47,190,.20);}
#hero h1 {margin:0;font-size:30px;line-height:1.15;} #hero p{margin:7px 0 0;opacity:.94;font-size:14px;}
.card {background:white;border:1px solid #e8eaf2;border-radius:16px;padding:16px;box-shadow:0 4px 16px rgba(30,41,59,.05);}
.stat {background:white;border:1px solid #e9eaf3;border-radius:15px;padding:15px;text-align:center;box-shadow:0 3px 12px rgba(30,41,59,.04)}
.stat b {font-size:25px;color:#4f46e5;display:block}.small-note,.footer-note{font-size:12px;color:#6b7280}.footer-note{text-align:center;margin-top:14px}
.tabs > .tab-nav {background:#fff;border:1px solid #e8eaf2;border-radius:14px;padding:7px;box-shadow:0 3px 14px rgba(30,41,59,.04)}
button.selected {background:#4f46e5 !important;color:white !important;border-radius:10px !important;}
button.primary {background:#4f46e5 !important;border-color:#4f46e5 !important;}
.dataframe, .gr-dataframe {border-radius:14px !important;overflow:hidden !important;}
#brandbar {display:flex;align-items:center;gap:12px;background:#211758;color:#fff;padding:13px 17px;border-radius:14px;margin-bottom:12px;}
#brandbar .mark{width:38px;height:38px;border-radius:11px;background:linear-gradient(135deg,#6f63ff,#8c7cff);display:grid;place-items:center;font-size:21px;font-weight:800;}
#brandbar .brand{font-weight:800;font-size:18px} #brandbar .sub{font-size:11px;opacity:.8}
.section-title {font-size:20px;font-weight:800;color:#20243a;margin:3px 0 8px}.muted{color:#6b7280;font-size:13px}
"""


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    if DB_PATH.exists():
        return
    c = conn()
    c.executescript('''
    PRAGMA foreign_keys = ON;
    CREATE TABLE programme (
        programme_id TEXT PRIMARY KEY,
        programme_name TEXT NOT NULL,
        award_type TEXT NOT NULL,
        utme_subjects TEXT NOT NULL,
        olevel_requirement TEXT NOT NULL,
        cut_off_mark INTEGER NOT NULL,
        riasec_code TEXT,
        last_updated TEXT
    );
    CREATE TABLE institution (
        institution_id TEXT PRIMARY KEY,
        institution_name TEXT NOT NULL,
        institution_type TEXT,
        town TEXT NOT NULL,
        annual_cost REAL
    );
    CREATE TABLE offering (
        institution_id TEXT NOT NULL,
        programme_id TEXT NOT NULL,
        cut_off_mark INTEGER NOT NULL,
        PRIMARY KEY (institution_id, programme_id)
    );
    CREATE TABLE career (
        career_id TEXT PRIMARY KEY,
        programme_id TEXT NOT NULL,
        career_title TEXT NOT NULL,
        sector TEXT,
        skills_required TEXT,
        entry_salary TEXT,
        demand_level TEXT
    );
    CREATE TABLE vocational_pathway (
        pathway_id TEXT PRIMARY KEY,
        pathway_name TEXT NOT NULL,
        duration TEXT,
        training_fee REAL,
        centre_name TEXT,
        town TEXT,
        demand_level TEXT,
        tags TEXT
    );
    CREATE TABLE session_log (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_json TEXT,
        user_message TEXT,
        bot_response TEXT,
        intent TEXT,
        rating INTEGER,
        comment TEXT,
        logged_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    ''')

    programmes = [
        ("PRG-001","Computer Engineering","B.Eng.","Mathematics,Physics,Chemistry","5 credits including English, Mathematics, Physics and Chemistry",200,"RI","2025-08-01"),
        ("PRG-002","Computer Science","B.Sc.","Mathematics,Physics,Chemistry","5 credits including English and Mathematics",190,"IC","2025-08-01"),
        ("PRG-003","Electrical/Electronic Engineering","B.Eng.","Mathematics,Physics,Chemistry","5 credits including English, Mathematics, Physics and Chemistry",200,"RI","2025-08-01"),
        ("PRG-004","Information Technology","B.Sc.","Mathematics,Physics,Chemistry","5 credits including English and Mathematics",180,"IC","2025-08-01"),
        ("PRG-005","Accounting","B.Sc.","Mathematics,Economics,Government","5 credits including English, Mathematics and Economics",180,"CE","2025-08-01"),
        ("PRG-006","Business Administration","B.Sc.","Mathematics,Economics,Government","5 credits including English and Mathematics",175,"EC","2025-08-01"),
        ("PRG-007","Biochemistry","B.Sc.","Biology,Chemistry,Physics","5 credits including English, Mathematics, Biology and Chemistry",185,"IS","2025-08-01"),
        ("PRG-008","Nursing Science","B.NSc.","Biology,Chemistry,Physics","5 credits including English, Mathematics, Biology, Chemistry and Physics",220,"SI","2025-08-01"),
    ]
    c.executemany("INSERT INTO programme VALUES (?,?,?,?,?,?,?,?)", programmes)

    institutions = [
        ("INS-01","Ekiti State University","University","Ado-Ekiti",250000),
        ("INS-02","Federal University Oye-Ekiti","University","Oye-Ekiti",180000),
        ("INS-03","Bamidele Olumilua University","University","Ikere-Ekiti",220000),
        ("INS-04","Afe Babalola University","University","Ado-Ekiti",1800000),
        ("INS-05","Federal Polytechnic Ado-Ekiti","Polytechnic","Ado-Ekiti",120000),
        ("INS-06","College of Education Ikere-Ekiti","College of Education","Ikere-Ekiti",110000),
    ]
    c.executemany("INSERT INTO institution VALUES (?,?,?,?,?)", institutions)

    offerings = []
    for ins in institutions:
        for p in programmes:
            if ins[2] == "Polytechnic" and p[2].startswith("B."):
                continue
            if ins[2] == "College of Education" and p[0] not in {"PRG-002","PRG-004","PRG-006"}:
                continue
            offerings.append((ins[0], p[0], max(160, p[5] - (10 if ins[0] in {"INS-05","INS-06"} else 0))))
    c.executemany("INSERT INTO offering VALUES (?,?,?)", offerings)

    careers = [
        ("CAR-01","PRG-001","Computer Engineer","Technology","hardware, networking, embedded systems","₦180,000–₦450,000/month","High"),
        ("CAR-02","PRG-002","Software Developer","Technology","programming, problem solving, databases","₦200,000–₦600,000/month","High"),
        ("CAR-03","PRG-003","Electrical Engineer","Engineering","circuits, power systems, maintenance","₦180,000–₦500,000/month","High"),
        ("CAR-04","PRG-004","IT Support / Systems Analyst","Technology","support, systems, networking","₦150,000–₦400,000/month","High"),
        ("CAR-05","PRG-005","Accountant","Finance","bookkeeping, audit, analysis","₦140,000–₦400,000/month","Medium"),
        ("CAR-06","PRG-006","Business Analyst","Business","analysis, communication, strategy","₦160,000–₦450,000/month","Medium"),
        ("CAR-07","PRG-007","Laboratory Scientist","Health/Science","lab analysis, chemistry, documentation","₦140,000–₦350,000/month","Medium"),
        ("CAR-08","PRG-008","Registered Nurse","Health","clinical care, communication, patient support","₦150,000–₦450,000/month","High"),
    ]
    c.executemany("INSERT INTO career VALUES (?,?,?,?,?,?,?)", careers)

    vocational = [
        ("VOC-01","Software Development","6-12 months",180000,"Ado Digital Skills Hub","Ado-Ekiti","High","coding technology computer"),
        ("VOC-02","Solar Installation & Maintenance","4-6 months",120000,"Ekiti Technical Centre","Ado-Ekiti","High","engineering electrical practical"),
        ("VOC-03","CAD and Technical Drawing","4 months",90000,"Technical Training Centre","Ikere-Ekiti","Medium","design engineering drawing"),
        ("VOC-04","Mobile Phone & Laptop Repair","6 months",100000,"ICT Skills Centre","Ado-Ekiti","High","repair computer electronics"),
        ("VOC-05","CNC Machining","6-9 months",150000,"Technical College","Ado-Ekiti","Medium","machine engineering practical"),
        ("VOC-06","Electrical Installation","6 months",110000,"Ekiti Technical Centre","Ado-Ekiti","High","electrical engineering repair"),
    ]
    c.executemany("INSERT INTO vocational_pathway VALUES (?,?,?,?,?,?,?,?)", vocational)
    c.commit(); c.close()


init_db()


def normalise_subjects(text: str) -> List[str]:
    t = text.lower()
    found = []
    for alias, canonical in sorted(SUBJECT_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
        if alias in t and canonical not in found:
            found.append(canonical)
    return found


def interest_code(text: str) -> str:
    t = text.lower()
    codes = []
    for token, code in INTEREST_TAGS.items():
        if token in t:
            codes.append(code)
    if not codes:
        return "I"
    # stable frequency order
    return max(sorted(set(codes)), key=codes.count)


def profile_from_inputs(name, age, lga, school_type, subjects_text, grades_text, interests, projected_utme):
    subjects = normalise_subjects(subjects_text)
    grade_pairs = GRADE_PATTERN.findall(grades_text or "")
    points = sorted([GRADE_POINTS[g.upper()] for g in grade_pairs], reverse=True)[:5]
    aggregate = sum(points) if points else 20
    return {
        "name": name or "Student",
        "age": age or "",
        "lga": lga or "Ado-Ekiti",
        "school_type": school_type or "Public",
        "subjects": subjects,
        "grades": [g.upper() for g in grade_pairs],
        "aggregate": aggregate,
        "interests": interests or "technology",
        "riasec": interest_code(interests or "technology"),
        "projected_utme": int(projected_utme or 180),
    }


def score_programmes(profile: Dict) -> List[Dict]:
    c = conn()
    rows = c.execute("SELECT * FROM programme").fetchall()
    results = []
    for p in rows:
        required = [s.strip() for s in p["utme_subjects"].split(",")]
        offered = set(profile["subjects"])
        subject_score = 100 if all(r in offered for r in required) else max(0, int(100 * len(set(required)&offered) / max(1,len(required))))
        grade_score = min(100, 100 * profile.get("aggregate", 20) / 40)
        interest_score = 95 if profile.get("riasec") in (p["riasec_code"] or "") else 55
        margin = profile.get("projected_utme", 180) - p["cut_off_mark"]
        margin_score = max(0, min(100, 50 + margin))
        availability = 100 if c.execute("SELECT 1 FROM offering WHERE programme_id=? LIMIT 1", (p["programme_id"],)).fetchone() else 60
        score = (WEIGHTS["subject"]*subject_score + WEIGHTS["grade"]*grade_score + WEIGHTS["interest"]*interest_score + WEIGHTS["margin"]*margin_score + WEIGHTS["availability"]*availability)
        if score >= 40:
            results.append({
                "programme_id": p["programme_id"],
                "programme": p["programme_name"],
                "award": p["award_type"],
                "score": round(score),
                "cut_off": p["cut_off_mark"],
                "requirements": p["olevel_requirement"],
                "subject_score": round(subject_score),
                "grade_score": round(grade_score),
                "interest_score": round(interest_score),
                "margin_score": round(margin_score),
                "availability": round(availability),
            })
    c.close()
    return sorted(results, key=lambda x: x["score"], reverse=True)[:6]


def dashboard_html():
    c = conn()
    counts = {
        "programmes": c.execute("select count(*) from programme").fetchone()[0],
        "careers": c.execute("select count(*) from career").fetchone()[0],
        "institutions": c.execute("select count(*) from institution").fetchone()[0],
        "vocational": c.execute("select count(*) from vocational_pathway").fetchone()[0],
    }
    c.close()
    return f"""
    <div id='hero'><h1>CareerMate — AI Career Guidance Chatbot</h1><p>Personalised, explainable guidance for secondary school leavers in Ekiti State.</p></div>
    <div style='display:grid;grid-template-columns:repeat(4,1fr);gap:12px'>
      <div class='stat'><b>{counts['careers']}</b>Careers</div>
      <div class='stat'><b>{counts['programmes']}</b>Programmes</div>
      <div class='stat'><b>{counts['institutions']}</b>Institutions</div>
      <div class='stat'><b>{counts['vocational']}</b>Vocational pathways</div>
    </div>
    <div class='card' style='margin-top:14px'><b>How CareerMate works</b><ol><li>Enter your subjects, grades and interests.</li><li>The system extracts and structures your profile.</li><li>Programmes are scored using transparent weighted criteria.</li><li>You receive ranked recommendations, institutions, careers and vocational alternatives.</li></ol></div>
    <div class='small-note'>Demonstration database supplied for project defence. Replace sample admission figures with verified current-cycle data before production use.</div>
    """


def render_profile(name, age, lga, school_type, subjects, grades, interests, projected_utme):
    p = profile_from_inputs(name, age, lga, school_type, subjects, grades, interests, projected_utme)
    completeness = sum(bool(p.get(k)) for k in ["name","lga","subjects","interests","projected_utme"]) / 5 * 100
    html = f"""
    <div class='card'><h3>Student Profile</h3>
    <p><b>Name:</b> {p['name']} &nbsp; <b>LGA:</b> {p['lga']} &nbsp; <b>School:</b> {p['school_type']}</p>
    <p><b>Recognised subjects:</b> {', '.join(p['subjects']) if p['subjects'] else 'None recognised yet'}</p>
    <p><b>Detected grades:</b> {', '.join(p['grades']) if p['grades'] else 'No grades supplied'} &nbsp; <b>Best-five aggregate:</b> {p['aggregate']}/40</p>
    <p><b>Interest orientation:</b> {p['riasec']} &nbsp; <b>Projected UTME:</b> {p['projected_utme']}</p>
    <p><b>Profile completeness:</b> {completeness:.0f}%</p></div>"""
    return html, p


def recommendation_table(profile):
    if not profile or not profile.get("subjects"):
        return [["Add at least three subjects", "-", "-", "-"]], "Please complete the Student Profile first.", None
    recs = score_programmes(profile)
    table = [[r["programme"], r["award"], f"{r['score']}%", r["requirements"]] for r in recs]
    if not recs:
        return [], "No programme met the threshold. Review vocational pathways.", None
    top = recs[0]
    breakdown = {
        "Subject combination": top["subject_score"],
        "Grade strength": top["grade_score"],
        "Interest alignment": top["interest_score"],
        "UTME margin": top["margin_score"],
        "Ekiti availability": top["availability"],
    }
    explanation = (f"Top match: **{top['programme']} ({top['score']}% match)**. The score combines subject fit, "
                   f"grade strength, interest alignment, projected UTME margin and local availability. "
                   f"This is a compatibility score, not a probability of admission.")
    return table, explanation, breakdown


def institution_table(programme_name, projected_utme):
    if not programme_name:
        return []
    c = conn()
    p = c.execute("SELECT programme_id FROM programme WHERE programme_name=?", (programme_name,)).fetchone()
    if not p:
        c.close(); return []
    rows = c.execute('''SELECT i.institution_name, i.institution_type, i.town, o.cut_off_mark, i.annual_cost
                        FROM offering o JOIN institution i ON i.institution_id=o.institution_id
                        WHERE o.programme_id=? ORDER BY o.cut_off_mark DESC''', (p[0],)).fetchall()
    c.close()
    score = int(projected_utme or 180)
    return [[r[0], r[1], r[2], r[3], f"₦{int(r[4]):,}", "Eligible" if score >= r[3] else "Borderline"] for r in rows]


def career_table(programme_name):
    c = conn()
    rows = c.execute('''SELECT c.career_title, c.sector, c.skills_required, c.entry_salary, c.demand_level
                        FROM career c JOIN programme p ON p.programme_id=c.programme_id
                        WHERE p.programme_name=?''', (programme_name,)).fetchall()
    c.close()
    return [[r[0],r[1],r[2],r[3],r[4]] for r in rows]


def vocational_table(interests):
    c = conn(); rows = c.execute("SELECT pathway_name,duration,training_fee,centre_name,town,demand_level,tags FROM vocational_pathway").fetchall(); c.close()
    tokens = set((interests or "").lower().split())
    scored=[]
    for r in rows:
        overlap=len(tokens & set((r[6] or '').lower().split()))
        score=70+min(25, overlap*8)
        scored.append([r[0],r[1],f"₦{int(r[2]):,}",r[3],r[4],r[5],f"{score}%"])
    return sorted(scored,key=lambda x:int(x[-1].rstrip('%')), reverse=True)


def extract_uploaded(file_obj):
    if file_obj is None:
        return "No file uploaded.", ""
    path = file_obj if isinstance(file_obj, str) else getattr(file_obj, 'name', str(file_obj))
    raw = ""
    try:
        if path.lower().endswith('.pdf'):
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                raw = "\n".join(page.extract_text() or "" for page in pdf.pages)
        else:
            import pytesseract
            from PIL import Image
            raw = pytesseract.image_to_string(Image.open(path))
    except Exception as e:
        return f"OCR dependency unavailable or document could not be read: {e}", ""
    found = GRADE_PATTERN.findall(raw)
    if len(found) < 5:
        return "The result sheet could not be read clearly. Please type the grades manually.", raw[:1200]
    best = sorted([GRADE_POINTS[g.upper()] for g in found], reverse=True)[:5]
    return f"Detected {len(found)} grades. Best-five aggregate: {sum(best)}/40.", raw[:1200]


def bot_reply(message, history, profile):
    p = profile or {}
    lower = (message or '').lower()
    if not message:
        return "Please type a question."
    if any(k in lower for k in ["recommend", "course", "study"]):
        if not p.get('subjects'):
            return "Tell me at least three of your best subjects first, then I can recommend suitable programmes."
        recs = score_programmes(p)
        if not recs:
            return "I could not find a degree programme above the compatibility threshold. Please check the Vocational Pathways tab for alternatives."
        top = recs[:3]
        lines = [f"{i+1}. {r['programme']} — {r['score']}% match" for i,r in enumerate(top)]
        return "Based on your profile, your strongest options are:\n\n" + "\n".join(lines) + "\n\nThe percentage is a compatibility score, not a guarantee of admission."
    if "cut" in lower or "requirement" in lower:
        c=conn(); rows=c.execute("SELECT programme_name,cut_off_mark,olevel_requirement FROM programme LIMIT 5").fetchall(); c.close()
        return "Here are sample verified-in-demo requirements:\n\n" + "\n".join([f"• {r[0]}: cut-off {r[1]}; {r[2]}" for r in rows])
    if "vocational" in lower or "trade" in lower or "skill" in lower:
        rows=vocational_table(p.get('interests','technology'))[:4]
        return "Vocational options you can consider:\n\n" + "\n".join([f"• {r[0]} — {r[1]} — {r[-1]} match" for r in rows])
    if "career" in lower or "job" in lower:
        return "Choose a recommended programme in the Career Explorer tab to see linked careers, skills, demand and indicative salary bands."
    return "I can help with course recommendations, admission requirements, institution comparisons, careers and vocational pathways. Try: ‘Recommend a course for me’."


def save_feedback(rating, comment, profile):
    c=conn(); c.execute("INSERT INTO session_log(profile_json,rating,comment) VALUES (?,?,?)", (json.dumps(profile or {}), int(rating or 0), comment or "")); c.commit(); c.close()
    return "Feedback saved. Thank you."


with gr.Blocks(css=CSS, title="CareerMate - AI Career Guidance") as demo:
    profile_state = gr.State({})
    gr.HTML("""<div id='brandbar'><div class='mark'>C</div><div><div class='brand'>CareerMate</div><div class='sub'>AI Career Guidance Chatbot • Ekiti State</div></div></div>""")
    gr.HTML(dashboard_html())

    with gr.Tabs():
        with gr.Tab("Dashboard"):
            gr.HTML("<div class='card'><div class='section-title'>Welcome to CareerMate</div><div class='muted'>Personalised course, institution, career and vocational guidance for secondary school leavers in Ekiti State. Use the navigation tabs to demonstrate the same modules presented in Chapter Four.</div></div>")

        with gr.Tab("Student Profile"):
            with gr.Row():
                with gr.Column():
                    name=gr.Textbox(label="Name", value="Valentine")
                    age=gr.Number(label="Age", value=18)
                    lga=gr.Textbox(label="Local Government Area", value="Ado-Ekiti")
                    school=gr.Dropdown(["Public","Private"], value="Public", label="School type")
                with gr.Column():
                    subjects=gr.Textbox(label="Best subjects", value="Mathematics, Physics, Chemistry, Further Maths")
                    grades=gr.Textbox(label="WAEC / NECO grades", value="A1 B2 B3 C4 C5")
                    interests=gr.Textbox(label="Interests", value="technology, coding, building things")
                    utme=gr.Slider(100,400,value=214,step=1,label="Projected UTME score")
            build=gr.Button("Build / Update Profile", variant="primary")
            profile_html=gr.HTML()
            build.click(render_profile, [name,age,lga,school,subjects,grades,interests,utme], [profile_html, profile_state])

        with gr.Tab("Chat"):
            gr.Markdown("### Conversational Interaction")
            chatbot = gr.ChatInterface(fn=bot_reply, additional_inputs=[profile_state], examples=["Recommend a course for me","What admission requirements should I check?","Show vocational alternatives","What careers can I explore?"])

        with gr.Tab("Result Upload"):
            gr.Markdown("### WAEC / NECO Result Upload and Grade Extraction")
            upload=gr.File(label="Upload PDF, JPG or PNG")
            parse_btn=gr.Button("Extract Grades", variant="primary")
            parse_status=gr.Textbox(label="Extraction result")
            raw_text=gr.Textbox(label="Extracted text preview", lines=8)
            parse_btn.click(extract_uploaded, upload, [parse_status, raw_text])

        with gr.Tab("Recommendations"):
            gr.Markdown("### Ranked Course Recommendations")
            rec_btn=gr.Button("Generate Recommendations", variant="primary")
            rec_table=gr.Dataframe(headers=["Programme","Award","Match","Entry requirement"], datatype=["str","str","str","str"], interactive=False)
            rec_expl=gr.Markdown()
            rec_json=gr.JSON(label="Top-match score breakdown")
            rec_btn.click(recommendation_table, profile_state, [rec_table, rec_expl, rec_json])

        with gr.Tab("Institutions"):
            gr.Markdown("### Course and Institution Matching")
            prog_choices=[r[0] for r in conn().execute("SELECT programme_name FROM programme ORDER BY programme_name").fetchall()]
            prog=gr.Dropdown(prog_choices, value=prog_choices[0], label="Programme")
            inst_utme=gr.Slider(100,400,value=214,step=1,label="Projected UTME score")
            inst_btn=gr.Button("Compare Institutions")
            inst_table=gr.Dataframe(headers=["Institution","Type","Town","Cut-off","Indicative annual cost","Status"], interactive=False)
            inst_btn.click(institution_table,[prog,inst_utme],inst_table)

        with gr.Tab("Career Explorer"):
            gr.Markdown("### Career Pathway Explorer")
            career_prog=gr.Dropdown(prog_choices, value="Computer Engineering" if "Computer Engineering" in prog_choices else prog_choices[0], label="Programme")
            career_btn=gr.Button("Explore Careers")
            career_df=gr.Dataframe(headers=["Career","Sector","Skills","Indicative salary band","Demand"], interactive=False)
            career_btn.click(career_table, career_prog, career_df)

        with gr.Tab("Vocational Pathways"):
            gr.Markdown("### Vocational and Technical Alternatives")
            voc_interest=gr.Textbox(value="technology repair engineering", label="Interests")
            voc_btn=gr.Button("Find Vocational Pathways")
            voc_df=gr.Dataframe(headers=["Pathway","Duration","Fee","Training centre","Town","Demand","Match"], interactive=False)
            voc_btn.click(vocational_table, voc_interest, voc_df)

        with gr.Tab("Session Summary & Feedback"):
            gr.Markdown("### Session Summary and Feedback")
            summary_btn=gr.Button("Generate Session Summary")
            summary=gr.JSON(label="Current student profile")
            summary_btn.click(lambda p: p or {}, profile_state, summary)
            rating=gr.Slider(1,5,value=5,step=1,label="Rate this session")
            comment=gr.Textbox(label="Comment")
            save=gr.Button("Save Feedback", variant="primary")
            status=gr.Textbox(label="Status")
            save.click(save_feedback,[rating,comment,profile_state],status)

    gr.HTML("<div class='footer-note'>CareerMate academic demonstration • AI-based career guidance for secondary school leavers in Ekiti State</div>")

if __name__ == "__main__":
    import os
port = int(os.environ.get('PORT', 8080))
demo.launch(server_name="0.0.0.0", server_port=port)