"""Step 17 — Word (.docx) reports, regenerated from current outputs on every run.

Documentation/Reports/
  01_Quality_Audit_Report.docx             all audit checks (Step 16), data-integrity counts, audit tables, open issues
  02_Process_Record.docx                   full process record: phases, decisions, errors found & fixes, runs, commits, environment
  03_Methodology_and_Validation_Report.docx  pandoc conversion of Documentation/Methodology_and_Validation_Report.md
  04_Coding_Guidelines.docx                pandoc conversion of Validation/CODING_GUIDELINES.md
  05_Project_README.docx                   pandoc conversion of README.md
  Conversation_Archive_local.docx          transcript of the working session (user + assistant messages, tool calls listed;
                                           tool outputs omitted). Contains ISS text excerpts and private download links ->
                                           git-ignored, kept for the user's audit only.
Requires node (docx package) and pandoc. Transcript path: env SESSION_TRANSCRIPT (optional).
"""
import json, os, re, subprocess, datetime as dt, platform, glob, pathlib
import pandas as pd
from config import PROJ, DOCS, LOGS, VALID, INTER, DICT, ANNUAL, CLASSIFIER_VERSION, get_logger

log = get_logger("17_build_reports")
OUT = DOCS / "Reports"; OUT.mkdir(exist_ok=True)
GEN = PROJ / "Code" / "docgen" / "make_docx.js"
NOW = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
REPO = PROJ.parent


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=REPO).stdout.strip()


