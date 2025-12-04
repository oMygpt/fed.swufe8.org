import streamlit as st
import pandas as pd
import io
import yaml
import bcrypt
from pathlib import Path
import streamlit.components.v1 as components
from modules.auth import get_authenticator, get_user_info
from modules.parsing import parse_uploaded_file
from modules.storage import (
    archive_raw_file,
    save_parsed_dataset,
    list_history,
    list_history_tests,
    merge_all_parsed,
    list_parsed_datasets,
    load_csv,
    delete_path,
    get_colleges,
    get_targets,
    save_targets,
    get_college_display,
)
from modules.quality import assess_qa, assess_exercises, summarize_quality

def _suggestions_for_errors(errs: dict, dtype: str) -> list[str]:
    tips = []
    if dtype == "问答对":
        mapping = {
            "Q_EMPTY": "填写问题（question），避免为空",
            "A_EMPTY": "填写答案（answer），避免为空",
            "Q_GARBLED": "修复问题乱码（检查编码/非法字符）",
            "A_GARBLED": "修复答案乱码（检查编码/非法字符）",
            "Q_SHORT": "问题长度建议不少于3个字符",
            "A_SHORT": "答案长度过短，补充完整",
        }
    else:
        mapping = {
            "STEM_EMPTY": "补充题干（stem）",
            "ANS_EMPTY": "补充答案（answer）",
            "OPT_EMPTY": "补充选项（options），使用格式：A: xxx\\nB: xxx",
            "OPT_GARBLED": "修复选项乱码（检查非法字符与编码）",
            "ANS_NOT_IN_OPTS": "答案需为选项字母（如 A/B/C/D），与选项一致",
            "ANS_INVALID": "判断题答案需在 True/False/是/否/对/错",
            "STEM_GARBLED": "修复题干乱码（检查编码）",
            "ANS_GARBLED": "修复答案乱码（检查编码）",
            "KN_EMPTY": "补充知识点（knowledge），关联课程章节或概念",
            "KN_GARBLED": "修复知识点乱码（检查编码）",
        }
    for code in sorted(errs.keys(), key=lambda c: -errs[c]):
        tip = mapping.get(code)
        if tip:
            tips.append(f"{tip}（问题数：{errs[code]}）")
    if not tips:
        tips.append("修复所有标红项（Error），并重新上传")
    return tips
from modules.ui import render_overview, render_tabs, render_history, hide_deploy_button, render_login_branding, style_sidebar_menu

st.set_page_config(page_title="应用经济学语料提交平台（本科）", layout="wide", menu_items={"Get help": None, "Report a bug": None, "About": None})
hide_deploy_button()
render_login_branding("应用经济学语料提交平台（本科）", "请使用学院账户登录")

authenticator = get_authenticator()
authenticator.login(
    location="main",
    fields={
        "Form name": "登录",
        "Username": "用户名",
        "Password": "密码",
        "Login": "登录",
    },
)
authentication_status = st.session_state.get("authentication_status")
username = st.session_state.get("username")
name = st.session_state.get("name")

if authentication_status is False:
    st.error("用户名或密码错误")
elif authentication_status is None:
    st.warning("请输入用户名和密码")
    from pathlib import Path as _P
    _gp = _P("handbook.md")
    if _gp.exists():
        _md = _gp.read_text(encoding="utf-8")
        with st.expander("在线查看使用指南"):
            st.markdown(_md)
    _gh = _P("handbook.html")
    if _gh.exists():
        _html = _gh.read_text(encoding="utf-8")
        components.html(_html, height=800, scrolling=True)
