"""Generate Level3_Journey.pdf, a plain-language walkthrough of our approach.

Uses only ASCII text and built-in fonts so it renders consistently anywhere.
Run: python build_journey_pdf.py
"""

from __future__ import annotations

from fpdf import FPDF
from fpdf.enums import XPos, YPos

NAVY = (23, 42, 69)
BLUE = (37, 99, 162)
GREY = (90, 90, 90)
DARK = (33, 33, 33)

LM, RM = XPos.LMARGIN, XPos.RIGHT
NEXT, TOP = YPos.NEXT, YPos.TOP


class Journey(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*GREY)
        self.cell(0, 8, "Deep Funding Level III - Methodology", align="L")
        self.cell(0, 8, f"Page {self.page_no()}", align="R",
                  new_x=LM, new_y=NEXT)
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*GREY)
        self.cell(0, 10, "deep-funding-l3  -  joinpond.ai", align="C")


def h1(pdf: Journey, text: str) -> None:
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(*NAVY)
    pdf.multi_cell(0, 8, text, new_x=LM, new_y=NEXT)
    pdf.set_draw_color(*BLUE)
    pdf.set_line_width(0.5)
    y = pdf.get_y() + 1
    pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
    pdf.ln(4)


def body(pdf: Journey, text: str) -> None:
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*DARK)
    pdf.multi_cell(0, 6, text, new_x=LM, new_y=NEXT)
    pdf.ln(2)


def bullet(pdf: Journey, text: str) -> None:
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*DARK)
    pdf.set_x(pdf.l_margin + 4)
    pdf.cell(5, 6, "-", new_x=RM, new_y=TOP)
    pdf.multi_cell(0, 6, text, new_x=LM, new_y=NEXT)


def code(pdf: Journey, text: str) -> None:
    pdf.set_fill_color(244, 246, 248)
    pdf.set_font("Courier", "", 10)
    pdf.set_text_color(*NAVY)
    pdf.multi_cell(0, 6, text, fill=True, border=0, new_x=LM, new_y=NEXT)
    pdf.ln(2)


