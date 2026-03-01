# נספח עדכון לתוכנית הראשית - נעילת מודל תמלול (2026-03-01)

מסמך זה מעדכן את `TRANSCRIPTION_SYSTEM_MASTER_PLAN_HE.md`.

## החלטה מחייבת

מודל התמלול הראשי של המערכת הוא:

- `ivrit-ai/whisper-large-v3`

## השפעה על שלבי הפרויקט

1. שלב 0:
- לא נדרש עוד Bake-off לבחירת מודל ראשי.
- נדרש smoke test תפעולי של המודל (בוצע).
- מדדי WER/CER נשארים חובה לצורכי בקרה ושיפור.

2. שלב 1:
- Worker ברירת מחדל חייב להשתמש ב-`ivrit-ai/whisper-large-v3`.
- fallback יוגדר רק למצבי כשל/זמינות.

3. שלב 2:
- פוקוס על שיפור איכות בעברית (נרמול, דיאריזציה, alignment),
  ולא על החלפת מודל ראשי.

## סטטוס יישום העדכון

- הוספת סקריפט ריצה: `scripts/transcription/transcribe_with_ivrit_whisper.py`
- בוצע תמלול בפועל בהצלחה ונשמר בנתיב:
  `data/transcriptions/ivrit_whisper_large_v3/`
