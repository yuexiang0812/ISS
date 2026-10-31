"""Step 18 — reports (Markdown + Word), regenerated from the current outputs on every run.

中文说明：每次运行都从当前输出重新生成全部报告。报告中的数字全部来自数据（Code/report_values.py），不手写；
方法报告的叙述在模板 Code/docgen/methodology_template.md 中，叙述性结论会被自动核对（不被数据支持时报告顶部出现警告）。

Documentation/Methodology_and_Validation_Report.md      rendered from the template (do not edit by hand)
Documentation/Reports/
  01_Quality_Audit_Report.docx           all Step 16 checks, data-integrity facts, audit tables, open issues
  02_Process_Record.docx                 phases, decisions, errors found & fixes, review findings, runs, commits, environment
  03_Methodology_and_Validation_Report.docx   pandoc of the rendered Markdown
  04_Coding_Guidelines.docx              pandoc of Validation/CODING_GUIDELINES.md
  05_Project_README.docx                 pandoc of README.md
  06_User_Guide_CN.docx                  中文使用指南：流水线、数据集、三态标签、lb/ub、示例、结果、FAQ
  07_Review_and_Changes_<ver>.docx       review findings of this version and the version comparison
  08_Worked_Example_local.docx           one real firm-year traced from text to firm level (ISS text -> local only, git-ignored)
  Conversation_Archive_local.docx        working-session transcript (ISS excerpts, private links -> local only, git-ignored)
Requires node (docx package) and pandoc. Transcript path: env SESSION_TRANSCRIPT (optional).
"""
import json, os, re, subprocess, platform, glob
import numpy as np, pandas as pd
from config import PROJ, DOCS, LOGS, VALID, INTER, DICT, ANNUAL, CODE, CLASSIFIER_VERSION as VER, PREVIOUS_VERSION as PREV, get_logger
from report_values import collect, fill, narrative_block, md, num, pct, sh
from classify import classify_unit

log = get_logger("18_build_reports")
OUT = DOCS / "Reports"; OUT.mkdir(exist_ok=True)
GEN = CODE / "docgen" / "make_docx.js"
X = collect(); V = X.V
for c in X.checks:
    (log.info if c["ok"] else log.warning)(f"narrative check {'OK ' if c['ok'] else 'FAILED'}: {c['claim']}")
META = [["Classifier version", VER], ["Generated", V["generated"]], ["Git commit", V["commit"]],
        ["Validation status", V["validation_label"]], ["Project", "ESG_Text_Based_Incentives (ISS Incentive Lab 1998-2021)"]]


