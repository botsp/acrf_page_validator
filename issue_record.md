
28May2026T7:41PM
Issue1.RawTexts 应该是要存储从box抓取到的文本对吧？如果要是多个box，那采用|进行分隔，但要确保完整的box内容；可是你现在解析的结果是这样的

| Variable   | Pages     | PageCount | Category           | Flag                   | RawTexts                                                                 |
|------------|-----------|-----------|--------------------|------------------------|--------------------------------------------------------------------------|
| ACNDD      | 3         | 1         | standard_variable   | suffix_prefix_match    | ACNDD in SUPPAE...                                                       |
| ACNDNC     | 3         | 1         | standard_variable   | suffix_prefix_match    | ACNDNC in SUPPAE...                                                      |
| ACNDW      | 3         | 1         | standard_variable   | suffix_prefix_match    | ACNDW in SUPPAE...                                                       |
| ACNNA      | 3         | 1         | standard_variable   | suffix_prefix_match    | ACNNA in SUPPAE...                                                       |
| AE         | 2,3,4,17  | 4         | standard_variable   | suffix_prefix_match    | AE (Adverse Events) | General Cause of Death #1 AE (Adverse Events) DDSPID= DDORRE | AE and CM | Use... |
| AEACN      | 3         | 1         | standard_variable   | suffix_prefix_match    | If multiple values are selected AEACN=MULTIPLE...                        |
| AEDIS      | 3         | 1         | standard_variable   | suffix_prefix_match    | AEDIS in SUPPAE...                                                       |
| AEDISCDT   | 4         | 1         | standard_variable   | suffix_prefix_match    | AEDISCDT in SUPPAE...                                                     |
| AEENDTC    | 2         | 1         | standard_variable   | suffix_prefix_match    | AEENDTC...                                                               |


Issue2.RawTexts 只存储box里的内容，不要抓取box以外的内容，你看目前的结果就不对

| Variable  | Pages | PageCount | Category         | Flag                | RawTexts                                                                 |
|-----------|-------|-----------|------------------|---------------------|--------------------------------------------------------------------------|
| AEPTRTPT  | 2     | 1         | standard_variable | suffix_prefix_match | Did this event occur prior to the first dose of study treatment? AEPTRTPT in SUPPAE | AEPTRTPT in SU... |
| AEREL     | 2     | 1         | standard_variable | suffix_prefix_match | y AEREL...                                                               |
| AERELPR   | 2     | 1         | standard_variable | suffix_prefix_match | Relationship to Study Procedure AERELPR in SUPPAE | AERELPR in SUPPAE... |

29May2026T11：43AM
Issue3. 现在RawTexts似乎是按照字母分隔的，示例如下，这更不对。

| Variable | Pages       | PageCount | Category          | Flag                | RawTexts                                                                 |
|---------:|-------------|----------:|-------------------|---------------------|-------------------------------------------------------------------------|
| ACNDD    | 3           | 1         | standard_variable | suffix_prefix_match | A | C | N | D | D | | i | n | | S | U | P | P | A | E...   |
| ACNDNC   | 3           | 1         | standard_variable | suffix_prefix_match | A | C | N | D | N | C | | i | n | | S | U | P | P | A | E... |
| ACNDW    | 3           | 1         | standard_variable | suffix_prefix_match | A | C | N | D | W | | i | n | | S | U | P | P | A | E...   |
| ACNNA    | 3           | 1         | standard_variable | suffix_prefix_match | A | C | N | N | A | | i | n | | S | U | P | P | A | E...   |
| AE       | 2,3,4,17    | 4         | standard_variable | suffix_prefix_match | A | E | | ( | A | d | v | e | r | s | e | | E | v | e | n | t | s | ) | | | | | U | s | e ... |

Issue4. 上述问题已纠正，现在RawTexts似乎好些了，示例如下；为什么有三个dot ..., 我觉得从box抓到哪些文本，就原样展示即可，只有对应多个box时，考虑|分隔连接，但也要是全部完整的文本

