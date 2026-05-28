## 1.Target&backgroud
我需要开发一个tool，你先不要着急写代码，我们先讨论下可行的技术思路： 用来验证SDTM define xml中来自acrf的变量所对应的acrf page，以及从acrf extract出每个变量所在的page，来交叉验证page在两个source中是否一致；

1.从XML提取acrf page，lxml ， 或者你有其它更高效的方法，下面是两个example xml code
````
     <ItemDef OID="IT.VS.VSDTC" Name="VSDTC" DataType="date" SASFieldName="VSDTC">
        <Description>
           <TranslatedText>Date/Time of Measurements</TranslatedText>
        </Description>
        <def:Origin Type="Collected" Source="Investigator">
           <def:DocumentRef leafID="LF.acrf">
              <def:PDFPageRef Type="PhysicalRef" PageRefs="77 78 79 80 81 82 83 84 85 86 87 119 120 121"/>
           </def:DocumentRef>
        </def:Origin>
     </ItemDef>

         <ItemDef OID="IT.VS.VSLOC.VS.VSTESTCD.IN.TEMPHIGHTEMP" Name="VSLOC.VS.VSTESTCD.IN.TEMPHIGHTEMP" DataType="text" Length="14" SASFieldName="VSLOC">
            <Description>
               <TranslatedText>Temperature, Highest Temperature</TranslatedText>
            </Description>
            <CodeListRef CodeListOID="CL.VSLOC"/>
            <def:Origin Type="Collected" Source="Investigator">
               <def:DocumentRef leafID="LF.acrf">
                  <def:PDFPageRef Type="PhysicalRef" PageRefs="77 78 79 80 81 82 83 84 85 86 87 119 120 121"/>
               </def:DocumentRef>
            </def:Origin>
         </ItemDef>
        <def:WhereClauseDef OID="WC.VS.VSTESTCD.IN.TEMPHIGHTEMP">
            <RangeCheck SoftHard="Soft" def:ItemOID="IT.VS.VSTESTCD" Comparator="IN">
               <CheckValue>TEMP</CheckValue>
               <CheckValue>HIGHTEMP</CheckValue>
            </RangeCheck>
         </def:WhereClauseDef>
		 
     <ItemDef OID="IT.SUPPCM.VACHISTR" Name="VACHISTR" DataType="text" Length="13" SASFieldName="QVAL">
        <Description>
           <TranslatedText>Source of Vaccination History</TranslatedText>
        </Description>
        <CodeListRef CodeListOID="CL.QVAL.SUPPCM.QNAM.EQ.VACHISTR"/>
        <def:Origin Type="Collected" Source="Investigator">
           <def:DocumentRef leafID="LF.acrf">
              <def:PDFPageRef Type="PhysicalRef" PageRefs="115"/>
           </def:DocumentRef>
        </def:Origin>
     </ItemDef>
````

2.从acrf导出变量所在的page，这里需要做一个汇总，因为一个变量可能出现多个page,我希望你在处理完整个acrf pdf后，我希望你能汇总下每个变量所出现的所有page number

3.关于从acrf导出变量page的问题，我实际上希望两种方式，opencv是一个路径，处理出来一个结果；PyMuPDF另一个路径也汇总结果;也就是说，如果
flattened-pdf: opencv能处理出结果；

non-flattened-pdf, opencv + PyMuPDF 有两种结果。

我晚点提供example pdf给你

4.我希望是一个streamlit操作平台，当然，你有其它python web解决方案，比如webassembly wasm stlite，也请给出你的建议

5.我希望web platform有一个上传define xml的地方，然后对应一个run button去解析XML的acrf page number，然后输出结果，也有一个上传acrf pdf的地方，另一个run button，解析acrf的结果，然后输出；第三个button是啊analysis，比较不同source的结果，可以是xml vs opencv, or xml vs opencv & PyMuPDF, 提示存在不一致风险的变量

