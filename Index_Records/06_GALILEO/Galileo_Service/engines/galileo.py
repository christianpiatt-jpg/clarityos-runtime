from .langbridg import clean_input, clean_output
from .codebridg import interpret, truth_test
from .capl import negotiate_mode, apply_constraints
from .markoff import run_markoff

from openai import OpenAI

client = OpenAI()   # ← THIS LINE IS REQUIRED

async def call_llm(prompt: str, mode: str):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"You are Galileo operating in {mode} mode."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

async def run_clarity_cycle(user_input: str, requested_mode: str | None, goal: str | None):
    cleaned = clean_input(user_input)
    interp = interpret(cleaned, goal)
    r1_class = "generic"
    mode = negotiate_mode(requested_mode)

    llm_raw = await call_llm(interp["meaning"], mode)
    constrained = apply_constraints(mode, llm_raw)

    # NEW: use the modern Markoff engine
    markoff_result = run_markoff(constrained)

    out_clean = clean_output(constrained)
    truth = truth_test(markoff_result)
    r2_state = "coherent"

    diagnostics = {
        "r1_class": r1_class,
        "r2_state": r2_state,
        "drift": truth["drift"],
        "lurking_variables": truth["lurking_variables"],
        "system_truth": truth["system_truth"],
        "markoff_state": markoff_result,
        "forecast": None  # no forecast function in the new engine
    }

    return {
        "output": out_clean,
        "mode": mode,
        "diagnostics": diagnostics
    }
