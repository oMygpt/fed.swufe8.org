import streamlit as st
import pandas as pd
from modules.quality import assess_qa, assess_exercises


def render_overview(meta: dict, warnings: list[str]):
    st.success("解析成功！")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("文件名", meta.get("filename", "-") )
    with col2:
        st.metric("类型", meta.get("type", "-") )
    with col3:
        st.metric("有效条目", meta.get("total", 0))
    st.write("包含 Sheet：", ", ".join(meta.get("sheets", [])))
    st.write("识别到的列名：", meta.get("columns", []))
    if meta.get("type") == "习题库" and meta.get("exercise_type"):
        st.write(f"题型：{meta.get('exercise_type')}")
    if meta.get("type") == "习题库" and meta.get("level"):
        st.write(f"级别：{meta.get('level')}")
    if meta.get("type") == "习题库" and meta.get("mixed_types"):
        mt = meta.get("mixed_types") or {}
        if mt:
            desc = ", ".join([f"{k}{v}条" for k, v in mt.items()])
            st.warning(f"检测到混合题型：{desc}")
    if meta.get("detected_type") and meta.get("type") and meta.get("detected_type") != meta.get("type"):
        st.error(f"类型选择与系统识别不一致：你选择了{meta.get('type')}，系统识别为{meta.get('detected_type')}")
    if meta.get("detected_level") and meta.get("level") and meta.get("detected_level") != meta.get("level"):
        st.error(f"级别选择与系统识别不一致：你选择了{meta.get('level')}，系统识别为{meta.get('detected_level')}")
    if meta.get("quality_summary"):
        q = meta["quality_summary"]
        st.write(f"质量：均分 {q.get('score_avg', 0)}，Error {q.get('error_count', 0)}，Warn {q.get('warn_count', 0)}")
        total = max(1, meta.get("total", 1))
        errs = q.get("errors", {}) or {}
        warnm = q.get("warns", {}) or {}
        def _pct(n):
            return round((n/total)*100, 2)
        missing = {k: v for k, v in errs.items() if k.endswith("_EMPTY")}
        garbled = {k: v for k, v in errs.items() if k.endswith("_GARBLED")}
        other = {k: v for k, v in errs.items() if not (k.endswith("_EMPTY") or k.endswith("_GARBLED"))}
        st.subheader("问题分类概览（Error）")
        rows = [
            {"类别": "缺失", "数量": sum(missing.values()), "占比(%)": _pct(sum(missing.values()))},
            {"类别": "乱码", "数量": sum(garbled.values()), "占比(%)": _pct(sum(garbled.values()))},
            {"类别": "其他问题", "数量": sum(other.values()), "占比(%)": _pct(sum(other.values()))},
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
    if warnings:
        for w in warnings:
            st.warning(w)


def render_tabs(df: pd.DataFrame, meta: dict | None = None, key_prefix: str = ""):
    if df is None or df.empty:
        st.info("未识别到有效数据")
        return
    tab1, tab2, tab3 = st.tabs(["随机抽检（20）", "顺序浏览", "类型抽检"])
    with tab1:
        n = min(20, len(df))
        assessed = assess_qa(df.sample(n)) if meta and meta.get("type") == "问答对" else assess_exercises(df.sample(n))
        def _cell_style(row):
            flags = str(row.get("quality_flags", ""))
            cols = list(assessed.columns)
            red_cols = set()
            if meta and meta.get("type") == "问答对":
                if "Error:Q_EMPTY" in flags or "Error:Q_GARBLED" in flags: red_cols.add("question")
                if "Error:A_EMPTY" in flags or "Error:A_GARBLED" in flags: red_cols.add("answer")
            else:
                if "Error:STEM_EMPTY" in flags or "Error:STEM_GARBLED" in flags: red_cols.add("stem")
                if "Error:OPT_EMPTY" in flags or "Error:OPT_GARBLED" in flags: red_cols.add("options")
                if "Error:ANS_EMPTY" in flags or "Error:ANS_GARBLED" in flags or "Error:ANS_NOT_IN_OPTS" in flags or "Error:ANS_INVALID" in flags: red_cols.add("answer")
                if "Error:KN_EMPTY" in flags or "Error:KN_GARBLED" in flags: red_cols.add("knowledge")
            return ["background-color: #fdecea" if c in red_cols else "" for c in cols]
        st.dataframe(assessed.style.apply(_cell_style, axis=1), use_container_width=True)
    with tab2:
        query = st.text_input("关键词搜索（如：答案为空）", key=f"{key_prefix}-search")
        only_issues = st.checkbox("仅显示问题项", value=False, key=f"{key_prefix}-only-issues")
        page_size = st.slider("每页条数", 10, 100, 20, key=f"{key_prefix}-page_size")
        page = st.number_input("页码", min_value=1, value=1, key=f"{key_prefix}-page")
        view = df
        if query:
            if query == "答案为空" and "answer" in df.columns:
                view = df[df["answer"].astype(str).str.len() == 0]
            else:
                view = df[df.astype(str).apply(lambda r: query in "\t".join(r.values), axis=1)]
        if only_issues and meta:
            assessed = assess_qa(view) if meta.get("type") == "问答对" else assess_exercises(view)
            view = assessed[assessed["quality_flags"].astype(str).str.contains("Error:|Warn:")]
        start = (page - 1) * page_size
        if only_issues and meta:
            def _cell_style2(row):
                flags = str(row.get("quality_flags", ""))
                cols = list(view.columns)
                red_cols = set()
                if meta.get("type") == "问答对":
                    if "Error:Q_EMPTY" in flags or "Error:Q_GARBLED" in flags: red_cols.add("question")
                    if "Error:A_EMPTY" in flags or "Error:A_GARBLED" in flags: red_cols.add("answer")
                else:
                    if "Error:STEM_EMPTY" in flags or "Error:STEM_GARBLED" in flags: red_cols.add("stem")
                    if "Error:OPT_EMPTY" in flags or "Error:OPT_GARBLED" in flags: red_cols.add("options")
                    if "Error:ANS_EMPTY" in flags or "Error:ANS_GARBLED" in flags or "Error:ANS_NOT_IN_OPTS" in flags or "Error:ANS_INVALID" in flags: red_cols.add("answer")
                    if "Error:KN_EMPTY" in flags or "Error:KN_GARBLED" in flags: red_cols.add("knowledge")
                return ["background-color: #fdecea" if c in red_cols else "" for c in cols]
            st.dataframe(view.iloc[int(start):int(start+page_size)].style.apply(_cell_style2, axis=1), use_container_width=True)
        else:
            st.dataframe(view.iloc[int(start):int(start+page_size)], use_container_width=True)
    with tab3:
        t = None
        if meta:
            t = meta.get("exercise_type") or meta.get("type")
        if t == "问答对" or (t is None and {"question", "answer"}.issubset(set(df.columns))):
            total = len(df)
            empty_ans = int((df["answer"].astype(str).str.len() == 0).sum()) if "answer" in df.columns else 0
            st.metric("总条目", total)
            st.metric("答案为空", empty_ans)
            if "question" in df.columns:
                st.write("问题长度统计")
                st.bar_chart(df["question"].astype(str).str.len())
        else:
            if "type" in df.columns:
                counts = df["type"].value_counts()
                st.write("题型分布")
                st.bar_chart(counts)
            if t == "判断题" or ("type" in df.columns and "判断" in set(df["type"].astype(str))):
                if "answer" in df.columns:
                    dist = df["answer"].astype(str).value_counts()
                    st.write("答案分布")
                    st.bar_chart(dist)
            if t == "选择题" or ("type" in df.columns and "选择" in set(df["type"].astype(str))):
                if "options" in df.columns and "answer" in df.columns:
                    from modules.quality import _parse_options_text
                    def _check_opts(row):
                        opts = _parse_options_text(row.get("options"))
                        ans = str(row.get("answer", "")).strip().upper()
                        return ("A" in opts and "B" in opts) and (ans in opts)
                    ok_ratio = float(df.apply(_check_opts, axis=1).mean()) if len(df) else 0.0
                    st.metric("选项与答案一致比例", round(ok_ratio*100, 2))
            if t == "填空题" or ("type" in df.columns and "填空" in set(df["type"].astype(str))):
                if "answer" in df.columns:
                    non_empty = float((df["answer"].astype(str).str.len() > 0).mean()) if len(df) else 0.0
                    st.metric("答案非空比例", round(non_empty*100, 2))
            if t in ["简答题", "论述题", "案例分析题"] or ("type" in df.columns and any(x in set(df["type"].astype(str)) for x in ["简答", "论述", "案例分析"])):
                if "analysis" in df.columns:
                    non_empty = float((df["analysis"].astype(str).str.len() > 0).mean()) if len(df) else 0.0
                    st.metric("解析非空比例", round(non_empty*100, 2))


def render_history(records: list[dict]):
    if not records:
        st.info("暂无历史记录")
        return
    st.dataframe(pd.DataFrame(records), use_container_width=True)


def hide_deploy_button():
    st.markdown(
        "<style>[data-testid='stToolbar']{visibility:hidden;} .stDeployButton{display:none!important}</style>",
        unsafe_allow_html=True,
    )

def render_login_branding(title: str, subtitle: str | None = None):
    st.markdown(
        """
        <style>
        .block-container{max-width:900px;padding-top:2rem}
        .login-hero{padding:24px;border-radius:14px;text-align:center;color:#0F172A;background:radial-gradient(circle at 50% 40%, rgba(37,99,235,0.08) 0%, rgba(30,64,175,0.12) 60%, rgba(2,6,23,0.08) 100%);border:1px solid #E5E7EB}
        .login-hero h1{margin:0;font-size:28px;letter-spacing:0.5px}
        .login-hero p{margin-top:8px;color:#475569}
        .login-hero .team{margin-top:10px;color:#334155;font-size:12px;letter-spacing:0.4px}
        [data-testid="stForm"]{background:#FFFFFF;border:1px solid #E5E7EB;border-radius:14px;padding:20px;box-shadow:0 10px 30px rgba(2,6,23,0.06)}
        .stTextInput>div>div>input,.stPasswordInput>div>div>input{border-radius:10px}
        .stButton>button{background:#2563EB;color:#FFFFFF;border-radius:10px;border:0;padding:8px 14px}
        .stButton>button:hover{background:#1D4ED8}
        div.stApp{background:linear-gradient(180deg,#F8FAFC 0%,#F1F5F9 100%)}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div class='login-hero'><h1>{title}</h1>" + (f"<p>{subtitle}</p>" if subtitle else "") + "<p class='team'>A³ T  @2025</p></div>",
        unsafe_allow_html=True,
    )

def style_sidebar_menu():
    st.sidebar.markdown(
        """
        <style>
        [data-testid="stSidebar"]{background:linear-gradient(180deg,#F8FAFC 0%,#EEF2F7 100%);border-right:1px solid #E5E7EB}
        .sidebar-brand{padding:12px 10px;margin:0 0 8px 0;border-radius:12px;background:#FFFFFF;border:1px solid #E5E7EB;box-shadow:0 8px 24px rgba(2,6,23,0.04);color:#0F172A}
        .sidebar-brand h2{margin:0;font-size:16px}
        .sidebar-brand p{margin:4px 0 0 0;color:#64748B;font-size:12px}
        .sidebar-team{margin-top:6px;color:#334155;font-size:11px}
        [role="radiogroup"] label{display:block;border:1px solid #E5E7EB;border-radius:10px;padding:8px 10px;margin-bottom:8px;background:#FFFFFF}
        [role="radiogroup"] label:hover{border-color:#2563EB;background:#F0F5FF}
        </style>
        """,
        unsafe_allow_html=True,
    )