6.注意，代码请给出完整的、稳健的，并严格遵循我们最后所讨论的实现规则； 尽量不要使用pandas以维护轻量，如果有必要使用pandas时，也要先提示我；代码中的注释要用英文；每次当我们针对一些issue更新代码时，请最低限度的更新，只针对issue相关的代码去更新，不要modify到前面确定好的、不相干的代码	 

注意在我的机器上调用python要这样子，e.g.
py -m streamlit run app.py

我们的交流，我提出需求时可能是中文，你也可以用中文回复，但是涉及专业名词的，用英文，比如Git Push，不要用"推送"，涉及任何专业领域的，programming CIDSC等area，都要有英文原始的转有名词，确保我能正确理解你的意思。


| 阶段 | 内容 | 目标 | 建议时长 |
| --- | --- | --- | --- |
| 1 | 项目初始化 + Streamlit 骨架 | 搭建整体框架、页面布局、文件上传、按钮、Tab | 1–2 天 |
| 2 | XML 解析模块 | 完善 Define-XML 提取逻辑（lxml + XPath） | 1–2 天 |
| 3 | PyMuPDF 解析模块 | 非 flattened + flattened 的文本 + 坐标提取 | 2–3 天 |
| 4 | OpenCV + OCR 模块 | 视觉路线处理，尤其适用于 flattened PDF | 2–3 天 |
| 5 | 对比分析 + 报告模块 | Cross-check 逻辑、差异高亮、Excel 输出 | 1–2 天 |
| 6 | 优化、配置、部署 | 错误处理、进度条、配置化、打包 | 持续优化 |

## 2.PyMuPDF
1. 一个变量横跨多页时，你希望如何记录？（所有页都记，还是只记首次出现页？）
记录所有页码，比如LBORRES可能出现在page8,10,16, 都应该汇总记录；

2.Flattened 降级策略： 当 PyMuPDF 提取不到足够文本时，是否自动 fallback / 并行调用 OpenCV？
在处理PDF前，先检测，如果是Flattened PDF，直接输出一条message，提示flattened；如果是non-flattented，再采取同时两个模块处理

3.性能考虑：
- PDF 页数通常多少？—>预估小于200，通常小于100
- 是否需要进度条和分批处理？—>不需要进度条，但可以加一个timer，记录正在运行了多少秒，例如2min13s

4.是否需要直接生成 Excel
可以加一个download csv button


最重要的问题是还是annotation的提取与整理:

1. 我确定[fixed rule1]这些annotation都是带有背景色的边框，但可能是实线边框，也可能是虚线边框
2. 边框内容有这几类:
    1. dataset/domain name( corner case: SQAP—, SUPP—, AP—开头的大写字段，RELREC， RELSPEC，RELREF, RELSUB, POOLDEF，即除了list csv以外，domain name多数情况下长度应该等于2，但绝对≤8)
    2. sdtm standard variable name: [fixed rule2] Annotations for variables and dataset codes should be capitalized， legnth一定≤8
    3. NOT SUBMISTTED(考虑大小写，可能以不同大小写出现（NOT SUBMITTED、Not Submitted、NOTSUBMITTED）提取后，单独作为一个提取类别保留输出)，它通常是标记某个页面其中的几个item NOT SUBMITTED，也可能是整个页面NOT SUBMITTED，所有我觉得你要计数全部的NOT SUBMITTED，不能有去重之类的处理
    统计每个NOT SUBMISTTED的所在页码，以及每页中所出现的全部次数
    4. 包含sdtm variable name的一段描述性文字，多个变量，比如边框内容if No then DSTERM/DSDECOD=COMPLETED，这个就包含DSTERM, DSDECOD变量
    5. SUPP变量，这个不是standard variable name，但是边框内容一定会包含SUPP这个关键词
        
        AEPTRTPT in SUPPAESUPPAE.AEPTRTPTPTRTPT in SUPPFAQNAM in SUPPxx 等
        
        - AEPTRTPT in SUPPAE
        - SUPPAE.AEPTRTPT
        - PTRTPT in SUPPFA
        - QNAM in SUPPxx 等
    
    我现在整理了两份list，尽量覆盖所有的dataset/domain name与sdtm standard variable name，我先给你看下一部分list，确保你理解list的结构和格式；
    
    - standard_term_suffix_prefix.csv, `standard_term_suffix_prefix`  tab; 它列举了所有可能可能是dataset name with suffix，以及variable name with prefix的情况
    - standard_term.csv, standard_term tab; 它列举了已知的所有的dataset name以及variable name
	
	
