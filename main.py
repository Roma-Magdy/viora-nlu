import time
import sys
import os
import arabic_reshaper
from typing import cast
from bidi.algorithm import get_display

# Fix imports if running from outside the folder
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fanar_nlu import fanar_nlu
from router import route_nlu_result

# ANSI colors for a beautiful terminal output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
RESET = "\033[0m"

def fix_text(text: str) -> str:
    """Fixes Arabic text rendering for the terminal."""
    if not text: return ""
    try:
        reshaped = arabic_reshaper.reshape(text)
        return cast(str, get_display(reshaped))
    except: return text

def test_command(text: str):
    display_text = fix_text(text)
    print(f"\n{YELLOW}User says:{RESET} '{display_text}'")
    
    start = time.time()
    # Call the Fanar API
    nlu_result = fanar_nlu(text)
    decision, payload = route_nlu_result(nlu_result)
    duration = time.time() - start
    
    # Colors based on decision
    color = GREEN if "EXECUTE" in decision else (CYAN if "CLARIFY" in decision else RED)

    print(f"   ⏱️ Latency: {duration:.2f}s")
    print(f"   🗣️ Viora Reply: {MAGENTA}{fix_text(payload.viora_response)}{RESET}")
    print(f"   ⚙️ Decision: {color}{decision}{RESET}")
    print(f"   🧠 Intent: {payload.intent} (Conf: {payload.confidence:.2f})")
    
    # Clean display of entities
    ents = payload.entities.model_dump(exclude_none=True)
    clean_ents = {k: fix_text(str(v)) if isinstance(v, str) else v for k, v in ents.items()}
    if clean_ents:
        print(f"   📦 Entities: {clean_ents}")

if __name__ == "__main__":
    print(f"{GREEN}=== Viora (Fanar Edition) Stress Test ==={RESET}")

    test_suite = {
        "1. Corrections (Changing Mind)": [
            "افتحلي سلايدز الـ AI.. لا لا استنى هات الـ Networks أهم", 
            "Go to page 50... actually make it 55"
        ],
        "2. Negations & Exclusions": [
            "I don't need the summary, just give me the key definitions",
            "متفتحش الكتاب القديم، هات النسخة الجديدة"
        ],
        "3. Heavy Dialect (Slang & Implicit)": [
            "يا عم خلاص ماتصدعناش", 
            "سمّعني الكلام ده"
        ],
        "4. Complex Code-Switching": [
            "عايز الـ implementation details بتاعة الـ main loop اللي في صفحة 3",
        ],
        "5. The 'Fake Out' (Hesitation)": [
            "كنت عايز أسأل على... ولا بلاش، لخصلي الفايل وخلاص",
        ],
        "6. Study Aids & Summaries": [
            "اعملي امتحان صغير",
            "بقولك ايه أنا مش فايق خالص وعايز أنجز، فـ ياريت تجيبلي الزتونة في نقط."
        ]
    }

    for category, commands in test_suite.items():
        print(f"\n{CYAN}{'='*40}\n--- {category} ---\n{'='*40}{RESET}")
        for cmd in commands:
            test_command(cmd)
            time.sleep(1) # Slight pause to be polite to the Fanar API rate limits