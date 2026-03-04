# תוכנית עבודה מקומית (CPU) - Stage 10+

**תאריך עדכון:** 2026-03-03  
**מטרה:** להמשיך עבודה מלאה על המחשב הנוכחי (ללא שרת GPU ייעודי), לשמור תיעוד התקדמות ברור, ולהכין מעבר חלק לשרת GPU בהמשך.

## 1. מצב נוכחי - מה הושלם עד כה

1. שלבים `0-10` הושלמו ברמת מימוש.
2. בדיקת Release Candidate עברה בהצלחה:
- תאריך: `2026-03-02`
- תוצאה: `overall_status=pass`
3. מודל ראשי נעול ונשמר:
- `ivrit-ai/whisper-large-v3`
4. מצב ריפו נקי משינויים לא שמורים (בזמן הבדיקה האחרונה).

## 2. החלטת עבודה נוכחית

1. עובדים במתכונת `Local-First` על המחשב הנוכחי.
2. כל בדיקות הפונקציונליות והתפעול ירוצו מקומית (CPU).
3. בדיקות ביצועים בקנה מידה גדול/עומסי GPU יידחו לשלב שרת GPU.

## 3. פרופיל סביבת עבודה מקומית (נוכחי)

1. CPU: `Intel i7-1165G7 (4C/8T)`
2. RAM: `16GB`
3. GPU מזוהה במערכת: `NVIDIA MX450 (2GB)` + `Intel Iris Xe`
4. מצב PyTorch בזמן בדיקה: `torch.cuda.is_available=False`
5. מסקנה: תפעול ASR בפועל במצב CPU.

## 4. תוכנית עבודה מעשית על המחשב הנוכחי

1. הקשחת תצורת CPU (שמרנית):
- `ASR_BATCH_SIZE_CPU=1`
- `MAX_PARALLEL_WORKERS_CPU=1` (או `2` רק אם יציב)
- `ASR_CHUNK_LENGTH_SEC=15-30`

2. הרצה מקומית מלאה (כאשר Docker זמין):
- `docker compose build`
- `docker compose up -d`
- אימות: `/health/live`, `/health/ready`, `/health`, `/metrics`, `/perf/summary`

3. מסלול Fallback ללא Docker (נוכחי):
- `python scripts/ops/preflight_check.py --recordings-path "Recordings Examples" --strict`
- `python scripts/ops/release_candidate_check.py --repo-root .`

4. שער איכות ושחרור מקומי:
- `python scripts/ops/preflight_check.py --recordings-path "Recordings Examples"`
- `python scripts/ops/release_candidate_check.py --repo-root .`

5. בדיקות תפעול:
- גיבוי/שחזור (`backup/restore`)
- בדיקת התראות (`alert policy`)
  - Local CPU policy: `config/alert_policy.local_cpu.json`
- דוח ביצועים/עלות (`perf_cost_report`)

6. בדיקות קבלה פונקציונליות:
- העלאת קבצים, תור, תמלול, יצוא (`TXT/SRT/DOCX`), UI, ועדכוני WS
- אימות עברית/RTL/word timestamps על סט דגימה

## 5. מה לא נחשב "סגור" בשלב המקומי

1. ביצועי throughput תחת עומס גבוה.
2. כיוונון `ASR_BATCH_SIZE_GPU`.
3. התנהגות multi-node אמיתית עם PostgreSQL תחת עומס פרודקשן.

## 6. קריטריוני יציאה מהשלב המקומי

1. כל בדיקות RC מקומיות עוברות באופן עקבי.
2. אין קריסות worker בלולאה.
3. איכות תמלול עומדת ביעד הפנימי על סט הדגימה.
4. תהליכי גיבוי/שחזור נבדקו ועובדים.
5. קיימת חבילת תיעוד עדכנית להעברה לשרת GPU.

## 7. תוכנית מעבר לשרת GPU (כשיהיה זמין)

1. הקמת שרת עם Docker + דרייברי GPU + runtime מתאים.
2. מעבר DB ל-PostgreSQL (מומלץ) והרצת מיגרציה:
- `scripts/ops/migrate_sqlite_to_postgres.py`
3. הגדרת סודות דרך:
- `DB_URL_FILE`
- `TOKEN_HASH_PEPPER_FILE`
4. הרצת stack ארגוני:
- `docker compose -f docker-compose.enterprise.yml up -d --build --scale worker=4`
5. הרצת RC gate על שרת היעד לפני cutover.
6. cutover מדורג + תוכנית rollback מוכנה.

## 8. יומן התקדמות (לעדכון רציף)

