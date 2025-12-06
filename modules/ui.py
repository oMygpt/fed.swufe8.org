import streamlit as st
import pandas as pd
from modules.quality import assess_qa, assess_exercises
from pathlib import Path

def load_custom_css():
    css_path = Path("assets/style.css")
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

def render_card(title: str, content: str = "", key: str = None):
    st.markdown(f"""
    <div class="css-card">
        <h3>{title}</h3>
        <div>{content}</div>
    </div>
    """, unsafe_allow_html=True)

def render_metric_card(label: str, value: str | int | float, delta: str | None = None, col=None):
    container = col if col else st
    delta_html = f"<div class='css-metric-delta' style='color: {'#10b981' if delta and not delta.startswith('-') else '#ef4444'}'>{delta}</div>" if delta else ""
    container.markdown(f"""
    <div class="css-metric-card">
        <div class="css-metric-label">{label}</div>
        <div class="css-metric-value">{value}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)



def render_overview(meta: dict):
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



def render_warnings(warnings: list[str]):
    if warnings:
        with st.expander("查看详细解析警告", expanded=False):
            for w in warnings:
                st.warning(w)


def render_tabs(df: pd.DataFrame, meta: dict | None = None, key_prefix: str = ""):
    if df is None or df.empty:
        st.info("未识别到有效数据")
        return
    tab1, tab2, tab3 = st.tabs(["顺序浏览 (预览/导出)", "随机抽检 (20条)", "类型统计"])
    
    # --- Tab 1: Sequential Browsing (Main View) ---
    with tab1:
        # Row 1: Controls for Issues & Export
        c_issue, c_enc, c_exp = st.columns([1.5, 2, 1.5])
        with c_issue:
            only_issues = st.checkbox("**:red[仅显示问题项]**", value=False, key=f"{key_prefix}-only-issues", help="勾选后仅展示存在质量问题的行")
        with c_enc:
            enc_opt = st.selectbox(
                "导出编码", 
                options=["utf-8-sig", "gbk"], 
                format_func=lambda x: "UTF-8 (推荐 WPS/通用)" if x == "utf-8-sig" else "GBK (推荐 Excel 直接打开)",
                key=f"{key_prefix}-enc"
            )
        
        view = df
        # Pre-filter view based on search (moved to Row 2)
        
        # Row 2: Search
        query = st.text_input("关键词搜索", placeholder="输入关键词或‘答案为空’...", key=f"{key_prefix}-search")
        
        # Apply Search Filter
        if query:
            if query == "答案为空" and "answer" in df.columns:
                view = df[df["answer"].astype(str).str.len() == 0]
            else:
                view = df[df.astype(str).apply(lambda r: query in "\t".join(r.values), axis=1)]
        
        # Apply Issue Filter
        if only_issues and meta:
            assessed = assess_qa(view) if meta.get("type") == "问答对" else assess_exercises(view)
            view = assessed[assessed["quality_flags"].astype(str).str.contains("Error:|Warn:")]
            
            # Export Button (In Row 1, Col 3) - requires 'view' to be filtered first
            with c_exp:
                if not view.empty:
                    try:
                        csv_data = view.to_csv(index=False).encode(enc_opt)
                        st.download_button(
                            label="📥 导出报告",
                            data=csv_data,
                            file_name=f"issue_report_{meta.get('filename','upload')}_{enc_opt}.csv",
                            mime="text/csv",
                            key=f"{key_prefix}-download-issues"
                        )
                    except UnicodeEncodeError:
                         st.error(f"{enc_opt} 编码无法保存某些字符，请尝试 UTF-8")

        # Row 3: Column & Width Control
        all_cols = list(df.columns)
        c_width, c_sel = st.columns([1, 4])
        with c_width:
             use_width_t1 = st.checkbox("适应宽度", value=False, key=f"{key_prefix}-t1-width")
        with c_sel:
             show_cols_t1 = st.multiselect("显示列", all_cols, default=all_cols, key=f"{key_prefix}-t1-cols")

        # Row 4: Pagination & Table
        page_size = st.slider("每页条数", 10, 100, 20, key=f"{key_prefix}-page_size")
        page = st.number_input("页码", min_value=1, value=1, key=f"{key_prefix}-page")
        
        start = (page - 1) * page_size
        end = start + page_size
        view_slice = view.iloc[int(start):int(end)]
        
        # Apply Column Filter
        if show_cols_t1:
            view_slice = view_slice[show_cols_t1]

        # Render Table
        if only_issues and meta:
             # Logic for styling issues (copied/adapted from previous implementation)
            flags_map = view["quality_flags"].to_dict() # Map index -> flags
            def _cell_style_safe(row):
                 flags = str(flags_map.get(row.name, ""))
                 cols = list(row.index)
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

            st.dataframe(view_slice.style.apply(_cell_style_safe, axis=1), use_container_width=use_width_t1)
        else:
            st.dataframe(view_slice, use_container_width=use_width_t1)

    # --- Tab 2: Random Inspection ---
    with tab2:
        cols = list(df.columns)
        toggle_col, sel_col = st.columns([1, 4])
        with toggle_col:
             use_width = st.checkbox("适应宽度", value=False, key=f"{key_prefix}-t2-width")
        with sel_col:
             show_cols = st.multiselect("显示列", cols, default=cols, key=f"{key_prefix}-t2-cols")
        
        n = min(20, len(df))
        sample_df = df.sample(n)
        view_df = sample_df[show_cols] if show_cols else sample_df 
        
        assessed = assess_qa(sample_df) if meta and meta.get("type") == "问答对" else assess_exercises(sample_df)
        
        def _cell_style(row):
            flags = str(row.get("quality_flags", ""))
            cols_to_style = list(view_df.columns) 
            red_cols = set()
            if meta and meta.get("type") == "问答对":
                if "Error:Q_EMPTY" in flags or "Error:Q_GARBLED" in flags: red_cols.add("question")
                if "Error:A_EMPTY" in flags or "Error:A_GARBLED" in flags: red_cols.add("answer")
            else:
                if "Error:STEM_EMPTY" in flags or "Error:STEM_GARBLED" in flags: red_cols.add("stem")
                if "Error:OPT_EMPTY" in flags or "Error:OPT_GARBLED" in flags: red_cols.add("options")
                if "Error:ANS_EMPTY" in flags or "Error:ANS_GARBLED" in flags or "Error:ANS_NOT_IN_OPTS" in flags or "Error:ANS_INVALID" in flags: red_cols.add("answer")
                if "Error:KN_EMPTY" in flags or "Error:KN_GARBLED" in flags: red_cols.add("knowledge")
            return ["background-color: #fdecea" if c in red_cols else "" for c in cols_to_style]
        
        final_view = assessed[show_cols]
        st.dataframe(final_view.style.apply(_cell_style, axis=1), use_container_width=use_width)
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
        .login-hero .byline{margin-top:6px;color:#64748B;font-size:12px;letter-spacing:0.3px}
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
        f"<div class='login-hero'><h1>{title}</h1>" + (f"<div class='byline'>{subtitle}</div>" if subtitle else "") + "</div>",
        unsafe_allow_html=True,
    )

def style_sidebar_menu():
    # The CSS is now largely handled by assets/style.css, but we can inject specific overrides if needed here.
    # For now, we rely on the global CSS.
    pass