| Variable  | Pages          | PageCount | Category          | Flag               | RawTexts |
|----------:|----------------|----------:|-------------------|--------------------|---------|
| CMSCAT    | 112,113        | 2         | standard_variable | suffix_prefix_match | CMSCAT... |
| CMSTDTC   | 17,101,111     | 3         | standard_variable | suffix_prefix_match | CMSTDTC... |
| CMSTTRPT  | 17,111         | 2         | standard_variable | suffix_prefix_match | CMSTTRPT... |
| CMSTTPT   | 17,111         | 2         | standard_variable | suffix_prefix_match | CMSTTPT=First Vaccination... |
| CMTRT     | 12,96,114,115  | 4         | standard_variable | suffix_prefix_match | CMTRT... |
| COHORT    | 20             | 1         | standard_variable | suffix_prefix_match | COHORT in SUPPDM... |
| CONSENT   | 19,20          | 2         | standard_variable | suffix_prefix_match | DSDECOD=INFORMED CONSENT OBTAINED | DSSTDTC when DSSTERM=INFORMED CONSENT OBTAINED | DSSTDTC when D... |
| CRITERIA  | 93,94          | 2         | standard_variable | suffix_prefix_match | IEORRES f Inclusion Criteria then IEORRES=N f Exclusion Criteria then IEORRES=Y... |
| DD        | 4              | 1         | standard_variable | suffix_prefix_match | DD (Death Details)... |
| DDORRES   | 4              | 1         | standard_variable | suffix_prefix_match | DDORRES when DDTESTCD=GENCDTH | DDORRES when DDTESTCD=AUTOPIND | DDORRES when DDTESTCD=DTHCOIND... |
| DDSPID    | 4              | 1         | standard_variable | suffix_prefix_match | DDSPID=1 | DDSPID=2 | DDSPID=3... |


Issue5. 一个NOT SUBMITTED只占据一行，然后把出现的page汇总即可，只要确保即使一页出现两次、也要相应汇总两次page，不要去重即可；现在是每页占据一行；
但也不一定，你可以先从整个tool features考虑下，怎样display合理

| Variable       | Pages | PageCount | Category      | Flag | RawTexts |
|---------------|------:|----------:|--------------|------|---------|
| NOT SUBMITTED | 1     | 1         | not_submitted |      |         |
| NOT SUBMITTED | 3     | 1         | not_submitted |      |         |
| NOT SUBMITTED | 4     | 1         | not_submitted |      |         |
| NOT SUBMITTED | 5     | 1         | not_submitted |      |         |
| NOT SUBMITTED | 6     | 1         | not_submitted |      |         |
| NOT SUBMITTED | 7     | 1         | not_submitted |      |         |
| NOT SUBMITTED | 8     | 1         | not_submitted |      |         |
| NOT SUBMITTED | 9     | 1         | not_submitted |      |         |
| NOT SUBMITTED | 10    | 1         | not_submitted |      |         |
| NOT SUBMITTED | 11    | 1         | not_submitted |      |         |
| NOT SUBMITTED | 18    | 1         | not_submitted |      |         |
| NOT SUBMITTED | 88    | 1         | not_submitted |      |         |
| NOT SUBMITTED | 90    | 1         | not_submitted |      |         |
| NOT SUBMITTED | 91    | 1         | not_submitted |      |         |
| NOT SUBMITTED | 92    | 1         | not_submitted |      |         |
| NOT SUBMITTED | 101   | 1         | not_submitted |      |         |
| NOT SUBMITTED | 102   | 1         | not_submitted |      |         |
| NOT SUBMITTED | 105   | 1         | not_submitted |      |         |
| NOT SUBMITTED | 108   | 1         | not_submitted |      |         |
| NOT SUBMITTED | 109   | 1         | not_submitted |      |         |
| NOT SUBMITTED | 110   | 1         | not_submitted |      |         |
| NOT SUBMITTED | 118   | 1         | not_submitted |      |         |
| NOT SUBMITTED | 119   | 1         | not_submitted |      |         |
| NOT SUBMITTED | 120   | 1         | not_submitted |      |         |
| NOT SUBMITTED | 121   | 1         | not_submitted |      |         |