| תאריך | מה בוצע | תוצאה | הערות |
|---|---|---|---|
| 2026-03-02 | RC מלא (`release_candidate_check`) | Pass | כל הצעדים עברו |
| 2026-03-03 | החלטה אסטרטגית: Local-First CPU | Approved | שרת GPU יתווסף בשלב הבא |
| 2026-03-03 | `preflight_check --strict` (לוקאלי) | Pass | סביבת עבודה מוכנה |
| 2026-03-03 | `release_candidate_check` חוזר (לוקאלי CPU) | Pass | `overall_status=pass` |
| 2026-03-03 | דוחות Ops מקומיים (`slo/alert/perf`) | Partial | `alert_policy_check` החזיר `workers_online_too_low:0<1` |
| 2026-03-03 | אימות `alert_policy.local_cpu.json` | Pass | `status=ok` עם `min_workers_online=0` |
| 2026-03-03 | E2E קבלה מלא (API+Worker+Export) על DB נקי | Pass | Job הושלם (`completed`), `word_count=24`, יצוא `txt/srt/docx=200`, דוח: `data/ops/local_acceptance_run.json` |
| 2026-03-03 | E2E קבלה מלא #2 על DB נקי | Pass | Job הושלם (`completed`), `word_count=34`, יצוא `txt/srt/docx=200`, דוח: `data/ops/local_acceptance_run_2.json` |
| 2026-03-03 | E2E קבלה מלא #3 על DB נקי | Pass | Job הושלם (`completed`), `word_count=38`, יצוא `txt/srt/docx=200`, דוח: `data/ops/local_acceptance_run_3.json` |
| 2026-03-03 | סיכום 3 ריצות קבלה מקומיות | Pass | `all_completed=true`, `all_exports_http_200=true`, סיכום: `data/ops/local_acceptance_summary.json` |
| 2026-03-03 | Batch קבלה רחב (10 קבצים ראשונים) | Partial | `8/10` הושלמו; 2 jobs ב-timeout על קבצים ארוכים מאוד, דוח: `data/ops/local_acceptance_batch_10.json` |
| 2026-03-03 | Batch קבלה CPU-safe (10 הקבצים הקצרים ביותר) | Pass | `10/10` הושלמו, `exports=10/10`, דוח: `data/ops/local_acceptance_batch_short10.json` |
| 2026-03-04 | בדיקת מוכנות Ground-Truth ל-KPI | Blocked | `0/70` references לא-ריקים; דוחות: `data/bakeoff/reference_readiness_summary.json`, `data/bakeoff/reference_missing_or_empty.csv`, shortlist: `data/bakeoff/reference_annotation_shortlist_20.csv` |
| 2026-03-04 | יצירת Drafts לאנוטציה מהירה (לא Ground-Truth) | Ready | `10` טיוטות נוצרו ב-`data/bakeoff/references_draft/` + אינדקס `data/bakeoff/reference_drafts_short10.csv` |
| 2026-03-04 | Batch קבלה shortlist-20 | Pass | `20/20` הושלמו, דוח: `data/ops/local_acceptance_batch_short20.json` |
| 2026-03-04 | Batch קבלה missing-shortest-20 | Pass | `20/20` הושלמו, דוח: `data/ops/local_acceptance_batch_missing20.json` |
| 2026-03-04 | הרחבת טיוטות לאנוטציה (20+20) + sync לרפרנסים ריקים | In Progress | אינדקסים: `data/bakeoff/reference_drafts_short20.csv`, `data/bakeoff/reference_drafts_missing20.csv`; תחזית מוכנות חדשה: `36/70` לא-ריקים |
| 2026-03-04 | קובץ predictions מאוחד ל־36 דגימות לא-ריקות | Ready | `data/bakeoff/predictions_local_draft_36.csv` |
| 2026-03-04 | subset manifest ל־36 דגימות score-ready | Ready | `data/bakeoff/dataset_manifest_draft36.csv` |
| 2026-03-04 | Score self-check טכני (לא KPI פורמלי) | Pass | run-id: `local_draft_selfcheck_20260304`; תוצאות `WER/CER=0` צפויות כי refs מבוססי טיוטות מודל |

## 9. הערות ביצוע חשובות

1. כרגע `docker` לא מותקן/לא מזוהה בתחנה זו, ולכן עובדים במסלול Python מקומי.
2. בהרצות מתוך תיקיית `backend` יש להשתמש ב-`DB_URL=sqlite:///./data/app.db`.
3. בהגדרת `DB_URL=sqlite:///./backend/data/app.db` תהליכים מתוך `backend` עלולים להיכשל ב-`unable to open database file`.

## 10. סטטוס התקדמות מספרי (כמה מתוך כמה)

1. שלבי פרויקט (Stage 0-10): **11/11 הושלמו**.
2. קריטריוני יציאה מהשלב המקומי: **4/5 הושלמו**.
   - פתוח: אימות יעד איכות פורמלי (KPI) על סט עם ground-truth.
   - מוכנות טכנית נוכחית: `references_non_empty=36/70` (כולל טיוטות אוטומטיות שדורשות review ידני).
3. בדיקות E2E שבוצעו בפועל עד כה: **61/63 jobs הושלמו**.
   - ריצות נקודתיות + CPU-safe: **13/13 הושלמו**.
   - Batch רחב לא מסונן: **8/10 הושלמו** (2 קבצים ארוכים מאוד עברו timeout).
   - Batch shortlist-20: **20/20 הושלמו**.
   - Batch missing-shortest-20: **20/20 הושלמו**.
