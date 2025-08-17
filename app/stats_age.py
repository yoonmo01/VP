# app/stats_age.py
from __future__ import annotations
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db.session import SessionLocal, engine

# ── DB 테이블 체크 ────────────────────────────────────────────────────────────
CHECK_TABLE_SQL = text("""
SELECT EXISTS (
  SELECT 1
  FROM information_schema.tables
  WHERE table_schema = 'public' AND table_name = :tname
) AS exists;
""")

SQL_AGE_METHOD_TMPL = """
WITH base AS (
  SELECT
    ac.id AS case_id,
    COALESCE(ac.scenario->>'type', ac.scenario->>'purpose', '미상') AS method,
    ac.phishing AS phishing,
    (v.meta->>'age')::int AS age
  FROM admincase ac
  LEFT JOIN LATERAL (
    SELECT c.victim_id
    FROM {conv_table} c
    WHERE c.case_id = ac.id
    ORDER BY c.created_at ASC NULLS LAST
    LIMIT 1
  ) cv ON TRUE
  LEFT JOIN victim v ON v.id = cv.victim_id
  WHERE (v.meta->>'age') IS NOT NULL
)
SELECT
  CASE
    WHEN age < 30 THEN '20대 이하'
    WHEN age BETWEEN 30 AND 39 THEN '30대'
    WHEN age BETWEEN 40 AND 49 THEN '40대'
    WHEN age BETWEEN 50 AND 59 THEN '50대'
    WHEN age BETWEEN 60 AND 69 THEN '60대'
    WHEN age BETWEEN 70 AND 79 THEN '70대'
    ELSE '80대 이상'
  END AS age_group,
  method,
  COUNT(*)                                           AS total_cases,
  COUNT(*) FILTER (WHERE phishing IS TRUE)           AS phishing_cases,
  ROUND(100.0 * COUNT(*) FILTER (WHERE phishing IS TRUE) / NULLIF(COUNT(*), 0), 1)
                                                    AS phishing_rate_pct
FROM base
GROUP BY 1, 2
ORDER BY 1, phishing_rate_pct DESC, total_cases DESC
"""

SQL_AGE_ONLY_TMPL = """
WITH base AS (
  SELECT
    ac.id AS case_id,
    ac.phishing AS phishing,
    (v.meta->>'age')::int AS age
  FROM admincase ac
  LEFT JOIN LATERAL (
    SELECT c.victim_id
    FROM {conv_table} c
    WHERE c.case_id = ac.id
    ORDER BY c.created_at ASC NULLS LAST
    LIMIT 1
  ) cv ON TRUE
  LEFT JOIN victim v ON v.id = cv.victim_id
  WHERE (v.meta->>'age') IS NOT NULL
)
SELECT
  CASE
    WHEN age < 30 THEN '20대 이하'
    WHEN age BETWEEN 30 AND 39 THEN '30대'
    WHEN age BETWEEN 40 AND 49 THEN '40대'
    WHEN age BETWEEN 50 AND 59 THEN '50대'
    WHEN age BETWEEN 60 AND 69 THEN '60대'
    WHEN age BETWEEN 70 AND 79 THEN '70대'
    ELSE '80대 이상'
  END AS age_group,
  COUNT(*)                                         AS total_cases,
  COUNT(*) FILTER (WHERE phishing IS TRUE)         AS phishing_cases,
  ROUND(100.0 * COUNT(*) FILTER (WHERE phishing IS TRUE) / NULLIF(COUNT(*), 0), 1)
                                                  AS phishing_rate_pct
FROM base
GROUP BY 1
ORDER BY 1
"""

def pick_conversation_table(db: Session) -> str:
    for tname in ("conversation", "conversationlog"):
        exists = db.execute(CHECK_TABLE_SQL, {"tname": tname}).scalar()
        if exists:
            return tname
    raise RuntimeError("conversation / conversationlog 테이블을 둘 다 찾을 수 없습니다.")

def fetch_df(db: Session, sql: str) -> pd.DataFrame:
    rows = db.execute(text(sql)).mappings().all()
    return pd.DataFrame(rows)

# ── Tkinter GUI: 탭별 DataFrame 표시 ─────────────────────────────────────────
import tkinter as tk
from tkinter import ttk, messagebox