提取思路:

1.按照[fixed rule1]，PyMuPDF 肯定可以提取出全部的annotation 内容，关键是如何进一步提取和整理; 我们只基于提取的annotation内容进行后续处理，PyMuPDF 几乎可以将pdf全部的内容extract出来，但是我只关注边框里的内容

2.[fixed rule2] 可以帮助提取出全部潜在的dataset/variable，也就是说variables and dataset一定是capitalized，但考虑项目多样性，我没有绝对把握说capitalized就一定是dataset/variable name；

3.其次我们可以按照两份list csv去匹配，如果是在standard_term.csv中，那我们就可以说是有百分百把握了，如果是匹配到prefix/suffix， 那也可以说是比较有把握

4.请确保恰当处理NOT SUBMITTED

5.还有一个blacklist.txt，凡是在这里面的term，无论是dataset variable name都可以排除掉

6.经过前面的处理，也许仍有一些annotation无法匹配，但也不能删掉，仍然保留在提取报告里，可以加一个flag标记为特殊情况

匹配优先级：Blacklist → NOT SUBMITTED → 精确匹配standard_term.csv → 模糊匹配standard_term_suffix_prefix.csv→SUPP variable（e.g. AEPTRTPT in SUPPAE)→ Unknown（这个顺序很重要）	
	
	
issue1. 我们只基于提取的annotation内容进行后续处理，PyMuPDF 几乎可以将pdf全部的内容extract出来，但是我只关注边框里的内容；

issues2:你存在遗漏的情况，比如我手动检查了pdf，e.g. CMTRT存在于page 12,96,114,115; 但是你只检测出12，115

| Variable | Pages | PageCount | Category | Flag | RawTexts |
| --- | --- | --- | --- | --- | --- |
| CMTRT | 12,115 | 2 | unknown | potential_nonstandard | CMTRT | CMTRT | CMTRT... |

issue3. 你对category和flag标记的不准确，比如DSTERM存在于standard_term.csv，但是你仍标记unkown

| Variable | Pages | PageCount | Category | Flag | RawTexts |
| --- | --- | --- | --- | --- | --- |
| DSTERM | 19,20,116 | 3 | unknown | potential_nonstandard | DSTERM | DSTERM | DSTERM... |

issue4. 我也奇怪，在pdf手动检索是查不到FATEST，FATESTC的，但是你却输出在report里

| FATEST | 72 | 1 | unknown | potential_nonstandard | FATEST... |
| --- | --- | --- | --- | --- | --- |
| FATESTC | 66,69,74,75 | 4 | unknown | potential_nonstandard | FATESTC | FATESTC | FATESTC... |

issue5. 我觉得RawTexts可以存储从方框提取到的完整内容，不要省略， 不要`ACNDD... `  或者`AESLCTD | AESLCTD…` 而是`ACNDD in SUPPAE`，  `AESLCTD in SUPPAE` `；

issue6.对于SUPP相关的变量，category不要supp_variable，它可以直接抓取到SUPPAE这种准确的对应的dataset name吧

issue7. 对于DSTERM这种存在于csv的标准变量，仍然标记unkown，

issue8，提取的信息不准确，为什么有DDORRE，这不正常，应该只有 DDORRES


28May2026: Now Copilot added into this project.

接下来，我会把执行streamlit后，碰到的问题记录在issue_record.md，我会及时命令你读取它，以理解我在网页端所发现的问题。	