import jieba
import jieba.posseg

def get_keyword(text):
    jieba.load_userdict("configs/dict.txt")
    words = jieba.posseg.cut(text)
    eng_words = []
    key_nouns = []
    for w in words:
        if w.flag == "eng":
            eng_words.append(w.word)
        elif w.flag == "nrt" or w.flag == "nr" or w.flag == "nz":
            key_nouns.append(w.word)

    if len(eng_words) > 0:
        keyword = " ".join(eng_words)
        key_nouns.append(keyword)

    return key_nouns