def render(spec, name):
    p = INTER / f"_spec_{name}.json"
    p.write_text(json.dumps(spec, ensure_ascii=False, allow_nan=False, default=str))
    r = subprocess.run(["node", str(GEN), str(p), str(OUT / name)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr)
    log.info(f"wrote {name}")


def tab(df, widths=None, size=16):
    df = df.astype(object).where(df.notna(), "")
    return dict(type="table", header=[str(c) for c in df.columns], rows=df.astype(str).values.tolist(), widths=widths, size=size)


def pandoc(src, name):
    r = subprocess.run(["pandoc", str(src), "-o", str(OUT / name), "--from", "gfm"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    log.info(f"wrote {name}")


warn_block = [] if all(c["ok"] for c in X.checks) else [dict(type="note", text="叙述核对未通过（报告中的部分结论不被当前数据支持）："
                                                              + "；".join(c["claim"] for c in X.checks if not c["ok"]))]

# ======================================================================= 03 methodology report (Markdown from template)
tmpl = (CODE / "docgen" / "methodology_template.md").read_text(encoding="utf-8")
mdtext = fill(tmpl, X)
(DOCS / "Methodology_and_Validation_Report.md").write_text(mdtext, encoding="utf-8")
log.info("rendered Documentation/Methodology_and_Validation_Report.md from template")
pandoc(DOCS / "Methodology_and_Validation_Report.md", "03_Methodology_and_Validation_Report.docx")
pandoc(VALID / "CODING_GUIDELINES.md", "04_Coding_Guidelines.docx")
pandoc(PROJ / "README.md", "05_Project_README.docx")

# ======================================================================= 01 quality audit report
Q = pd.read_csv(DOCS / "quality_audit_results.csv")
S = pd.read_csv(DOCS / "dataset_summary.csv")
cnt = Q.status.value_counts().to_dict()
EXPLAIN = [  # (pattern on check text, explanation) — explanations only; numbers come from the audit table
    (r"Unknown \(Strict\)", "未知（Unknown）单元主要是 Individual / Strategic / Discretionary 等占位描述，以及模糊词；所有比例同时给出 lb/ub 与覆盖率。"),
    (r"structured context", "metric 与 metricOther 均为空（或占位）的单元，仅当 metricType 为跨年一致的财务类别时判为 0；文本-only 标签另存为 Unknown。"),
    (r"human-reviewed", "尚无人工裁定标签：所有标签为暂定（Provisional）。"),
    (r"not matched to a grant|missing_in_grant", "少量目标记录所属 grantID 不在 Grants 表中：保留并列入审计表，未猜测匹配。"),
    (r"missing identifiers", "ISS 原始记录缺少标识符（CIK / 年 / 高管 ID）：保留并标记。"),
    (r"incomplete keys", "KPI 主键成分有缺失（来自上一项）：保留并标记 kpi_key_complete = 0。"),
    (r"expiration_date", "ISS 原始数据中到期日早于授予日：标记 grant_dates_inconsistent，不修改。"),
    (r"suspect", "授予日不在 [FY-3, FY+2] 内：标记 grant_date_suspect，不修改。"),
    (r"duplicated grantIDs", "重复 grantID 的 performancetype 互相矛盾，按目标数据裁定（grant_dup_resolved）。"),
    (r"value source", "价值来源：授予日公允价值；现金奖励无公允价值时用非股权目标支付额；两者都无则缺失。"),
    (r"identity match", "高管身份按 (CIK, FY, FM, participantID) 精确匹配；未匹配者保留并标记。"),
    (r"CEO identification", "CEO 识别状态（按 CEO-年行计）；多个 currentCEO 标记时保留全部候选人，不静默挑选。"),
    (r"unmatched_participant", "无法精确匹配 ParticipantFY 的 grant 列表。"),
    (r"ceo_exceptions", "多 CEO 标记、无 CEO、角色代码不明确的公司-年及候选人。"),
    (r"human validation", "独立人工验证尚未完成：不得报告分类准确率。"),
]
iw = Q[Q.status.isin(["INFO", "WARN"])].copy()
iw["explanation"] = iw.check.map(lambda c: next((e for p, e in EXPLAIN if re.search(p, c, re.I)), ""))
blocks = warn_block + [
    dict(type="h1", text="1. 审计结论 (Summary)"),
    dict(type="p", text=f"Step 16 重新读取最终 .dta 文件，独立执行 **{len(Q)}** 项检查：PASS {cnt.get('PASS', 0)}，FAIL {cnt.get('FAIL', 0)}，"
                        f"WARN {cnt.get('WARN', 0)}，INFO {cnt.get('INFO', 0)}。关键逻辑（Grant ESG、各层计数、采用指标、E/S/G 采用、lb 占比、"
                        "同一文本标签一致性、text_id 哈希）均从下层数据重新推导后与成品比对，而非直接复用构建步骤的结果。"),
    dict(type="note", text=("FAIL 项必须修正后才能使用数据。" if cnt.get("FAIL") else "没有 FAIL 项。") +
                           ("WARN 项与人工验证有关：在人工标注返回之前，所有 ESG 标签为暂定（Provisional），不得报告分类准确率。" if cnt.get("WARN") else "")),
    dict(type="h1", text="2. 数据集概况 (Dataset summary)"),
    tab(S.rename(columns={"observations": "obs", "variables": "vars"}), [2600, 1100, 800, 2400, 900, 900, 900, 900]),
    dict(type="h1", text="3. 全部检查结果 (All checks)"),
    tab(Q[["check_id", "dataset", "check", "status", "value"]].assign(value=Q.value.astype(str).str.slice(0, 120)), [800, 700, 4700, 800, 2600], 15),
    dict(type="h1", text="4. INFO / WARN 项解释"),
    dict(type="p", text="INFO = 需要使用者知道、但不是错误的事实（数值见表）；WARN = 需要注意的未完成事项。"),
    tab(iw[["check_id", "check", "status", "value", "explanation"]].assign(value=iw.value.astype(str).str.slice(0, 90)), [700, 2600, 600, 2100, 3600], 15),
    dict(type="h1", text="5. 数据完整性处理记录 (Data integrity)"),
    dict(type="bullets", items=[
        f"ISS 缺失值编码 -9999.xx / -99999 统一转为缺失：grantDateFV {V['n_fv_missing_code']} 个，nonEquityTarget {V['n_net_missing_code']} 个；"
        f"日期 01/01/9999 转为缺失：grantDate {V['n_grantdate_missing_code']} 个。",
        f"不可能取值设为缺失：负的 grantDateFV {V['n_neg_fv']} 个，负的 vestHighGrant {V['n_neg_vest']} 个。",
        f"重复 grantID：{V['n_dup_grant_ids']} 个（{V['n_dup_grant_rows']} 行），除 performancetype 外完全一致，按目标数据裁定类型。",
        f"目标记录匹配 grant：{V['goal_match_share']}（未匹配 {V['n_goal_unmatched']} 条，涉及 {V['n_goal_unmatched_grants']} 个 grantID）。",
        f"grant 匹配 ParticipantFY（四键精确）：{V['grant_pfy_match_share']}（未匹配 {V['n_grant_pfy_unmatched']} 个）。",
        f"目标数据不完整的 grant（申报目标数多于记录数）：{V['n_goal_incomplete']} 个，ESG 状态不记 0。",
        f"日期问题：授予日可疑 {V['n_date_suspect']} 个，到期日早于授予日 {V['n_date_inconsistent']} 个（均标记，未修改）。"]),
    dict(type="h1", text="6. 审计表 (Audit tables, Data/Intermediate)"),
    dict(type="table", header=["File", "Content"], widths=[3800, 5800], rows=[
        ["audit_goal_grants_missing_in_grant_table.csv", "目标记录引用但 Grants 表中不存在的 grantID"],
        ["audit_grants_unmatched_participant.csv", "无法在 ParticipantFY 中按 (CIK,FY,FM,pid) 精确匹配的 grant"],
        ["audit_ceo_exceptions.csv", "多 CEO 标记、无 CEO、角色代码不明确的公司-年及候选人"],
        [f"Validation/human_review_queue_{VER}_local.csv", "高频 Unknown / 规则冲突文本复核队列（非验证样本）"],
        ["Validation/e_top_disagreements_local.csv", "论文词典与修订分类器分歧最大的文本"],
        [f"Validation/version_changed_units_{PREV}_to_{VER}_local.csv", "相对上一版本标签发生变化的全部文本单元"]]),
    dict(type="h1", text="7. 未解决事项 (Open issues)"),
    dict(type="numbered", items=[x for x in [
        ("完成 601 单元独立人工标注与裁定，计算 Precision / Recall / F1 / kappa（流程见 04_Coding_Guidelines）。" if V["validation_label"] == "PROVISIONAL" else None),
        f"审核复核队列中的高频 Unknown（{V['n_review_queue']} 个单元），确认后作为人工标签写入并重跑 Step 06 起。",
        "Summary Compensation 文件缺少 participantID 列，无法与高管链接（如需，向数据提供方确认）。",
        "ESG 归属薪酬价值无法可靠测算（无可靠 KPI 权重），仅提供含 ESG 条件 grant 的价值占比（暴露度）。"] if x]),
]
render(dict(title="Quality Audit Report — ESG Text-Based Incentives", subtitle="质量审计报告（自动生成，随数据更新）",
            header="Quality Audit Report", meta=META, blocks=blocks), "01_Quality_Audit_Report.docx")

# ======================================================================= 02 process record
mr = (LOGS / "master_run.log").read_text() if (LOGS / "master_run.log").exists() else ""
steps = [[m.group(1), m.group(2)] for m in re.finditer(r"=== (\S+) done in (\d+)s", mr)]
gitlog = [l.split("|", 2) for l in sh("git log --date=iso --pretty=format:'%h|%ad|%s'").splitlines() if l.count("|") >= 2]
chg = pd.read_csv(DICT / "c_change_log.csv")
kw = pd.read_csv(DICT / f"b_paper_keyword_review_{VER}.csv").decision.value_counts().rename_axis("decision").reset_index(name="keywords")
fy = pd.read_csv(ANNUAL / "annual_firm_year.csv")
rf = pd.read_csv(DOCS / f"review_findings_{VER}.csv")
vers = {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__, "node": sh("node --version"),
        "pandoc": sh("pandoc --version | head -1"), "pdftotext": sh("pdftotext -v 2>&1 | head -1")}
PHASES = [
    ("阶段 0 — 下载与初步检查", [
        "用 requests 从 Dropbox 直链 (dl=1) 下载 ISS Incentive Lab 压缩包（18 个 .dta + User Guide），解压到独立目录，用 pandas 输出每个文件的行列数、类型、缺失率。",
        "下载论文 PDF 与任务书 docx，并通过文件签名 (%PDF / PK) 确认得到的是真实文件而非网页。",
        "压缩包中的 __MACOSX 元数据文件会导致读取报错，脚本改为自动跳过。"]),
    ("阶段 1 — 阅读与需求梳理", [
        "通读论文全文（第 3.2 节 ESG 识别方法、附录 A.1–A.6）与任务书（第 1–17 节），整理为需求清单与七个数据集的变量清单。",
        "读取 ISS User Guide：缺失值编码 -9999.xx、日期 01/01/9999、metricType 2018 年扩展（Market-related = 原 Stock Price）、periodID 含义、performanceType 取值、角色代码（UC = 分部 CEO）。"]),
    ("阶段 2 — 论文词典提取 (a)", [
        "用 pdftotext -layout 提取附录 A.3：得到 953 个唯一词，与论文声明一致；raw 模式会错排两端对齐行（产生虚假词 'CO2 coal-exit'），因此固定使用 layout 模式。",
        "记录页码与出处；印刷问题（women‚Äôs 乱码、multiculural 拼写）原样保留并注释；A.4 仅公开 3 个被删词，其余 78 个不补造。"]),
    ("阶段 3 — 数据结构核查", [
        "目标记录真实主键为 (source, grantId, goal_id, periodId)：absId / relId 跨 grant 复用。",
        "metric 中的 ESG 标签几乎只在 2018 年后出现 → 属 ISS 2018 改分类，仅作诊断；metricOther 空白率从 1998 年约 68% 降到 2020 年起 0%：文本可得性断点，如实报告 Unknown 而非填补。",
        f"Grants 表有 {V['n_dup_grant_ids']} 个 grantID 重复出现（{V['n_dup_grant_rows']} 行）。v1.0 只核对了 CIK/高管/年/月/奖励类型（一致）；"
        "v1.1 审查发现这些重复行的 performancetype 互相矛盾（见阶段 8）。ParticipantFY 在 (CIK,FY,FM,pid) 唯一，按四键精确匹配。",
        "Summary Compensation 文件缺少 participantID 列，无法与高管链接，未使用。"]),
    ("阶段 4 — 分类体系 v1.0 开发与冻结", [
        "对出现在数据中的论文关键词逐个审查其匹配文本；对 Unknown、Strict=1、Extended-only、模糊类按频次审查；随机抽查低频 Strict=1 与 Strict=0 文本；审查全部论文-修订分歧。",
        "三态判定：0 必须有正向非 ESG 证据，未匹配不等于 0；metric 与 metricOther 联合读取；2018 ESG 标签与 ISS ESG metricType 从不作为依据；"
        "两字段皆空时仅允许跨年一致的财务 metricType 作为结构化上下文，并保留文本-only 标签。",
        "规则冻结后才抽取验证样本（601 单元，32 层，之后永不重抽）。"]),
    ("阶段 5 — 数据集构建与检查", [
        "依次构建 A 文本字典、B KPI（及原始目标记录层）、C Grant、D 高管-年、E CEO-年（含例外表）、F 公司-年、G 非 CEO 公司-年；"
        "每步执行主键唯一性、计数恒等、[0,1] 范围、lb≤ub、采用/占比一致性断言，失败即停止。"]),
    ("阶段 6 — 比较、验证与年度分析", [
        "论文词典与修订分类器在同一单元与年份上比较（重叠矩阵、分歧类别、年度采用率）；生成编码手册、盲编码表与评分代码。",
        "年度分析：ISS 原分类 2018 年的跳升在统一文本分类下不存在；真实上升集中于 2020–2021 年，以广延边际与社会类为主。"]),
    ("阶段 7 — 可复现性、审计与归档 (v1.0)", [
        "用 master_run.py 从原始数据完整重跑；增加独立质量审计、Word 报告与审计归档包（含 SHA-256 清单）。"]),
    (f"阶段 8 — 全面复审与 {VER}", [
        f"对 v1.0 的规则、聚合、验证代码与文档做全面复审（逐条对照数据），形成 {V['n_findings']} 条发现（见第 5 节与 07 报告），全部在 {VER} 修正。",
        f"冻结 v1.0 全部成品为快照；{VER} 与 v1.0 逐层比较：{V['n_units_changed']} 个文本单元（{V['n_rows_changed']} 条目标记录）至少一个标签变化，每个变化单元均人工复核。",
        "开发中发现并修正的回归（未进入发布版本）：'work environment' 被环境规则误判、'placement' 匹配到 'replacement'、董事会治理表述变为 Unknown、'Diversityls)' 漏判、"
        "S 维度采用率因列名冲突等于 Strict 采用率（审计新增从 grant 重新推导 E/S/G 的检查后发现）。",
        "随后进行独立多角度代码审查（逐行、删除行为、跨文件、语言陷阱、适配器、复用、简化、效率、根因），确认的问题修正后完整重跑。",
        "报告改为全部自动生成：数字来自数据，叙述性结论自动核对。"]),
]
ERRORS = [
    ["pdftotext raw 模式错排", "两端对齐行词序错乱（'CO2 coal-exit'）", "改用 -layout；交叉核对两种提取结果"],
    ["页码归属偏移", "最后一个词被记到下一页", "按词起始页记录"],
    ["absId 非唯一", "断言失败", "主键改为 (source, grantId, goal_id, periodId)"],
    ["被消费片段用 '~' 填充", "'Regulatory Compliance' 被误判 Unknown", "改用 '_' 填充（单词字符）"],
    ["屏蔽短语不计证据", "'Safety and Soundness' 变为 Unknown", "新增 MASKN：屏蔽且计为非 ESG 证据"],
    ["财务标签下的限定词", "'Cashflow::Discretionary' 判为 Unknown", "财务标签 + ≤2 词限定词视为财务指标"],
    ["验证样本过小 (322)", "分组分析不足", "编码开始前重抽为 601（之后永不重抽）"],
    ["报告数字填错年份 (v1.0)", "手写数字与数据不一致", f"{VER}：报告全部自动生成"],
    ["latin-1 写出 Stata 字符串 (v1.0)", "418 个单元的非 ASCII 字符被破坏，text_id 哈希不一致", f"{VER}：UTF-8；审计核对 text_id = 哈希(text_key)"],
    ["S 维度采用率 = Strict 采用率 (开发中)", "辅助列名冲突 (_s1p)", "改名 + 断言 + 审计从 grant 重新推导 E/S/G"],
]
blocks = warn_block + [
    dict(type="h1", text="1. 项目目标与范围"),
    dict(type="p", text="以 Agarwal, Gómez, Hosseini & Jha (2025) 的 953 个 ESG 关键词为起点，构建 1998–2021 年统一、可追溯、可验证的文本 ESG 绩效指标识别体系，"
                        "并据此构建 KPI、Grant、高管、CEO、非 CEO 与公司-年七个 Stata 数据集。"),
    dict(type="h1", text="2. 全过程记录 (chronological)")]
for t, items in PHASES:
    blocks += [dict(type="h2", text=t), dict(type="bullets", items=items)]
blocks += [dict(type="h1", text="3. 关键方法决策 (decision log, c_change_log.csv)"),
           tab(chg, [700, 1100, 1700, 4300, 1800], 15),
           dict(type="h1", text="4. 发现的错误与修正 (errors found and fixed)"),
           dict(type="table", header=["问题", "表现", "修正"], rows=ERRORS, widths=[3000, 3000, 3600]),
           dict(type="h1", text=f"5. {VER} 审查发现 (review_findings_{VER}.csv)"),
           tab(rf[["finding_id", "area", "severity", "finding", "fix_in_v1.1" if "fix_in_v1.1" in rf.columns else rf.columns[5]]], [600, 1000, 800, 3900, 3300], 14),
           dict(type="h1", text="6. 论文关键词审查结论"), tab(kw, [7500, 2100]),
           dict(type="h1", text="7. 流水线步骤与最近一次完整运行"),
           dict(type="table", header=["step", "runtime (s)"], rows=steps or [["(no master_run.log)", ""]], widths=[7000, 2600]),
           dict(type="p", text="最近一次完整运行结果：" + ("完成（pipeline complete）" if "pipeline complete" in mr else "见 Logs/master_run.log")),
           dict(type="h1", text="8. 主要结果快照（公司-年，业绩型 grant，Strict 采用率）"),
           tab(fy[fy.fiscalyear.isin([1998, 2008, 2015, 2016, 2017, 2018, 2019, 2020, 2021])][
               ["fiscalyear", "n_units_with_perf_grants", "adopt_strict_lb", "adopt_strict_cc", "adopt_strict_ub", "iss_esg_adopt_diag"]].round(3)),
           dict(type="h1", text="9. 版本控制记录 (git log)"),
           dict(type="table", header=["commit", "date", "message"], rows=gitlog or [["", "", ""]], widths=[1000, 2600, 6000], size=15),
           dict(type="h1", text="10. 运行环境"),
           dict(type="table", header=["component", "version"], rows=[[k, v] for k, v in vers.items()], widths=[2600, 7000]),
           dict(type="note", text="完整对话存档见 Conversation_Archive_local.docx（仅本地，含 ISS 原文片段与私有下载链接，不推送到 GitHub）。")]
render(dict(title="Process Record — ESG Text-Based Incentives", subtitle="全过程记录（自动生成，随数据更新）", header="Process Record",
            meta=META, blocks=blocks), "02_Process_Record.docx")

# ======================================================================= 06 user guide (Chinese)
lab = lambda v: "未知" if v is None else str(int(v))
EX = [("Other", "Safety (TRIR)", ""), ("Other", "Reduce greenhouse gas emissions", ""), ("Other", "Diversity and inclusion", ""),
      ("Other", "Corporate governance", ""), ("Other", "Governance", ""), ("Other", "Safety and governance", ""), ("Other", "ESG goals", ""),
      ("Customer Satisfaction", "", ""), ("Other", "Customer engagement index", ""), ("Other", "Regulatory compliance", ""),
      ("Other", "Succession planning", ""), ("Other", "Energy efficiency", ""), ("Individual", "Individual performance", ""),
      ("EPS", "", ""), ("Cashflow", "Free", ""), ("", "", "Stock Price")]
ex_rows = []
for m, o, t in EX:
    r = classify_unit(m, o, t)
    ex_rows.append([m or "(空)", o or "(空)", t or "", lab(r["esg_strict"]), lab(r["esg_extended"]),
                    f"{lab(r['esg_e'])}/{lab(r['esg_s'])}/{lab(r['esg_g'])}", r["classification_reason"].split(" || ")[0][:70]])
DS = pd.read_csv(DOCS / "dataset_summary.csv").set_index("dataset")
dsrow = lambda f, unit, key, vars_: [f, unit, key, num(DS.loc[f, "observations"]), vars_]
fyv = pd.read_csv(ANNUAL / "annual_firm_year.csv").set_index("fiscalyear")
blocks = warn_block + [
    dict(type="h1", text="1. 一句话说明"),
    dict(type="p", text=f"本项目把 ISS Incentive Lab 1998–2021 年全部 {V['n_goal_records']} 条高管绩效目标记录的文字描述，用同一套、不随年份变化的规则判断"
                        "“是否是 ESG 指标”，再逐层汇总成 KPI、Grant、高管、CEO、非 CEO 和公司-年七个 Stata 数据集；每个数字都能追溯到原始文本和具体规则。"),
    dict(type="h1", text="2. 使用前必须知道的五件事"),
    dict(type="numbered", items=[
        "**三态标签**：每个 ESG 标签只有 1（是）、0（否）、.（未知）三种取值。0 需要明确的非 ESG 证据（如 EPS、Sales）；"
        "找不到 ESG 关键词本身**不等于 0**。分析时绝不能把 . 当作 0。",
        "**Strict 与 Extended**：Strict = 明确的环境（E）、社会（S）、治理（G）目标；Extended = Strict + 利益相关者类指标（客户满意度、产品/患者安全、服务可靠性等）。"
        "Strict = 1 一定 Extended = 1。",
        "**下界 lb / 上界 ub / 覆盖率**：未知的部分按 0 算得到下界 lb，按 1 算得到上界 ub；真实值一定在 [lb, ub] 之间。"
        "只有没有任何未知时，才给出“精确”比例。覆盖率 = 已判定部分 / 全部。",
        "**ISS 自带的 ESG 分类只做诊断**：ISS 2018 年改了分类体系（新增 Social / Environment / CSR 等），直接使用会制造 2018 年的人为跳升；"
        "本项目从不把它作为判断依据，只在 *_diag 变量里保留以便对比。",
        f"**验证状态**：{V['validation_cn']}"]),
    dict(type="h1", text="3. 数据从哪里来"),
    tab(X.F["inventory"], [3600, 3800, 2200]),
    dict(type="p", text="其余 ISS 文件（持股、董事薪酬、同行、持股要求、顾问等）与本构念无关，未使用。Summary Compensation 文件缺少 participantID，无法与高管链接。"),
    dict(type="h1", text="4. 流水线：19 个步骤"),
    dict(type="table", header=["步骤", "做什么", "主要输出"], widths=[2200, 4600, 2800], rows=[
        ["01 data_inventory", "清点 18 个原始文件：行列数、主键重复、缺失编码", "Documentation/data_inventory_*.csv"],
        ["02 extract_paper_dictionary", "从论文 PDF 附录 A.3 提取 953 个关键词（逐字、带页码）", "Dictionaries/a_*.csv"],
        ["03 goal_extraction", "合并绝对/相对/加速三类目标记录，统一主键，附加 grant 信息", "goal_records.parquet"],
        ["04 text_classification", "把文本归一化成“分类单元”，逐个用规则判定", "text_units_classified.parquet"],
        ["05 dictionary_deliverables", "规则表、论文关键词逐词审查、新增表达、修改记录", "Dictionaries/b_*, c_*"],
        ["06 dataset_A", "文本字典（可用人工裁定覆盖模型标签）", "ESG_Text_Dictionary.dta"],
        ["07 dataset_B", "KPI 层与原始目标记录层", "ESG_KPI_Master.dta 等"],
        ["08 dataset_C", "Grant 层：业绩型/时间型、ESG 三态、价值、数据完整性标记", "ESG_Grant_Master.dta"],
        ["09–11 datasets D–G", "高管-年、CEO-年、公司-年、非 CEO 公司-年汇总", "D/E/F/G .dta"],
        ["12 paper_vs_revised", "与论文关键词方法逐单元比较；复现论文表 1", "Validation/e_*.csv"],
        ["13 validation", "冻结的盲验证样本、编码表、评分（有人工标签时）", "Validation/*"],
        ["14 annual_trends", "年度趋势与 2018 年断点分析", "Annual_Analysis/*.csv"],
        ["15 variable_dictionary", "全部变量的定义、分子、分母、缺失含义", "variable_dictionary.csv"],
        ["16 quality_audit", "重新读取成品、独立重算并核对", "quality_audit_results.csv"],
        ["17 version_comparison", "与上一版本逐层比较；审查发现清单", "version_comparison_*, review_findings_*"],
        ["18 build_reports", "生成本指南及全部报告（数字自动来自数据）", "Documentation/Reports/*.docx"],
        ["19 build_audit_archive", "打包代码、日志、文档与 SHA-256 清单", "Audit_Archive/*.zip"]]),
    dict(type="p", text="运行方式：python Code/master_run.py（从头运行）；python Code/master_run.py 06（从第 06 步开始，例如加入人工标签后）。任何一步出错都会停止，不会静默跳过。"),
    dict(type="h1", text="5. 分类器如何工作"),
    dict(type="bullets", items=[
        "**分类单元**：metric（ISS 标准化标签）与 metricOther（描述文本）一起读；完全相同的文字在所有年份得到相同标签（时间一致性）。",
        f"**规则**：{V['n_rules']} 条正则规则按固定顺序执行，每条规则匹配到的文字会被“消费”，后面的规则不能再用它。顺序为：保护短语 → 屏蔽误报 → "
        "定向短语（如 product safety → Extended）→ Strict ESG → Extended → 模糊 → ESG 相邻排除 → 占位描述 → 非 ESG 财务/经营证据 → 填充词。",
        "**判定**：有 Strict 规则命中 → 1；否则有模糊或占位命中 → 未知；否则有明确非 ESG / 相邻 / 利益相关者证据 → 0；什么都没命中 → 未知。",
        "**E/S/G 维度**：命中某维度的具体规则 → 该维度 1；只出现 ESG / CSR / 可持续 等通用词，或该维度只有模糊词 → 该维度未知。",
        "所有规则、理由、版本修改都在 Dictionaries/b_revised_rules_*.csv；每个单元的命中规则与原因在数据集 A 的 rule_ids、classification_reason。"]),
    dict(type="p", text="下表由当前分类器实时计算（通用指标名称示例）："),
    dict(type="table", header=["metric", "metricOther", "metricType", "Strict", "Extended", "E/S/G", "命中规则（原因）"],
         widths=[1300, 2000, 900, 700, 800, 900, 3000], size=14, rows=ex_rows),
    dict(type="h1", text="6. 七个数据集"),
    dict(type="table", header=["文件", "一行是什么", "主键", "观测数", "最常用变量"], widths=[2400, 2000, 2000, 1000, 2200], size=15, rows=[
        dsrow("ESG_Text_Dictionary.dta", "A：一个分类单元（唯一文本）", "text_id", "esg_strict, esg_extended, esg_e/s/g, classification_reason"),
        dsrow("ESG_KPI_Master.dta", "B：一个 grant 中的一个指标", "kpi_id", "kpi_esg_strict, kpi_esg_extended"),
        dsrow("ESG_Goal_Record_Classification.dta", "B 附：原始目标记录（指标 × 考核期）", "goal_record_id", "esg_strict"),
        dsrow("ESG_Grant_Master.dta", "C：一个 grant（奖励）", "grantid", "grant_is_perf, grant_esg_strict, grant_esg_share_lb/ub"),
        dsrow("ESG_Executive_Firm_Year.dta", "D：高管-公司-年", "cik+fiscalyear+participantid", "exec_perf_esg_adopt_strict, exec_esg_perf_share_lb/ub"),
        dsrow("ESG_CEO_Firm_Year.dta", "E：CEO-公司-年", "cik+fiscalyear+participantid", "ceo_strict_sample, ceo_perf_esg_adopt_strict"),
        dsrow("ESG_Firm_Year_Master.dta", "F：公司-年（ISS 全部公司-年）", "cik+fiscalyear", "firm_perf_esg_adopt_strict, firm_esg_[e|s|g]_adopt"),
        dsrow("ESG_NonCEO_Firm_Year.dta", "G：非 CEO 高管汇总到公司-年", "cik+fiscalyear", "nonceo_perf_esg_adopt_strict")]),
    dict(type="p", text="合并方式：D、E 与 F 通过 (cik, fiscalyear) 合并；C 通过 (cik, fiscalyear, participantid) 汇总到 D；B 通过 grantid 汇总到 C；"
                        "B 通过 text_id 连接 A。每个变量的精确定义见 Documentation/variable_dictionary.csv。"),
    dict(type="h1", text="7. 如何读 lb / ub：一个虚构的例子"),
    dict(type="p", text="（以下公司与数字均为虚构，仅用于说明计算方法。）某 CEO 某年有 3 个业绩型 grant："),
    dict(type="table", header=["Grant", "包含的指标（KPI）", "各 KPI 的 Strict 标签", "Grant ESG"], widths=[1300, 3600, 2700, 2000], rows=[
        ["G1 年度现金奖金", "EPS；Safety (TRIR)", "0；1", "1（至少一个 KPI = 1）"],
        ["G2 业绩股 PSU", "Relative TSR", "0", "0（全部 KPI = 0）"],
        ["G3 年度现金奖金", "Revenue；Individual performance", "0；未知", "未知（没有 1，且有未知）"]]),
    dict(type="bullets", items=[
        "**采用（adopt）** = 1：只要有一个 grant = 1 就是 1。（若 G1 不存在，则 G2 = 0、G3 = 未知 → 采用 = 未知，**不是 0**。）",
        "**业绩型 grant 的 ESG 占比**：精确值不可得（G3 未知）。下界 lb = 1/3 = 33%（未知按 0）；上界 ub = 2/3 = 67%（未知按 1）；覆盖率 = 2/3。",
        "**KPI 占比**（单位内不重复的指标）：5 个指标中 1 个是 ESG、1 个未知 → lb = 20%，ub = 40%。",
        "**价值占比**：含 ESG 条件的 grant 的价值 / 有价值的 grant 的总价值——这是“暴露度”，**不是**归属于 ESG 的薪酬金额（ISS 无可靠的 KPI 权重）。"]),
    dict(type="h1", text="8. 主要结果（自动来自数据）"),
    dict(type="bullets", items=[
        f"业绩型 grant 的公司-年 Strict ESG 采用率（下界）：2017 年 {V['lb_2017']}，2018 年 {V['lb_2018']}，2020 年 {V['lb_2020']}，2021 年 {V['lb_2021']}。",
        f"ISS 原分类（诊断）：2017 年 {V['iss_2017']} → 2018 年 {V['iss_2018']}——这个跳升来自 ISS 改分类，统一文本分类下不存在。",
        f"持续存在的公司（2017 与 2018 都在样本中，{V['n_continuing']} 家）：{V['cont_2017']} → {V['cont_2018']}；样本进出不是原因。",
        V["margin_sentence"],
        f"ESG 条件主要出现在现金奖金计划中：2021 年含 ESG 现金奖励的公司-年占 {pct(pd.read_csv(ANNUAL / 'annual_cash_vs_equity_firm.csv').set_index('fiscalyear').loc[2021, 'adopt_cash_perf_lb'])}，"
        f"含 ESG 股权业绩奖励的占 {pct(pd.read_csv(ANNUAL / 'annual_cash_vs_equity_firm.csv').set_index('fiscalyear').loc[2021, 'adopt_equity_perf_lb'])}。",
        f"维度（2021 年下界）：E {pct(fyv.loc[2021, 'adopt_E_lb'])}，S {pct(fyv.loc[2021, 'adopt_S_lb'])}，G {pct(fyv.loc[2021, 'adopt_G_lb'])}；社会类（安全、多元化）是主体。"]),
    tab(X.F["annual_firm"], size=14),
    dict(type="h1", text=f"9. {VER} 相对 {PREV} 改了什么"),
    dict(type="p", text=f"全面复审形成 {V['n_findings']} 条发现（{V['n_findings_high']} 条高严重性），全部修正；{V['n_units_changed']} 个文本单元"
                        f"（{V['n_rows_changed']} 条目标记录）至少一个标签改变。每条发现的证据与修正见 07_Review_and_Changes_{VER}.docx。"),
    dict(type="h1", text="10. 人工验证怎么做"),
    dict(type="numbered", items=[
        f"两位编码员分别打开 Validation/validation_coding_sheet_{V['sample_version']}_coder1_local.csv 与 coder2（盲表：看不到模型标签）。",
        "按 Validation/CODING_GUIDELINES.md 对每个单元填写 human_esg_strict / extended / e / s / g，取值 1、0 或 U（无法判断）。",
        "分别另存为 Validation/human_labels/coder1_labels.csv、coder2_labels.csv（保留 sample_id 列）。",
        "运行 python Code/master_run.py 13：计算两位编码员一致性（kappa），并生成 adjudication_sheet_local.csv（一致的已预填）。",
        "裁定分歧后另存为 Validation/human_labels/adjudicated_labels.csv，运行 python Code/master_run.py 06：人工标签写入数据集，"
        "并计算精确率、召回率、F1（含分层权重与自助法置信区间）；所有报告自动更新。"]),
    dict(type="h1", text="11. 文件夹地图"),
    dict(type="table", header=["位置", "内容", "可否外传"], widths=[3200, 4800, 1600], rows=[
        ["Code/", "全部代码（按步骤编号）；docgen/ 为报告模板与 Word 生成器", "可以"],
        ["Dictionaries/", "论文词典 (a)、修订规则与逐词审查 (b)、修改记录 (c)；local/ 含 ISS 原文示例", "local/ 不可"],
        ["Data/Final/", "七个 Stata 数据集", "不可（ISS 授权数据）"],
        ["Data/Intermediate/", "中间 parquet 与审计表", "不可"],
        ["Annual_Analysis/", "年度趋势与 2018 断点分析表", "可以（仅汇总统计）"],
        ["Validation/", "验证样本 ID、编码手册、对比统计；*_local.csv 含原文", "*_local 不可"],
        ["Documentation/", "方法报告、变量字典、审计结果、审查发现、版本对比；Reports/ 为 Word 报告", "*_local.docx 不可"],
        ["Logs/", "每一步的运行日志", "可以"]]),
    dict(type="h1", text="12. 常见问题"),
    dict(type="bullets", items=[
        "**为什么不直接用 ISS 的 ESG 分类？** 它在 2018 年改变了定义，前后不可比，会制造人为的跳升；而且 2018 年前几乎没有 ESG 标签。",
        "**为什么未知这么多？** 年度奖金常写“Individual performance”“Strategic goals”之类，文字本身无法判断是否含 ESG。如实标为未知，并用 lb/ub 给出范围。",
        "**回归里用哪个变量？** 推荐 firm_perf_esg_adopt_strict（三态，缺失即未知），同时报告 firm_esg_perf_share_lb / _ub 与覆盖率；"
        "稳健性检验可用 Extended 版本、完整样本（*_esg_measurement_complete = 1）和现金/股权拆分。",
        "**能算出“ESG 相关薪酬金额”吗？** 不能可靠计算：ISS 的 percentVest 是按考核期的支付比例，并与 AND/OR 组合规则相互作用，KPI 权重不可观测；本项目不编造权重。",
        "**想换定义怎么办？** 数据集 A 中每个单元都有 esg_topics（命中的主题）与 adjacent_flags（被排除的相邻主题），可以按自己的边界重新汇总。",
        "**规则改了怎么办？** 修改 Code/esg_rules.py，升级 config.py 中的 CLASSIFIER_VERSION，在 c_change_log.csv 记录原因，从 04 步重跑；版本对比与全部报告会自动更新。"]),
]
render(dict(title="使用指南 — 文本 ESG 高管薪酬数据库", subtitle=f"User Guide (Chinese) — classifier {VER}；自动生成，数字随数据更新",
            header="User Guide (CN)", meta=META, blocks=blocks), "06_User_Guide_CN.docx")

# ======================================================================= 07 review findings and version comparison
tagv = f"{PREV}_to_{VER}"
TRp = DOCS / f"version_comparison_{tagv}_label_transitions.csv"
blocks = warn_block + [
    dict(type="h1", text="1. 为什么要出新版本"),
    dict(type="p", text=f"{PREV} 完成后，对全部任务要求、代码、规则与文档做了一次全面复审：逐条规则对照真实文本，逐个聚合公式对照定义，"
                        f"并检查验证代码、Stata 导出与文档中的每个数字。复审共形成 {V['n_findings']} 条发现，全部在 {VER} 修正；"
                        "随后又做了独立多角度代码审查，确认的问题同样修正。原则不变：同一套规则用于所有年份，不为消除 2018 年断点调整标准。"),
    dict(type="h1", text="2. 发现清单（每条：发现了什么、证据/影响、如何修正）"),
    tab(rf, [500, 800, 600, 2700, 2000, 2400, 700], 13),
    dict(type="h1", text="3. 标签变化（文本单元层面）"),
    dict(type="p", text=f"{V['n_units_changed']} 个分类单元（{V['n_rows_changed']} 条目标记录）至少一个标签改变。主要变化类型："),
    tab(X.F["change_types"], [5600, 1800, 2200], 14) if "change_types" in X.F else dict(type="p", text="(no comparison available)"),
]
if TRp.exists():
    tr = pd.read_csv(TRp)
    st_ = tr[tr.dimension == "esg_strict"].pivot_table(index="label_prev", columns="label_current", values="goal_rows", aggfunc="sum").fillna(0).astype(int)
    st_ = st_.reset_index().rename(columns={"label_prev": f"Strict {PREV} \\ {VER}"})
    blocks += [dict(type="p", text="Strict 标签迁移矩阵（按目标记录加权）："), tab(st_.astype(str))]
blocks += [dict(type="h1", text="4. 对主要结果的影响（公司-年，业绩型 grant，下界）"),
           tab(X.F["version_firm_compare"], size=14) if "version_firm_compare" in X.F else dict(type="p", text="(no comparison available)"),
           dict(type="p", text="价值占比变化主要来自 R16：现金奖励在 ISS 中没有授予日公允价值，v1.0 因此把大部分现金奖金排除在价值分母之外；"
                               "v1.1 对现金奖励使用非股权目标支付额。"),
           dict(type="h1", text="5. 如何核对"),
           dict(type="bullets", items=[
               f"每个变化单元（含原文）：Validation/version_changed_units_{tagv}_local.csv（仅本地）。",
               f"按变化类型汇总：Documentation/version_comparison_{tagv}_change_types.csv；迁移矩阵：…_label_transitions.csv；年度对比：…_firm_annual.csv。",
               f"规则级修改：Dictionaries/b_revised_rules_{VER}.csv 的 version_change 列；决策记录：Dictionaries/c_change_log.csv。",
               f"{PREV} 的全部成品保存在 Data/Intermediate/snapshot_{PREV}/，可随时复算对比。"])]
render(dict(title=f"Review Findings and Changes — {VER}", subtitle=f"版本复审与修改报告（{PREV} → {VER}；自动生成）",
            header=f"Review and Changes {VER}", meta=META, blocks=blocks), f"07_Review_and_Changes_{VER}.docx")

# ======================================================================= 08 worked example (local only: contains ISS text)
try:
    A = pd.read_parquet(INTER / "dataset_A.parquet", columns=["text_id", "text_original", "metric", "esg_strict", "esg_extended", "esg_e", "esg_s", "esg_g", "classification_reason"])
    B = pd.read_parquet(INTER / "dataset_B.parquet", columns=["kpi_id", "grantid", "goal_source", "text_id", "cik", "fiscalyear", "participantid", "kpi_esg_strict", "kpi_esg_extended"])
    C = pd.read_parquet(INTER / "dataset_C.parquet", columns=["grantid", "cik", "fiscalyear", "participantid", "grant_type", "performancetype", "grant_is_perf",
                                                            "grant_esg_strict", "grant_n_kpis", "grant_n_esg_kpis_strict", "grant_n_unknown_kpis", "grant_value_combined"])
    F = pd.read_parquet(INTER / "dataset_F.parquet")
    E = pd.read_parquet(INTER / "dataset_E.parquet", columns=["cik", "fiscalyear", "participantid", "ceo_name", "ceo_strict_sample"])
    # deterministic choice: 2020 firm-year with a CEO in the strict sample, >=1 Strict ESG perf grant, >=1 Unknown perf grant, fewest grants
    cand = F[(F.fiscalyear == 2020) & (F.firm_n_perf_esg_grants_strict > 0) & (F.firm_n_perf_unknown_grants > 0) & (F.firm_n_grants.between(4, 12))]
    cand = cand.merge(E[E.ceo_strict_sample == 1][["cik", "fiscalyear"]].drop_duplicates(), on=["cik", "fiscalyear"])
    pick = cand.sort_values(["firm_n_grants", "cik"]).iloc[0]
    ck, yr = pick.cik, pick.fiscalyear
    c = C[(C.cik == ck) & (C.fiscalyear == yr)].sort_values(["participantid", "grantid"])
    b = B[B.grantid.isin(c.grantid)].merge(A, on="text_id", how="left")
    ceo = E[(E.cik == ck) & (E.fiscalyear == yr)]
    fcols = ["firm_n_grants", "firm_n_perf_grants", "firm_n_perf_esg_grants_strict", "firm_n_perf_unknown_grants", "firm_perf_esg_adopt_strict",
             "firm_esg_perf_grant_share_strict", "firm_esg_perf_share_lb", "firm_esg_perf_share_ub", "firm_perf_classification_coverage",
             "firm_esg_e_adopt", "firm_esg_s_adopt", "firm_esg_g_adopt", "firm_n_kpis", "firm_esg_kpi_share_lb", "firm_esg_kpi_share_ub"]
    blocks = [
        dict(type="note", text="本文件含 ISS 授权原文，仅供本地审计，勿外传（已被 .gitignore 排除）。"),
        dict(type="h1", text=f"1. 选中的公司-年：{pick.company_name}（CIK {ck}），{int(yr)} 财年"),
        dict(type="p", text="选择规则（固定、可复现）：2020 年、CEO 在严格样本中、至少一个业绩型 grant 为 Strict ESG、至少一个业绩型 grant 为未知、grant 数 4–12，按 grant 数与 CIK 排序取第一个。"),
        dict(type="p", text="CEO：" + "; ".join(f"{r.ceo_name} (participantid {r.participantid})" for r in ceo.itertuples())),
        dict(type="h1", text="2. 文本单元 → KPI（数据集 A → B）"),
        tab(b[["grantid", "goal_source", "text_id", "metric", "text_original", "esg_strict", "esg_extended", "esg_e", "esg_s", "esg_g", "classification_reason"]]
            .assign(text_original=lambda d: d.text_original.astype(str).str.slice(0, 80), classification_reason=lambda d: d.classification_reason.astype(str).str.slice(0, 80)),
            [900, 500, 1000, 900, 2200, 450, 450, 400, 400, 400, 2000], 12),
        dict(type="h1", text="3. KPI → Grant（数据集 B → C）"),
        tab(c[["participantid", "grantid", "grant_type", "performancetype", "grant_is_perf", "grant_n_kpis", "grant_n_esg_kpis_strict", "grant_n_unknown_kpis",
               "grant_esg_strict", "grant_value_combined"]], size=13),
        dict(type="p", text="规则：grant ESG = 1 若至少一个 KPI = 1；= 0 若全部 KPI = 0（或无业绩条件的时间型 grant）；否则未知。"),
        dict(type="h1", text="4. Grant → 公司-年（数据集 C → F）"),
        tab(pd.DataFrame({"variable": fcols, "value": [pick[k] for k in fcols]}), [5000, 4600]),
        dict(type="p", text=f"核对：lb = ESG 业绩型 grant 数 / 业绩型 grant 数 = {int(pick.firm_n_perf_esg_grants_strict)} / {int(pick.firm_n_perf_grants)}；"
                            f"ub = (ESG + 未知) / 业绩型 = ({int(pick.firm_n_perf_esg_grants_strict)} + {int(pick.firm_n_perf_unknown_grants)}) / {int(pick.firm_n_perf_grants)}。")]
    render(dict(title=f"Worked Example (local) — {pick.company_name} {int(yr)}", subtitle="从原始文本到公司-年的逐层追溯（本地，勿外传）",
                header="Worked Example (local)", meta=META, blocks=blocks), "08_Worked_Example_local.docx")
except Exception as e:   # the example is an illustration; a failure must be visible but not hide the other reports
    log.warning(f"worked example skipped: {e!r}")

# ======================================================================= conversation archive (local only)
tp = os.environ.get("SESSION_TRANSCRIPT") or next(iter(sorted(glob.glob("/root/.claude/projects/*ISS*/*.jsonl"), key=os.path.getmtime, reverse=True)), None)
if tp and os.path.exists(tp):
    strip = lambda s: re.sub(r"<system-reminder>.*?</system-reminder>", "", s, flags=re.S).strip()
    blocks, n_user, n_asst, n_tool = [], 0, 0, 0
    for line in open(tp, encoding="utf-8"):
        d = json.loads(line)
        if d.get("type") not in ("user", "assistant") or d.get("isMeta"):
            continue
        ts = (d.get("timestamp") or "")[:19].replace("T", " ")
        cont = d.get("message", {}).get("content")
        parts = [{"type": "text", "text": cont}] if isinstance(cont, str) else (cont or [])
        for p in parts:
            if p.get("type") == "text" and strip(p.get("text", "")):
                txt = strip(p["text"])
                if d["type"] == "user":
                    if txt.startswith("[Request interrupted") or txt.startswith("Stop hook feedback") or "<task-notification>" in txt:
                        blocks.append(dict(type="note", text=f"{ts}  [system/harness] {txt[:300]}")); continue
                    n_user += 1; blocks += [dict(type="h2", text=f"用户 / User  ({ts})")]
                else:
                    n_asst += 1; blocks += [dict(type="h3", text=f"Claude  ({ts})")]
                for para in txt.split("\n"):
                    if para.strip():
                        blocks.append(dict(type="p", text=para))
            elif p.get("type") == "tool_use":
                n_tool += 1
                inp = p.get("input", {})
                desc = inp.get("description") or inp.get("file_path") or inp.get("subject") or inp.get("query") or inp.get("skill") or ""
                blocks.append(dict(type="p", text=f"[tool call] {p.get('name')}: {desc}", italic=True, color="7F7F7F", size=16))
    head = [dict(type="note", text="本存档包含本次工作会话中的全部用户消息与 Claude 回复正文，以及每一次工具调用（名称与说明）。工具输出未收录以控制篇幅，"
                                   "且其中含 ISS 授权数据；原始完整记录（JSONL）保存在审计归档包中。本文件含 ISS 原文片段及私有下载链接，仅供本地审计，勿外传。"),
            dict(type="table", header=["item", "count"], rows=[["user messages", n_user], ["assistant messages", n_asst], ["tool calls", n_tool],
                                                              ["source transcript", os.path.basename(tp)]], widths=[3000, 6600])]
    render(dict(title="Conversation Archive — ESG Text-Based Incentives", subtitle="对话存档（本地，勿外传）", header="Conversation Archive (local)",
                meta=META, blocks=head + blocks), "Conversation_Archive_local.docx")
else:
    log.info("no session transcript found -> conversation archive skipped")
