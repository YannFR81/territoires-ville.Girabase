"""Vérifie que le guide PDF contient du texte lisible (et non des pavés noirs faute de police).

Utilisation : python outils/verifier_guide_pdf.py dist/Guide-utilisateur-Girabase.pdf   (nécessite pypdf)
"""
import sys
import unicodedata

from pypdf import PdfReader


def main(chemin: str) -> int:
    # NFKC : ligatures (« ﬁ ») ramenées à leurs lettres
    texte = " ".join(unicodedata.normalize("NFKC", PdfReader(chemin).pages[0].extract_text()).split())
    attendus = ["Guide d'utilisation de Girabase", "capacité des carrefours giratoires", "L’intelligence artificielle"]
    manquants = [a for a in attendus if a not in texte]
    if manquants:
        print(f"Guide PDF illisible : texte non retrouvé {manquants}. Début de la page 1 : {texte[:200]!r}")
        return 1
    print(f"Guide PDF lisible : {texte[:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