def _make_treeview(frame: ttk.Frame, df: pd.DataFrame) -> ttk.Treeview:
    # 스크롤러
    yscroll = ttk.Scrollbar(frame, orient="vertical")
    xscroll = ttk.Scrollbar(frame, orient="horizontal")

    tree = ttk.Treeview(
        frame,
        columns=list(df.columns),
        show="headings",
        yscrollcommand=yscroll.set,
        xscrollcommand=xscroll.set,
    )
    yscroll.config(command=tree.yview)
    xscroll.config(command=tree.xview)

    yscroll.pack(side="right", fill="y")
    xscroll.pack(side="bottom", fill="x")
    tree.pack(fill="both", expand=True)

    # 컬럼 헤더/폭
    for col in df.columns:
        tree.heading(col, text=col)
        # 폭은 데이터 길이를 참고해서 대략 지정
        max_len = max([len(str(x)) for x in df[col].tolist()[:200]] + [len(col)])
        width_px = min(max(80, int(max_len * 9)), 380)  # 최소 80, 최대 380px 정도
        tree.column(col, width=width_px, anchor="center", stretch=True)

    # 데이터
    for _, row in df.iterrows():
        tree.insert("", "end", values=[row.get(c, "") for c in df.columns])

    # 컬럼 정렬 토글 기능
    def sort_by(col: str, reverse: bool):
        try:
            # 숫자 정렬 시도
            data = [(float(tree.set(k, col)), k) for k in tree.get_children("")]
        except ValueError:
            # 문자열 정렬
            data = [(tree.set(k, col), k) for k in tree.get_children("")]
        data.sort(reverse=reverse)
        for idx, (_, k) in enumerate(data):
            tree.move(k, "", idx)
        # 다음 클릭에 반전
        tree.heading(col, command=lambda: sort_by(col, not reverse))

    for c in df.columns:
        tree.heading(c, command=lambda cc=c: sort_by(cc, False))

    return tree

def show_results_in_window(df_age_method: pd.DataFrame,
                           df_age_only: pd.DataFrame,
                           df_topn: pd.DataFrame):
    root = tk.Tk()
    root.title("나이대별 피싱 취약도 통계")
    root.geometry("1100x700")

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True)

    # 탭 1: 나이대 × 수법별
    frame1 = ttk.Frame(notebook)
    notebook.add(frame1, text="나이대 × 수법별 피싱율")
    if df_age_method.empty:
        ttk.Label(frame1, text="데이터가 없습니다.").pack(pady=20)
    else:
        _make_treeview(frame1, df_age_method)

    # 탭 2: 나이대 전체
    frame2 = ttk.Frame(notebook)
    notebook.add(frame2, text="나이대 전체 피싱율")
    if df_age_only.empty:
        ttk.Label(frame2, text="데이터가 없습니다.").pack(pady=20)
    else:
        _make_treeview(frame2, df_age_only)

    # 탭 3: 나이대별 Top-3 수법
    frame3 = ttk.Frame(notebook)
    notebook.add(frame3, text="나이대별 Top-3 취약 수법")
    if df_topn.empty:
        ttk.Label(frame3, text="데이터가 없습니다.").pack(pady=20)
    else:
        _make_treeview(frame3, df_topn)

    root.mainloop()

# ── 엔트리 포인트 ────────────────────────────────────────────────────────────
def main() -> None:
    db = SessionLocal()
    print("현재 연결된 DB URL:", str(engine.url))
    try:
        conv_table = pick_conversation_table(db)

        sql_age_method = SQL_AGE_METHOD_TMPL.format(conv_table=conv_table)
        sql_age_only   = SQL_AGE_ONLY_TMPL.format(conv_table=conv_table)

        df_age_method = fetch_df(db, sql_age_method)
        df_age_only   = fetch_df(db, sql_age_only)

        # Top-3 (각 나이대 내에서 피싱율, 표본수 우선)
        if not df_age_method.empty:
            df_topn = (
                df_age_method.sort_values(
                    ["age_group", "phishing_rate_pct", "total_cases"],
                    ascending=[True, False, False]
                )
                .groupby("age_group")
                .head(3)
                .reset_index(drop=True)
            )
        else:
            df_topn = pd.DataFrame()

        # GUI 표시
        show_results_in_window(df_age_method, df_age_only, df_topn)

    except Exception as e:
        # GUI 환경에서 에러 팝업
        try:
            tk = __import__("tkinter")
            from tkinter import messagebox
            root = tk.Tk(); root.withdraw()
            messagebox.showerror("오류", str(e))
            root.destroy()
        except Exception:
            print("오류:", e)
    finally:
        db.close()

if __name__ == "__main__":
    main()
