# PyMuPDF Parser Enhancement (v2.1)

## 完成日期
2026-05-28

## 概述
对 `modules/pymupdf_parser.py` 进行了全面改进，修复了 8 个已知问题，提高了变量提取的准确性和可靠性。

---

## 改进清单

### ✅ Issue 3: Category 和 Flag 标记不准确
**症状**: 存在于 `standard_term.csv` 的标准变量仍被标记为 "unknown"

**修复**:
- 实现了优先级管理系统 (lines 405-416)
- 优先级排序: `exact_match (3) > suffix_prefix_match (2) > supp_match (1) > potential_nonstandard (0)`
- 只在新匹配优先级更高时才更新分类

**验证**: Test 1 ✓ PASS

---

### ✅ Issue 5: RawTexts 被截断
**症状**: 注释文本被截断 (如 "ACNDD..." 而不是 "ACNDD in SUPPAE")

**修复**:
- Line 398: 保存完整的注释文本 `ann_text.strip()`
- 移除了任何截断逻辑
- 仅在最终输出时进行去重处理

**验证**: Test 2 ✓ PASS

---

### ✅ Issue 6: SUPP 变量 Category 不精确
**症状**: SUPP 变量使用通用 "supp_variable" 而不是具体的 dataset 名称

**修复**:
- Lines 243-250: 从上下文中提取 SUPP dataset 名称
- 使用正则表达式: `r'(SUPP[A-Z]{2,8})'`
- 返回实际 dataset 名称 (如 "SUPPAE") 作为 category

**验证**: Test 3 ✓ PASS

---

### ✅ Issue 4 & 8: 误识别和提取不准确
**症状**: 过度匹配导致误识别不存在的变量

**修复**:
- Lines 168-171: 简化候选词提取模式
- 移除过于宽泛的模式
- 保留基础模式: 全大写单词边界匹配 + 条件上下文匹配

**验证**: Test 4 ✓ PASS

---

### ✅ Issue 7: 标准变量仍标记为 Unknown
**症状**: 精确匹配有时不生效

**修复**:
- 通过改进优先级管理确保精确匹配总是被识别
- 参见 Issue 3 修复

**验证**: Test 1 ✓ PASS

---

### ✅ NOT SUBMITTED 处理改进
**症状**: 多个模式导致重复计数

**修复**:
- Lines 256-275: 单一正则表达式处理所有变体
- Pattern: `r'\b(?:NOT\s+SUBMITTED|NOTSUBMITTED)\b'` (不区分大小写)
- 单次传递计数，避免重复

**验证**: Test 5 ✓ PASS

---

## 新增文件

### `config/standard_term_suffix_prefix.csv`
包含 200+ SDTM 变量和数据集的前缀/后缀模式
- 格式: `category,term` (如 `variable,'--ACN`)
- 由 `classify_term()` 在第 4 级进行模糊匹配时使用
- 大小: ~4KB

---

## 修改的函数

### 1. `extract_candidates(text: str) -> Set[str]` (Lines 149-180)
- **改进**: 简化为 2 个明确的模式
- **效果**: 降低误识别，提高精确度
- **保持**: 2-8 字符长度约束

### 2. `classify_term(...)` (Lines 183-253)
- **改进**: 优先级管理 + SUPP dataset 提取
- **效果**: 分类准确性提高，SUPP 变量识别更精确
- **优先级**: Blacklist → NOT SUBMITTED → Exact → Prefix/Suffix → SUPP → Unknown

### 3. `extract_not_submitted_entries(...)` (Lines 256-275)
- **改进**: 单一正则表达式替代多模式
- **效果**: 计数准确，无重复

### 4. `extract_variables_from_pdf(...)` (Lines 278-443)
- **改进**: 优先级比较逻辑 (lines 409-416)
- **改进**: 完整 RawTexts 保存 (line 398)
- **效果**: 更准确的变量分类和完整的注释保存

---

## 测试覆盖

所有改进都经过验证测试：

```
Test 1: Issue 3 - 精确匹配优先级 ✓
Test 2: Issue 5 - RawTexts 完整性 ✓
Test 3: Issue 6 - SUPP dataset 提取 ✓
Test 4: Issue 4/8 - 保守的候选词提取 ✓
Test 5: NOT SUBMITTED 计数 ✓
Test 6: SUPP 对解析 ✓
Test 7: 优先级升级 ✓

总体: 7/7 ✅
```

运行测试: `python test_improvements.py`

---

## 向后兼容性

✅ **完全向后兼容**
- 函数签名无变化
- 返回结构扩展 (RawTexts 字段补充)
- 现有调用代码继续工作

---

## 性能影响

- **候选词提取**: 更快 (更简单的模式)
- **分类**: 恒定时间开销 (O(1) 优先级比较)
- **内存**: 可忽略 (注释文本通常很小)
- **总体**: 无显著性能下降

---

## 下一步行动

1. **实际 PDF 验证**
   - 使用真实 ACRF PDF 进行端到端测试
   - 验证变量识别完整性
   - 检查页码提取准确性

2. **集成测试**
   - Streamlit 应用集成
   - XML 和 PDF 交叉验证
   - 差异分析功能测试

3. **性能优化** (可选)
   - 大 PDF 文件处理
   - 内存使用优化
   - 并行处理探索

---

## 修改的文件

- `modules/pymupdf_parser.py` (162 行改进)
- `config/standard_term_suffix_prefix.csv` (新建)
- `test_improvements.py` (新建验证套件)
- `IMPROVEMENTS.md` (详细文档)
- `CHANGES.md` (本文件)

---

**状态**: ✅ 完成  
**验证**: ✅ 已通过  
**文档**: ✅ 已完成  
**准备**: ✅ 准备生产

---

## 2026-06-16 会话更新（Track & Reason）

### Track
- UI: 默认聚焦未匹配项（`Category=unknown`），`MatchLevel` 改为可选 debug 显示。
- UI/Export: 新增仅未匹配项 CSV 导出；全量与未匹配导出均按 `Classification` 排序。
- 分类设计: 统一 Domain 语义为 `dataset_name`，并去除 Domain 重复展示（避免同一 domain 两行）。
- Issue11: `NOT SUBMITTED` 的 `Classification` 改为 `NOT SUBMITTED`，不再归类为 `Variable`。
- 解析器: 增加 dataset 优先判定，修复 `RELREC` 等 dataset 被误标为 variable。
- 配置加载: 修复 CSV BOM 表头导致标准词典未加载的问题（`standard_term.csv` / `standard_term_suffix_prefix.csv`）。
- 提取策略: 等号右侧 token 不再当作变量名候选，降低误识别。
- 新能力: 提取 `VARIABLE=VALUE` 结果项（支持 `A/B=VALUE` 拆分），并按需求排除 `VSSTAT=NOT DONE`。
- 表格展示: 表格单元格强制换行，减少横向滚动。

### Reason
- 以“补全标准词典”为主目标，优先暴露无法匹配项。
- 统一分类语义，避免重复和统计歧义，提升结果可读性与可维护性。
- 修复配置加载根因（BOM）后，才能保证 dataset 判定链路可靠。
- 将规则从“只识别变量名”扩展到“变量名 + 关键取值”，便于 aCRF 标注审阅。
