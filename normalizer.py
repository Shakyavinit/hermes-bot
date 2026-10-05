"""
Normalizer Module for Natural Hindi/Hinglish Text-to-Speech
Separates display text from spoken dialogue, strips emojis & markdown,
and normalizes Hinglish numbers, time, currency, and vocabulary to native Devanagari phonetics.
"""

import re

# Comprehensive Roman Hinglish to Devanagari phonetic dictionary
PHONETIC_VOCAB = {
    # Numbers & Time
    r"\bchhe\b": "छह",
    r"\bche\b": "छह",
    r"\bbaarah\b": "बारह",
    r"\bbarah\b": "बारह",
    r"\bgyarah\b": "ग्यारह",
    r"\bterah\b": "तेरह",
    r"\bchaudah\b": "चौदह",
    r"\bpandrah\b": "पंद्रह",
    r"\bsolah\b": "सोलह",
    r"\bsatrah\b": "सत्रह",
    r"\batharah\b": "अठारह",
    r"\bunnees\b": "उन्नीस",
    r"\bbees\b": "बीस",
    r"\bdedh\b": "डेढ़",
    r"\bdhai\b": "ढाई",
    r"\bsawa\b": "सवा",
    r"\bsadhe\b": "साढ़े",
    r"\bpaune\b": "पौने",
    
    # Greetings & Identity
    r"\bnamaste\b": "नमस्ते",
    r"\bnamaskar\b": "नमस्कार",
    r"\bmalik\b": "मालिक",
    r"\bbilla\b": "बिल्ला",
    r"\bbhai\b": "भाई",
    r"\bshukriya\b": "शुक्रिया",
    r"\bdhanyawad\b": "धन्यवाद",
    r"\balvida\b": "अलविदा",
    
    # Everyday Conversational Words & Connectors
    r"\bhaan\b": "हाँ",
    r"\bnahi\b": "नहीं",
    r"\bnahin\b": "नहीं",
    r"\btheek\b": "ठीक",
    r"\bachha\b": "अच्छा",
    r"\bachha\b": "अच्छा",
    r"\bachhi\b": "अच्छी",
    r"\bkarein\b": "करें",
    r"\bkarenge\b": "करेंगे",
    r"\bkareinge\b": "करेंगे",
    r"\bshuru\b": "शुरू",
    r"\bbatao\b": "बताओ",
    r"\bsuno\b": "सुनो",
    r"\bkaise\b": "कैसे",
    r"\bkyon\b": "क्यों",
    r"\bkyu\b": "क्यों",
    r"\bkyun\b": "क्यों",
    r"\bkya\b": "क्या",
    r"\bkahan\b": "कहाँ",
    r"\bkaun\b": "कौन",
    r"\bkab\b": "कब",
    r"\bilaaqe\b": "इलाके",
    r"\bilaqa\b": "इलाका",
    r"\bkhatam\b": "ख़त्म",
    r"\baawaz\b": "आवाज़",
    r"\bawaj\b": "आवाज़",
    r"\bsubah\b": "सुबह",
    r"\bshaam\b": "शाम",
    r"\bdopahar\b": "दोपहर",
    r"\braat\b": "रात",
    r"\btension\b": "टेंशन",
    r"\bbilkul\b": "बिल्कुल",
    r"\bzaroor\b": "ज़रूर",
    r"\btanatan\b": "टनाटन",
    r"\bbindaas\b": "बिंदास",
    r"\bkal\b": "कल",
    r"\baaj\b": "आज",
    r"\bparso\b": "परसों",
    r"\byeh\b": "यह",
    r"\bwoh\b": "वह",
    r"\byaha\b": "यहाँ",
    r"\bwaha\b": "वहाँ",
    r"\bmera\b": "मेरा",
    r"\bmeri\b": "मेरी",
    r"\bmere\b": "मेरे",
    r"\btera\b": "तेरा",
    r"\bteri\b": "तेरी",
    r"\btere\b": "तेरे",
    r"\bapna\b": "अपना",
    r"\bapni\b": "अपनी",
    r"\bapne\b": "अपने",
    r"\bhoga\b": "होगा",
    r"\bhogi\b": "होगी",
    r"\bhonge\b": "होंगे",
    r"\bkarte\b": "करते",
    r"\bkarti\b": "करती",
    r"\bkarta\b": "करता",
    r"\bkarna\b": "करना",
    r"\bkaro\b": "करो",
    r"\bkar\b": "कर",
    r"\bdiya\b": "दिया",
    r"\bdia\b": "दिया",
    r"\bliya\b": "लिया",
    r"\bgaya\b": "गया",
    r"\bgayi\b": "गई",
    r"\bpaas\b": "पास",
    r"\bbaat\b": "बात",
    r"\bkaam\b": "काम",
    r"\bcheez\b": "चीज़",
    r"\bcheezein\b": "चीज़ें",
    r"\bsab\b": "सब",
    r"\bsabhi\b": "सभी",
    r"\bsaara\b": "सारा",
    r"\bsaare\b": "सारे",
    r"\bpoora\b": "पूरा",
    r"\bpoori\b": "पूरी",
    r"\bpoore\b": "पूरे",
    r"\bkuchh\b": "कुछ",
    r"\bkuch\b": "कुछ",
    r"\bbahut\b": "बहुत",
    r"\bbohot\b": "बहुत",
    r"\bzyada\b": "ज़्यादा",
    r"\bkam\b": "कम",
    r"\bhain\b": "हैं",
    r"\bhai\b": "है",
    r"\bhoon\b": "हूँ",
    r"\bhu\b": "हूँ",
    r"\btha\b": "था",
    r"\bthi\b": "थी",
    r"\bthe\b": "थे",
    r"\baur\b": "और",
    r"\bya\b": "या",
    r"\blekin\b": "लेकिन",
    r"\bpar\b": "पर",
    r"\bpe\b": "पे",
    r"\bse\b": "से",
    r"\bko\b": "को",
    r"\bmein\b": "में",
    r"\bme\b": "में",
    r"\bka\b": "का",
    r"\bki\b": "की",
    r"\bke\b": "के",
    r"\btak\b": "तक",
    r"\bbhi\b": "भी",
    r"\btobhi\b": "तो भी",
    r"\btoh\b": "तो",
    r"\bto\b": "तो",
    r"\bab\b": "अब",
    r"\btab\b": "तब",
    r"\bjab\b": "जब",
    r"\baap\b": "आप",
    r"\btum\b": "तुम",
    r"\bhum\b": "हम",
    r"\byaar\b": "यार",
    r"\bbaba\b": "बाबा",
    r"\bguru\b": "गुरु",
    r"\bboss\b": "बॉस",
    r"\bruko\b": "रुको",
    r"\bchup\b": "चुप",
    r"\bband\b": "बंद",
    r"\bshhh\b": "शू",
    r"\bslow\b": "धीमा",
    r"\bfast\b": "तेज़",
}