Issue6.
1.Rowtextss存在`( ) FAOBJ=ASTHENIA`, 前面的()是不是虚线box导致的？现在是怎样处理实线、虚线box的，有区分吗；
2.为什么仍有..., `FAOBJ=PAIN ...`
3.`( y ) FAORRES when FATESTCD=REL | ( y g ) FAORRES when FATESTCD=RELPR`,( y ) ,( y g )从哪来的？

| Variable  | Pages                                                                                                                                                           | PageCount | Category          | Flag                | RawTexts |
|----------|------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------:|-------------------|---------------------|---------|
| FADTC    | 21,22,24,26,27,29,31,32,34,36,37,39,41,42,45,46,47,49,50,51,53,54,55,57,58,59,61,62,65,66,67,68,69,71,72,73,74,75,102,105,108,109                       | 42        | standard_variable | suffix_prefix_match | FADTC | : FADTC |
| FALOC    | 102,105                                                                                                                                                          | 2         | standard_variable | suffix_prefix_match | FALOC |
| FAOBJ    | 21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,102,103,104,105,106,108,109 | 73        | standard_variable | suffix_prefix_match | FAOBJ=HEADACHE | ( ) FAOBJ=ASTHENIA | FAOBJ=MALAISE | FAOBJ=MYALGIA | FAOBJ=ASTHENIA | Headache FAOBJ=HEADACHE | FAOBJ=IRRITABILITY/ FUSSINESS | FAOBJ=DROWSINESS | FAOBJ=LOSS OF APPETITE | FAOBJ=PAIN ... |
| FAORRES  | 21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,102,103,104,105,106,107,108,109 | 74        | standard_variable | suffix_prefix_match | FAORRES when FATESTCD=SEV | FAORRES when FATESTCD=OCCUR | FAORRES when FATESTCD=REL | FAORRES when FATESTCD=RELPR | ( y ) FAORRES when FATESTCD=REL | ( y g ) FAORRES when FATESTCD=RELPR | ( ) FAORRES ... |
| FAORRESU | 102,105                                                                                                                                                          | 2         | standard_variable | suffix_prefix_match | FAORRESU |

Issue7.
7.1.standard_term_suffix_prefix.csv Column value，这只是一个问题，确认下，你再匹配prefix的时候，理解'--是'--AGENT 的prefix占位符吗

| variable | value     |
|----------|-----------|
| variable | '--AGENT  |
| variable | '--ANMETH |
| variable | '--ANTREG |
| variable | '--BDAGNT |
| variable | '--BDSYCD |
| variable | '--BEATNO |