def render(spec, name):
    p = INTER / f"_spec_{name}.json"
    p.write_text(json.dumps(spec, ensure_ascii=False, allow_nan=False, default=str))
    r = subprocess.run(["node", str(GEN), str(p), str(OUT / name)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr)
    log.info(f"wrote {name}")


def df_table(df, widths=None, size=16):
    return dict(type="table", header=[str(c) for c in df.columns], rows=df.astype(object).where(df.notna(), "").astype(str).values.tolist(), widths=widths, size=size)


def logline(fname, pattern):
    p = LOGS / fname
    if not p.exists():
        return ""
    for line in p.read_text().splitlines():
        if re.search(pattern, line):
            return line.split(" INFO ", 1)[-1]
    return ""


commit = sh("git rev-parse --short HEAD"); branch = sh("git rev-parse --abbrev-ref HEAD")
META = [["Classifier version", CLASSIFIER_VERSION], ["Generated", NOW], ["Git commit / branch", f"{commit} / {branch}"],
        ["Project", "ESG_Text_Based_Incentives (ISS Incentive Lab 1998-2021)"]]

# ======================================================================= 01 Quality audit report
Q = pd.read_csv(DOCS / "quality_audit_results.csv")
S = pd.read_csv(DOCS / "dataset_summary.csv")
cnt = Q.status.value_counts().to_dict()
blocks = [
    dict(type="h1", text="1. 审计结论 (Summary)"),
    dict(type="p", text=f"本报告由 Step 16 重新读取最终 .dta 文件独立生成，共执行 **{len(Q)}** 项检查："
                        f"PASS {cnt.get('PASS',0)}，FAIL {cnt.get('FAIL',0)}，WARN {cnt.get('WARN',0)}，INFO {cnt.get('INFO',0)}。"
                        "关键逻辑（Grant ESG、各层计数、采用指标聚合、同一文本标签一致性）均从下层数据重新推导后与成品比对，而非直接复用构建步骤的结果。"),
    dict(type="note", text="WARN 项均与人工验证有关：目前没有独立人工标注，所有 ESG 标签仍为暂定 (Provisional)，不得报告分类准确率。"
                           if cnt.get("WARN") else "No warnings."),
    dict(type="h1", text="2. 数据集概况 (Dataset summary)"),
    df_table(S.rename(columns={"observations": "obs", "variables": "vars"}), [2600, 1100, 800, 2400, 900, 900, 900, 900]),
    dict(type="h1", text="3. 全部检查结果 (All checks)"),
    df_table(Q[["check_id", "dataset", "check", "status", "value"]].assign(value=Q.value.str.slice(0, 120)), [800, 700, 4700, 800, 2600], 15),
    dict(type="h1", text="4. INFO / WARN 项解释"),
    dict(type="bullets", items=[
        "**Unknown 比例**：约 20% 的文本单元 Strict 标签为 Unknown，主要是 Individual / Strategic / Discretionary 等占位描述；所有占比均同时给出 lb/ub 与覆盖率。",
        "**结构化上下文**：metric 与 metricOther 同时为空的单元，仅在 metricType 为跨年一致的财务类别时判为 0；文本-only 标签保留为 Unknown（esg_strict_textonly）。",
        "**未匹配记录**：10 条目标记录所属的 3 个 grantID 不在 Grants 表中；117 个 grant 无法在 ParticipantFY 中精确匹配（见审计表）。均保留并标记，未做猜测匹配。",
        "**日期问题**：49 个 grant 到期日早于授予日（ISS 原始数据），256 个授予日不在 [FY-3, FY+2] 内，已标记 grant_date_suspect，未删除。",
        "**CEO 例外**：505 个公司-年存在多个 currentCEO=1（共 1,033 个候选 CEO 行），515 个公司-年无法识别 CEO；未静默挑选，见 audit_ceo_exceptions.csv。",
        "**人工验证**：601 个单元的盲编码样本已冻结（rules MD5 已记录），等待人工标注；标注返回后重跑 Step 06 起即可更新全部数据与本报告。"]),
    dict(type="h1", text="5. 数据完整性处理记录 (Data integrity)"),
    dict(type="bullets", items=[x for x in [
        logline("08_dataset_C_grant.log", "impossible values"), logline("08_dataset_C_grant.log", "grant dates outside"),
        logline("08_dataset_C_grant.log", "KPIs whose grant is absent"), logline("09_dataset_D_executive.log", "grants matched to ParticipantFY"),
        logline("03_goal_extraction.log", "grants table:"), logline("03_goal_extraction.log", "goal records matched"),
        logline("07_dataset_B_kpi.log", "reconciliation"), logline("11_dataset_F_G_firm.log", "reconciliation"),
        "ISS 缺失值编码 -9999.xx / -99999 与日期 01/01/9999 统一转为缺失（User Guide p.3）；不可能取值（负的公允价值、负的归属月数）设为缺失。"] if x]),
    dict(type="h1", text="6. 审计表 (Audit tables, Data/Intermediate)"),
    dict(type="table", header=["File", "Content"], widths=[3800, 5800], rows=[
        ["audit_goal_grants_missing_in_grant_table.csv", "目标记录引用但 Grants 表中不存在的 grantID"],
        ["audit_grants_unmatched_participant.csv", "无法在 ParticipantFY 中按 (CIK,FY,FM,pid) 精确匹配的 grant"],
        ["audit_ceo_exceptions.csv", "多 CEO 标记、无 CEO、角色代码不明确的公司-年及候选人"],
        ["Validation/human_review_queue_v1.0_local.csv", "高频 Unknown / 规则冲突文本复核队列（非验证样本）"],
        ["Validation/e_top_disagreements_local.csv", "论文词典与修订分类器分歧最大的文本"]]),
    dict(type="h1", text="7. 未解决事项 (Open issues)"),
    dict(type="numbered", items=["完成 601 单元独立人工标注与裁定，计算 Precision / Recall / F1 / kappa。",
                                 "审核复核队列中的高频 Unknown，发布 v1.1（版本号与修改记录同步更新）。",
                                 "Summary Compensation 文件缺少 participantID 列，无法与高管链接（如需，向数据提供方确认）。",
                                 "ESG 归属薪酬价值无法可靠测算（无可靠 KPI 权重），仅提供含 ESG 条件 grant 的价值占比。"]),
]
render(dict(title="Quality Audit Report — ESG Text-Based Incentives", subtitle="质量审计报告（自动生成，随数据更新）",
            header="Quality Audit Report", meta=META, blocks=blocks), "01_Quality_Audit_Report.docx")

# ======================================================================= 02 Process record
steps = []
mr = (LOGS / "master_run.log").read_text() if (LOGS / "master_run.log").exists() else ""
for m in re.finditer(r"=== (\S+) done in (\d+)s", mr):
    steps.append([m.group(1), m.group(2)])
gitlog = sh("git log --date=iso --pretty=format:'%h|%ad|%s'").splitlines()
rules = pd.read_csv(DICT / f"b_revised_rules_{CLASSIFIER_VERSION}.csv")
chg = pd.read_csv(DICT / "c_change_log.csv")
kw = pd.read_csv(DICT / f"b_paper_keyword_review_{CLASSIFIER_VERSION}.csv").decision_v1.value_counts().reset_index()
fy = pd.read_csv(ANNUAL / "annual_firm_year.csv")
vers = {"python": platform.python_version(), "pandas": pd.__version__, "node": sh("node --version"), "pandoc": sh("pandoc --version | head -1"),
        "pdftotext": sh("pdftotext -v 2>&1 | head -1")}
PHASES = [
    ("阶段 0 — 下载与初步检查", [
        "用 requests 从 Dropbox 直链 (dl=1) 下载 ISS Incentive Lab 压缩包（112 MB，18 个 .dta + User Guide），解压到独立目录，用 pandas 输出每个文件的行列数、类型、缺失率。",
        "下载论文 PDF 与任务书 docx，并通过文件签名 (%PDF / PK) 确认得到的是真实文件而非网页；PDF 与 CFR 官网版本 MD5 一致 (e50f74f6…)。",
        "发现压缩包中的 __MACOSX 元数据文件会导致读取报错，脚本改为自动跳过。"]),
    ("阶段 1 — 阅读与需求梳理", [
        "通读论文全文（正文第 3.2 节 ESG 识别方法、附录 A.1–A.6）与任务书（第 1–17 节），并在对话中整理为需求清单与七个数据集的变量清单。",
        "读取 ISS User Guide：缺失值编码 -9999.xx、日期 01/01/9999、metricType 2018 年扩展（Market-related = 原 Stock Price）、periodID 含义、performanceType 取值、角色代码（UC = 分部 CEO）。"]),
    ("阶段 2 — 论文词典提取 (a)", [
        "用 pdftotext -layout 提取附录 A.3：得到 953 个唯一词，与论文声明一致；raw 模式会错排两端对齐行（产生虚假词 'CO2 coal-exit'），因此固定使用 layout 模式。",
        "记录页码与出处；印刷问题（women‚Äôs 乱码、multiculural 拼写）原样保留并注释；A.4 仅公开 3 个被删词，其余 78 个不补造。"]),
    ("阶段 3 — 数据结构核查", [
        "确认目标记录真实主键为 (source, grantId, goal_id, periodId)：absId / relId 跨 grant 复用（absId 单独重复 191,919 次）。",
        "metric 中的 ESG 标签（Staff Health And Safety 等）几乎只在 2018 年后出现（2018 年前仅 58 行）→ 属 ISS 2018 改分类，仅作诊断。",
        "metricOther 空白率 1998 年 68% → 2018 年 3% → 2020 年起 0%：文本可得性断点，如实报告 Unknown 而非填补。",
        "Grants 表 144 个 grantID 重复（属性完全一致，可安全去重）；ParticipantFY 在 (CIK,FY,FM,pid) 唯一，按四键精确匹配 99.975%。",
        "Summary Compensation 文件缺少 participantID 列，无法与高管链接，未使用。"]),
    ("阶段 4 — 分类体系 v1.0 开发与冻结", [
        "对 402 个在数据中出现的论文关键词逐个审查其匹配文本；对 Unknown、Strict=1、Extended-only、模糊类按频次审查；随机抽查 150 个低频 Strict=1 与 300 个 Strict=0 文本；审查全部论文-修订分歧。",
        "设计三态判定：0 必须有正向非 ESG 证据，未匹配不等于 0；metric 与 metricOther 联合读取；2018 ESG 标签与 ISS ESG metricType 从不作为依据；两字段皆空时仅允许跨年一致的财务 metricType 作为结构化上下文，并保留文本-only 标签。",
        f"规则按优先级消费文本片段（屏蔽 → 定向短语 → Strict → Extended → 模糊 → 邻近排除 → 占位 → 非 ESG → 填充），共 {len(rules)} 条规则；冻结后才抽取验证样本。"]),
    ("阶段 5 — 数据集构建与检查", [
        "依次构建 A 文本字典、B KPI（及原始目标记录层）、C Grant、D 高管-年、E CEO-年（含例外表）、F 公司-年、G 非 CEO 公司-年；每步执行主键唯一性、计数恒等、[0,1] 范围、lb≤ub、采用/占比一致性断言，失败即停止。",
        "Stata 变量名上限 32 字符：超长首选名按固定规则缩写，映射写入变量字典。"]),
    ("阶段 6 — 比较、验证与年度分析", [
        "论文词典与 v1.0 在同一单元与年份上比较（重叠矩阵、分歧类别、年度采用率）；抽取 601 单元分层盲验证样本（32 层，种子 20261031），生成编码手册与评分代码。",
        "年度分析显示：ISS 原分类 2018 年跳升在统一文本分类下不存在；真实上升集中于 2020–2021 年，以广延边际与社会类为主。"]),
    ("阶段 7 — 可复现性、审计与归档", [
        "清空中间文件后用 master_run.py 从原始数据完整重跑，EXIT=0，结果与开发运行完全一致；增加 Step 16 独立质量审计、Step 17 Word 报告、Step 18 审计归档包（含 SHA-256 清单）。"]),
]
ERRORS = [
    ["pdftotext raw 模式错排", "两端对齐行词序错乱（'CO2 coal-exit'）", "改用 -layout；交叉核对两种提取结果"],
    ["页码归属偏移", "最后一个词被记到第 64 页", "按词起始页记录"],
    ["absId 非唯一", "断言失败", "主键改为 (source, grantId, goal_id, periodId)"],
    ["缺少 pyarrow", "parquet 写入失败", "安装 pyarrow"],
    ["正则替换补丁定位失败", "字符串定位异常", "逐项检查后重写补丁"],
    ["被消费片段用 '~' 填充", "'Regulatory Compliance' 被误判 Unknown", "改用 '_' 填充（单词字符）"],
    ["屏蔽短语不计证据", "'Safety and Soundness' 变为 Unknown", "新增 MASKN：屏蔽且计为非 ESG 证据"],
    ["财务标签下的限定词", "'Cashflow::Discretionary' 判为 Unknown", "财务标签 + ≤2 词占位视为限定词"],
    ["误报：inclusive of / Women viewers / scrubber securitization / NOV / Climate Solutions 等", "Strict 假阳性", "新增屏蔽规则（见修改记录 c）"],
    ["漏报：Retain key talent、EH&S、D&I、flaring 等", "Strict 假阴性", "新增规则（见 b_new_expressions）"],
    ["重跑时 text_id 重复合并", "列名冲突 text_id_x", "合并前删除旧列"],
    ["KPI / 高管合并列名冲突", "drop_duplicates 报错；ceo_name 重复", "合并前删除重复列"],
    ["验证样本过小 (322)", "分组分析不足", "编码开始前重抽为 601（之后永不重抽）"],
    ["报告数字填错年份", "2008 行、CEO 2017 数字错误", "从 CSV 重新生成并更正"],
]
blocks = [dict(type="h1", text="1. 项目目标与范围"),
          dict(type="p", text="以 Agarwal, Gómez, Hosseini & Jha (2025) 的 953 个 ESG 关键词为基准，构建 1998–2021 年统一、可追溯、可验证的文本 ESG 绩效指标识别体系，并据此构建 KPI、Grant、高管、CEO、非 CEO 与公司-年七个 Stata 数据集。"),
          dict(type="h1", text="2. 全过程记录 (chronological)")]
for t, items in PHASES:
    blocks += [dict(type="h2", text=t), dict(type="bullets", items=items)]
blocks += [dict(type="h1", text="3. 关键方法决策 (decision log, c_change_log.csv)"),
           df_table(chg, [700, 1100, 1700, 4300, 1800], 15),
           dict(type="h1", text="4. 发现的错误与修正 (errors found and fixed)"),
           dict(type="table", header=["问题", "表现", "修正"], rows=ERRORS, widths=[3000, 3000, 3600]),
           dict(type="h1", text="5. 论文关键词审查结论"), df_table(kw.rename(columns={"decision_v1": "decision", "count": "keywords"}), [7500, 2100]),
           dict(type="h1", text="6. 流水线步骤与最近一次完整运行"),
           dict(type="table", header=["step", "runtime (s)"], rows=steps or [["(no master_run.log)", ""]], widths=[7000, 2600]),
           dict(type="p", text="最近一次完整运行结果：" + ("EXIT=0（成功）" if "EXIT=0" in mr else "见 Logs/master_run.log")),
           dict(type="h1", text="7. 主要结果快照（公司-年，业绩型 grant，Strict 采用率下界）"),
           df_table(fy[fy.fiscalyear.isin([1998, 2008, 2015, 2016, 2017, 2018, 2019, 2020, 2021])][
               ["fiscalyear", "n_units_with_perf_grants", "adopt_strict_lb", "adopt_strict_cc", "adopt_strict_ub", "iss_esg_adopt_diag"]].round(3)),
           dict(type="h1", text="8. 版本控制记录 (git log)"),
           dict(type="table", header=["commit", "date", "message"], rows=[l.split("|", 2) for l in gitlog], widths=[1000, 2600, 6000], size=15),
           dict(type="h1", text="9. 运行环境"),
           dict(type="table", header=["component", "version"], rows=[[k, v] for k, v in vers.items()], widths=[2600, 7000]),
           dict(type="note", text="完整对话存档见 Conversation_Archive_local.docx（仅本地，含 ISS 原文片段与私有下载链接，不推送到 GitHub）。")]
render(dict(title="Process Record — ESG Text-Based Incentives", subtitle="全过程记录（自动生成，随数据更新）", header="Process Record",
            meta=META, blocks=blocks), "02_Process_Record.docx")

# ======================================================================= 03-05 pandoc conversions
for src, name in [(DOCS / "Methodology_and_Validation_Report.md", "03_Methodology_and_Validation_Report.docx"),
                  (VALID / "CODING_GUIDELINES.md", "04_Coding_Guidelines.docx"), (PROJ / "README.md", "05_Project_README.docx")]:
    r = subprocess.run(["pandoc", str(src), "-o", str(OUT / name), "--from", "gfm"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    log.info(f"wrote {name}")

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
        c = d.get("message", {}).get("content")
        parts = [{"type": "text", "text": c}] if isinstance(c, str) else (c or [])
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
    head = [dict(type="note", text="本存档包含本次工作会话中的全部用户消息与 Claude 回复正文，以及每一次工具调用（名称与说明）。工具输出（命令运行结果、文件内容）"
                                   "未收录以控制篇幅，且其中含 ISS 授权数据；原始完整记录（JSONL）保存在审计归档包中。本文件含 ISS 原文片段及私有下载链接，仅供本地审计，勿外传。"),
            dict(type="table", header=["item", "count"], rows=[["user messages", n_user], ["assistant messages", n_asst], ["tool calls", n_tool],
                                                              ["source transcript", os.path.basename(tp)]], widths=[3000, 6600])]
    render(dict(title="Conversation Archive — ESG Text-Based Incentives", subtitle="对话存档（本地，勿外传）", header="Conversation Archive (local)",
                meta=META, blocks=head + blocks), "Conversation_Archive_local.docx")
else:
    log.info("no session transcript found -> conversation archive skipped")
