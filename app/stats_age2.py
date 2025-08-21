# app/stats_age2.py
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

# 한글/영문 통일 폰트(중간사이즈)
BASE_FONT = ("Malgun Gothic", 9)   # 본문(표)
HEAD_FONT = ("Malgun Gothic", 9)   # 헤더
TITLE_FONT = ("Malgun Gothic", 11)  # 상단 타이틀
SUB_FONT = ("Malgun Gothic", 8)    # 서브 설명

KOR_COLUMNS_FULL = {
    "age_group": "나이대",
    "method": "수법",
    "total_cases": "총 건수",
    "phishing_cases": "피싱 발생 건수",
    "phishing_rate_pct": "피싱율(%)",
}

KOR_COLUMNS_AGE_ONLY = {
    "age_group": "나이대",
    "total_cases": "총 건수",
    "phishing_cases": "피싱 발생 건수",
    "phishing_rate_pct": "피싱율(%)",
}

def _rename_columns(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    if df.empty:
        return df
    return df.rename(columns={k: v for k, v in mapping.items() if k in df.columns})

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
        height=18,
    )
    yscroll.config(command=tree.yview)
    xscroll.config(command=tree.xview)

    # 패킹
    yscroll.pack(side="right", fill="y")
    xscroll.pack(side="bottom", fill="x")
    tree.pack(fill="both", expand=True, padx=8, pady=8)

    # 컬럼 헤더/폭
    for col in df.columns:
        tree.heading(col, text=col)
        max_len = max([len(str(x)) for x in df[col].tolist()[:200]] + [len(col)])
        width_px = min(max(100, int(max_len * 10)), 480)
        tree.column(col, width=width_px, anchor="center", stretch=True)

    # 지브라 스트라이프 태그 지정
    for i, (_, row) in enumerate(df.iterrows()):
        tags = ("oddrow",) if i % 2 else ("evenrow",)
        tree.insert("", "end", values=[row.get(c, "") for c in df.columns], tags=tags)

    # 정렬 토글
    def sort_by(col: str, reverse: bool):
        try:
            data = [(float(tree.set(k, col)), k) for k in tree.get_children("")]
        except ValueError:
            data = [(tree.set(k, col), k) for k in tree.get_children("")]
        data.sort(reverse=reverse)
        for idx, (_, k) in enumerate(data):
            tree.move(k, "", idx)
        tree.heading(col, command=lambda: sort_by(col, not reverse))

    for c in df.columns:
        tree.heading(c, command=lambda cc=c: sort_by(cc, False))

    return tree

def _apply_style(root: tk.Tk):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    # 통일 폰트/색상
    style.configure(
        "Treeview",
        font=BASE_FONT,
        rowheight=28,
        borderwidth=0,
        relief="flat",
        foreground="#222222"
    )
    style.configure(
        "Treeview.Heading",
        font=HEAD_FONT,
        padding=6,
        relief="flat",
        foreground="#222222"
    )
    style.map("Treeview",
              background=[("selected", "#4C6EF5")],
              foreground=[("selected", "white")])

    # 지브라 행 배경
    style.configure("evenrow", background="#F7F9FC")
    style.configure("oddrow", background="#EEF2F7")

def show_results_in_window(df_age_method: pd.DataFrame,
                           df_age_only: pd.DataFrame,
                           df_topn: pd.DataFrame):
    root = tk.Tk()
    root.title("나이대별 피싱 취약도 통계")
    root.geometry("1180x760")

    _apply_style(root)

    # 상단 헤더바
    header = ttk.Frame(root)
    header.pack(fill="x", padx=12, pady=(12, 6))
    title_lbl = ttk.Label(header, text="나이대별 피싱 취약도 통계", font=TITLE_FONT)
    sub_lbl = ttk.Label(
        header,
        text="연령대별 전체·수법별 통계와 Top-3 취약 수법을 한 눈에 확인하세요.",
        font=SUB_FONT
    )
    title_lbl.pack(anchor="w")
    sub_lbl.pack(anchor="w")

    # 노트북 탭
    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=10, pady=10)

    # ── 탭 1: 나이대 × 수법별 ────────────────────────────────────────────────
    frame1 = ttk.Frame(notebook)
    notebook.add(frame1, text="나이대 × 수법별 피싱율")

    if not df_age_method.empty:
        df1 = _rename_columns(df_age_method, KOR_COLUMNS_FULL)
        _make_treeview(frame1, df1)
    else:
        ttk.Label(frame1, text="데이터가 없습니다.", font=BASE_FONT).pack(pady=20)

    # ── 탭 2: 나이대 전체 ───────────────────────────────────────────────────
    frame2 = ttk.Frame(notebook)
    notebook.add(frame2, text="나이대 전체 피싱율")

    if not df_age_only.empty:
        df2 = _rename_columns(df_age_only, KOR_COLUMNS_AGE_ONLY)
        _make_treeview(frame2, df2)
    else:
        ttk.Label(frame2, text="데이터가 없습니다.", font=BASE_FONT).pack(pady=20)

    # ── 탭 3: 나이대별 Top-3 취약 수법 ───────────────────────────────────────
    frame3_outer = ttk.Frame(notebook)
    notebook.add(frame3_outer, text="나이대별 Top-3 취약 수법")

    top_bar = ttk.Frame(frame3_outer)
    top_bar.pack(fill="x", padx=8, pady=(8, 4))
    ttk.Label(
        top_bar,
        text="나이대별 Top-3 취약 수법",
        font=HEAD_FONT
    ).pack(side="left")

    frame3 = ttk.Frame(frame3_outer, borderwidth=0)
    frame3.pack(fill="both", expand=True)

    if not df_topn.empty:
        df3 = _rename_columns(df_topn, KOR_COLUMNS_FULL)
        _make_treeview(frame3, df3)
    else:
        ttk.Label(frame3, text="데이터가 없습니다.", font=BASE_FONT).pack(pady=20)

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
