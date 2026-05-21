# ---------------------------------------------------------
# Library Scanner v5 — Targeted Subsystem + Analytics Scanner
# ---------------------------------------------------------

import os
import re

class LibraryScanner:
    def __init__(self, engine):
        self.engine = engine

        # The exact folders you want scanned
        self.target_folders = [
            r"C:\Users\chris\OneDrive\Documents\Library_Clarity_OS\Clarity_Library\02_Subsystems\Narrative_Architecture",
            r"C:\Users\chris\OneDrive\Documents\Library_Clarity_OS\Clarity_Library\02_Subsystems\ELINS_Library",
            r"C:\Users\chris\OneDrive\Documents\Library_Clarity_OS\Clarity_Library\02_Subsystems\ELINS_PLUS",
            r"C:\Users\chris\OneDrive\Documents\Library_Clarity_OS\Clarity_Library\02_Subsystems\ELINS_PLUS_PRO",
            r"C:\Users\chris\OneDrive\Documents\Library_Clarity_OS\Clarity_Library\02_Subsystems\ELINS_PRO",
            r"C:\Users\chris\OneDrive\Documents\Library_Clarity_OS\Clarity_Library\02_Subsystems\Lawbridg References",
            r"C:\Users\chris\OneDrive\Documents\Library_Clarity_OS\Clarity_Library\04_Analytics",
        ]

    # ------------------------------
    # Sentence splitter
    # ------------------------------
    def split_sentences(self, text):
        raw = re.split(r'[.!?]+', text)
        return [s.strip() for s in raw if s.strip()]

    # ------------------------------
    # Scan a single .txt file
    # ------------------------------
    def scan_file(self, filepath):
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            return 0, 0

        sentences = self.split_sentences(content)
        transitions = 0

        for s in sentences:
            before = self.engine.transition_count()
            self.engine.train(s)
            after = self.engine.transition_count()
            transitions += (after - before)

        return len(sentences), transitions

    # ------------------------------
    # Scan all target folders
    # ------------------------------
    def scan_folder(self, _ignored):
        total_sentences = 0
        total_transitions = 0

        for folder_path in self.target_folders:
            if not os.path.exists(folder_path):
                continue

            for root, dirs, files in os.walk(folder_path):
                for filename in files:
                    if filename.lower().endswith(".txt"):
                        full_path = os.path.join(root, filename)
                        s_count, t_count = self.scan_file(full_path)
                        total_sentences += s_count
                        total_transitions += t_count

        return total_sentences, total_transitions