def build() -> None:
    pdf = Journey()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(20, 18, 20)
    pdf.add_page()

    # Title block
    pdf.ln(18)
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(*NAVY)
    pdf.multi_cell(0, 11, "Deep Funding Level III", new_x=LM, new_y=NEXT)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*BLUE)
    pdf.multi_cell(0, 9, "How We Built Our Dependency Weight Model",
                   new_x=LM, new_y=NEXT)
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*GREY)
    pdf.multi_cell(
        0, 6,
        "A plain-language walkthrough of the problem, what we discovered, and "
        "the method behind our submission. No jargon, just the path we took.",
        new_x=LM, new_y=NEXT,
    )
    pdf.ln(8)
    pdf.set_draw_color(*BLUE)
    pdf.set_line_width(0.8)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(10)

    h1(pdf, "The Problem in Plain Terms")
    body(
        pdf,
        "Every software project depends on other projects. The contest gives us "
        "83 repositories and asks a simple question: for each one, how much of "
        "its value should flow to each of its dependencies?"
    )
    body(
        pdf,
        "We put a number (a weight) on every dependency, and for each repository "
        "all of its weights have to add up to 1.0. That is 3,677 (dependency, "
        "repository) pairs to fill in. A panel of human jurors set the true "
        "weights, and our score is how far our numbers are from theirs. Lower is "
        "better."
    )
    body(
        pdf,
        "The hard part: we never see the jury's answers for most repositories, "
        "so we cannot memorize them. We have to build something that judges "
        "well on repositories it has never scored."
    )

    h1(pdf, "Step 1: We Figured Out Exactly How the Score Is Calculated")
    body(
        pdf,
        "Most people optimize blind, because the contest never states the exact "
        "scoring formula. We pinned it down first, because you cannot improve a "
        "number you cannot measure."
    )
    body(
        pdf,
        "The contest gives one small public file of real jury answers (162 pairs "
        "across 3 repositories). We used it as a test sheet and tried formulas "
        "until our local score matched what the leaderboard reported."
    )
    bullet(pdf, "Our first guess (average error per pair) gave 0.006. Way off, so wrong.")
    bullet(
        pdf,
        "The formula that matched: for each repository add up the errors of all "
        "its dependencies, then average that total across repositories. That gave "
        "0.3440, matching our baseline's leaderboard score of 0.34 to the decimals.",
    )
    pdf.ln(2)
    code(pdf, "score = average over repos of\n        ( sum of |our weight - jury weight| )")
    body(
        pdf,
        "We then wrote local_score.py, an exact copy of the scorer. Now we could "
        "test any idea on our own machine before spending a real submission. This "
        "was the single most useful thing we did."
    )

    h1(pdf, "Step 2: We Found Where the Error Actually Comes From")
    body(
        pdf,
        "With the local scorer we could see which dependencies hurt us most. The "
        "answer was clear: in every repository, the top 6 or so dependencies "
        "cause 85 to 100 percent of the total error. The hundreds of tiny "
        "dependencies are already close to the jury and barely move the score."
    )
    body(
        pdf,
        "That changed the whole plan. We did not need to fix thousands of "
        "numbers. We needed to get the handful of big, important dependencies "
        "right for each repository."
    )

    h1(pdf, "Step 3: We Saw What Was Wrong With the Starting Weights")
    body(
        pdf,
        "The contest provides baseline weights derived from funding and usage "
        "data. Their overall shape is right: small dependencies get small "
        "weights, big ones get big weights."
    )
    body(
        pdf,
        "But the head was off. The funding data piles too much weight onto one "
        "dependency, and it under-rates libraries that are genuinely critical "
        "simply because they did not receive much historical funding. Funding "
        "history is not the same as technical importance, and a juror scores on "
        "technical importance."
    )

    h1(pdf, "Step 4: Our Fix, an Expert Juror That Corrects the Head")
    body(
        pdf,
        "Instead of throwing away the baseline (which is good in the tail), we "
        "keep the tail and fix only the head. For each repository we do this:"
    )
    bullet(pdf, "Take the top dependencies by baseline weight, since those drive the score.")
    bullet(pdf, "Show them, with their baseline weights, to Claude acting as an expert juror.")
    bullet(
        pdf,
        "Ask one question: how central and irreplaceable is this dependency to "
        "what the repository actually does? Core, hard-to-swap pieces get more; "
        "easily replaced ones get less.",
    )
    bullet(pdf, "Keep the baseline weights for the long tail of small dependencies.")
    bullet(pdf, "Normalize so the repository's weights add up to 1.0.")
    pdf.ln(2)
    body(
        pdf,
        "One detail matters for fairness. We do not tell the juror which kinds of "
        "dependencies to favor. If we hard-coded patterns from the 3 public "
        "repositories, we would just overfit them and likely hurt the 80 we "
        "cannot see. So the juror judges every dependency on its own merits, "
        "which keeps the method general."
    )

    h1(pdf, "How Well It Works")
    body(pdf, "Scored locally with the exact metric on the 3 public repositories:")
    pdf.ln(1)
    rows = [
        ("Model", "Score (lower is better)"),
        ("Funding baseline", "0.344"),
        ("Rough manual corrections", "0.237"),
        ("Expert-juror head correction", "0.121"),
    ]
    for i, (a, b) in enumerate(rows):
        if i == 0:
            pdf.set_fill_color(*NAVY)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Helvetica", "B", 11)
        else:
            pdf.set_fill_color(244, 246, 248)
            pdf.set_text_color(*DARK)
            pdf.set_font("Helvetica", "", 11)
        pdf.cell(95, 8, "  " + a, border=0, fill=True, new_x=RM, new_y=TOP)
        pdf.cell(75, 8, "  " + b, border=0, fill=True, new_x=LM, new_y=NEXT)
    pdf.ln(4)
    body(
        pdf,
        "Then we confirmed it end to end. We uploaded the corrected submission "
        "and the public leaderboard returned 0.1206, matching our local 0.121 "
        "almost exactly. For context, the cluster of genuine models near the top "
        "sat around 0.18, so our method is comfortably ahead of that group."
    )

    h1(pdf, "Why We Did Not Just Copy the Answer Key")
    body(pdf, "This is the most important thing to understand about our submission.")
    body(
        pdf,
        "That public file is also the file the public leaderboard scores against. "
        "So anyone can paste those exact numbers and score close to zero on the "
        "public board. Many top entries do exactly this. We chose not to, on "
        "purpose, because:"
    )
    bullet(
        pdf,
        "The prize is decided on hidden repositories, where no answer key exists. "
        "A copied submission scores near zero on the public 3 and proves nothing "
        "about the other 80.",
    )
    bullet(
        pdf,
        "A pasted answer key shows no method that carries over to unseen data. It "
        "is a leaderboard trick, not a model.",
    )
    pdf.ln(1)
    body(
        pdf,
        "So our submission carries the juror's real judgment for all 83 "
        "repositories: the 3 public ones land around 0.12 (not zero), and the 80 "
        "hidden ones use the exact same method. We would rather be the strongest "
        "honest model than the top fake number."
    )

    h1(pdf, "Being Honest About the Limits")
    body(
        pdf,
        "We can only directly check 3 of the 83 repositories, because that is all "
        "the public answer key covers. Those 3 prove the mechanism works (0.34 "
        "down to 0.12). The other 80 use the same method applied fresh. We expect "
        "it to carry over, but we cannot verify them directly. This is an "
        "informed bet built on a validated mechanism, and we want to say that "
        "plainly rather than overclaim."
    )

    h1(pdf, "How to Reproduce")
    code(
        pdf,
        "pip install -r requirements.txt\n"
        "python run_ai_juror_pipeline.py\n"
        "python -c \"from src.local_score import score_file;\n"
        "           score_file('submission_ai_juror_full.csv')\"",
    )
    bullet(pdf, "claude_juror_corrections.py holds the juror's head corrections per repo.")
    bullet(pdf, "run_ai_juror_pipeline.py blends them with the baseline and writes the submission.")
    bullet(pdf, "local_score.py reproduces the exact leaderboard metric so you can verify it.")

    pdf.output("Level3_Journey.pdf")
    print("Wrote Level3_Journey.pdf")


if __name__ == "__main__":
    build()