else:
    user_info = get_user_info(username)
    st.sidebar.success(f"当前用户：{user_info['display']}（{user_info['role']}）")
    from pathlib import Path as _P
    _gp = _P("handbook.md")
    if _gp.exists():
        _md = _gp.read_text(encoding="utf-8")
    _gh = _P("handbook.html")
    if _gh.exists():
        _html = _gh.read_text(encoding="utf-8")
        with st.sidebar.expander("在线阅读指南 (HTML)"):
            components.html(_html, height=600, scrolling=True)
    try:
        from modules.storage import log_login
        if not st.session_state.get("login_logged"):
            log_login(username, user_info["college"])
            st.session_state["login_logged"] = True
    except Exception:
        pass
    try:
        authenticator.logout("退出登录", "sidebar")
    except Exception:
        pass
    if st.sidebar.button("切换账号"):
        for k in ["authentication_status", "username", "name"]:
            st.session_state.pop(k, None)
    if user_info["role"] == "admin":
        menu = ["📊 汇总统计", "🏫 学院管理", "🧪 测试样例", "📦 汇总输出"]
    else:
        menu = ["⬆️ 上传数据", "🕘 历史记录"]
    style_sidebar_menu()
    st.sidebar.markdown("<div class='sidebar-brand'><h2>应用经济学语料提交平台（本科）</h2><p>请选择菜单</p><div class='sidebar-team'>A³ T  @2025</div></div>", unsafe_allow_html=True)
    choice = st.sidebar.radio("菜单", menu)

    if choice.endswith("上传数据"):
        st.header("上传数据")
        # 进度概览（含研究生分项）
        items = list_parsed_datasets(user_info["college"]) 
        qa_count = 0
        ex_count = 0
        ex_ug_count = 0
        ex_grad_count = 0
        for it in items:
            dfc = load_csv(it["path"])
            if it["type"] == "qa":
                qa_count += len(dfc)
            else:
                ex_count += len(dfc)
                lev = it.get("level") or (dfc.get("level").iloc[0] if "level" in dfc.columns and len(dfc) else "本科")
                if lev == "研究生":
                    ex_grad_count += len(dfc)
                else:
                    ex_ug_count += len(dfc)
        tgt = get_targets(user_info["college"]) 
        qa_t = int(tgt.get("qa", 0))
        ex_t = int(tgt.get("ex", 0))
        ex_ug_t = int(tgt.get("levels", {}).get("ug", {}).get("ex", 0))
        ex_grad_t = int(tgt.get("levels", {}).get("grad", {}).get("ex", 0))
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("问答对数量", qa_count)
        with c2: st.metric("问答对目标", qa_t)
        with c3: st.metric("习题数量", ex_count)
        with c4: st.metric("习题目标", ex_t)
        st.progress(0 if qa_t == 0 else min(1.0, qa_count/qa_t))
        c5, c6 = st.columns(2)
        with c5: st.metric("本科习题", f"{ex_ug_count}/{ex_ug_t}")
        with c6: st.metric("研究生习题", f"{ex_grad_count}/{ex_grad_t}")
        st.progress(0 if ex_ug_t == 0 else min(1.0, ex_ug_count/ex_ug_t))
        st.progress(0 if ex_grad_t == 0 else min(1.0, ex_grad_count/ex_grad_t))
        info = st.session_state.get("last_import_info")
        if info:
            msg = f"已{'强制' if info.get('force') else ''}入库：{info.get('type','-')}（{info.get('count',0)} 条）"
            if info.get('force'):
                st.warning(msg)
            else:
                st.success(msg)
            st.session_state.pop("last_import_info", None)

        st.subheader("上传学院收集的语料集")
        upload_type = st.radio("上传类型", ["问答对", "本科习题库", "研究生习题库"], horizontal=True)
        exercise_types = ["自动识别", "选择题", "填空题", "简答题", "论述题", "案例分析题", "判断题"]
        level_types = ["自动识别", "本科", "研究生"]
        chosen_ex_type = None
        chosen_level = None
        if upload_type == "本科习题库":
            # 本科习题库：不显示级别选择，默认本科
            sel = st.selectbox("题型", exercise_types)
            chosen_ex_type = None if sel == "自动识别" else sel
            chosen_level = "本科"
        elif upload_type == "研究生习题库":
            # 强制研究生级别，不进行级别自动识别
            sel = st.selectbox("题型", exercise_types)
            chosen_ex_type = None if sel == "自动识别" else sel
            chosen_level = "研究生"
        nonce = st.session_state.get("upload_nonce", 0)
        uploaded = st.file_uploader("上传学院收集的语料集（支持 Excel/CSV）", type=["xlsx", "xls", "csv"], key=f"main_upload_{nonce}") 
        if uploaded is not None:
            raw_path = archive_raw_file(uploaded, user_info["college"]) 
            # 本科/研究生习题库均按“习题库”解析，但强制传入 level
            _u_type = "习题库" if upload_type in ("本科习题库", "研究生习题库") else upload_type
            meta, df, warnings = parse_uploaded_file(uploaded, _u_type, chosen_ex_type, chosen_level)
            render_overview(meta, warnings)
            render_tabs(df, meta, key_prefix="upload_preview")
            type_mismatch = bool(meta.get("detected_type") and meta.get("type") and meta.get("detected_type") != meta.get("type"))
            if type_mismatch:
                st.error("类型选择与系统识别不一致：请检查文件结构或更正上传类型。已禁用入库与强制入库。")
            else:
                QUALITY_ERROR_RATIO_THRESHOLD = 0.05
                qs = (meta.get("quality_summary") or {})
                err_ratio = float(qs.get("error_row_ratio", 0.0))
                st.caption(f"质量错误占比：{round(err_ratio*100,2)}%（阈值 {int(QUALITY_ERROR_RATIO_THRESHOLD*100)}%）")
                c1, c2 = st.columns(2)
                with c1:
                    if err_ratio <= QUALITY_ERROR_RATIO_THRESHOLD:
                        if st.button("入库", type="primary"):
                            save_parsed_dataset(df, meta, user_info["college"]) 
                            st.session_state["last_import_info"] = {"type": meta.get('type','-'), "count": len(df), "force": False}
                            st.session_state["upload_nonce"] = nonce + 1
                            if hasattr(st, "rerun"):
                                st.rerun()
                            elif hasattr(st, "experimental_rerun"):
                                st.experimental_rerun()
                    else:
                        st.error(f"质量错误占比 {round(err_ratio*100,2)}% 超过阈值，建议修复后再入库")
                with c2:
                    if st.button("强制入库（忽略质量检测）"):
                        save_parsed_dataset(df, meta, user_info["college"]) 
                        st.session_state["last_import_info"] = {"type": meta.get('type','-'), "count": len(df), "force": True}
                        st.session_state["upload_nonce"] = nonce + 1
                        if hasattr(st, "rerun"):
                            st.rerun()
                        elif hasattr(st, "experimental_rerun"):
                            st.experimental_rerun()

    elif choice.endswith("历史记录"):
        st.header("历史记录")
        # 进度概览
        items = list_parsed_datasets(user_info["college"]) 
        qa_count = 0
        ex_count = 0
        for it in items:
            dfc = load_csv(it["path"])
            if it["type"] == "qa":
                qa_count += len(dfc)
            else:
                ex_count += len(dfc)
        tgt = get_targets(user_info["college"]) 
        qa_t = int(tgt.get("qa", 0))
        ex_t = int(tgt.get("ex", 0))
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("问答对数量", qa_count)
        with c2: st.metric("问答对目标", qa_t)
        with c3: st.metric("习题数量", ex_count)
        with c4: st.metric("习题目标", ex_t)
        st.progress(0 if qa_t == 0 else min(1.0, qa_count/qa_t))
        st.progress(0 if ex_t == 0 else min(1.0, ex_count/ex_t))
        records = list_history(user_info["college"]) 
        if not records:
            st.info("暂无历史记录")
        else:
            summaries = []
            for it in records:
                is_qa = it["file"].endswith("_parsed_qa.csv")
                is_ex = it["file"].endswith("_parsed_ex.csv")
                if is_qa or is_ex:
                    df_tmp = load_csv(it["path"])
                    summaries.append({"上传日期": it["date"], "文件": it["file"], "类型": ("问答对" if is_qa else "习题库"), "条目数": len(df_tmp)})
            if summaries:
                st.subheader("上传记录汇总")
                st.dataframe(pd.DataFrame(summaries), use_container_width=True)
            for item in records:
                is_parsed_qa = item["file"].endswith("_parsed_qa.csv")
                is_parsed_ex = item["file"].endswith("_parsed_ex.csv")
                if is_parsed_qa or is_parsed_ex:
                    df = load_csv(item["path"])
                    type_name = "问答对" if is_parsed_qa else "习题库"
                    with st.expander(f"{item['date']} - {item['file']} · 类型：{type_name} · 条目：{len(df)}"):
                        meta = {"type": type_name, "filename": item["file"], "total": len(df)}
                        render_overview(meta, [])
                        render_tabs(df, meta, key_prefix=f"history-{item['path']}")
                        if st.button("删除", key=f"user-del-{item['path']}"):
                            if delete_path(item["path"]):
                                st.success("已删除")
                                if hasattr(st, "rerun"):
                                    st.rerun()
                                elif hasattr(st, "experimental_rerun"):
                                    st.experimental_rerun()
                            else:
                                st.error("删除失败")
                else:
                    with st.expander(f"{item['date']} - {item['file']} · 原始文件"):
                        st.info("原始文件（预览略）")
                        with open(item["path"], "rb") as fh:
                            st.download_button("下载原始文件", fh.read(), file_name=item["file"]) 

    elif choice.endswith("汇总统计"):
        st.header("汇总统计")
        cols = get_colleges()
        name_map = {get_college_display(c): c for c in cols}
        st.subheader("选择学院")
        selected_cols = []
        for disp, code in name_map.items():
            if st.checkbox(disp, value=True, key=f"stats-col-{code}"):
                selected_cols.append(code)
        level_filter = st.radio("级别过滤", ["全部", "本科", "研究生"], horizontal=True)
        sort_opt = st.radio("排序", ["按问答对数量", "按习题数量", "按达标状态", "按研究生习题数量"], horizontal=True)
        rows = []
        for c in selected_cols:
            items = list_parsed_datasets(c)
            qa_count = 0
            ex_count = 0
            qa_frames = []
            ex_frames = []
            for it in items:
                df = load_csv(it["path"])
                if it["type"] == "qa":
                    qa_count += len(df)
                    if not df.empty:
                        qa_frames.append(df)
                else:
                    lev = it.get("level") or "本科"
                    if level_filter == "全部" or lev == level_filter:
                        ex_count += len(df)
                        if not df.empty:
                            df["level"] = lev
                            ex_frames.append(df)
            tgt = get_targets(c)
            qa_status = "达标" if qa_count >= int(tgt.get("qa", 0)) and int(tgt.get("qa", 0)) > 0 else ("未设定" if int(tgt.get("qa", 0)) == 0 else "未达标")
            # 统计级别：本科与研究生
            ex_ug_count = 0
            ex_grad_count = 0
            for it in items:
                if it["type"] == "ex":
                    df = load_csv(it["path"])
                    lev = it.get("level") or (df.get("level").iloc[0] if "level" in df.columns and len(df) else "本科")
                    if lev == "研究生":
                        ex_grad_count += len(df)
                    else:
                        ex_ug_count += len(df)
            ex_ug_t = int(tgt.get("levels", {}).get("ug", {}).get("ex", 0))
            ex_grad_t = int(tgt.get("levels", {}).get("grad", {}).get("ex", 0))
            ex_status = "达标" if (ex_ug_count + ex_grad_count) >= int(tgt.get("ex", 0)) and int(tgt.get("ex", 0)) > 0 else ("未设定" if int(tgt.get("ex", 0)) == 0 else "未达标")
            ex_ug_status = "达标" if ex_ug_count >= ex_ug_t and ex_ug_t > 0 else ("未设定" if ex_ug_t == 0 else "未达标")
            ex_grad_status = "达标" if ex_grad_count >= ex_grad_t and ex_grad_t > 0 else ("未设定" if ex_grad_t == 0 else "未达标")
            # 质量汇总（动态评估，不写入文件）
            qa_summary = {"score_avg": 0, "error_row_ratio": 0.0}
            ex_summary = {"score_avg": 0, "error_row_ratio": 0.0}
            if qa_frames:
                qa_all = pd.concat(qa_frames, ignore_index=True)
                qa_summary = summarize_quality(assess_qa(qa_all))
            if ex_frames:
                ex_all = pd.concat(ex_frames, ignore_index=True)
                ex_summary = summarize_quality(assess_exercises(ex_all))
            total_rows = (len(pd.concat(qa_frames, ignore_index=True)) if qa_frames else 0) + (len(pd.concat(ex_frames, ignore_index=True)) if ex_frames else 0)
            overall_error_ratio = 0.0
            if total_rows > 0:
                overall_error_ratio = (
                    qa_summary.get("error_row_ratio", 0.0) * (len(pd.concat(qa_frames, ignore_index=True)) if qa_frames else 0)
                    + ex_summary.get("error_row_ratio", 0.0) * (len(pd.concat(ex_frames, ignore_index=True)) if ex_frames else 0)
                ) / total_rows
            overall_score = 0.0
            if total_rows > 0:
                overall_score = (
                    qa_summary.get("score_avg", 0.0) * (len(pd.concat(qa_frames, ignore_index=True)) if qa_frames else 0)
                    + ex_summary.get("score_avg", 0.0) * (len(pd.concat(ex_frames, ignore_index=True)) if ex_frames else 0)
                ) / total_rows
            rows.append({
                "学院": get_college_display(c),
                "问答对": qa_count,
                "问答对目标": int(tgt.get("qa", 0)),
                "问答对状态": qa_status,
                "习题": ex_count,
                "习题目标": int(tgt.get("ex", 0)),
                "习题状态": ex_status,
                "本科习题": ex_ug_count,
                "本科目标": ex_ug_t,
                "本科状态": ex_ug_status,
                "研究生习题": ex_grad_count,
                "研究生目标": ex_grad_t,
                "研究生状态": ex_grad_status,
                "质量均分": round(overall_score, 2),
                "红色问题比例": round(overall_error_ratio * 100, 2),
            })
        if rows:
            df_rows = pd.DataFrame(rows)
            if sort_opt == "按问答对数量":
                df_rows = df_rows.sort_values(by=["问答对"], ascending=False)
            elif sort_opt == "按习题数量":
                df_rows = df_rows.sort_values(by=["习题"], ascending=False)
            elif sort_opt == "按研究生习题数量":
                df_rows = df_rows.sort_values(by=["研究生习题"], ascending=False)
            else:
                status_map = {"达标": 2, "未设定": 1, "未达标": 0}
                df_rows = df_rows.sort_values(by=["问答对状态"], key=lambda s: s.map(status_map), ascending=False)
            st.dataframe(df_rows, use_container_width=True)
            for r in rows:
                with st.expander(f"{r['学院']} 详情"):
                    code = name_map.get(r["学院"], None)
                    items = list_parsed_datasets(code or r["学院"])  
                    # 质量细节：按类型显示
                    qa_frames = []
                    ex_frames = []
                    for it in items:
                        with st.expander(f"{it['date']} - {it['file']}"):
                            df = load_csv(it["path"])
                            meta = {"type": ("问答对" if it["type"] == "qa" else "习题库")}
                            render_tabs(df, meta, key_prefix=f"stats-{it['path']}")
                        if it["type"] == "qa" and not df.empty:
                            qa_frames.append(df)
                        elif it["type"] == "ex" and not df.empty:
                            df["level"] = it.get("level") or df.get("level", "本科")
                            ex_frames.append(df)
                    st.subheader("质量汇总")
                    if qa_frames:
                        qa_all = pd.concat(qa_frames, ignore_index=True)
                        qa_sum = summarize_quality(assess_qa(qa_all))
                        st.write(f"问答对：均分 {qa_sum.get('score_avg',0)}，红色问题比例 {round(qa_sum.get('error_row_ratio',0)*100,2)}%")
                    if ex_frames:
                        ex_all = pd.concat(ex_frames, ignore_index=True)
                        ex_sum = summarize_quality(assess_exercises(ex_all))
                        st.write(f"习题（全部级别）：均分 {ex_sum.get('score_avg',0)}，红色问题比例 {round(ex_sum.get('error_row_ratio',0)*100,2)}%")
                        if "level" in ex_all.columns:
                            for lev, part in ex_all.groupby("level"):
                                psum = summarize_quality(assess_exercises(part))
                                st.write(f"{lev}：均分 {psum.get('score_avg',0)}，红色问题比例 {round(psum.get('error_row_ratio',0)*100,2)}%")
        else:
            st.info("暂无学院提交数据")

    elif choice.endswith("学院管理"):
        st.header("学院管理")
        cols_codes = get_colleges()
        name_map = {code: get_college_display(code) for code in cols_codes}
        palette = {
            "economy": "#E3F2FD",
            "finance": "#FFF3E0",
            "intl": "#E8F5E9",
            "west": "#F3E5F5",
            "tax": "#FBE9E7",
            "mgmt": "#EDE7F6",
        }
        sel_code = st.session_state.get("manage_sel_code")
        if not sel_code:
            st.subheader("进度缩略图")
            cols_per_row = 3
            for i in range(0, len(cols_codes), cols_per_row):
                row = st.columns(cols_per_row)
                for j, code in enumerate(cols_codes[i:i+cols_per_row]):
                    with row[j]:
                        items = list_parsed_datasets(code)
                        qa_count = 0
                        ex_count = 0
                        ex_ug_count = 0
                        ex_grad_count = 0
                        for it in items:
                            df = load_csv(it["path"])
                            if it["type"] == "qa":
                                qa_count += len(df)
                            else:
                                ex_count += len(df)
                                lev = it.get("level") or (df.get("level").iloc[0] if "level" in df.columns and len(df) else "本科")
                                if lev == "研究生":
                                    ex_grad_count += len(df)
                                else:
                                    ex_ug_count += len(df)
                        tgt = get_targets(code)
                        qa_t = int(tgt.get("qa", 0))
                        ex_t = int(tgt.get("ex", 0))
                        ex_ug_t = int(tgt.get("levels", {}).get("ug", {}).get("ex", 0))
                        ex_grad_t = int(tgt.get("levels", {}).get("grad", {}).get("ex", 0))
                        qa_ratio = 0 if qa_t == 0 else min(1.0, qa_count/qa_t)
                        ex_ratio = 0 if ex_t == 0 else min(1.0, ex_count/ex_t)
                        ex_ug_ratio = 0 if ex_ug_t == 0 else min(1.0, ex_ug_count/ex_ug_t)
                        ex_grad_ratio = 0 if ex_grad_t == 0 else min(1.0, ex_grad_count/ex_grad_t)
                        bg = palette.get(code, "#F5F5F5")
                        hx = bg.lstrip('#')
                        r, g, b = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
                        gradient = f"radial-gradient(circle at 50% 40%, rgba({r},{g},{b},0.12) 0%, rgba({r},{g},{b},0.22) 60%, rgba({r},{g},{b},0.32) 100%)"
                        st.markdown(
                            f"<div style='background:{gradient};padding:12px;border-radius:8px;color:#0F172A'>"
                            f"<b>{name_map[code]}</b><br/>"
                            f"问答对：{qa_count}/{qa_t}<br/>"
                            f"本科习题：{ex_ug_count}/{ex_ug_t}<br/>"
                            f"研究生习题：{ex_grad_count}/{ex_grad_t}</div>",
                            unsafe_allow_html=True,
                        )
                        st.progress(qa_ratio)
                        st.progress(ex_ug_ratio)
                        st.progress(ex_grad_ratio)
                        if st.button("查看详情", key=f"goto-{code}"):
                            st.session_state["manage_sel_code"] = code
            if st.button("➕ 添加学院", key="add_college_toggle"):
                st.session_state["show_add_form"] = not st.session_state.get("show_add_form", False)
            if st.session_state.get("show_add_form"):
                with st.form("add_college_form"):
                    new_username = st.text_input("用户名", help="例如 user_newcollege")
                    new_name = st.text_input("学院名称")
                    new_email = st.text_input("邮箱")
                    new_password = st.text_input("初始密码", type="password")
                    submitted = st.form_submit_button("添加学院")
                    if submitted and new_username and new_name and new_email and new_password:
                        cfg_path = Path("config/users.yaml")
                        if cfg_path.exists():
                            with open(cfg_path, "r", encoding="utf-8") as f:
                                data = yaml.safe_load(f)
                        else:
                            data = {"credentials": {"usernames": {}}, "cookie": {"name": "auth_cookie", "key": "random_key", "expiry_days": 1}, "preauthorized": {"emails": []}}
                        hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
                        data.setdefault("credentials", {}).setdefault("usernames", {})[new_username] = {"email": new_email, "name": new_name, "password": hashed}
                        cfg_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(cfg_path, "w", encoding="utf-8") as f:
                            yaml.safe_dump(data, f, allow_unicode=True)
                        st.success("已新增学院与账户")
        else:
            code = sel_code
            st.subheader(f"目标设置 - {get_college_display(code)}")
            targets = get_targets(code)
            qa_t = st.number_input("问答对目标数量", min_value=0, value=int(targets.get("qa", 0)))
            ex_ug_t = st.number_input("本科习题目标数量", min_value=0, value=int(targets.get("levels", {}).get("ug", {}).get("ex", 0)))
            ex_grad_t = st.number_input("研究生习题目标数量", min_value=0, value=int(targets.get("levels", {}).get("grad", {}).get("ex", 0)))
            st.subheader("习题题型目标设置")
            type_target_names = ["选择题", "填空题", "简答题", "论述题", "案例分析题", "判断题"]
            type_target_vals = {}
            for tname in type_target_names:
                type_target_vals[tname] = st.number_input(f"{tname}目标数量", min_value=0, value=int(targets.get("types", {}).get(tname, 0)))
            if st.button("保存目标设置", key="save_targets_manage"):
                save_targets(code, qa_t, ex_ug_t, ex_grad_t, types=type_target_vals)
                st.success("已保存")
            if st.button("返回学院管理", key="back_manage"):
                st.session_state.pop("manage_sel_code", None)
                if hasattr(st, "rerun"):
                    st.rerun()
                elif hasattr(st, "experimental_rerun"):
                    st.experimental_rerun()
            if st.button("保存目标设置"):
                save_targets(code, qa_t, ex_t, types=type_target_vals)
                st.success("已保存")
                st.session_state.pop("manage_sel_code", None)
                if hasattr(st, "rerun"):
                    st.rerun()
                elif hasattr(st, "experimental_rerun"):
                    st.experimental_rerun()
            with st.expander("上传记录与预览"):
                parsed = list_parsed_datasets(code)
                for item in parsed:
                    with st.expander(f"{item['date']} - {item['file']} ({'问答对' if item['type']=='qa' else '习题库'})"):
                        df = load_csv(item["path"])
                        meta = {"type": ("问答对" if item["type"] == "qa" else "习题库")}
                        render_tabs(df, meta, key_prefix=f"manage-{item['path']}")
                        if st.button("删除", key=f"del-{item['path']}"):
                            if delete_path(item["path"]):
                                st.success("已删除")
                            else:
                                st.error("删除失败")
            with st.expander("账户与登录管理"):
                with st.form("change_password_form"):
                    ch_username = st.text_input("选择用户名")
                    ch_new_pwd = st.text_input("新密码", type="password")
                    ch_submit = st.form_submit_button("修改密码")
                    if ch_submit and ch_username and ch_new_pwd:
                        cfg_path = Path("config/users.yaml")
                        if not cfg_path.exists():
                            st.error("配置不存在")
                        else:
                            with open(cfg_path, "r", encoding="utf-8") as f:
                                data = yaml.safe_load(f)
                            users = data.get("credentials", {}).get("usernames", {})
                            if ch_username not in users:
                                st.error("用户不存在")
                            else:
                                users[ch_username]["password"] = bcrypt.hashpw(ch_new_pwd.encode(), bcrypt.gensalt()).decode()
                                with open(cfg_path, "w", encoding="utf-8") as f:
                                    yaml.safe_dump(data, f, allow_unicode=True)
                                st.success("已修改密码")
                from modules.storage import list_logins
                logs = list_logins(code)
                if not logs:
                    st.info("暂无登录记录")
                else:
                    for entry in logs:
                        with st.expander(entry["date"]):
                            for e in entry["events"]:
                                st.write(e)

    elif choice.endswith("测试样例"):
        st.header("测试样例")
        if user_info["role"] == "admin":
            tab_sample, tab_upload, tab_history, tab_history_test = st.tabs(["上传样例", "上传数据", "历史记录", "测试历史"])
            with tab_sample:
                upload_type = st.radio("类型", ["问答对", "习题库"], horizontal=True, key="test_type")
                exercise_types = ["自动识别", "选择题", "填空题", "简答题", "论述题", "案例分析题", "判断题"]
                chosen_ex_type = None
                if upload_type == "习题库":
                    sel = st.selectbox("题型", exercise_types, key="test_ex_type")
                    chosen_ex_type = None if sel == "自动识别" else sel
                uploaded = st.file_uploader("上传样例文件", type=["xlsx", "xls", "csv"], key="test_uploader")
                if uploaded is not None:
                    meta, df, warnings = parse_uploaded_file(uploaded, upload_type, chosen_ex_type)
                    render_overview(meta, warnings)
                    render_tabs(df, meta, key_prefix="test_sample")
                    ok = True
                    if upload_type == "问答对":
                        ok = df is not None and not df.empty and set(["question", "answer"]).issubset(set(df.columns))
                    else:
                        required = {"stem", "answer"}
                        ok = df is not None and not df.empty and required.issubset(set(df.columns))
                    st.success("样例满足基本要求") if ok else st.error("样例不满足基本要求")
            with tab_upload:
                upload_type = st.radio("类型", ["问答对", "习题库"], horizontal=True, key="admin_upload_type")
                exercise_types = ["自动识别", "选择题", "填空题", "简答题", "论述题", "案例分析题", "判断题"]
                chosen_ex_type = None
                if upload_type == "习题库":
                    sel = st.selectbox("题型", exercise_types, key="admin_upload_ex_type")
                    chosen_ex_type = None if sel == "自动识别" else sel
                uploaded = st.file_uploader("上传数据文件", type=["xlsx", "xls", "csv"], key="admin_upload_uploader")
                if uploaded is not None:
                    raw_path = archive_raw_file(uploaded, user_info["college"]) 
                    meta, df, warnings = parse_uploaded_file(uploaded, upload_type, chosen_ex_type)
                    render_overview(meta, warnings)
                    render_tabs(df, meta, key_prefix="admin_upload_preview")
                    save_parsed_dataset(df, meta, user_info["college"]) 
            with tab_history:
                records = list_history(user_info["college"]) 
                if not records:
                    st.info("暂无历史记录")
                else:
                    summaries = []
                    for it in records:
                        is_qa = it["file"].endswith("_parsed_qa.csv")
                        is_ex = it["file"].endswith("_parsed_ex.csv")
                        if is_qa or is_ex:
                            df_tmp = load_csv(it["path"])
                            summaries.append({"上传日期": it["date"], "文件": it["file"], "类型": ("问答对" if is_qa else "习题库"), "条目数": len(df_tmp)})
                    if summaries:
                        st.subheader("上传记录汇总")
                        st.dataframe(pd.DataFrame(summaries), use_container_width=True)
                    for item in records:
                        is_parsed_qa = item["file"].endswith("_parsed_qa.csv")
                        is_parsed_ex = item["file"].endswith("_parsed_ex.csv")
                        if is_parsed_qa or is_parsed_ex:
                            df = load_csv(item["path"])
                            type_name = "问答对" if is_parsed_qa else "习题库"
                            with st.expander(f"{item['date']} - {item['file']} · 类型：{type_name} · 条目：{len(df)}"):
                                meta = {"type": type_name, "filename": item["file"], "total": len(df)}
                                render_overview(meta, [])
                                render_tabs(df, meta, key_prefix=f"test_history-{item['path']}")
                        else:
                            with st.expander(f"{item['date']} - {item['file']} · 原始文件"):
                                st.info("原始文件（预览略）")
                                with open(item["path"], "rb") as fh:
                                    st.download_button("下载原始文件", fh.read(), file_name=item["file"]) 
            with tab_history_test:
                records = list_history_tests(user_info["college"]) 
                if not records:
                    st.info("暂无测试历史")
                else:
                    summaries = []
                    for it in records:
                        is_qa = it["file"].endswith("_parsed_qa.csv")
                        is_ex = it["file"].endswith("_parsed_ex.csv")
                        if is_qa or is_ex:
                            df_tmp = load_csv(it["path"])
                            summaries.append({"上传日期": it["date"], "文件": it["file"], "类型": ("问答对" if is_qa else "习题库"), "条目数": len(df_tmp)})
                    if summaries:
                        st.subheader("测试记录汇总")
                        st.dataframe(pd.DataFrame(summaries), use_container_width=True)
                    for item in records:
                        is_parsed_qa = item["file"].endswith("_parsed_qa.csv")
                        is_parsed_ex = item["file"].endswith("_parsed_ex.csv")
                        if is_parsed_qa or is_parsed_ex:
                            df = load_csv(item["path"])
                            type_name = "问答对" if is_parsed_qa else "习题库"
                            with st.expander(f"{item['date']} - {item['file']} · 类型：{type_name} · 条目：{len(df)}"):
                                meta = {"type": type_name, "filename": item["file"], "total": len(df)}
                                render_overview(meta, [])
                                render_tabs(df, meta, key_prefix=f"test_history_test-{item['path']}")
                        else:
                            with st.expander(f"{item['date']} - {item['file']} · 原始文件"):
                                st.info("原始文件（预览略）")
                                with open(item["path"], "rb") as fh:
                                    st.download_button("下载原始文件", fh.read(), file_name=item["file"]) 
        else:
            upload_type = st.radio("类型", ["问答对", "习题库"], horizontal=True, key="test_type")
            exercise_types = ["自动识别", "选择题", "填空题", "简答题", "论述题", "案例分析题", "判断题"]
            chosen_ex_type = None
            if upload_type == "习题库":
                sel = st.selectbox("题型", exercise_types, key="test_ex_type")
                chosen_ex_type = None if sel == "自动识别" else sel
            uploaded = st.file_uploader("上传样例文件", type=["xlsx", "xls", "csv"], key="test_uploader")
            if uploaded is not None:
                meta, df, warnings = parse_uploaded_file(uploaded, upload_type, chosen_ex_type)
                render_overview(meta, warnings)
                render_tabs(df, meta, key_prefix="test_sample_non_admin")
                ok = True
                if upload_type == "问答对":
                    ok = df is not None and not df.empty and set(["question", "answer"]).issubset(set(df.columns))
                else:
                    required = {"stem", "answer"}
                    ok = df is not None and not df.empty and required.issubset(set(df.columns))
                st.success("样例满足基本要求") if ok else st.error("样例不满足基本要求")

    elif choice.endswith("汇总输出"):
        st.header("汇总输出")
        cols = get_colleges()
        name_map = {get_college_display(c): c for c in cols}
        st.subheader("选择学院")
        select_all = st.checkbox("选择所有学院（去除演示账户）", value=True, key="export-select-all")
        selected_names = []
        for disp, code in name_map.items():
            if st.checkbox(disp, value=not select_all, key=f"export-col-{code}"):
                selected_names.append(disp)
        fmt = st.radio("格式", ["CSV", "Excel"], horizontal=True, key="export_fmt")
        def _to_excel(frames: dict[str, pd.DataFrame]):
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
                for name, frame in frames.items():
                    frame.to_excel(writer, index=False, sheet_name=name[:31])
            buf.seek(0)
            return buf
        if select_all:
            selected_codes = [code for disp, code in name_map.items() if ("演示" not in disp) and (code != "demo")]
        else:
            selected_codes = [name_map[n] for n in selected_names] if selected_names else cols
        if len(selected_codes) == 1:
            code = selected_codes[0]
            items = list_parsed_datasets(code)
            qa_frames = []
            ex_frames = []
            for it in items:
                df = load_csv(it["path"])
                if it["type"] == "qa":
                    qa_frames.append(df)
                else:
                    ex_frames.append(df)
            qa_df = pd.concat(qa_frames, ignore_index=True) if qa_frames else pd.DataFrame()
            ex_df = pd.concat(ex_frames, ignore_index=True) if ex_frames else pd.DataFrame()
            disp = get_college_display(code)
            if fmt == "CSV":
                st.download_button("下载该学院问答对 (CSV)", qa_df.to_csv(index=False).encode("utf-8"), file_name=f"{disp}_qa.csv")
                st.download_button("下载该学院习题 (CSV)", ex_df.to_csv(index=False).encode("utf-8"), file_name=f"{disp}_exercises.csv")
                if not ex_df.empty and "level" in ex_df.columns:
                    grad_df = ex_df[ex_df["level"].astype(str) == "研究生"]
                    st.download_button("下载该学院研究生习题 (CSV)", grad_df.to_csv(index=False).encode("utf-8"), file_name=f"{disp}_研究生_习题库.csv")
            else:
                sheets = {"问答对": qa_df}
                if not ex_df.empty and "type" in ex_df.columns:
                    for t, part in ex_df.groupby("type"):
                        sheets[str(t)] = part
                else:
                    sheets["习题库"] = ex_df
                buf = _to_excel(sheets)
                st.download_button("下载该学院汇总 (Excel)", buf.getvalue(), file_name=f"{disp}_汇总.xlsx")
        else:
            all_cols = selected_codes
            qa_frames = []
            ex_frames = []
            for c in all_cols:
                items = list_parsed_datasets(c)
                for it in items:
                    df = load_csv(it["path"])
                    if it["type"] == "qa":
                        df["college"] = get_college_display(c)
                        qa_frames.append(df)
                    else:
                        df["college"] = get_college_display(c)
                        ex_frames.append(df)
            qa_all = pd.concat(qa_frames, ignore_index=True) if qa_frames else pd.DataFrame()
            ex_all = pd.concat(ex_frames, ignore_index=True) if ex_frames else pd.DataFrame()
            if fmt == "CSV":
                st.download_button("下载所有学院问答对 (CSV)", qa_all.to_csv(index=False).encode("utf-8"), file_name="全部_问答对.csv")
                st.download_button("下载所有学院习题 (CSV)", ex_all.to_csv(index=False).encode("utf-8"), file_name="全部_习题库.csv")
                if not ex_all.empty and "level" in ex_all.columns:
                    grad_all = ex_all[ex_all["level"].astype(str) == "研究生"]
                    st.download_button("下载所有学院研究生习题 (CSV)", grad_all.to_csv(index=False).encode("utf-8"), file_name="全部_研究生_习题库.csv")
            else:
                sheets = {"问答对": qa_all}
                if not ex_all.empty and "type" in ex_all.columns:
                    for t, part in ex_all.groupby("type"):
                        sheets[str(t)] = part
                else:
                    sheets["习题库"] = ex_all
                buf = _to_excel(sheets)
                st.download_button("下载所有学院汇总 (Excel)", buf.getvalue(), file_name="全部_汇总.xlsx")