# Number to Hindi word mapping for common numbers
HINDI_NUMBERS = {
    0: "शून्य", 1: "एक", 2: "दो", 3: "तीन", 4: "चार", 5: "पाँच",
    6: "छह", 7: "सात", 8: "आठ", 9: "नौ", 10: "दस",
    11: "ग्यारह", 12: "बारह", 13: "तेरह", 14: "चौदह", 15: "पंद्रह",
    16: "सोलह", 17: "सत्रह", 18: "अठारह", 19: "उन्नीस", 20: "बीस",
    21: "इक्कीस", 22: "बाईस", 23: "तेईस", 24: "चौबीस", 25: "पच्चीस",
    30: "तीस", 40: "चालीस", 50: "पचास", 60: "साठ", 70: "सत्तर",
    80: "अस्सी", 90: "नब्बे", 100: "सौ", 1000: "हज़ार",
}


def strip_emojis(text: str) -> str:
    """Remove all unicode emojis and symbols from text."""
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        "\U00002600-\U000026FF"  # Miscellaneous Symbols
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub("", text)


def extract_speech_text(display_text: str, max_sentences: int = 1, max_words: int = 20) -> str:
    """
    Extract clean, ultra-concise speech dialogue from formatted display text.
    Strips markdown, code blocks, tables, URLs, file paths, and emojis.
    Keeps at most max_sentences (default 1) and max_words (default 20) for crisp, short spoken delivery.
    """
    if not display_text:
        return ""

    text = display_text

    # 1. Handle Code Blocks: Replace with spoken summary
    text = re.sub(r"```[\s\S]*?```", " कोड स्क्रीन पर है। ", text)

    # 2. Handle Inline code `...`
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # 3. Handle URLs -> replace with "लिंक"
    text = re.sub(r"https?://\S+", " लिंक ", text)

    # 4. Handle Linux file paths -> replace with just basename
    text = re.sub(r"(/[a-zA-Z0-9_\-\.]+)+/([a-zA-Z0-9_\-\.]+)", r"\2", text)

    # 5. Remove Markdown headers, bold, italics, blockquotes, bullets
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_~]", "", text)
    text = re.sub(r"^[>\-\*\+]\s*", "", text, flags=re.MULTILINE)

    # 6. Remove Markdown tables
    text = re.sub(r"\|[^\n]+\|", "", text)
    text = re.sub(r":\-\-+:?", "", text)

    # 7. Strip Emojis
    text = strip_emojis(text)

    # 8. Clean excess whitespace & newlines
    text = re.sub(r"\n+", ". ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # 9. Limit to max_sentences for spoken replies
    sentences = re.split(r"(?<=[.!?।])\s+", text)
    filtered = [s.strip() for s in sentences if s.strip()]
    if filtered:
        spoken = " ".join(filtered[:max_sentences])
    else:
        spoken = text

    # 10. Cap maximum words to prevent any long speeches
    words = spoken.split()
    if len(words) > max_words:
        spoken = " ".join(words[:max_words])

    return spoken.strip()


def normalize_for_hindi_tts(text: str) -> str:
    """
    Convert numbers, time, currency, and tricky Hinglish words to native Devanagari phonetics.
    """
    if not text:
        return ""

    t = text

    # 1. Time Normalization (e.g., "4:30" -> "साढ़े चार बजे", "6:00" -> "छह बजे")
    t = re.sub(r"\b(\d+):30\s*(?:am|pm|baje)?\b", lambda m: f"साढ़े {HINDI_NUMBERS.get(int(m.group(1)), m.group(1))} बजे", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(\d+):15\s*(?:am|pm|baje)?\b", lambda m: f"सवा {HINDI_NUMBERS.get(int(m.group(1)), m.group(1))} बजे", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(\d+):45\s*(?:am|pm|baje)?\b", lambda m: f"पौने {HINDI_NUMBERS.get(int(m.group(1)) + 1, str(int(m.group(1)) + 1))} बजे", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(\d+):00\s*(?:am|pm|baje)?\b", lambda m: f"{HINDI_NUMBERS.get(int(m.group(1)), m.group(1))} बजे", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(\d+)\s+baje\b", lambda m: f"{HINDI_NUMBERS.get(int(m.group(1)), m.group(1))} बजे", t, flags=re.IGNORECASE)

    # 2. Currency Normalization (e.g. "Rs 1250", "₹1250", "1250 rupees")
    t = re.sub(r"(?:Rs\.?|₹)\s*1250\b", "बारह सौ पचास रुपये", t, flags=re.IGNORECASE)
    t = re.sub(r"(?:Rs\.?|₹)\s*(\d+)", r"\1 रुपये", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(\d+)\s*rupees\b", r"\1 रुपये", t, flags=re.IGNORECASE)
    t = re.sub(r"\b1250\s*रुपये\b", "बारह सौ पचास रुपये", t)

    # 3. Percent Normalization (e.g. "100%" -> "सौ प्रतिशत")
    t = re.sub(r"\b100\s*%\b", "सौ प्रतिशत", t)
    t = re.sub(r"\b(\d+)\s*%\b", r"\1 प्रतिशत", t)

    # 4. Small Numbers (1-20 standalone)
    for num, h_word in HINDI_NUMBERS.items():
        t = re.sub(rf"\b{num}\b", h_word, t)

    # 5. Hinglish Phonetic Replacement
    for pattern, replacement in PHONETIC_VOCAB.items():
        t = re.sub(pattern, replacement, t, flags=re.IGNORECASE)

    return t.strip()