7.2.关于issue6，多数得到了纠正，但仍存在下面这种情况`(x FAORRES when FATESTCD=LDIAM` ，先检查原因，按说不应该是全部都能改到吗
| Variable | Pages                                                                                                                               | PageCount | Category          | Flag                | RawTexts |
|---------|--------------------------------------------------------------------------------------------------------------------------------------|----------:|-------------------|---------------------|---------|
| FAORRES | 21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,102,103,104,105,106,107,108,109 | 74        | standard_variable | suffix_prefix_match | FAORRES when FATESTCD=SEV | FAORRES when FATESTCD=OCCUR | FAORRES when FATESTCD=REL | FAORRES when FATESTCD=RELPR | FAORRES when FATESTCD=LDIAM | (x FAORRES when FATESTCD=LDIAM | ( FAORRES when FATEST... |

7.3. 我希望能把domain annotation单独区分出来，它们的的特征之一是standard_term.csv 有对应标记为`dataset`, 但缺点是standard_term.csv 可能无法覆盖所有的domain name，另一个特征是domain annotation通常是DM (Demographics) 这种形式，如果你了解cdisc sdtm background knowledge，你应该明白我的意思；
然后在提取结果上分两类，一类是domain annotation的汇总，用来表示domain都出现在哪些page；另一类就是我们前面关于variable的整理。

| Variable | Pages | PageCount | Category          | Flag                | RawTexts            |
|---------|-------|----------:|-------------------|---------------------|---------------------|
| DM      | 19,20 | 2         | standard_variable | suffix_prefix_match | DM (Demographics)   |

Issue8.
1.这次仍存在issue 7.2的问题，示例如下

| Variable | Pages                                                                                                                               | PageCount | Category          | Flag                | RawTexts |
|---------|--------------------------------------------------------------------------------------------------------------------------------------|----------:|-------------------|---------------------|---------|
| FAORRES | 21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,102,103,104,105,106,107,108,109 | 74        | standard_variable | suffix_prefix_match | FAORRES when FATESTCD=SEV | FAORRES when FATESTCD=OCCUR | FAORRES when FATESTCD=REL | FAORRES when FATESTCD=RELPR | FAORRES when FATESTCD=LDIAM | (x FAORRES when FATESTCD=LDIAM | ( FAORRES when FATESTCD=LDIAM | FAORRES when FATESTCD=TEMP |

2.issue 7.3我并没有在streamlit web page看到有对应的更新变化;
关于分类后怎样display，我觉得加一列，表示它是domain还是variable，至于NOT submitted，就给空，不区分；

| classification|Annotattion | Pages | PageCount | Category          | Flag                | RawTexts            |
| Domain|Annotattion | Pages | PageCount | Category          | Flag                | RawTexts            |
| Variable|Annotattion | Pages | PageCount | Category          | Flag                | RawTexts            |


3.C:\dev\acrf_page_validator\config\acf.pdf 我放在这里了，希望 对你完善解析正则表达式有帮助，但担心过度消耗你的token

Issue9.
1.仍然存在这个问题`(x FAORRES when FATESTCD=LDIAM | ( FAORRES when FATESTCD=LDIAM`, 另外，我想知道为什么这个Rawtexts只有这些box，我原本想着每个box都放出来，即使内容重复
| Variable | Pages                             | PageCount | Category          | Flag                | RawTexts |
|---------|-----------------------------------|----------:|-------------------|---------------------|---------|
| LDIAM   | 65,66,67,68,69,70,71,72,73,74,75,76,108,109 | 14        | standard_variable | suffix_prefix_match | FAORRES when FATESTCD=LDIAM | (x FAORRES when FATESTCD=LDIAM | ( FAORRES when FATESTCD=LDIAM |

2.DOMAIN相关的分类不对，NOT SUBMITTED不区分Classification，应该是空的
| Classification | Name | Pages    | PageCount | Category          | Flag                | RawTexts                                   |
|----------------|------|----------|----------:|-------------------|---------------------|--------------------------------------------|
| Variable       | DM   | 19,20    | 2         | standard_variable | suffix_prefix_match | DM (Demographics)                          |
| Variable       | AE   | 2,3,4,17 | 4         | standard_variable | suffix_prefix_match | AE (Adverse Events) \| Used for RELREC of AE and CM |

3.回答我，目前的代码，Category，Flag的处理机制是怎样的
classify_term 按优先级判定：黑名单 → NOT SUBMITTED → exact match (standard_terms) → suffix/prefix match → SUPP pattern → unknown。
Flag 值表示匹配来源（exact_match, suffix_prefix_match, supp_match, potential_nonstandard）。在聚合时，
代码用一个 priority 表（exact=3,suffix=2,supp=1,unknown=0）来保留最高优先级的 category/flag。

Issue10.
1.为什么这里提取出AND, 我理解这是一段文本，实际上是没有真的SDTM variable，但好奇你为什么提取出来AND，还标记了standard_variable

| Classification | Name | Pages | PageCount | Category | MatchLevel | RawTexts |
| Variable | AND | 18 | 1 | standard_variable | suffix_prefix | Note: The information would be included in SVUPDES if type of Visit equals "Unscheduled". And if multiple are selected, concatenate with the annotated values with ";" |


2.我突然觉得这两列都没意义， Category | MatchLevel ，也许我只要知道无法从given term里匹配到、以完善csv即可，对吧？你从整个项目feature的角度评估下


Issue11.
1.NOT SUBMITTED对应的Classification，不应该是variable，直接标记NOT SUBMITTED;
2.做下排序，按照Classification，Domain->Variable->Not submitted排序
3.RELREC被标记为variable了，但实际上它是Domain，我理解可能的原因是，把row text all upper case的字段识别为变量了；如果是这个原因的话，我希望加一个判断，优先匹配dataset name，然后再标记variable

Issue12.
1.annotation里并不是全部的大写都是潜在变量或者domain/dataset，比如下面这三个，--TESTCD=, DSDECOD=,DSTERM=,但我无法列举全部的情况，但我比较有把握应该这样去判断：即等号后紧跟的大写字段，通常是variable value，不是variable name
if Y then DSDECOD/DSTERM=ENTERED INTO TRIAL
if No then VSSTAT=NOT DONE when VSTESTCD=VSALL
VSORRES when VSTESTCD=HEIGHT
new feature: 把variable value一起提取出来：DSDECOD=ENTERED INTO TRIAL，DSTERM=ENTERED INTO TRIAL, VSTESTCD=VSALL,VSTESTCD=HEIGHT
2.前面issue11.3(3.RELREC被标记为variable了，但实际上它是Domain，我理解可能的原因是，把row text all upper case的字段识别为变量了；如果是这个原因的话，我希望加一个判断，优先匹配dataset name，然后再标记variable)
这个问题并没有解决。
| Classification | Name   | Pages | PageCount | Category            | RawTexts                                       |
|----------------|--------|-------|-----------|---------------------|------------------------------------------------|
| Variable       | RELREC | 17    | 1         | standard_variable   | Used for RELREC of AE \| Used for RELREC of MH and CM |



Issue13.
接下来，我在想是不是要先把PyMuPDF 的结构去和xml结果进行compare，确保compare功能基本满足需求后再开发OpenCV + OCR 模块；还是现在就开发OpenCV + OCR 模块，你觉得哪个开发流程更好；
基于我整体的feature goal&blueprint

更好的流程是：先把 PyMuPDF ↔ XML 的 compare 主链路做稳，再开发 OpenCV+OCR。

基于你现在的 goal（结果可解释、可补 CSV、分类稳定、可导出），先把 compare 的输入/输出结构、判定规则、报告格式固定下来，能先把“业务正确性”闭环；否则现在同时上 OCR，会把误差来源混在一起（解析问题 vs compare 规则问题），调试成本会明显变高。

建议顺序就是两步：1) 定义并稳定 compare contract（字段、分类、差异类型、排序/导出） → 2) 让 OpenCV+OCR 作为第二个 parser 接入同一 contract，这样后续只是“替换输入源”，不是重写比较逻辑。

Issue 14. compare

建议的 compare 思路（先定 contract，不改代码逻辑）：

L1 基础变量层：只比 Variable（不含 =、不含复合语法），目标是“业务主字段覆盖率”。
L2 条件语义层：把两边都标准化为谓词结构再比：target_var + qualifier_var + operator + value。
例如把 XML 的 DDORRES.DD.DDTESTCD.EQ.AUTOPIND 映射为 (DDORRES, DDTESTCD, EQ, AUTOPIND)
与 PyMuPDF 的 DDTESTCD=AUTOPIND、DDORRES when DDTESTCD=AUTOPIND 对齐。
统一 key 规则（contract 核心）：
entity_type: domain | variable | predicate | not_submitted
compare_key: 稳定主键（大写、去冗余空白、换行折叠）
pages: 整数列表（内部排序去重）
source: xml | pymupdf
差异类型固定（报告稳定）：
missing_in_pdf / extra_in_pdf
page_mismatch（同 key 但页码集合不同）
format_only_diff（仅写法差异，语义等价）
low_confidence_parse（无法可靠归一化）
报告输出建议：
Summary：L1/L2 各自 precision/recall 风格计数
Detail：一行一个 compare_key，含 xml_pages / pdf_pages / diff_type / evidence
CSV 至少三份：summary.csv、diffs_l1.csv、diffs_l2.csv

1.我希望以define解析的结果和格式为准，目前就这样不再改了，试着让 PyMuPDF 的格式向define解析靠拢；
2.整体上还是比较variable为主，define有解析出每个variable对应的domain/dataset name，但是PyMuPDF无法解析到variable对应的domain这个element；
3.其次，当然要检查一个variable在两份解析里都出现、且解析出的pages是一样的，比如两边都能确定解析到9，10，11三页；


case1:xml的结果对应到PyMuPDF是DDORRES，DDTESTCD两条，但这种就认为是两侧一致匹配了；
xml parse
| Dataset | 	Variable        | 	ACRF Pages | PageCount |
|----------------|------------------------------------|-------|-----------|
| DD             | DDORRES.DD.DDTESTCD.EQ.AUTOPIND     | 4     | 1         |

PyMuPDF parse

| Classification | Name        | Pages | PageCount | Category            | RawTexts                                                                 |
|----------------|-------------|-------|-----------|---------------------|--------------------------------------------------------------------------|
| Variable       | DDORRES     | 4     | 1         | standard_variable   | DDORRES when DDTESTCD=GENCDTH \| DDORRES when DDTESTCD=AUTOPIND \| DDORRES when DDTESTCD=DTHCOIND |
| Variable       | DDTESTCD=AUTOPIND | 4 | 1 | standard_variable | DDTESTCD=AUTOPIND |


case2:这种情况也认为是两侧一致匹配了；
xml parse
| Dataset | 	Variable        | 	ACRF Pages | PageCount |
|----------------|------------------------------------|-------|-----------|
| VS             | VSORRES.VS.VSTESTCD.EQ.HEIGHT     | 119     | 1         |

PyMuPDF parse
| Classification | Name              | Pages | PageCount | Category          | RawTexts           |
|----------------|-------------------|-------|-----------|-------------------|--------------------|
| Variable       | VSTESTCD=HEIGHT   | 119   | 1         | standard_variable | VSTESTCD=HEIGHT    |


补充1：
a.define解析的结果和格式为准, 但是如果某个变量只在PyMuPDF解析的有，那也应该标记出来的；
b.对于define解析结果IEORRES.IE.IETESTCD.EQ.I03V020，它有一个固定的规律IEORRES is variable name;IE is domain name;IETESTCD is variable name;EQ means equal;I03V020 is value of variable IETESTCD.





Issue/question 15.
1.SUPPVS.QNAM = "VSCOLSRT" /QNAM = "VSSSCAT" 居然没有从xml parse解析出来，你可以先读example_xml_export.md确认下，
然后分析下原因，不着急改代码，按说xml是正则解析，应该很准确吧？
-->那这类问题是可接受的，只提取xml有page element的，然后用pdf的用最大限度比较，这样的feature design也合理

2.COMPOUND_RESOLVED relation: exact path: path_A_target_var，MATCH relation: exact path: simple，
PAGE_MISMATCH relation: pdf_superset path: path_A_target_var 什么意思；能否整理一个说明书，每个结果element都是什么意思，你可以写出一个md file保留下

3.为什么下面这里有些对应着FAORRES,有些则是FATESTCD=REL，为什么有这种差别
| Classification | Name | Pages | PageCount | Category | RawTexts |
|----------------|------|-------|-----------|----------|----------|
| FA FAORRES.FA.FATESTCD.EQ.LDIAM | FAORRES | XML: 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 108, 109 PDF: 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 102, 103, 104, 105, 106, 107, 108, 109 | PAGE_MISMATCH relation: pdf_superset path: path_A_target_var | pdf_only=21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 65, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 102, 103, 104, 105, 106, 107 |
| FA FAORRES.FA.FATESTCD.EQ.OCCUR | FAORRES | XML: 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 102, 103, 104, 105, 106, 108 PDF: 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 102, 103, 104, 105, 106, 107, 108, 109 | PAGE_MISMATCH relation: pdf_superset path: path_A_target_var | pdf_only=107, 109 |
| FA FAORRES.FA.FATESTCD.EQ.REL | FATESTCD=REL | XML: 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 102, 103, 104, 105, 106 PDF: 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 102, 103, 104, 105, 106 | COMPOUND_RESOLVED relation: exact path: path_B_qualifier_value |  |
| FA FAORRES.FA.FATESTCD.EQ.RELPR | FATESTCD=RELPR | XML: 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 102, 103, 104, 105, 106, 107 PDF: 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 102, 103, 104, 105, 106, 107 | COMPOUND_RESOLVED relation: exact path: path_B_qualifier_value |  |
| FA FAORRES.FA.FATESTCD.EQ.SEV | FATESTCD=SEV | XML: 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 103, 104, 106, 108, 109 PDF: 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 103, 104, 106, 108, 109 | COMPOUND_RESOLVED relation: exact path: path_B_qualifier_value |  |
| FA FAORRES.FA.FATESTCD.EQ.TEMP | FATESTCD=TEMP | XML: 102, 105 PDF: 102, 105 | FATESTCD=TEMP | COMPOUND_RESOLVED relation: exact path: path_B_qualifier_value |  |
| FA FAORRESU.FA.FATESTCD.EQ.TEMP | FAORRESU | XML: 102, 105 PDF: 102, 105 | FAORRESU | COMPOUND_RESOLVED relation: exact path: path_A_target_var |  |


Issue/question 16.
1.感觉现在的compare result读起来有点复杂，它有太多分类了，不容易快速理解；但感觉好像也只能这样，因为从acrf.pdf解析出来的种类就多，交叉xml对比就产生更多分类了。不过从寻找diff的goal来说，
有哪些关键词是需要我关注的
unmapped_variable，PAGE_MISMATCH，extra_domain，还有其他的吗


-------------------------------------------------------------------------------
round3, 17Jun2026;
接下来我们开发OpenCV+OCR 模块，你先复习所有的md文件以回忆先前的设想、也回忆下我们在这个folder下所有session的讨论；然后你也可以加载config folder下的两个PDF文件，他们虽然是non-flattened，
但你就开发 OpenCV+OCR 模块，通过图像识别去抓取下annotation；
1.抓取规则或者内部的处理，原则上尽量遵循 PyMuPDF 先前确定的处理，当然，如果有什么地方你觉得异常，也请告诉我；
2.我暂时还没想好UI怎样设计，在同一个界面display PyMuPDF + OpenCV的结果吗，我原先的设想是
	-flattened pdf，只能通过OpenCV解析出结果；
	-non-flattened pdf，两个模块都能解析出结果，这时候先对他们俩做一次一次性检查，确保他们一致，再把他们一致的结果去和xml解析的compare


IF non-flattened PDF AND 两个都运行:
  1. PyMuPDF 运行 → 结果A
  2. OpenCV运行 → 结果B
  3. 对比A vs B:
     - 相同的变量/页码 → 绿色 ✅ (confidence high)
     - 只在A中 → 黄色 ⚠️  (likely valid, OpenCV missed)
     - 只在B中 → 红色 ❌ (suspicious, possible OCR error)
  4. 只展示 ✅ 和 ⚠️ 的结果，给用户标记 ❌ 的

自动检测 + 用户控制
策略：
1. 先自动检测PDF类型 (用PyMuPDF的 is_flattened_pdf())
2. 根据PDF类型自动调整

IF flattened PDF:
   ├─ PyMuPDF: ❌ 禁用 (无文本层，无法提取)
   └─ OpenCV: ✅ 自动启用 + 运行

IF non-flattened PDF:
   ├─ PyMuPDF: ✅ 自动启用 + 运行 (快速，~0.25-0.8s)
   ├─ OpenCV: 📌 用户可勾选 (可选，用来验证)
   └─ 如果用户勾选: 运行方案A的两层验证
方面	效果
自动适应	Flattened/Non-flattened自动选择最佳方案
速度	Non-flattened默认不用OpenCV（节省30-50秒）
灵活性	用户可选打开双验证（用于质量检查）
可控性	保留所有勾选选项，用户有完全的选择权
用户体验	智能提示"自动启用"，清晰告知为什么


Newissue1.
1. 只勾选 PyMuPDF 时接下结果才如下
Classification, Name, Pages, PageCount, Category, RawTexts

如果同事勾选OPENCV，解析的结果就是
Variable, Pages, PageCount, Category
为什么有这种差异；
2.0 variables confirmed by both parsers

No consensus between parsers
为什么，怎么理解，OPENCV only也是空的

OpenCV 和 OCR 是两件事。
OpenCV负责“找框/找区域”（图像检测），但不负责“读字”。
真正把框里的像素转成文字的是 OCR 引擎，这里用的是 Tesseract。
所以现在你会看到：OpenCV检测到很多框，但没有Tesseract就读不出文本，变量自然是空。

是按内容判断 flattened，不是按文件属性。
当前逻辑在 is_flattened_pdf() 里是读取每页 get_text("text") 的文本量和词数来判定（text layer强弱）。
不是看 PDF metadata/properties。

为什么这个“flattened”文件还能提取出 NOT SUBMITTED？
因为这份文件按内容检测其实是 non-flattened（text layer 很强），不是纯图片扫描件。
所以 PyMuPDF 还能直接读到文本；当前规则里 NOT SUBMITTED 是一个明确关键词，会被单独聚合成变量项。
你现在看到“只剩 NOT SUBMITTED”说明：


Newissue2.
1.为什么关于NOT SUBMITTED PyMuPDF,,OPENCV提取到不同，还被归类到Consensus
Classification	Name	Pages	PageCount	Category	RawTexts	PyMuPDF Pages	OpenCV Pages
Variable	NOT SUBMITTED	10,11,13,16,17,24,26,30,31,32,33,34,40,41,42,43,46,48,49,51,52,57,58,60,61	25	not_submitted		10,10,10,11,13,13,16,17,17,24,26,30,30,31,31,32,32,32,33,33,34,40,41,42,43,46,46,48,49,51,51,52,57,58,60,60,61,61	10,10,10,13,13,16,24,46,46,51,52,61
------------------------------------
先这样吧，目前似乎还行，请做充分的记录然后push GitHub；明天聚焦两个任务；
1.首先是清晰OCR的提取文本；
2.对于non-flanttened anntatotion pdf，怎样确保结果一致，其次如果有不一致，怎样纳入和XML的comparison

记录与当前结论：
1. OpenCV 与 OCR 已拆清楚：OpenCV 负责检测 annotation/文本区域，Tesseract 负责把图像区域转成文本。已安装并配置 Tesseract，OpenCV+OCR 链路在 acrf_3039_UC_flattened.pdf 上可运行。
2. "Flattened" 在本项目中改为 MSG 2.0 aCRF annotation 语境，不再以 PDF text layer 为主判断：
   - MSG 2.0 readable annotations: annotation objects 存在且 /Contents 可读，PyMuPDF 为主。
   - Annotation-flattened PDF: annotation objects 缺失或不可读，即使页面 text layer 仍存在，OpenCV+OCR 为主。
   - Partial/weak annotation layer: annotation layer 不完整，需 PyMuPDF + OpenCV 双跑并人工/规则复核。
3. 两层验证规则已更新：
   - Consensus: variable name 一致且 page set 一致；NOT SUBMITTED 还需要重复 occurrence count 一致。
   - Page Mismatch: 两个 parser 都找到同一名称，但页码或 NOT SUBMITTED occurrence 不一致。
   - PyMuPDF Only / OpenCV Only: 只在单侧出现。
4. acrf_3039_UC_flattened.pdf 当前被识别为 Annotation-flattened PDF；对比结果示例为 Consensus=0, Page Mismatch=1 (NOT SUBMITTED), OpenCV Only=466。

明天重点：
1. 清晰化 OCR 提取文本：检查 RawTexts 噪声、误识别、box 合并/截断、重复文本保留策略，并决定怎样展示 OCR confidence/debug 信息。
2. non-flattened annotation PDF 的双 parser 一致性策略：定义哪些差异可以自动接受，哪些进入 Page Mismatch/Needs Review，并设计这些差异如何进入 XML comparison（例如只用 Consensus，还是带风险等级纳入）。
